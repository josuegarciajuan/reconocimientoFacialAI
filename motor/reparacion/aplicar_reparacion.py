"""Aplicación reversible de una propuesta de reparación.

Aplica el JSON generado por ``proponer_reparacion`` con tres garantías:

1. **Dry-run por defecto**: sin ``--si`` imprime exactamente las operaciones que
   haría y no toca nada.
2. **Backup + journal**: antes de mutar guarda un snapshot completo del store en
   ``motor/backups/reparacion/<ts>/face_enc_v2.bak`` y escribe un journal JSONL
   op por op. Con ``--db`` también respalda la BD (``db_snapshot.sql``) y aborta
   si no puede, para no dejar cambios irreversibles.
3. **Reversibilidad**: las fusiones usan ``FaceStore.merge_undoable`` (journal
   con la persona fuente exacta), de modo que un merge puede deshacerse con
   ``restore_person``. El snapshot permite además rollback manual completo.

Alcance:

- **MERGE**: fusiona cada cod fuente en el destino (store), mueve carpetas y
  retratos (``_merge_folders``) y, si ``--db``, reasigna estancias y borra la
  fila de ``personas`` de la fuente (``_merge_bd``).
- **CONTAMINACIÓN**: mueve por proveniencia exacta (``move_by_source``) los
  encodings cuyo ``source`` aparece íntegramente en el conjunto contaminado de
  ese grupo. Si el ``source`` está compartido con encodings NO contaminados se
  omite (moverlo arrastraría encodings legítimos). Sin ``source`` no se borra
  nada: se reporta en ``omitidos``. Con ``--db`` se reasigna además la estancia
  de la foto (``identificador_unico == source``) a la persona destino.

El módulo no fusiona/despliega; eso lo decide el operador con ``--si``.
"""
from __future__ import annotations

import argparse
import json
import os
import pickle
import time
from typing import Any, Callable, Mapping, Sequence

from motor.core.backup import Journal, snapshot_db
from motor.core.store import FaceStore
from motor.consolidar_nacidos import _merge_bd, _merge_folders

#: Tope de encodings por identidad si no se puede leer la config del proyecto.
MAX_PER_PERSON_DEFAULT = 500


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------
def _store_path(ruta: str, local: str) -> str:
    """Ruta del store ``face_enc_v2`` del local dado."""
    return os.path.join(ruta, "motor", "bbdd_reconocimiento", str(local), "face_enc_v2")


def _max_per_person(ruta: str) -> int:
    """Lee ``max_encodings_per_person`` de la config; 500 si no hay config."""
    try:
        from motor.core.config import Config  # import diferido (evita IO en tests)
        return int(Config.from_env(ruta).max_encodings_per_person)
    except Exception:  # noqa: BLE001
        return MAX_PER_PERSON_DEFAULT


def _nueva_carpeta_backup(ruta: str) -> str:
    """Crea ``motor/backups/reparacion/<ts>`` única (sufijo si colisiona)."""
    base = os.path.join(ruta, "motor", "backups", "reparacion")
    ts = time.strftime("%Y%m%d_%H%M%S")
    out = os.path.join(base, ts)
    if os.path.exists(out):
        out = os.path.join(base, f"{ts}_{os.getpid()}")
    os.makedirs(out, exist_ok=True)
    return out


def _sql_str(valor: Any) -> str:
    """Escapa un literal SQL entre comillas simples (anti-inyección básico)."""
    return str(valor).replace("\\", "\\\\").replace("'", "\\'")


