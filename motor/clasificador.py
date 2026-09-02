#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Clasificador de caras — motor/clasificador.py

Sustituye a `procesa_fotos_def_borrosaparteV2.py`. Flujo por pasada:
  1. Recorre `motor/caras/sinclasificar/<local>/<cam>/`.
  2. Filtra: sin cara -> removidas/notienecaras; desenfocada -> removidas/nopasafiltros.
  3. Agrupa por proximidad temporal ("baterías", < batch_seconds).
  4. Dentro de cada batería, agrupa caras de la misma persona (coseno).
  5. Match contra face_enc_v2 (mejor coincidencia multi-plantilla).
  6. Asigna persona (match) o crea nueva; mueve la foto representativa con el
     MISMO contrato de nombre que espera clasificadorV2.php:
        motor/caras/<local>/<cam>/<persona>/<stem>[_----<stem2>]_<id>.jpg

CASCADA DE FUSIÓN (F0-F7, feature-flags en Config, OFF por defecto):
  - cfg.cascade_enabled: sustituye la decisión binaria por fusión ponderada
    + escalada (L1a cara -> L1b torso -> L1c zonas -> L2 VLM local -> L3 OpenAI).
  - ENDURECIDO 2026-09-01 (anti-mezcla): el veredicto "uncertain" NO enriquece la
    galería del candidato (evita contaminar la identidad): crea persona nueva
    (duplicada) y copia a revisión manual. Ante la duda, mejor un duplicado.
  - En zona gris tras la cascada: UNCERTAIN -> motor/revision/, NUNCA se crea
    persona duplicada en silencio (ya no se asigna al top-1 dudoso).

Uso (daemon, como antes):
    motor/venv/bin/python motor/clasificador.py <local> <cam>
Uso (una pasada, para tests/calibración):
    motor/venv/bin/python motor/clasificador.py <local> <cam> --once
