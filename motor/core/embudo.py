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
import os
import time

TIPOS = ("video", "descarte", "decision", "cuerpo")


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