def _reassign_estancia_foto(ruta: str, source: str, dst_cod: str) -> str:
    """Reasigna la estancia de la foto ``source`` a la persona ``dst_cod``.

    Devuelve un estado textual (``"ok"`` o el motivo de la omisión/error).
    No lanza: el fallo de BD no debe abortar el resto del journal.
    """
    from motor.core.photos import _mysql  # import diferido (usa .env en prod)

    s, d = _sql_str(source), _sql_str(dst_cod)
    try:
        rows = _mysql(ruta, f"SELECT id FROM personas WHERE cod_interno='{d}' LIMIT 1")
        if not rows:
            return "persona_destino_no_en_bd"
        pid = int(rows[0])
        frows = _mysql(
            ruta, f"SELECT estancia_id FROM fotos WHERE identificador_unico='{s}' LIMIT 1"
        )
        if not frows:
            return "foto_sin_fila_en_bd"
        eid = int(frows[0])
        _mysql(ruta, f"UPDATE estancias SET persona_id={pid} WHERE id={eid}")
        return "ok"
    except Exception as e:  # noqa: BLE001
        return f"error_bd: {e}"


# ---------------------------------------------------------------------------
# Plan (puro respecto al store; usado por dry-run y por --si)
# ---------------------------------------------------------------------------
def _construir_plan(
    propuesta: Mapping[str, Any], store: FaceStore, usar_db: bool
) -> tuple[list[dict], dict[str, str]]:
    """Traduce la propuesta a una lista ordenada de operaciones.

    Los merges van primero; las contaminaciones cuyo ``destino_cod`` sea un cod
    fuente de algún merge se remapean al destino de ese merge (si no, el
    ``move_by_source`` recrearía una identidad ya fusionada).

    Returns:
        ``(ops, remap)`` con ``remap: {cod_fuente -> cod_destino}``.
    """
    ops: list[dict] = []
    remap: dict[str, str] = {}
    for m in propuesta.get("merges") or []:
        dst = m.get("destino")
        if not dst:
            continue
        for src in m.get("cods_fuente") or []:
            if not src or src == dst:
                continue
            n = store.count(src) if store.person(src) is not None else 0
            ops.append({"tipo": "merge", "src": src, "dst": dst,
                        "n_encodings": int(n), "db": bool(usar_db)})
            remap[src] = dst

    for g in propuesta.get("contaminaciones") or []:
        src = g.get("cod_origen")
        # Si el cod de origen fue fusionado, sus encodings viven ya en el destino
        # del merge (misma persona ground-truth): buscar la proveniencia allí.
        src = remap.get(src, src)
        dst = g.get("destino_cod")
        if dst in remap:
            dst = remap[dst]
        persona = g.get("persona_destino")
        entries = g.get("encodings") or []
        if not dst or src == dst:
            if entries:
                ops.append({
                    "tipo": "omitido_purga", "src": src, "dst": None,
                    "persona_destino": persona, "n": len(entries),
                    "motivo": ("sin cod destino distinto (persona externa desconocida o "
                               "coincidente); no se borra sin embedding"),
                })
            continue
        por_source: dict[str, list[dict]] = {}
        for e in entries:
            s = e.get("source")
            if s is None:
                continue
            por_source.setdefault(str(s), []).append(e)
        for s in sorted(por_source):
            ents = por_source[s]
            ops.append({"tipo": "move_source", "src": src, "dst": dst, "source": s,
                        "n": len(ents), "persona_destino": persona,
                        "db": bool(usar_db)})
        for e in g.get("sin_fuente") or []:
            ops.append({"tipo": "omitido_sin_fuente", "src": src, "dst": dst,
                        "idx": e.get("idx"),
                        "motivo": "encoding sin proveniencia: no movible exacto, no se borra"})
    return ops, remap


def formato_plan(ops: Sequence[Mapping[str, Any]]) -> str:
    """Render legible del plan (dry-run)."""
    lineas = [f"== Plan de reparación ({len(ops)} operaciones) =="]
    for i, op in enumerate(ops, 1):
        t = op.get("tipo")
        if t == "merge":
            lineas.append(
                f"{i:>3}. MERGE {op['src']} -> {op['dst']} "
                f"(~{op.get('n_encodings', 0)} encodings, carpetas, db={op.get('db')})"
            )
        elif t == "move_source":
            lineas.append(
                f"{i:>3}. MOVE  {op['src']} -> {op['dst']} source='{op['source']}' "
                f"({op.get('n', 0)} encodings, db={op.get('db')})"
            )
        else:
            lineas.append(
                f"{i:>3}. OMITE {t} src={op.get('src')} dst={op.get('dst')} "
                f"({op.get('motivo', '')})"
            )
    if not ops:
        lineas.append("  (vacío)")
    return "\n".join(lineas)