"""
from __future__ import annotations

import argparse
import json
import os
import random
import shutil
import sys
import time
from datetime import datetime

import cv2
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from motor.core.config import Config            # noqa: E402
from motor.core.matching import LayerScore, match_group, scores_per_person, scores_per_person_pose_aware  # noqa: E402
from motor.core.model import analyze            # noqa: E402
from motor.core.quality import face_sharpness, pose_label  # noqa: E402
from motor.core.store import FaceStore          # noqa: E402
from motor.core.superres import enhance_embedding, photo_busto  # noqa: E402
from motor.core.photo_audit import (build_audit_record, layer_scores_json,
                                    write_audit_queue)  # noqa: E402

ALPHABET = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
IMG_EXTS = (".jpg", ".jpeg", ".png")

# C (idempotencia): hash del embedding representativo ya consumido en esta
# sesión del daemon. Si el MISMO rostro (mismo crop re-leído o re-escrito) se
# vuelve a procesar en una pasada posterior, se salta: antes generaba una foto
# duplicada del mismo stem y un segundo match con score 1.0 (autocoincidencia
# tras autoenriquecer la galería con la primera pasada). Se usa el hash de la
# cara (no el stem) para no descartar a una 2ª persona legítima que en crops
# legacy pudiera compartir stem.
_PROCESSED_FACES: set[str] = set()

# Cola de foto HQ para el worker único (motor/photo_worker.py): el clasificador
# YA NO carga GFPGAN/RealESRGAN-x4plus (refactor RAM: los modelos pesados viven
# en UN solo proceso rf-photo, no en N clasificadores de cámara).


def _queue_hq(out_path: str, img, bbox, cfg: Config, ruta: str,
              local_id: str, camara_id: str, foto_id: str) -> None:
    """Encola la generación HQ (x4plus + GFPGAN) al worker único de foto.

    El worker lee el crop fuente (PNG lossless) + bbox desde
    `motor/photo_queue/<local>/<cam>/` y escribe `<out_path>.hq`; el panel lo
    "autonitida" sin recargar (mismo contrato que el hilo HQ anterior:
    clasificadorV2.php ingesta `*.hq` como upgrade de la foto rápida).
    """
    try:
        qdir = os.path.join(ruta, "motor/photo_queue", local_id, camara_id)
        os.makedirs(qdir, exist_ok=True)
        src_path = os.path.join(qdir, foto_id + ".png")
        cv2.imwrite(src_path, img, [cv2.IMWRITE_PNG_COMPRESSION, 3])
        job = {
            "src": src_path,
            "out": out_path,          # el worker escribe out_path + ".hq"
            "bbox": [int(round(v)) for v in bbox],
            "ts": time.time(),
        }
        with open(os.path.join(qdir, foto_id + ".json"), "w", encoding="utf-8") as fh:
            json.dump(job, fh)
    except Exception as e:  # noqa: BLE001
        log(f"[hq] fallo encolando HQ: {e}")


def random_code(n: int = 25) -> str:
    return "".join(random.choice(ALPHABET) for _ in range(n))


def parse_timestamp(filename: str) -> float | None:
    """Del nombre `{cam}_{fecha}_{hora}.{micro}.avi_{segs}.jpg` extrae epoch (float)."""
    stem = filename.rsplit(".", 1)[0]           # quita la extensión de imagen
    parts = stem.split("_")
    if len(parts) < 4:
        return None
    fecha, hora_part, segs_part = parts[1], parts[2], parts[3]
    hora = hora_part.split(".")[0]
    segs = segs_part.split(".")[0]
    try:
        base = datetime.strptime(f"{fecha} {hora}", "%Y-%m-%d %H:%M:%S")
        return base.timestamp() + float(segs)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# P1-P3 (2026-09-02): dedup PERSISTENTE por local. `_PROCESSED_FACES` (memoria
# del proceso) no sobrevivía a restarts ni a varios clasificadores: los 18
# "uncertain" con best=1.0 de producción eran 8 stems re-procesados en pasadas
# distintas. El registro vive en motor/dedup/<local>/faces.jsonl (gitignored;
# el reset lo borra junto al resto de datos runtime).
# ---------------------------------------------------------------------------
_DEDUP_MEM: set[tuple[str, str]] = set()     # (local, hash) recientes
_DEDUP_TS: dict[tuple[str, str], float] = {}  # ts por clave (ventana)

def _dedup_file(ruta: str, local_id: str, cfg: Config) -> str:
    return os.path.join(ruta, cfg.dedup_dir, str(local_id), "faces.jsonl")

def _dedup_load(ruta: str, local_id: str, cfg: Config) -> None:
    """Carga en memoria las entradas dentro de la ventana y poda el fichero."""
    path = _dedup_file(ruta, local_id, cfg)
    if not os.path.exists(path):
        return
    window = cfg.dedup_window_hours * 3600.0
    now = time.time()
    from filelock import FileLock  # noqa: E402
    try:
        with FileLock(path + ".lock"):
            with open(path, encoding="utf-8") as fh:
                lines = [ln for ln in fh.read().splitlines() if ln.strip()]
    except OSError:
        return
    keep: list[str] = []
    for ln in lines:
        try:
            e = json.loads(ln)
        except json.JSONDecodeError:
            continue
        if now - float(e.get("ts", 0)) <= window:
            key = (str(e.get("local", local_id)), str(e.get("hash", "")))
            _DEDUP_MEM.add(key)
            _DEDUP_TS[key] = float(e.get("ts", now))
            keep.append(ln)
    if len(keep) < len(lines):
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with FileLock(path + ".lock"):
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write("\n".join(keep) + ("\n" if keep else ""))
        except OSError:
            pass

def _dedup_seen(ruta: str, local_id: str, cfg: Config, h: str) -> bool:
    return (str(local_id), h) in _DEDUP_MEM

def _dedup_record(ruta: str, local_id: str, cfg: Config, h: str,
                  stem: str, camara_id: str) -> None:
    """Registra un rostro consumido (append bajo lock, poda perezosa en load)."""
    key = (str(local_id), h)
    now = time.time()
    window = cfg.dedup_window_hours * 3600.0
    if key in _DEDUP_MEM and now - _DEDUP_TS.get(key, 0) <= window:
        return
    _DEDUP_MEM.add(key)
    _DEDUP_TS[key] = now
    path = _dedup_file(ruta, local_id, cfg)
    from filelock import FileLock  # noqa: E402
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with FileLock(path + ".lock"):
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps({"hash": h, "stem": stem, "cam": camara_id,
                                     "local": str(local_id), "ts": now}) + "\n")
    except OSError:
        pass


# ---------------------------------------------------------------------------
# A4 (2026-09-02): log del clasificador a fichero. detector.php lanza el
# clasificador con stdout a /dev/null (Jos_thread), así que las decisiones se
# perdían; aquí se escriben a motor/logs/clasificador_<local>.log.
# ---------------------------------------------------------------------------
_LOG_FILE = None  # ruta absoluta; se fija en main()

def log(*args):
    msg = " ".join(str(a) for a in args)
    if _LOG_FILE:
        try:
            with open(_LOG_FILE, "a", encoding="utf-8") as fh:
                fh.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}\n")
        except OSError:
            pass
    print(msg, flush=True)


def _cfg_snapshot(cfg: Config) -> dict:
    """Config efectiva mínima para auditoría/replay (A1)."""
    keys = ("secure_threshold", "match_threshold", "margin", "group_threshold",
            "cluster_confirm", "admission_cosine", "min_sharpness", "face_min_side",
            "new_low_floor", "low_band_min_agreements", "early_exit_min_margin",
            "silueta_min_score", "min_layer_conf", "llm_min_conf", "veto_conf",
            "gray_low", "gray_high", "exact_match_cos", "batch_seconds")
    out = {}
    for k in keys:
        v = getattr(cfg, k, None)
        out[k] = round(float(v), 4) if isinstance(v, float) else v
    return out


def _preserve_evidence(ruta: str, local_id: str, camara_id: str,
                       src_path: str, stem: str, tag: str) -> None:
    """Conserva un crop conflictivo como evidencia en la cola de revisión."""
    if not src_path or not os.path.exists(src_path):
        return
    try:
        rev_dir = os.path.join(ruta, "motor/revision", local_id, camara_id)
        os.makedirs(rev_dir, exist_ok=True)
        dst = os.path.join(rev_dir, f"{stem}_{tag}_{random_code(8)}.jpg")
        shutil.copy2(src_path, dst)
    except OSError as e:  # noqa: BLE001
        log(f"[preserve] fallo copiando evidencia {stem}: {e}")


def cluster_faces(faces_emb, group_threshold: float) -> list[list[int]]:
    """Union-Find sobre los embeddings de la batería (misma persona = mismo clúster)."""
    n = len(faces_emb)
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    from motor.core.matching import cosine  # noqa: E402
    for i in range(n):
        for j in range(i + 1, n):
            if cosine(faces_emb[i], faces_emb[j]) >= group_threshold:
                union(i, j)

    groups: dict[int, list[int]] = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)
    return list(groups.values())


def split_coherent_clusters(cluster: list[int], face_list: list[tuple],
                            battery: list[dict], cfg: Config) -> list[list[int]]:
    """Divide un clúster de batería en sub-clústeres COHERENTES (F1.1).

    El union-find a `group_threshold` puede enlazar transitivamente caras de
    personas distintas (impostor p95 ~0.36): A~B y B~C unen A~C sin que A~C
    se parezcan. Aquí cada sub-clúster se construye alrededor de su cara más
    nítida (representativo) y un miembro permanece SOLO si confirma contra él
    (coseno >= cfg.cluster_confirm). Dos personas juntas en la escena acaban en
    sub-clústeres distintos y dejan de contaminarse mutuamente.

    C1 (2026-09-02): cada entrada de `face_list` es (emb, item_idx, face_idx)
    y los sub-clústeres devueltos son índices GLOBALES de `face_list` (el bug
    original devolvía índices locales del clúster y `_process_subcluster` los
    usaba como globales, procesando caras que no pertenecían al sub-clúster).

    face_list: lista de (embedding, item_idx, face_idx) de la batería.
    """
    from motor.core.matching import cosine  # noqa: E402

    infos = []   # (emb, item_idx, sharpness)
    for fi in cluster:
        emb, item_idx, face_idx = face_list[fi]
        faces = battery[item_idx]["faces"]
        if 0 <= face_idx < len(faces):
            sh = face_sharpness(battery[item_idx]["img"], faces[face_idx])
        else:
            sh = 0.0
        infos.append((emb, item_idx, sh))

    remaining = set(range(len(infos)))
    subs: list[list[int]] = []
    while remaining:
        # semilla = cara más nítida restante (representativa del sub-clúster)
        seed = max(remaining, key=lambda i: infos[i][2])
        members = {seed}
        rep_emb = infos[seed][0]
        for i in sorted(remaining - {seed}):
            if cosine(infos[i][0], rep_emb) >= cfg.cluster_confirm:
                members.add(i)
        # Mapear a índices GLOBALES de face_list (C1: antes se devolvían locales)
        subs.append(sorted(cluster[m] for m in members))
        remaining -= members
    return subs


def _face_scores(embs: list[np.ndarray], store: FaceStore, cfg: Config,
                 pose: str | None) -> dict[str, float]:
    """Similitudes por persona agregadas con MAX (una cara fuerte no se diluye).

    Si cfg.zones_enabled, el ranking es pose-consciente (solo encodings de
    clase de pose comparable con la del query).
    """
    agg: dict[str, list[float]] = {}
    for q in embs:
        if cfg.zones_enabled and pose is not None:
            sp = scores_per_person_pose_aware(q, store, cfg, pose)
        else:
            sp = scores_per_person(q, store)
        for cod, s in sp.items():
            agg.setdefault(cod, []).append(s)
    return {cod: float(np.max(v)) for cod, v in agg.items()}


def select_display_face(b_faces, ref_emb, min_cos: float):
    """Cara del crop de BUSTO que mejor coincide con la persona del sub-clúster.

    El crop de busto (ancho 3x la cara) puede contener a OTRA persona cuando dos
    personas están juntas en el frame. Antes se elegía `max(det_score)` (la cara
    más grande), que podía ser la persona EQUIVOCADA (foto 723 mostraba al
    acompañante aunque el match por embeddings era correcto). Ahora se elige la
    cara con MAYOR COSENO contra el embedding representativo del sub-clúster; si
    ninguna supera `min_cos`, devuelve None y el llamador cae al crop tight
    (que muestra SIEMPRE la cara correcta).
    """
    from motor.core.matching import cosine  # noqa: E402
    best, best_s = None, -1.0
    for f in b_faces:
        s = cosine(f.embedding, ref_emb)
        if s > best_s:
            best, best_s = f, s
    if best is not None and best_s >= min_cos:
        return best
    return None


def dedup_faces_near_duplicates(faces: list, img, cfg: Config) -> list:
    """Elimina detecciones casi idénticas del MISMO rostro dentro de un crop.

    C (2 caras en el mismo crop): RetinaFace puede devolver 2 cajas casi iguales
    sobre la misma cara. Sin este dedup, el mismo stem generaba DOS sub-clústeres
    con el mismo embedding -> 2 fotos del mismo crop, la 2ª con score 1.0
    (autocoincidencia tras autoenriquecer la galería) y una foto display de la
    persona equivocada. Se conserva la más nítida de cada rostro distinto.
    """
    if len(faces) <= 1:
        return list(faces)
    from motor.core.matching import cosine  # noqa: E402
    keep: list = []
    for fc in sorted(faces, key=lambda x: face_sharpness(img, x), reverse=True):
        if all(cosine(fc.embedding, k.embedding) < cfg.dedup_cosine for k in keep):
            keep.append(fc)
    return keep


class _CascadeCtx:
    """Proveedores de capas superiores (L1b/L1c/L2/L3) para la fusión."""

    def __init__(self, ruta, local_id, camara_id, cfg, store, face_scores,
                 query_pose, rep_face_crop, rep_torso_path, rep_busto_path,
                 rep_img, rep_face, query_attributes=None):
        self.ruta = ruta
        self.local_id = local_id
        self.camara_id = camara_id
        self.cfg = cfg
        self.store = store
        self.face_scores = face_scores
        self.query_pose = query_pose
        self.rep_face_crop = rep_face_crop          # path del crop de cara (si existe)
        self.rep_torso_path = rep_torso_path        # path del crop de torso (si existe)
        self.rep_busto_path = rep_busto_path        # path del crop de busto/media-superior
        self.rep_img = rep_img                      # frame completo de la representativa
        self.rep_face = rep_face                    # Face detectada (bbox/landmarks)
        self.query_attributes = query_attributes
        self._vlm = None
        self._openai = None
        self._torso_desc_cache = {}

    # --- L1b: cuerpo/apariencia (media superior, Fase 1) ---
    # Antes esta capa usaba un crop diminuto bajo la barbilla (o el fallback
    # sobre el crop tight de la cara): daba similitudes ~0.0-0.42 incluso para
    # la misma persona. Ahora se compara con el BUSTO (cabeza-hombros/pecho)
    # recortado del frame completo, que sí contiene ropa real del sujeto.
    def torso_score(self, cod: str) -> LayerScore:
        from motor.core.appearance import Appearance, layer_score, torso_descriptor
        if not self.cfg.torso_enabled:
            return LayerScore(available=False, reason="torso_disabled")
        gallery = self.store.person_appearance(cod)
        if not gallery or not gallery.get("desc"):
            return LayerScore(available=False, reason="sin_galeria_cuerpo")
        desc = self._torso_desc_cache.get("q")
        if desc is None:
            desc = self._query_torso_desc()
            self._torso_desc_cache["q"] = desc
        if desc is None or desc.size == 0:
            return LayerScore(available=False, reason="sin_crop_cuerpo")
        gal = [Appearance(d, ts, s) for d, ts, s in zip(gallery["desc"], gallery["ts"], gallery.get("src", [""] * len(gallery["desc"])))]
        s, c, available = layer_score(desc, gal, ttl_days=self.cfg.torso_ttl_days)
        return LayerScore(score=s, confidence=c, available=available)

    def attributes_score(self, cod: str) -> LayerScore:
        from motor.core.attributes import attributes_layer_score
        if not self.cfg.attributes_enabled or not self.query_attributes:
            return LayerScore(available=False)
        gallery = self.store.person_attributes(cod) or {}
        values = gallery.get("values") or []
        scores = [attributes_layer_score(self.query_attributes, value) for value in values]
        scores = [s for s in scores if s.available]
        if not scores:
            return LayerScore(available=False)
        return max(scores, key=lambda s: (s.score, s.confidence))

    def _query_torso_desc(self):
        """Descriptor del cuerpo del query: busto (media superior) > torso > tight."""
        from motor.core.appearance import torso_descriptor
        from motor.procesa_video import torso_bbox
        for path in (self.rep_busto_path, self.rep_torso_path):
            if path and os.path.exists(path):
                img = cv2.imread(path)
                if img is not None and min(img.shape[:2]) >= 24:
                    h, w = img.shape[:2]
                    return torso_descriptor(img, (0, 0, w, h))
        if self.rep_img is not None and self.rep_face is not None:
            h, w = self.rep_img.shape[:2]
            tb = torso_bbox(self.rep_face, w, h, self.cfg)
            if tb is not None:
                return torso_descriptor(self.rep_img, tb)
        return None

    # --- L1c: zonas/ángulos (pose-consciente + silueta) ---
    def zonas_score(self, cod: str) -> LayerScore:
        from motor.core.zones import pose_confidence
        if not self.cfg.zones_enabled:
            return LayerScore(available=False)
        s_face = self.face_scores.get(cod, 0.0)
        # comparabilidad de pose contra la galería de la persona candidata
        p = self.store.person(cod)
        poses = (p.get("poses") or [None] * len(p.get("encodings", []))) if p else []
        pconf = max((pose_confidence(self.query_pose, po) for po in poses), default=0.6)
        sil, sil_conf, sil_avail = self._silueta_gallery(cod)
        if not sil_avail:
            return LayerScore(score=float(s_face), confidence=0.0, available=False)
        c = float(np.clip(0.6 * pconf + 0.4 * sil, 0.0, 1.0))
        return LayerScore(score=float(s_face), confidence=c, available=True)

    # --- L1c (reenfoque): silueta geométrica como SCORE propio ---
    # C3 (2026-09-02): la silueta del candidato se compara contra los
    # descriptores GUARDADOS en la galería (`sil`, la geometría REAL de la cara
    # que generó cada encoding), no contra una foto de archivo del panel
    # (`_candidate_face` elegía por det_score y podía ser la del acompañante).
    # La CONFIANZA es la fiabilidad del descriptor (landmarks 106 = alta,
    # fallback 5pt = media), nunca el propio score (evita circularidad).
    def silueta_score(self, cod: str) -> LayerScore:
        sil, sil_conf, sil_avail = self._silueta_gallery(cod)
        if not sil_avail:
            return LayerScore(available=False)
        return LayerScore(score=float(sil), confidence=sil_conf, available=True)

    def _query_silhouette(self):
        """Descriptor de silueta del rostro representativo del query (cacheado)."""
        from motor.core.zones import silhouette_descriptor
        if not hasattr(self, "_sil_q"):
            if self.rep_face is None:
                self._sil_q = None
            else:
                self._sil_q = silhouette_descriptor(self.rep_face)
            if self._sil_q is not None and self._sil_q.size == 0:
                self._sil_q = None
        return self._sil_q

    def _silueta_gallery(self, cod: str) -> tuple[float, float, bool]:
        """(mejor_similitud, confianza, available) contra la galería de `cod`.

        Compara el descriptor del query contra los `sil` almacenados por
        encoding (C3), filtrando por pose comparable si zones_enabled. La
        confianza combina la calidad del descriptor del query y del mejor match
        de galería (silhouette_quality: 106pt alta / 5pt media / sin señal 0).
        """
        from motor.core.zones import silhouette_quality, silhouette_sim, pose_compatible
        desc_q = self._query_silhouette()
        if desc_q is None:
            return 0.0, 0.0, False
        q_avail, q_conf = silhouette_quality(desc_q)
        if not q_avail:
            return 0.0, 0.0, False
        p = self.store.person(cod)
        if not p or not p.get("sil"):
            return 0.0, 0.0, False
        poses = p.get("poses") or [None] * len(p["sil"])
        best_sim, best_conf = -1.0, 0.0
        for g_sil, g_pose in zip(p["sil"], poses):
            if g_sil is None:
                continue
            g_sil = np.asarray(g_sil, dtype=np.float32)
            if g_sil.size == 0:
                continue
            if self.cfg.zones_enabled and not pose_compatible(self.query_pose, g_pose):
                continue
            s = silhouette_sim(desc_q, g_sil)
            if s > best_sim:
                best_sim = s
                g_avail, g_conf = silhouette_quality(g_sil)
                best_conf = min(q_conf, g_conf)
        if best_sim < 0.0:
            return 0.0, 0.0, False
        return float(best_sim), float(best_conf), True

    # --- L2/L3: VLM local y OpenAI (misma pareja de imágenes) ---
    def _query_images(self) -> list[str]:
        """Imágenes del query para el VLM/OpenAI: cara + busto (cuerpo real)."""
        out = []
        if self.rep_face_crop and os.path.exists(self.rep_face_crop):
            out.append(self.rep_face_crop)
        if self.rep_busto_path and os.path.exists(self.rep_busto_path):
            out.append(self.rep_busto_path)
        elif self.rep_torso_path and os.path.exists(self.rep_torso_path):
            out.append(self.rep_torso_path)
        return out

    def _candidate_photo(self, cod: str) -> str | None:
        from motor.core.photos import find_person_photos
        photos = find_person_photos(self.ruta, self.local_id, cod, max_n=3)
        return photos[0] if photos else None

    def _candidate_photos_pose(self, cod: str) -> list[str]:
        """Referencias del candidato ordenadas por pose COMPARABLE al query
        (Fase 3): los LLMs deben comparar contra una pose similar, no la última."""
        from motor.core.photos import find_person_photos
        from motor.core.quality import pose_label
        from motor.core.model import analyze
        from motor.core.zones import pose_compatible
        photos = find_person_photos(self.ruta, self.local_id, cod, max_n=6)
        if not photos:
            return []
        scored = []
        for p in photos:
            img = cv2.imread(p)
            if img is None:
                continue
            faces = analyze(img, det_size=(self.cfg.crop_det_size, self.cfg.crop_det_size),
                            min_score=self.cfg.min_det_score)
            if not faces:
                continue
            f = max(faces, key=lambda x: x.det_score)
            po = pose_label(f, self.cfg.yaw_frontal, self.cfg.yaw_45,
                            self.cfg.yaw_90, self.cfg.pitch_frontal)
            compat = int(pose_compatible(self.query_pose, po)) if self.query_pose else 1
            scored.append((compat, p))
        scored.sort(key=lambda x: -x[0])
        return [p for _, p in scored]

    def vlm_score(self, cod: str) -> LayerScore:
        if not self.cfg.vlm_enabled:
            return LayerScore(available=False)
        if self._vlm is None:
            from motor.core.vlm_local import VLMClient
            self._vlm = VLMClient(self.cfg, self.ruta)
        return self._llm_pair(self._vlm, cod)

    def openai_score(self, cod: str) -> LayerScore:
        if not self.cfg.openai_enabled:
            return LayerScore(available=False)
        if self._openai is None:
            from motor.core.llm_openai import OpenAICompare
            self._openai = OpenAICompare(self.cfg, self.ruta)
        return self._llm_pair(self._openai, cod)

    def _llm_pair(self, client, cod: str) -> LayerScore:
        # Fase 3: referencia del candidato con pose COMPARABLE al query (no la
        # más reciente): comparar dos perfiles espejo hace que el LLM diga
        # "distintas" aunque sean la misma persona.
        refs = self._candidate_photos_pose(cod)
        if not refs:
            return LayerScore(available=False, reason="sin_foto_referencia")
        ref = refs[0]
        queries = self._query_images()
        if not queries:
            return LayerScore(available=False, reason="sin_imagenes_query")
        # con cara y busto: 2 llamadas (baratas en volumen bajo); nos quedamos
        # con la de mayor confianza si concluyen igual, si no con la media.
        scores = [client.compare(q, ref) for q in queries]
        scores = [ls for ls in scores if ls.available]
        if not scores:
            return LayerScore(available=False, reason="proveedor_sin_respuesta")
        if len(scores) == 1:
            return scores[0]
        # C6 (2026-09-02): si las comparaciones (cara y torso) se CONTRADICEN,
        # la confianza agregada baja al MÍNIMO (nunca al máximo, que fabricaba
        # confianza alta sobre conclusiones opuestas). Scores: media.
        cs = [ls.confidence for ls in scores]
        agree = [ls.score >= 0.5 for ls in scores]
        c = float(max(cs) if all(agree) or not any(agree) else min(cs))
        return LayerScore(score=float(np.mean([ls.score for ls in scores])),
                          confidence=c, available=c > 0.0)


def process_battery(battery, ruta: str, local_id: str, camara_id: str, cfg: Config,
                    store: FaceStore, feedback=None, torso_map: dict[str, str] | None = None,
                    busto_map: dict[str, str] | None = None):
    # batería: lista de dicts {file, path, img, faces, ts}
    # C1: aplanar caras conservando (emb, item_idx, face_idx): la cara EXACTA
    # de cada detección. Perder este índice (como antes) hacía que cada
    # sub-clúster re-procesara TODAS las caras del crop (mezcla de personas).
    face_list = []  # (emb, item_idx, face_idx)
    for idx, it in enumerate(battery):
        for fidx, f in enumerate(it["faces"]):
            face_list.append((f.embedding, idx, fidx))

    clusters = cluster_faces([e for e, _, _ in face_list], cfg.group_threshold)

    for cluster in clusters:
        # F1.1: dividir en sub-clústeres coherentes — nunca mezclar personas
        # distintas dentro de la misma batería.
        for sub in split_coherent_clusters(cluster, face_list, battery, cfg):
            _process_subcluster(sub, face_list, battery, ruta, local_id, camara_id,
                                cfg, store, feedback, torso_map, busto_map)


def _process_subcluster(sub, face_list, battery, ruta: str, local_id: str,
                        camara_id: str, cfg: Config, store: FaceStore,
                        feedback=None, torso_map: dict[str, str] | None = None,
                        busto_map: dict[str, str] | None = None) -> None:
    """Clasifica un sub-clúster coherente de caras y actualiza galería/álbum.

    C1 (2026-09-02): `sub` son índices GLOBALES de `face_list` y TODAS las
    operaciones (representante, dedup, foto, galería) usan SOLO esas caras,
    nunca "todas las caras de los items" (fuente de la mezcla de personas en
    crops con dos caras: IDs 2/5/8/18/34/35 en producción).
    """
    from motor.core.feedback import embedding_hash  # noqa: E402
    from motor.core.zones import silhouette_descriptor  # noqa: E402
    from motor.core.matching import exact_band_persons  # noqa: E402

    members = [face_list[g] for g in sub]              # (emb, item_idx, face_idx)
    item_idxs = sorted({m[1] for m in members})
    embs = [m[0] for m in members]

    # foto representativa: la más NÍTIDA Y CERCANA del SUB-CLÚSTER.
    # Se pondera sharpness por √(área de la cara): una cara lejana enfocada
    # tiene menos píxeles reales que una cercana algo menos nítida.
    best = None
    best_score = -1.0
    best_sharp = 0.0
    for emb, idx, fidx in members:
        it = battery[idx]
        f = it["faces"][fidx]
        fw = f.bbox[2] - f.bbox[0]
        fh = f.bbox[3] - f.bbox[1]
        sh = face_sharpness(it["img"], f)
        score = sh * (float(fw * fh) ** 0.5)
        if score > best_score:
            best_score = score
            best_sharp = sh
            best = (idx, fidx, emb)
    rep_item = battery[best[0]]
    rep_face = rep_item["faces"][best[1]]
    rep_stem = rep_item["file"].rsplit(".", 1)[0]
    query_pose = pose_label(rep_face, cfg.yaw_frontal, cfg.yaw_45, cfg.yaw_90, cfg.pitch_frontal)
    rep_hash = embedding_hash(best[2]) if best[2] is not None else None

    # crop de torso compañero (mismo stem en <cam>_cuerpo/)
    torso_path = None
    if torso_map:
        torso_path = torso_map.get(rep_stem)

    # crop de busto compañero (mismo stem en <cam>_busto/) para la foto final de display
    busto_path = None
    if busto_map:
        busto_path = busto_map.get(rep_stem)

    # C + P (idempotencia persistente): si este MISMO rostro (mismo embedding
    # representativo) ya se procesó en esta sesión O en una pasada anterior del
    # daemon (registro persistente), el crop es un duplicado re-leído/re-escrito
    # tras restart. Se consumen sus ficheros y se salta: antes producía una 2ª
    # foto del mismo crop y N identidades duplicadas con score 1.0.
    if rep_hash is not None and (
            rep_hash in _PROCESSED_FACES or _dedup_seen(ruta, local_id, cfg, rep_hash)):
        for _idx in item_idxs:
            _p = battery[_idx]["path"]
            if os.path.exists(_p):
                os.remove(_p)
        if torso_path and os.path.exists(torso_path):
            os.remove(torso_path)
        if busto_path and os.path.exists(busto_path):
            os.remove(busto_path)
        log(f"[skip] rostro ya procesado (persistente): {rep_stem}")
        return
    if rep_hash is not None:
        _PROCESSED_FACES.add(rep_hash)
        _dedup_record(ruta, local_id, cfg, rep_hash, rep_stem, camara_id)

    # F2 fix (ENDURECIDO 2026-09-01 anti-mezcla): "uncertain" ya no se asigna al
    # top-1 ni enriquece su galería (contaminaba la identidad). Se crea persona
    # nueva/duplicada y va a revisión manual. Ante la duda, mejor un duplicado que
    # mezclar caras de gente distinta.

    query_attributes = None
    if cfg.attributes_enabled:
        try:
            from motor.core.vlm_local import VLMClient
            query_attributes = VLMClient(cfg, ruta).attributes(rep_item["path"])
        except Exception:  # noqa: BLE001
            query_attributes = None
        if query_attributes is None and cfg.openai_enabled:
            try:
                from motor.core.llm_openai import OpenAICompare
                query_attributes = OpenAICompare(cfg, ruta).attributes(rep_item["path"])
            except Exception:  # noqa: BLE001
                query_attributes = None

    ctx = None
    from motor.core.matching import MatchResult, face_confidence, select_candidates  # noqa: E402
    from motor.core.router import Situation  # noqa: E402
    from motor.core.fusion import CascadeContext, run_cascade  # noqa: E402

    # C5 (2026-09-02): identidad EXACTA autónoma. Si el rostro (o alguno del
    # sub-clúster) es idéntico a un encoding de UN SOLO candidato de la galería,
    # es la MISMA cara ya enrolada: match directo ANTES de silueta/cascada
    # (la silueta no puede bloquear un coseno >= exact_match_cos). Si hay >1
    # candidato en banda exacta, la galería está contaminada: NUNCA auto-fusión
    # ni nueva copia — evidencia a revisión y fin (autónomo, sin mezcla).
    exact_persons, best_exact = exact_band_persons(embs, store, cfg.exact_match_cos)
    exact_match = len(exact_persons) == 1
    exact_conflict = len(exact_persons) > 1

    if exact_conflict:
        # conservar el crop como evidencia y consumir la batería sin tocar BD
        _preserve_evidence(ruta, local_id, camara_id, rep_item["path"], rep_stem,
                           "conflicto-exacto")
        for _idx in item_idxs:
            _p = battery[_idx]["path"]
            if os.path.exists(_p):
                os.remove(_p)
        if torso_path and os.path.exists(torso_path):
            os.remove(torso_path)
        if busto_path and os.path.exists(busto_path):
            os.remove(busto_path)
        log(f"[exact-conflict] rostro idéntico en 2+ personas: {rep_stem} "
            f"-> {exact_persons}")
        if feedback is not None and cfg.feedback_enabled:
            from motor.core.feedback import embedding_hash  # noqa: E402
            feedback.log_decision({
                "local": local_id, "cam": camara_id,
                "verdict": "uncertain", "person": None,
                "top1": exact_persons[0], "top2": exact_persons[1] if len(exact_persons) > 1 else None,
                "best": float(best_exact), "second": 0.0,
                "layers": {"cara": LayerScore(score=float(best_exact), confidence=1.0)},
                "query_hash": embedding_hash(embs[0]) if embs else None,
                "stem": rep_stem, "pose": query_pose,
                "yaw": float(rep_face.yaw), "pitch": float(rep_face.pitch),
                "sharpness": best_sharp, "has_face": True,
                "exact_match": True, "exact_conflict": True,
                "branch": "exact_conflict",
            })
        return

    if exact_match:
        face_scores = _face_scores(embs, store, cfg, query_pose)
        result = MatchResult(
            verdict="match", person=exact_persons[0],
            best_score=float(best_exact), second_score=0.0,
            scores=dict(face_scores), confidence=1.0,
            layer_scores={"cara": LayerScore(score=float(best_exact), confidence=1.0)},
            candidates=[exact_persons[0]])
    elif cfg.cascade_enabled:
        face_scores = _face_scores(embs, store, cfg, query_pose)
        ranked = sorted(face_scores.items(), key=lambda kv: kv[1], reverse=True)
        s1 = ranked[0][1] if ranked else 0.0
        s2 = ranked[1][1] if len(ranked) > 1 else 0.0
        face_layer = LayerScore(score=s1, confidence=face_confidence(s1, s2, best_sharp, cfg))
        ctx = _CascadeCtx(ruta, local_id, camara_id, cfg, store, face_scores,
                          query_pose, rep_item["path"], torso_path, busto_path,
                          rep_item["img"], rep_face,
                          query_attributes=query_attributes)
        cc = CascadeContext(torso=ctx.torso_score, attributes=ctx.attributes_score,
                            zonas=ctx.zonas_score,
                            silueta=ctx.silueta_score,
                            vlm=ctx.vlm_score, openai=ctx.openai_score)
        situ = Situation(pose=query_pose, sharpness=best_sharp,
                         has_face=True, has_torso=torso_path is not None)
        result = run_cascade(face_scores, cc, cfg, face_layer, situation=situ)
    else:
        result = match_group(embs, store, cfg)
        # pose-consciente (F2) sin cascada: se activa con zones_enabled
        if cfg.zones_enabled:
            result = match_group(embs, store, cfg, sharpness=best_sharp, pose=query_pose)
        # F3 (autoaprendizaje): aunque no haya cascada, registrar features de la
        # capa cara (score+confidence) y candidatos top-1/top-2. Sin esto,
        # decisions.jsonl quedaba con layers={} y la calibración nunca tenía
        # matriz de features (feedback.py::_features descartaba la decisión).
        face_scores = _face_scores(embs, store, cfg, query_pose)
        s1 = result.best_score
        s2 = result.second_score
        face_layer = LayerScore(score=s1, confidence=face_confidence(s1, s2, best_sharp, cfg))
        result.layer_scores = {"cara": face_layer}
        result.candidates = select_candidates(face_scores, cfg)

    # C2 (2026-09-02): "review" se trata como "uncertain": NUNCA asigna al top-1
    # existente (contaminaba su galería vía new_person=True). Crea persona nueva
    # del sub-clúster (coherente) + copia a revisión.
    if result.verdict in ("new", "uncertain", "review") or result.person is None:
        person = random_code()
    else:
        person = result.person

    # nombre de salida: stem representativo (+ "----" entrada/salida si hay >=2 fotos distintas)
    stems = [battery[idx]["file"].rsplit(".", 1)[0] for idx in item_idxs]
    stems_sorted = sorted(stems, key=lambda s: parse_timestamp(s + ".jpg") or 0)
    if len(stems_sorted) >= 2 and stems_sorted[0] != stems_sorted[-1]:
        nombre = f"{stems_sorted[0]}----{stems_sorted[-1]}"
    else:
        nombre = stems_sorted[0] if stems_sorted else rep_stem

    foto_id = random_code()
    out_dir = os.path.join(ruta, "motor/caras", local_id, camara_id, person)
    os.makedirs(out_dir, exist_ok=True)
    out_name = f"{nombre}_{foto_id}.jpg"
    out_path = os.path.join(out_dir, out_name)

    # A1/A3 (2026-09-02): auditoría rica y publicada ANTES que el JPEG.
    #  - A3: escribir el sidecar primero elimina la carrera con clasificadorV2.php
    #    (escanea cada ~1 s; si la foto aparecía antes que el sidecar, este
    #    quedaba huérfano y la decisión sin auditar).
    #  - A1: registrar rama de decisión, mapa top-N de scores por candidato y
    #    la configuración efectiva usada (para el replay posterior).
    if cfg.attributes_enabled and result.candidates:
        if ctx is not None:
            result.layer_scores["attributes"] = ctx.attributes_score(result.candidates[0])
        else:
            from motor.core.attributes import attributes_layer_score
            values = (store.person_attributes(result.candidates[0]) or {}).get("values", [])
            cands = [attributes_layer_score(query_attributes, value) for value in values]
            cands = [sc for sc in cands if sc.available]
            result.layer_scores["attributes"] = max(cands, key=lambda sc: sc.score) if cands else LayerScore(available=False)
    elif cfg.attributes_enabled:
        # Keep activation visible in the audit even when no identity candidate
        # exists; there is intentionally no candidate score in that case.
        result.layer_scores["attributes"] = LayerScore(
            score=0.0,
            confidence=float(query_attributes.get("confidence", 0.0)) if query_attributes else 0.0,
            available=False,
        )
    if query_attributes is not None and person:
        store.add_attributes(person, query_attributes, ts=rep_item["ts"] or time.time(), src=foto_id)

    from motor.core.matching import top_scores  # noqa: E402
    audit_meta = {
        "exact_match": bool(exact_match),
        "exact_conflict": False,
        "branch": "exact" if exact_match else ("cascade" if cfg.cascade_enabled else "scalar"),
        "top_scores": top_scores(face_scores, n=5),
        "cfg": _cfg_snapshot(cfg),
        "stem": rep_stem,
        "pose": query_pose,
    }
    write_audit_queue(ruta, local_id, camara_id, foto_id, build_audit_record(
        foto_id, local_id, camara_id, result.verdict, person,
        layer_scores_json(result.layer_scores), attributes=query_attributes,
        meta=audit_meta))

    # Foto final: BUSTO (torso real + cara restaurada) para display. Internamente
    # el matching usa los crops tight; aquí se genera la imagen que se muestra.
    # Se prefiere el crop de busto (si existe); si no, el crop de cara tight.
    # B (2 caras en el mismo busto): se elige la cara del busto con mayor coseno
    # contra la persona del sub-clúster (no la de mayor det_score, que podía ser
    # la persona equivocada). Si el busto no contiene una cara de esa persona
    # (coseno < display_face_min_cosine), se cae al crop tight: la foto final
    # muestra SIEMPRE la cara correcta.
    photo_img = rep_item["img"]
    photo_bbox = rep_face.bbox
    if cfg.busto_enabled and busto_path and os.path.exists(busto_path):
        b_img = cv2.imread(busto_path)
        if b_img is not None:
            b_faces = analyze(b_img, det_size=(cfg.crop_det_size, cfg.crop_det_size),
                              min_score=cfg.min_det_score)
            bf = select_display_face(b_faces, rep_face.embedding, cfg.display_face_min_cosine)
            if bf is not None:
                photo_img = b_img
                photo_bbox = bf.bbox

    # Versión rápida (compact, SIN GFPGAN): aparece al instante en el panel.
    # La restauración facial (GFPGAN) y la versión HQ (x4plus) las genera el
    # worker único (photo_worker.py) desde la cola: los modelos pesados ya no
    # se cargan en N clasificadores (ahorro de RAM del refactor).
    t_foto = time.time()
    final_img = photo_busto(photo_img, photo_bbox, cfg, model="compact", restore=False)
    cv2.imwrite(out_path, final_img, [cv2.IMWRITE_JPEG_QUALITY, 95])
    log(f"[foto] {out_name} guardada ({final_img.shape[1]}x{final_img.shape[0]}) "
        f"en {time.time() - t_foto:.1f}s")

    # Versión HQ progresiva (sr_model_photo, p.ej. x4plus): el worker único la
    # genera y sobreescribe la foto ~35-40 s después; el panel la "autonitida".
    if cfg.hq_enabled and cfg.sr_model_photo != "compact":
        _queue_hq(out_path, photo_img, photo_bbox, cfg, ruta, local_id, camara_id, foto_id)

    # Fase 2: registrar el retrato (cara + busto) de la decisión ANTES de borrar
    # el crop fuente. `find_person_photos` leerá de aquí para las próximas
    # decisiones (VLM/OpenAI/silueta) aunque el ingestor vacíe motor/caras.
    from motor.core.photos import save_portrait  # noqa: E402
    save_portrait(ruta, local_id, person, query_pose, foto_id,
                  rep_item["path"], busto_path)

    if os.path.exists(rep_item["path"]):
        os.remove(rep_item["path"])

    # refinar el diccionario (F1.2: admisión por cara + C1: SOLO las caras del
    # sub-clúster; nunca "todas las caras de los items"). P2: se etiquetan con
    # la proveniencia `foto_id` de la foto representativa de este sub-clúster.
    if result.verdict == "match":
        _store_add(store, person, members, battery, cfg, foto_id=foto_id)
    else:
        # "new", "uncertain" y "review" (ENDURECIDO 2026-09-01 + C2): persona
        # nueva/duplicada. El sub-clúster es internamente coherente
        # (split_coherent_clusters + C1) -> se construye su galería desde cero
        # (new_person=True), sin contaminar a nadie. `review` NUNCA toca la
        # galería del candidato existente (antes lo hacía vía new_person=True).
        _store_add(store, person, members, battery, cfg, new_person=True, foto_id=foto_id)

    # F1/F3: galería de apariencia (cuerpo/media superior) por persona.
    # Fase 1: preferir el BUSTO (cabeza-hombros/pecho del frame completo) sobre
    # el crop de torso diminuto; el fallback tight solo si no hay otro contexto.
    if cfg.torso_enabled and person:
        from motor.core.appearance import torso_descriptor
        desc = None
        for cand in (busto_path, torso_path):
            if cand and os.path.exists(cand):
                img = cv2.imread(cand)
                if img is not None and min(img.shape[:2]) >= 24:
                    h, w = img.shape[:2]
                    desc = torso_descriptor(img, (0, 0, w, h))
                    break
        if desc is None:
            tb = torso_bbox_local(rep_face, rep_item["img"], cfg)
            if tb is not None:
                desc = torso_descriptor(rep_item["img"], tb)
        if desc is not None and desc.size > 0:
            store.add_appearance(person, desc, ts=rep_item["ts"] or time.time(),
                                 src=out_name)

    # UNCERTAIN/REVIEW (C2): copia a cola de revisión manual (nunca duplicado
    # en silencio; el sub-clúster queda como persona nueva coherente).
    if result.verdict in ("uncertain", "review"):
        _copy_to_revision(ruta, local_id, camara_id, out_dir, out_name, cfg)

    # feedback: registrar la decisión con features por capa + trazabilidad (A1)
    if feedback is not None and cfg.feedback_enabled:
        from motor.core.feedback import embedding_hash
        feedback.log_decision({
            "local": local_id, "cam": camara_id,
            "verdict": result.verdict, "person": person,
            "top1": result.candidates[0] if result.candidates else None,
            "top2": result.candidates[1] if len(result.candidates) > 1 else None,
            "best": result.best_score, "second": result.second_score,
            "layers": result.layer_scores,
            "query_hash": embedding_hash(embs[0]) if embs else None,
            "stem": rep_stem,
            "pose": query_pose,
            "yaw": float(rep_face.yaw),
            "pitch": float(rep_face.pitch),
            "sharpness": best_sharp,
            "has_face": True,
            # A1: trazabilidad completa para el replay/validación posterior
            "foto_id": foto_id,
            "exact_match": bool(exact_match),
            "exact_conflict": False,
            "branch": "exact" if exact_match else ("cascade" if cfg.cascade_enabled else "scalar"),
            "top_scores": [{"person": c, "score": round(float(s), 4)}
                           for c, s in sorted(face_scores.items(),
                                              key=lambda kv: kv[1], reverse=True)[:5]],
            "cfg": _cfg_snapshot(cfg),
        })

    # Persist an immutable, access-controlled audit sidecar. Attributes remain
    # potentially sensitive; PHP links it to the
    # eventual fotos.id using this classifier-generated correlation id.
    # Classification phase is derived by PHP from durable BD move events; no
    # mutable marker or journal participates in authority decisions.
    # (A3) El sidecar se publica ANTES que el JPEG, justo tras fijar `foto_id`.

    # eliminar el resto de fotos del sub-clúster (ya procesadas)
    for idx in item_idxs:
        p = battery[idx]["path"]
        if os.path.exists(p):
            os.remove(p)

    # consumir el crop de torso compañero (ya no hace falta)
    if torso_path and os.path.exists(torso_path):
        os.remove(torso_path)

    # consumir el crop de busto compañero (ya no hace falta)
    if busto_path and os.path.exists(busto_path):
        os.remove(busto_path)

    log(f"[{result.verdict}] {len(item_idxs)} foto(s) -> {person} (best={result.best_score:.3f})")


def torso_bbox_local(face, img, cfg):
    from motor.procesa_video import torso_bbox
    if img is None:
        return None
    h, w = img.shape[:2]
    return torso_bbox(face, w, h, cfg)


def _store_add(store: FaceStore, person: str, members, battery, cfg: Config,
               new_person: bool = False, foto_id: str | None = None) -> None:
    """Añade encodings a la galería de `person` con CONTROL DE ADMISIÓN (F1.2).

    C1 (2026-09-02): `members` son (emb, item_idx, face_idx) — las caras EXACTAS
    del sub-clúster. Antes se recibían `item_idxs` y se añadían TODAS las caras
    de cada item (mezcla de personas en crops con 2+ caras, IDs 2/5/8/18/34/35).

    - new_person=True (verdict "new"/"uncertain"/"review"): el sub-clúster ya es
      internamente coherente (split_coherent_clusters + C1) -> se añaden todas
      sus caras (solo las del sub-clúster, nunca las de otros sub-clústeres).
    - new_person=False (match): cada cara se admite SOLO si su mejor similitud
      individual contra la persona asignada >= cfg.admission_cosine
      (pose-consciente si cfg.zones_enabled). Las caras que no confirmen NO
      entran en la galería: evita que una cara ajena contamine la identidad.

    C3: por cada encoding admitido se guarda su descriptor de silueta (`sil`,
    lista paralela en face_enc_v2): la capa de silueta de decisiones futuras
    comparará contra la geometría REAL de la cara enrolada (no contra una foto
    de archivo del panel, que podía ser la del acompañante).

    P2 (proveniencia): todos los encodings de este sub-clúster se etiquetan con
    `foto_id` (el identificador_unico de la foto representativa) para que luego
    "mover foto"/"separar" pueda quitarlos de forma EXACTA (move_by_source).
    """
    from motor.core.quality import face_sharpness as _fs, pose_label as _pl
    from motor.core.matching import best_cosine, scores_per_person_pose_aware
    from motor.core.zones import silhouette_descriptor

    gal_encs = store.person_encodings(person)
    encs, quals, poses, sils, srcs = [], [], [], [], []
    for emb, idx, fidx in members:
        it = battery[idx]
        if not (0 <= fidx < len(it["faces"])):
            continue
        f = it["faces"][fidx]
        # B4 (2026-08-26): higiene de galería — nunca admitir un encoding
        # de una cara demasiado pequeña aunque pase admission_cosine: su
        # embedding es poco fiable y con la agregación MAX puede arrastrar
        # el score de la persona. (La nitidez ya está filtrada aguas arriba.)
        if max(f.bbox[2] - f.bbox[0], f.bbox[3] - f.bbox[1]) < cfg.face_min_side:
            continue
        if new_person:
            admit = True
        elif gal_encs is None or len(gal_encs) == 0:
            admit = False                 # sin galería no puede confirmar (no ocurre en match)
        elif cfg.zones_enabled and cfg.admission_pose_aware:
            pose = _pl(f, cfg.yaw_frontal, cfg.yaw_45, cfg.yaw_90, cfg.pitch_frontal)
            sp = scores_per_person_pose_aware(f.embedding, store, cfg, pose)
            admit = sp.get(person, 0.0) >= cfg.admission_cosine
        else:
            admit = best_cosine(f.embedding, gal_encs) >= cfg.admission_cosine
        if admit:
            sil = silhouette_descriptor(f)
            encs.append(f.embedding)
            quals.append(_fs(it["img"], f))
            poses.append(_pl(f, cfg.yaw_frontal, cfg.yaw_45, cfg.yaw_90, cfg.pitch_frontal))
            sils.append(sil)
            srcs.append(foto_id)
    if encs:
        store.add(person, encs, quals, poses, sources=srcs, sils=sils)


def _copy_to_revision(ruta: str, local_id: str, camara_id: str,
                      out_dir: str, out_name: str, cfg: Config) -> None:
    """Copia la foto del veredicto UNCERTAIN a la cola de revisión manual."""
    rev_dir = os.path.join(ruta, cfg.revision_dir, local_id, camara_id)
    os.makedirs(rev_dir, exist_ok=True)
    src = os.path.join(out_dir, out_name)
    if os.path.exists(src):
        shutil.copy2(src, os.path.join(rev_dir, out_name))


def process_body_once(ruta: str, local_id: str, camara_id: str, cfg: Config,
                      store: FaceStore) -> int:
    """F7: procesa crops de CUERPO sin cara (`*_nocara.jpg` en <cam>_cuerpo/).

    Solo torso (L1b) + VLM (L2): si identifican a la persona con confianza MUY
    alta (>= cfg.body_match_conf) se asigna; si no, el crop va a revisión manual.
    NUNCA se crea una persona nueva por un crop de espaldas no identificable.
    """
    from motor.core.appearance import Appearance, layer_score, torso_descriptor
    from motor.core.feedback import FeedbackCollector
    from motor.core.matching import LayerScore
    from motor.core.fusion import CascadeContext, run_cascade

    torso_dir = os.path.join(ruta, "motor/caras/sinclasificar", local_id, f"{camara_id}_cuerpo")
    if not os.path.isdir(torso_dir):
        return 0

    items = []
    for f in sorted(os.listdir(torso_dir)):
        if not f.lower().endswith(IMG_EXTS) or not f.endswith("_nocara.jpg"):
            continue
        p = os.path.join(torso_dir, f)
        img = cv2.imread(p)
        if img is None:
            os.remove(p)
            continue
        items.append({"file": f, "path": p, "img": img, "ts": parse_timestamp(f)})

    if not items:
        return 0
    items.sort(key=lambda x: (x["ts"] is None, x["ts"] or 0))

    # baterías temporales (mismo criterio que las caras)
    baterias = []
    cur = []
    prev_ts = None
    for it in items:
        if prev_ts is None or (it["ts"] is not None and prev_ts is not None
                               and (it["ts"] - prev_ts) <= cfg.batch_seconds):
            cur.append(it)
        else:
            if cur:
                baterias.append(cur)
            cur = [it]
        prev_ts = it["ts"]
    if cur:
        baterias.append(cur)

    n = 0
    for bat in baterias:
        # representativo = el item más reciente de la batería
        it = max(bat, key=lambda x: x["ts"] or 0)
        h, w = it["img"].shape[:2]
        query_desc = torso_descriptor(it["img"], (0, 0, w, h))

        # candidatos por apariencia (galería de torso de cada persona)
        scores: dict[str, LayerScore] = {}
        for cod in store.persons():
            gal = store.person_appearance(cod)
            if not gal or not gal.get("desc"):
                continue
            gallery = [Appearance(d, ts, s) for d, ts, s in
                       zip(gal["desc"], gal["ts"], gal.get("src", [""] * len(gal["desc"])))]
            s, c, avail = layer_score(query_desc, gallery, ttl_days=cfg.torso_ttl_days)
            if avail and c > 0:
                scores[cod] = LayerScore(score=s, confidence=c)
        if not scores:
            # sin galería de torso todavía: revisión manual, nunca persona nueva
            _body_to_revision(ruta, local_id, camara_id, [x["path"] for x in bat], cfg)
            n += 1
            continue

        face_scores = {c: ls.score for c, ls in scores.items()}
        best_cod = max(scores, key=lambda c: scores[c].score * scores[c].confidence)

        def _body_vlm(cod: str) -> LayerScore:
            from motor.core.photos import find_person_photos
            from motor.core.vlm_local import VLMClient
            refs = find_person_photos(ruta, local_id, cod, max_n=1)
            if not refs or not cfg.vlm_enabled:
                return LayerScore(available=False)
            vlm = VLMClient(cfg, ruta)
            return vlm.compare(it["path"], refs[0])

        ctx = CascadeContext(torso=lambda cod: scores.get(cod, LayerScore(available=False)),
                             vlm=_body_vlm)
        face_layer = LayerScore(score=scores[best_cod].score,
                                confidence=scores[best_cod].confidence)
        from motor.core.router import Situation
        result = run_cascade(face_scores, ctx, cfg, face_layer,
                             situation=Situation(has_face=False))

        if result.verdict == "match" and result.person is not None:
            # asignar: mover el crop al álbum de la persona (mismo contrato)
            out_dir = os.path.join(ruta, "motor/caras", local_id, camara_id, result.person)
            os.makedirs(out_dir, exist_ok=True)
            foto_id = random_code()
            out_name = f"{it['file'].rsplit('.', 1)[0]}_{foto_id}.jpg"
            cv2.imwrite(os.path.join(out_dir, out_name), it["img"],
                        [cv2.IMWRITE_JPEG_QUALITY, 95])
            store.add_appearance(result.person, query_desc, ts=it["ts"] or time.time(),
                                 src=out_name)
            for x in bat:
                if os.path.exists(x["path"]):
                    os.remove(x["path"])
            log(f"[body-match] {len(bat)} crop(s) -> {result.person} (torso+VLM)")
        else:
            _body_to_revision(ruta, local_id, camara_id, [x["path"] for x in bat], cfg)
            log(f"[body-revision] {len(bat)} crop(s) sin identidad concluyente -> revisión")
        n += 1
    return n


def _body_to_revision(ruta: str, local_id: str, camara_id: str,
                      paths: list[str], cfg: Config) -> None:
    rev_dir = os.path.join(ruta, cfg.revision_dir, local_id, camara_id)
    os.makedirs(rev_dir, exist_ok=True)
    for p in paths:
        if os.path.exists(p):
            shutil.move(p, os.path.join(rev_dir, os.path.basename(p)))


def process_once(ruta: str, local_id: str, camara_id: str, cfg: Config,
                 store: FaceStore, feedback=None) -> int:
    dir_in = os.path.join(ruta, "motor/caras/sinclasificar", local_id, camara_id)
    notienecaras = os.path.join(ruta, "motor/removidas/notienecaras")
    nopasafiltros = os.path.join(ruta, "motor/removidas/nopasafiltros")
    os.makedirs(notienecaras, exist_ok=True)
    os.makedirs(nopasafiltros, exist_ok=True)

    if not os.path.isdir(dir_in):
        return 0

    items = []
    for f in sorted(os.listdir(dir_in)):
        if not f.lower().endswith(IMG_EXTS):
            continue
        p = os.path.join(dir_in, f)
        img = cv2.imread(p)
        if img is None:
            shutil.move(p, os.path.join(nopasafiltros, f))
            continue
        faces = analyze(img, det_size=(cfg.crop_det_size, cfg.crop_det_size), min_score=cfg.min_det_score)
        if not faces:
            shutil.move(p, os.path.join(notienecaras, f))
            continue
        # B2 (2026-08-26): además de nitidez, exigir un tamaño mínimo de cara.
        # Una cara diminuta (< cfg.face_min_side) tiene tan poca información que
        # el embedding ArcFace es poco fiable y causaba falsos match/new. Se
        # descarta (nopasafiltros) en vez de decidir con datos pobres.
        focused = [
            fc for fc in faces
            if face_sharpness(img, fc) >= cfg.min_sharpness
            and max(fc.bbox[2] - fc.bbox[0], fc.bbox[3] - fc.bbox[1]) >= cfg.face_min_side
        ]
        if not focused:
            shutil.move(p, os.path.join(nopasafiltros, f))
            continue
        # C (2 caras en el mismo crop): dedup de detecciones casi idénticas del
        # MISMO rostro dentro del crop (ver dedup_faces_near_duplicates).
        focused = dedup_faces_near_duplicates(focused, img, cfg)
        # SR-before-embedding: las caras pequeñas (< sr_embed_min_face) recalculan
        # su embedding sobre el recorte super-resuelto -> matching más fiable.
        for fc in focused:
            fc.embedding = enhance_embedding(img, fc, cfg)
        items.append({"file": f, "path": p, "img": img, "faces": focused, "ts": parse_timestamp(f)})

    if not items:
        return 0

    # mapa stem -> crop de torso compañero (F1, misma batería)
    torso_map: dict[str, str] = {}
    torso_dir = os.path.join(ruta, "motor/caras/sinclasificar", local_id, f"{camara_id}_cuerpo")
    if os.path.isdir(torso_dir):
        for f in sorted(os.listdir(torso_dir)):
            if f.lower().endswith(IMG_EXTS):
                stem = f.rsplit(".", 1)[0]
                if not stem.endswith("_nocara"):      # F7: los body-only se tratan aparte
                    torso_map[stem] = os.path.join(torso_dir, f)

    # mapa stem -> crop de busto compañero (foto final de display)
    busto_map: dict[str, str] = {}
    busto_dir = os.path.join(ruta, "motor/caras/sinclasificar", local_id, f"{camara_id}_busto")
    if os.path.isdir(busto_dir):
        for f in sorted(os.listdir(busto_dir)):
            if f.lower().endswith(IMG_EXTS):
                stem = f.rsplit(".", 1)[0]
                busto_map[stem] = os.path.join(busto_dir, f)

    items.sort(key=lambda x: (x["ts"] is None, x["ts"] or 0))

    # agrupar en baterías
    baterias = []
    cur = []
    prev_ts = None
    for it in items:
        if prev_ts is None or (it["ts"] is not None and prev_ts is not None and (it["ts"] - prev_ts) <= cfg.batch_seconds):
            cur.append(it)
        else:
            if cur:
                baterias.append(cur)
            cur = [it]
        prev_ts = it["ts"]
    if cur:
        baterias.append(cur)

    n = 0
    for bat in baterias:
        process_battery(bat, ruta, local_id, camara_id, cfg, store, feedback, torso_map, busto_map)
        n += 1
    return n


def _ram_available_gb() -> float:
    """GB disponibles (MemAvailable de /proc/meminfo); 99.0 si no se puede leer."""
    try:
        with open("/proc/meminfo", encoding="ascii") as fh:
            for line in fh:
                if line.startswith("MemAvailable:"):
                    return int(line.split()[1]) / 1024 / 1024
    except Exception:  # noqa: BLE001
        pass
    return 99.0


def _apply_calib_weights(cfg, ruta: str) -> bool:
    """Aplica los pesos-prior calibrados (motor/calib/calib_model.pkl) al Config.

    Solo si RF_CALIB_APPLY=1 y el modelo dice weights_applied (calibrar.py lo
    guarda versionado con cap anti-drift y validación held-out). El bucle de
    autoaprendizaje re-pondera las capas; la decisión actual usa autoridad/veto
    (no la media ponderada), así que estos pesos afinan el desempate/reporte.
    """
    if not getattr(cfg, "calib_apply", False):
        return False
    try:
        from motor.core.calibration import CalibrationModel
        model = CalibrationModel(os.path.join(ruta, cfg.calib_dir))
        if not model.load():
            return False
        if not model.weights_applied or not model.weights:
            return False
        w = model.weights
        cfg.w_cara = float(w.get("cara", cfg.w_cara))
        cfg.w_torso = float(w.get("torso", cfg.w_torso))
        cfg.w_llm = float(w.get("llm", cfg.w_llm))
        return True
    except Exception:  # noqa: BLE001 — un modelo corrupto degrada, no rompe
        return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("local_id")
    ap.add_argument("camara_id")
    ap.add_argument("token", nargs="?", default=None, help="token identificador de Jos_Thread (se ignora)")
    ap.add_argument("--ruta", default=os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    ap.add_argument("--once", action="store_true", help="una sola pasada (sin bucle)")
    ap.add_argument("--secure", type=float, default=None)
    ap.add_argument("--match", type=float, default=None)
    ap.add_argument("--margin", type=float, default=None)
    ap.add_argument("--min-sharpness", type=float, default=None)
    args, _desconocidos = ap.parse_known_args()  # tolera el token final de Jos_Thread

    # camara_id admite una lista separada por comas (pool): un único proceso
    # atiende varias cámaras en round-robin para reducir el nº de procesos y la
    # RAM total de modelos. detector.php agrupa las cámaras en chunks y pasa
    # "13,14,17" como camara_id; el token final de Jos_Thread se ignora.
    cameras = [c.strip() for c in str(args.camara_id).split(",") if c.strip()]

    cfg = Config.from_env(args.ruta)
    if args.secure is not None:
        cfg.secure_threshold = args.secure
    if args.match is not None:
        cfg.match_threshold = args.match
    if args.margin is not None:
        cfg.margin = args.margin
    if args.min_sharpness is not None:
        cfg.min_sharpness = args.min_sharpness
    # A4: persistir el log del clasificador (el daemon lanza con stdout a /dev/null)
    global _LOG_FILE
    try:
        logs_dir = os.path.join(args.ruta, "motor/logs")
        os.makedirs(logs_dir, exist_ok=True)
        _LOG_FILE = os.path.join(logs_dir, f"clasificador_{args.local_id}.log")
    except OSError:
        _LOG_FILE = None
    # P1: cargar el registro persistente de rostros ya procesados (ventana)
    _dedup_load(args.ruta, args.local_id, cfg)

    store = FaceStore(os.path.join(args.ruta, "motor/bbdd_reconocimiento", args.local_id, "face_enc_v2"),
                      max_per_person=cfg.max_encodings_per_person)

    from motor.core.feedback import FeedbackCollector
    feedback = FeedbackCollector(args.ruta, args.local_id, enabled=cfg.feedback_enabled)

    _apply_calib_weights(cfg, args.ruta)

    log(f"clasificador {args.local_id}/[{','.join(cameras)}] — face_enc_v2 con {len(store.persons())} personas"
        f" | cascada={cfg.cascade_enabled} torso={cfg.torso_enabled} zonas={cfg.zones_enabled}"
        f" silueta={cfg.silueta_enabled}"
        f" vlm={cfg.vlm_enabled} openai={cfg.openai_enabled}")
    _last_calib_check = 0.0
    cam_idx = 0
    while True:
        try:
            # reload periódico de pesos calibrados (timer rf-calibra a las 05:10)
            now = time.time()
            if now - _last_calib_check > 60:
                _last_calib_check = now
                if _apply_calib_weights(cfg, args.ruta):
                    log("[calib] pesos calibrados aplicados: "
                        f"w_cara={cfg.w_cara:.3f} w_torso={cfg.w_torso:.3f} w_llm={cfg.w_llm:.3f}")
            # RAM-gate: con la memoria disponible escasa (p. ej. autotube
            # renderizando en la misma máquina) se duerme en vez de procesar;
            # evita el pico de RAM de los 12 clasificadores + procesa_video
            # que disparaba el OOM killer global (mataba rf o autotube).
            if _ram_available_gb() < cfg.ram_min_free_gb:
                time.sleep(5)
                continue
            cam = cameras[cam_idx % len(cameras)]
            n = process_once(args.ruta, args.local_id, cam, cfg, store, feedback)
            nb = process_body_once(args.ruta, args.local_id, cam, cfg, store)
            if n or nb:
                log(f"[{cam}] procesadas {n} batería(s) de caras, {nb} de cuerpos")
            cam_idx += 1
            if args.once and cam_idx >= len(cameras):
                return 0
            time.sleep(1)
        except KeyboardInterrupt:
            return 0


if __name__ == "__main__":
    sys.exit(main())
