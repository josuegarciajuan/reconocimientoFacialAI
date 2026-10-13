"""Instrumentación del embudo de recall — motor/core/embudo.py

Registra, sin cambiar el comportamiento del pipeline, por dónde se van perdiendo
las personas entre la captura y la identificación. Cada proceso escribe eventos
JSON-línea en `motor/logs/embudo_<local>.jsonl` (append bajo FileLock) y el CLI
`motor/embudo.py` los agrega y los cruza con la BD (`ws.php embudo_datos`).

Tipos de evento (contrato estable; los consume `motor/embudo.py`):

- `video`   (procesa_video.py): resultado de analizar UN vídeo.
    {frames, caras_detect, caras_guard, caras_borroso, caras_dedup,
     cuerpos, cruces}
- `descarte` (clasificador.py): crops descartados al leer `sinclasificar/`.
    {motivo: notienecaras|nopasafiltros, n}
- `decision` (clasificador.py): veredicto de un sub-clúster de caras.
    {verdict, branch, sharp, size}
- `cuerpo`  (clasificador.py): resultado de un crop de cuerpo sin cara (F7).
    {resultado: match|revision, n}

Reglas:
- Best-effort: nunca lanza (un fallo de disco no debe tumbar captura/clasificación).
- Solo métricas; NUNCA datos personales ni embeddings.
- Gitignored (`motor/logs/`): git = código, no datos.
"""
from __future__ import annotations

import json
import math
import os
import time

TIPOS = ("video", "descarte", "decision", "cuerpo", "latencia")


def _path(ruta: str, local_id) -> str:
    return os.path.join(ruta, "motor", "logs", f"embudo_{local_id}.jsonl")


def log_evento(ruta: str, local_id, tipo: str, **campos) -> None:
    """Append de un evento del embudo (best-effort, bajo FileLock)."""
    try:
        path = _path(ruta, local_id)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        evento = {"ts": time.time(), "tipo": tipo}
        evento.update(campos)
        line = json.dumps(evento, ensure_ascii=False, default=float)
        try:
            from filelock import FileLock
            with FileLock(path + ".lock"):
                with open(path, "a", encoding="utf-8") as fh:
                    fh.write(line + "\n")
        except ImportError:  # sin filelock: append simple (no bloqueante)
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(line + "\n")
    except Exception:  # noqa: BLE001 — la métrica nunca rompe el pipeline
        pass


def leer_eventos(ruta: str, local_id) -> list[dict]:
    """Lee todos los eventos del local (ignora líneas corruptas)."""
    path = _path(ruta, local_id)
    if not os.path.exists(path):
        return []
    out: list[dict] = []
    try:
        with open(path, encoding="utf-8") as fh:
            for ln in fh:
                ln = ln.strip()
                if not ln:
                    continue
                try:
                    out.append(json.loads(ln))
                except json.JSONDecodeError:
                    continue
    except OSError:
        return []
    return out


def log_latencia(ruta: str, local_id, etapa: str, **campos) -> None:
    """Registra una medida de latencia de una etapa del pipeline.

    Etapas (contrato estable, lo consume `resumir_latencia`):
    - ``extract`` : análisis del vídeo. Campos sugeridos: ``cam``, ``fichero``,
      ``frames``, ``t_clip`` (epoch del inicio de captura), ``t_cierre`` (epoch
      del cierre del clip, mtime), ``t_ini``/``t_fin`` (epoch del procesado),
      ``dur_s`` (t_fin-t_ini: latencia de la etapa) y ``espera_s`` (t_ini-t_cierre:
      tiempo en cola antes de procesar).
    - ``classify``: decisión de un lote/batería. ``cam``, ``n_baterias``,
      ``t_ini``/``t_fin``/``dur_s``.
    - ``bd``      : foto publicada en BD. ``cam``, ``foto_id``, ``frame_ts``
      (epoch del fotograma) y ``e2e_s`` (fin-a-fin: t_bd - frame_ts).

    Best-effort: nunca lanza (no debe tumbar el pipeline por una métrica).
    """
    try:
        campos["etapa"] = etapa
        log_evento(ruta, local_id, "latencia", **campos)
    except Exception:  # noqa: BLE001
        pass