# ---------------------------------------------------------------------------
# Ejecución
# ---------------------------------------------------------------------------
def _ejecutar_plan(
    ops: Sequence[Mapping[str, Any]],
    store: FaceStore,
    ruta: str,
    local: str,
    usar_db: bool,
    journal: Journal,
) -> list[dict]:
    """Ejecuta el plan, journalizando cada operación. Devuelve el resultado."""
    resultados: list[dict] = []
    for op in ops:
        tipo = op.get("tipo")
        base = {"tipo": tipo, "src": op.get("src"), "dst": op.get("dst"),
                "ts": time.time()}
        if tipo == "merge":
            src, dst = op.get("src"), op.get("dst")
            if store.person(src) is None:
                rec = {**base, "resultado": "omitido_origen_inexistente",
                       "encodings_movidos": 0}
            elif store.person(dst) is None:
                rec = {**base, "resultado": "omitido_destino_inexistente",
                       "encodings_movidos": 0}
            else:
                j = store.merge_undoable(dst, src)
                _merge_folders(ruta, local, src, dst)
                db_ok = None
                if usar_db:
                    try:
                        _merge_bd(ruta, src, dst)
                        db_ok = "ok"
                    except Exception as e:  # noqa: BLE001
                        db_ok = f"error_bd: {e}"
                rec = {**base, "resultado": "ok",
                       "encodings_movidos": int(j.get("encodings_moved", 0)),
                       "src_person_reversible": True, "db_ok": db_ok}
        elif tipo == "move_source":
            src, dst, source = op.get("src"), op.get("dst"), op.get("source")
            if src == dst:
                rec = {**base, "source": source, "resultado": "omitido_origen_igual_destino"}
            elif store.person(src) is None:
                rec = {**base, "source": source, "resultado": "omitido_origen_inexistente"}
            elif store.person(dst) is None:
                rec = {**base, "source": source, "resultado": "omitido_destino_inexistente"}
            else:
                srcs = store.person_sources(src) or []
                total = int(sum(1 for s in srcs if s == source))
                if total == 0:
                    rec = {**base, "source": source, "resultado": "omitido_ya_movido"}
                elif total != int(op.get("n", total)):
                    rec = {**base, "source": source, "resultado": "omitido_source_compartido",
                           "motivo": ("el source también etiqueta encodings no contaminados; "
                                      "moverlo arrastraría encodings legítimos"),
                           "n_source": total, "n_contaminados": int(op.get("n", 0))}
                else:
                    moved = store.move_by_source(src, dst, source)
                    db_ok = None
                    if usar_db and moved:
                        db_ok = _reassign_estancia_foto(ruta, source, dst)
                    rec = {**base, "source": source, "resultado": "ok",
                           "encodings_movidos": int(moved), "db_ok": db_ok}
        else:
            rec = {**base, "resultado": "omitido",
                   "motivo": op.get("motivo"), "n": op.get("n"),
                   "idx": op.get("idx")}
        journal.append(rec)
        resultados.append(rec)
    return resultados


def _verificar_store(store_path: str) -> dict:
    """Comprueba que el store sigue siendo un pickle ``face_enc_v2`` legible."""
    try:
        with open(store_path, "rb") as fh:
            data = pickle.load(fh)
        if not isinstance(data, dict) or data.get("schema") != "face_enc_v2":
            return {"ok": False, "error": "schema inesperado tras la reparación"}
        return {"ok": True, "n_personas": int(len((data.get("persons") or {})))}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)}


