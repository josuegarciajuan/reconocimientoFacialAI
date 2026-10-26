"""Procesador real de unidades de vídeo.

Envuelve ``motor.procesa_video.process_video`` para producir un ``UnitResult``
con detecciones faciales, cuerpos y referencias a artefactos. Las detecciones se
capturan en vivo mediante un colector inyectado en ``process_video``, de modo
que los embeddings no se recalculan.
"""
from __future__ import annotations

import os
import time
import uuid
from typing import Any

from motor.core.artifact_lifecycle import ArtifactLifecycle
from motor.core.config import Config
from motor.core.model import Face
from motor.core.pipeline_contracts import (
    BoundingBox,
    BodyDetection,
    FaceDetection,
    ResultKind,
    UnitResult,
)


class DetectionCollector:
    """Acumula detecciones durante el procesado de un vídeo."""

    def __init__(self, min_face_size: int = 0):
        self.faces: list[FaceDetection] = []
        self.bodies: list[BodyDetection] = []
        self.crossings: list[dict[str, Any]] = []
        self._min_face_size = int(min_face_size or 0)

    def on_face(self, face: Face, frame_idx: int, frame_ts: float, state: str) -> None:
        if state not in ("saved", "dedup", "blur"):
            return
        x1, y1, x2, y2 = face.bbox
        if self._min_face_size and max(x2 - x1, y2 - y1) < self._min_face_size:
            return
        kps = {}
        if face.kps is not None:
            for i, (kx, ky) in enumerate(face.kps):
                kps[f"kps_{i}"] = (float(kx), float(ky))
        embedding = None
        try:
            embedding = [float(v) for v in face.embedding]
        except Exception:  # noqa: BLE001
            embedding = None
        self.faces.append(
            FaceDetection(
                detection_id=f"det-{uuid.uuid4().hex[:12]}",
                frame_idx=int(frame_idx),
                frame_ts=float(frame_ts),
                bbox=BoundingBox(float(x1), float(y1), float(x2), float(y2)),
                keypoints=kps,
                confidence=float(face.det_score),
                embedding=embedding,
                quality_score=float(face.det_score),
                sharpness=None,
                is_profile=abs(float(face.yaw)) > 30.0,
            )
        )

    def on_body(
        self, bbox: tuple[int, int, int, int], frame_idx: int, frame_ts: float,
        has_face: bool,
    ) -> None:
        if has_face:
            return
        x, y, w, h = bbox
        self.bodies.append(
            BodyDetection(
                detection_id=f"body-{uuid.uuid4().hex[:12]}",
                frame_idx=int(frame_idx),
                frame_ts=float(frame_ts),
                bbox=BoundingBox(float(x), float(y), float(x + w), float(y + h)),
                confidence=1.0,
                face_detection_id=None,
            )
        )

    def on_crossing(self, ev: Any, linea: Any) -> None:
        self.crossings.append(
            {
                "linea_id": str(getattr(linea, "line_id", "")),
                "direction": int(getattr(ev, "direction", 0)),
                "x": int(getattr(ev, "x", 0)),
                "y": int(getattr(ev, "y", 0)),
            }
        )


def _lineas_from_config(params: dict[str, Any] | None) -> list:
    """Reconstruye las líneas desde la configuración de la unidad."""
    raw = (params or {}).get("lineas")
    if not raw:
        return []
    try:
        from motor.cruces import Line

        return [
            Line(
                float(it["x1"]),
                float(it["y1"]),
                float(it["x2"]),
                float(it["y2"]),
                line_id=str(it["id"]),
            )
            for it in raw
        ]
    except (KeyError, TypeError, ValueError):
        return []


def _artifact_paths(ruta: str, local_id: str, camara_id: str) -> dict[str, str]:
    base = os.path.join(ruta, "motor/caras/sinclasificar", local_id)
    return {
        "faces": os.path.join(base, camara_id),
        "busto": os.path.join(base, f"{camara_id}_busto"),
        "frame": os.path.join(base, f"{camara_id}_frame"),
        "cuerpo": os.path.join(base, f"{camara_id}_cuerpo"),
        "fotos_lineas": os.path.join(ruta, "motor/fotos_lineas"),
    }


def process_unit(unit, ctx) -> UnitResult:
    """Procesa una ``AnalysisUnit`` de vídeo y devuelve ``UnitResult``.

    Requiere que la unidad tenga ``source_paths['video']`` o que el vídeo exista
    bajo la ruta convencional del proyecto.
    """
    from motor.procesa_video import process_video

    unit_config = unit.config.params or {}
    ruta = ctx.worker.project_root if ctx.worker else os.getcwd()

    cfg = Config.from_env(ruta)
    face_every = int(unit_config.get("face_every", cfg.face_every))

    local_id = str(unit.event.camera.local_id)
    camara_id = unit.event.camera.camera_id
    fichero = unit.source_paths.get("video")
    if not fichero:
        # Fallback: buscar por nombre en la ruta convencional.
        fichero = os.path.basename(unit.source_paths.get("video_path", ""))
    if not fichero:
        raise ValueError("La unidad no referencia ningún vídeo")

    collector = DetectionCollector()
    resumen: dict[str, Any] = {}
    eventos: list[dict[str, Any]] = []

    # Las líneas deben viajar en la unidad (el worker no habla con la BD).
    # Si no vienen, se procesa sin cruces en lugar de invocar ws.php.
    lineas = _lineas_from_config(unit_config)

    t_ini = time.time()
    process_video(
        local_id,
        camara_id,
        fichero,
        ruta,
        cfg,
        face_every,
        lineas=lineas,
        efectos=False,
        eventos=eventos,
        resumen=resumen,
        frame_ini=unit.frame_range.first_frame_idx,
        frame_fin=unit.frame_range.last_frame_idx + 1,
        collector=collector,
    )
    dur_s = time.time() - t_ini

    artifacts = _artifact_paths(ruta, local_id, camara_id)
    # Manifiesto: solo los directorios que realmente existen.
    manifest_id = unit.unit_id
    lifecycle = ArtifactLifecycle(os.path.join(ruta, "motor", "artifacts"))
    existing = {k: v for k, v in artifacts.items() if os.path.exists(v)}
    if existing:
        lifecycle.create_manifest(manifest_id, unit.unit_id, unit.unit_id, existing)
        lifecycle.publish_manifest(manifest_id)

    return UnitResult(
        unit_id=unit.unit_id,
        instance=unit.event.camera.instance,
        trace_id=unit.trace_id,
        kind=ResultKind.FINAL,
        generated_at=time.time(),
        faces=collector.faces,
        bodies=collector.bodies,
        candidates=[],
        artifacts={k: v for k, v in artifacts.items() if os.path.exists(v)},
        metrics={
            "frames": int(resumen.get("frames", 0)),
            "caras_detect": int(resumen.get("caras_detect", 0)),
            "caras_guard": int(resumen.get("caras_guard", 0)),
            "caras_borroso": int(resumen.get("caras_borroso", 0)),
            "caras_dedup": int(resumen.get("caras_dedup", 0)),
            "cuerpos": int(resumen.get("cuerpos", 0)),
            "cruces": len(collector.crossings),
            "duration_s": round(dur_s, 3),
        },
    )