def _pct(vals: list[float], p: float):
    """Percentil por interpolación lineal (same as numpy 'linear' para n>1).

    None si no hay datos; el mismo valor si solo hay uno.
    """
    xs = sorted(float(v) for v in vals if v is not None)
    if not xs:
        return None
    if len(xs) == 1:
        return xs[0]
    k = (len(xs) - 1) * (float(p) / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return xs[int(k)]
    return xs[f] + (xs[c] - xs[f]) * (k - f)


def resumir_latencia(eventos: list[dict], desde: str | None = None) -> dict:
    """Agrega los eventos `latencia` en percentiles por etapa (función pura).

    Devuelve::

        {
          "extraccion_s":  {n,p50,p95,max},   # dur_s de extract
          "espera_cola_s": {n,p50,p95,max},   # t_ini-t_cierre de extract
          "clasificacion_s":{n,p50,p95,max},  # dur_s de classify
          "e2e_s":         {n,p50,p95,max},   # t_bd-frame_ts de bd
        }
    """
    extraccion: list[float] = []
    espera: list[float] = []
    clasificacion: list[float] = []
    e2e: list[float] = []
    for e in eventos:
        if not isinstance(e, dict) or e.get("tipo") != "latencia":
            continue
        if desde and _fecha(e.get("ts")) < desde:
            continue
        etapa = e.get("etapa")
        if etapa == "extract":
            if e.get("dur_s") is not None:
                extraccion.append(e["dur_s"])
            if e.get("espera_s") is not None:
                espera.append(e["espera_s"])
        elif etapa == "classify":
            if e.get("dur_s") is not None:
                clasificacion.append(e["dur_s"])
        elif etapa == "bd":
            if e.get("e2e_s") is not None:
                e2e.append(e["e2e_s"])

    def _block(xs: list[float]) -> dict:
        return {"n": len(xs), "p50": _pct(xs, 50), "p95": _pct(xs, 95),
                "max": (max(xs) if xs else None)}

    return {
        "extraccion_s": _block(extraccion),
        "espera_cola_s": _block(espera),
        "clasificacion_s": _block(clasificacion),
        "e2e_s": _block(e2e),
    }


def _fecha(ts: float) -> str:
    return time.strftime("%Y-%m-%d", time.localtime(float(ts or 0)))


def resumir(eventos: list[dict], desde: str | None = None) -> dict:
    """Agrega eventos por día y por cámara. Función pura (testeable).

    Devuelve:
        {
          "total": {...sumas globales...},
          "por_dia": {fecha: {cam: resumen}},
        }
    Cada resumen tiene: videos, frames, caras_detect, caras_guard,
    caras_borroso, caras_dedup, cuerpos, cruces, descartes_{motivo},
    verdicts_{verdict}, cuerpos_match, cuerpos_revision.
    """
    total: dict = {}
    por_dia: dict[str, dict] = {}
    for e in eventos:
        if not isinstance(e, dict):
            continue
        fecha = _fecha(e.get("ts"))
        if desde and fecha < desde:
            continue
        cam = str(e.get("cam", ""))
        dia = por_dia.setdefault(fecha, {})
        acc = dia.setdefault(cam, {})
        _acumular(acc, e)
        _acumular(total, e)
    # ordenar cámaras dentro de cada día
    for fecha in por_dia:
        por_dia[fecha] = {k: por_dia[fecha][k] for k in sorted(por_dia[fecha])}
    return {"total": total, "por_dia": por_dia}


def _acumular(acc: dict, e: dict) -> None:
    tipo = e.get("tipo")
    if tipo == "video":
        _add(acc, "videos", 1)
        for k in ("frames", "caras_detect", "caras_guard", "caras_borroso",
                  "caras_dedup", "cuerpos", "cruces"):
            _add(acc, k, e.get(k, 0) or 0)
    elif tipo == "descarte":
        _add(acc, f"descartes_{e.get('motivo', 'otro')}", e.get("n", 1) or 1)
    elif tipo == "decision":
        _add(acc, f"verdicts_{e.get('verdict', 'otro')}", 1)
    elif tipo == "cuerpo":
        _add(acc, f"cuerpos_{e.get('resultado', 'otro')}", e.get("n", 1) or 1)


def _add(acc: dict, key: str, val) -> None:
    try:
        acc[key] = acc.get(key, 0) + float(val)
    except (TypeError, ValueError):
        pass


def cobertura(estancias: float, cruces: float) -> float:
    """Cobertura = personas registradas / personas que cruzaron. 0.0 si no hay cruces."""
    try:
        est = float(estancias)
        cru = float(cruces)
    except (TypeError, ValueError):
        return 0.0
    if cru <= 0:
        return 0.0
    return max(0.0, min(1.0, est / cru))