def aplicar_propuesta(
    propuesta: Mapping[str, Any],
    ruta: str,
    local: str,
    aplicar: bool = False,
    usar_db: bool = False,
    log: Callable[[str], None] = print,
) -> dict:
    """Aplica (o simula con ``aplicar=False``) una propuesta de reparación.

    Args:
        propuesta: JSON de ``proponer_reparacion.construir_propuesta``.
        ruta: raíz del repo (donde cuelgan ``motor/`` y ``admin/``).
        local: id del local cuyo store se repara.
        aplicar: ``False`` = dry-run (no toca nada); ``True`` = aplica de verdad.
        usar_db: además de store/carpetas, reasigna estancias en BD.
        log: función de log (inyectable en tests).

    Returns:
        Resumen JSON-safe con ``aplicado``, ``ops``, backup y verificación.
    """
    merges = propuesta.get("merges") or []
    contams = propuesta.get("contaminaciones") or []
    if not merges and not contams:
        log("Propuesta vacía: no se toca nada.")
        return {"aplicado": False, "motivo": "propuesta_vacia", "ops": []}

    store_path = _store_path(ruta, local)
    store = FaceStore(store_path, max_per_person=_max_per_person(ruta))
    ops, _remap = _construir_plan(propuesta, store, usar_db)

    if not aplicar:
        log(formato_plan(ops))
        return {"aplicado": False, "motivo": "dry_run", "store": store_path,
                "n_ops": len(ops), "ops": ops}

    # --- backup primero (store + BD si aplica) ---
    out_dir = _nueva_carpeta_backup(ruta)
    bak = os.path.join(out_dir, "face_enc_v2.bak")
    store.save_snapshot_bytes(bak)
    db_bak = None
    if usar_db:
        try:
            db_bak = snapshot_db(ruta, out_dir)
        except Exception as e:  # noqa: BLE001
            raise RuntimeError(
                f"no se pudo respaldar la BD; abortando SIN tocar el store: {e}"
            ) from e

    journal = Journal(os.path.join(out_dir, "journal.jsonl"))
    journal.append({
        "op": "inicio", "local": str(local), "db": bool(usar_db),
        "store": store_path, "snapshot": bak, "db_snapshot": db_bak,
        "rollback_store": f"cp '{bak}' '{store_path}'",
        "rollback_db": (f"mysql ... < '{db_bak}'" if db_bak else None),
        "n_ops": len(ops), "ts": time.time(),
    })

    ejecutadas = _ejecutar_plan(ops, store, ruta, local, usar_db, journal)
    verificacion = _verificar_store(store_path)
    journal.append({"op": "fin", "verificacion": verificacion,
                    "n_ops": len(ejecutadas), "ts": time.time()})

    n_ok = int(sum(1 for r in ejecutadas if r.get("resultado") == "ok"))
    omitidas = int(len(ejecutadas) - n_ok)
    return {
        "aplicado": True,
        "backup_dir": out_dir,
        "snapshot": bak,
        "db_snapshot": db_bak,
        "journal": journal.path,
        "n_ops": len(ejecutadas),
        "n_ok": n_ok,
        "n_omitidas": omitidas,
        "verificacion": verificacion,
        "ops": ejecutadas,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    raiz = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    ap = argparse.ArgumentParser(
        description="Aplica una propuesta de reparación (dry-run por defecto)."
    )
    ap.add_argument("--propuesta", required=True, help="JSON de proponer_reparacion")
    ap.add_argument("--ruta", default=raiz, help="raíz del repo")
    ap.add_argument("--local", required=True, help="id del local")
    modo = ap.add_mutually_exclusive_group()
    modo.add_argument("--dry-run", dest="dry_run", action="store_true", default=True,
                      help="simular sin tocar nada (por defecto)")
    modo.add_argument("--si", dest="dry_run", action="store_false",
                      help="aplicar de verdad")
    ap.add_argument("--db", action="store_true",
                    help="reasignar también estancias/personas en BD")
    ap.add_argument("--json", action="store_true", help="emitir el resumen como JSON")
    return ap.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Punto de entrada CLI. Nunca aplica sin ``--si``."""
    args = _parse_args(argv)
    with open(args.propuesta, "r", encoding="utf-8") as fh:
        propuesta = json.load(fh)
    res = aplicar_propuesta(
        propuesta, args.ruta, args.local,
        aplicar=(not args.dry_run), usar_db=bool(args.db),
    )
    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
