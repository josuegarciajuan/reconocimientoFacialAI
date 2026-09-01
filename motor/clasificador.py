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


def log(*args):
    print(*args, flush=True)


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

    El union-find a `group_threshold` (0.30) puede enlazar transitivamente caras
    de personas distintas (impostor p95 ~0.36): A~B y B~C unen A~C sin que A~C
    se parezcan. Aquí cada sub-clúster se construye alrededor de su cara más
    nítida (representativo) y un miembro permanece SOLO si confirma contra él
    (coseno >= cfg.cluster_confirm). Dos personas juntas en la escena acaban en
    sub-clústeres distintos y dejan de contaminarse mutuamente.

    face_list: lista de (embedding, item_idx) de la batería (mismo orden que cluster).
    """
    from motor.core.matching import cosine  # noqa: E402

    infos = []   # (emb, item_idx, sharpness)
    for fi in cluster:
        emb, item_idx = face_list[fi]
        sh = max(face_sharpness(battery[item_idx]["img"], f)
                 for f in battery[item_idx]["faces"]) if battery[item_idx]["faces"] else 0.0
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
        subs.append(sorted(members))
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
                 query_pose, rep_face_crop, rep_torso_path, rep_img, rep_face,
                 query_attributes=None):
        self.ruta = ruta
        self.local_id = local_id
        self.camara_id = camara_id
        self.cfg = cfg
        self.store = store
        self.face_scores = face_scores
        self.query_pose = query_pose
        self.rep_face_crop = rep_face_crop          # path del crop de cara (si existe)
        self.rep_torso_path = rep_torso_path        # path del crop de torso (si existe)
        self.rep_img = rep_img                      # frame completo de la representativa
        self.rep_face = rep_face                    # Face detectada (bbox/landmarks)
        self.query_attributes = query_attributes
        self._vlm = None
        self._openai = None
        self._torso_desc_cache = {}

    # --- L1b: torso/ropa ---
    def torso_score(self, cod: str) -> LayerScore:
        from motor.core.appearance import Appearance, layer_score, torso_descriptor
        if not self.cfg.torso_enabled:
            return LayerScore(available=False)
        gallery = self.store.person_appearance(cod)
        if not gallery or not gallery.get("desc"):
            return LayerScore(available=False)
        desc = self._torso_desc_cache.get("q")
        if desc is None:
            desc = self._query_torso_desc()
            self._torso_desc_cache["q"] = desc
        if desc is None or desc.size == 0:
            return LayerScore(available=False)
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
        from motor.core.appearance import torso_descriptor
        from motor.procesa_video import torso_bbox
        if self.rep_torso_path and os.path.exists(self.rep_torso_path):
            img = cv2.imread(self.rep_torso_path)
            if img is not None:
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
        from motor.core.zones import pose_confidence, silhouette_descriptor, silhouette_sim
        if not self.cfg.zones_enabled:
            return LayerScore(available=False)
        s_face = self.face_scores.get(cod, 0.0)
        # comparabilidad de pose contra la galería de la persona candidata
        p = self.store.person(cod)
        poses = (p.get("poses") or [None] * len(p.get("encodings", []))) if p else []
        pconf = max((pose_confidence(self.query_pose, po) for po in poses), default=0.6)
        sil = 0.5
        if self.rep_face is not None:
            cand_face = self._candidate_face(cod)
            if cand_face is not None:
                a = silhouette_descriptor(self.rep_face)
                b = silhouette_descriptor(cand_face)
                sil = silhouette_sim(a, b) if a.size and b.size else 0.5
        c = float(np.clip(0.6 * pconf + 0.4 * sil, 0.0, 1.0))
        return LayerScore(score=float(s_face), confidence=c, available=True)

    # --- L1c (reenfoque): silueta geométrica como SCORE propio ---
    # En perfil/ángulos raros es CO-AUTORIDAD: debe superar silueta_min_score
    # para confirmar el acuerdo. Antes solo modulaba la confianza de zonas.
    # El descriptor usa landmarks 106 o, si faltan (arr/aba extremas), el
    # fallback a keypoints 5-punto (zones.silhouette_descriptor): la capa
    # sigue disponible donde más se necesita.
    def silueta_score(self, cod: str) -> LayerScore:
        from motor.core.zones import silhouette_descriptor, silhouette_sim
        if not self.cfg.silueta_enabled:
            return LayerScore(available=False)
        if self.rep_face is None:
            return LayerScore(available=False)
        cand_face = self._candidate_face(cod)
        if cand_face is None:
            return LayerScore(available=False)
        a = silhouette_descriptor(self.rep_face)
        b = silhouette_descriptor(cand_face)
        if not a.size or not b.size:
            return LayerScore(available=False)
        sil = silhouette_sim(a, b)
        return LayerScore(score=float(sil), confidence=float(sil), available=True)

    def _candidate_face(self, cod: str):
        """Primera cara de la foto representativa del candidato (para silueta)."""
        from motor.core.photos import find_person_photos
        photos = find_person_photos(self.ruta, self.local_id, cod, max_n=1)
        if not photos:
            return None
        img = cv2.imread(photos[0])
        if img is None:
            return None
        faces = analyze(img, det_size=(self.cfg.crop_det_size, self.cfg.crop_det_size),
                        min_score=self.cfg.min_det_score)
        if not faces:
            return None
        return max(faces, key=lambda f: f.det_score)

    # --- L2/L3: VLM local y OpenAI (misma pareja de imágenes) ---
    def _query_images(self) -> list[str]:
        """Imágenes del query disponibles para el VLM: crop de cara y/o torso."""
        out = []
        if self.rep_face_crop and os.path.exists(self.rep_face_crop):
            out.append(self.rep_face_crop)
        if self.rep_torso_path and os.path.exists(self.rep_torso_path):
            out.append(self.rep_torso_path)
        return out

    def _candidate_photo(self, cod: str) -> str | None:
        from motor.core.photos import find_person_photos
        photos = find_person_photos(self.ruta, self.local_id, cod, max_n=1)
        return photos[0] if photos else None

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
        ref = self._candidate_photo(cod)
        if not ref:
            return LayerScore(available=False)
        queries = self._query_images()
        if not queries:
            return LayerScore(available=False)
        # con cara y torso: 2 llamadas (baratas en volumen bajo); nos quedamos
        # con la de mayor confianza si concluyen igual, si no con la media.
        scores = [client.compare(q, ref) for q in queries]
        scores = [ls for ls in scores if ls.available]
        if not scores:
            return LayerScore(available=False)
        if len(scores) == 1:
            return scores[0]
        s = float(np.mean([ls.score for ls in scores]))
        c = float(np.max([ls.confidence for ls in scores]))
        return LayerScore(score=s, confidence=c, available=c > 0.0)


def process_battery(battery, ruta: str, local_id: str, camara_id: str, cfg: Config,
                    store: FaceStore, feedback=None, torso_map: dict[str, str] | None = None,
                    busto_map: dict[str, str] | None = None):
    # batería: lista de dicts {file, path, img, faces, ts}
    # aplanar caras -> (embedding, índice_item)
    face_list = []  # (emb, item_idx)
    for idx, it in enumerate(battery):
        for f in it["faces"]:
            face_list.append((f.embedding, idx))

    clusters = cluster_faces([e for e, _ in face_list], cfg.group_threshold)

    for cluster in clusters:
        # F1.1: dividir en sub-clústeres coherentes — nunca mezclar personas
        # distintas dentro de la misma batería (union-find transitivo a 0.30
        # enlazaba caras ajenas y contaminaba la galería).
        for sub in split_coherent_clusters(cluster, face_list, battery, cfg):
            _process_subcluster(sub, face_list, battery, ruta, local_id, camara_id,
                                cfg, store, feedback, torso_map, busto_map)


def _process_subcluster(sub, face_list, battery, ruta: str, local_id: str,
                        camara_id: str, cfg: Config, store: FaceStore,
                        feedback=None, torso_map: dict[str, str] | None = None,
                        busto_map: dict[str, str] | None = None) -> None:
    """Clasifica un sub-clúster coherente de caras y actualiza galería/álbum."""
    from motor.core.feedback import embedding_hash  # noqa: E402 (guarda C de idempotencia)
    item_idxs = sorted({face_list[i][1] for i in sub})
    embs = [face_list[i][0] for i in sub]

    # foto representativa: la más NÍTIDA Y CERCANA del sub-clúster.
    # Se pondera sharpness por √(área de la cara): una cara lejana enfocada
    # tiene menos píxeles reales que una cercana algo menos nítida.
    best = None
    best_score = -1.0
    best_sharp = 0.0
    for idx in item_idxs:
        it = battery[idx]
        for f in it["faces"]:
            fw = f.bbox[2] - f.bbox[0]
            fh = f.bbox[3] - f.bbox[1]
            sh = face_sharpness(it["img"], f)
            score = sh * (float(fw * fh) ** 0.5)
            if score > best_score:
                best_score = score
                best_sharp = sh
                best = (idx, f)
    rep_item = battery[best[0]]
    rep_face = best[1]
    rep_stem = rep_item["file"].rsplit(".", 1)[0]
    query_pose = pose_label(rep_face, cfg.yaw_frontal, cfg.yaw_45, cfg.yaw_90, cfg.pitch_frontal)

    # crop de torso compañero (mismo stem en <cam>_cuerpo/)
    torso_path = None
    if torso_map:
        torso_path = torso_map.get(rep_stem)

    # crop de busto compañero (mismo stem en <cam>_busto/) para la foto final de display
    busto_path = None
    if busto_map:
        busto_path = busto_map.get(rep_stem)

    # C (idempotencia): si este MISMO rostro (mismo embedding representativo) ya
    # se procesó en esta sesión, el crop es un duplicado re-leído/re-escrito. Se
    # consumen sus ficheros y se salta: antes producía una 2ª foto del mismo crop
    # y un match con score 1.0 (autocoincidencia tras autoenriquecer la galería).
    rep_hash = embedding_hash(embs[0]) if embs else None
    if rep_hash is not None and rep_hash in _PROCESSED_FACES:
        for _idx in item_idxs:
            _p = battery[_idx]["path"]
            if os.path.exists(_p):
                os.remove(_p)
        if torso_path and os.path.exists(torso_path):
            os.remove(torso_path)
        if busto_path and os.path.exists(busto_path):
            os.remove(busto_path)
        log(f"[skip] rostro ya procesado en esta sesión: {rep_stem}")
        return
    if rep_hash is not None:
        _PROCESSED_FACES.add(rep_hash)

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
    if cfg.cascade_enabled:
        from motor.core.router import Situation
        face_scores = _face_scores(embs, store, cfg, query_pose)
        ranked = sorted(face_scores.items(), key=lambda kv: kv[1], reverse=True)
        s1 = ranked[0][1] if ranked else 0.0
        s2 = ranked[1][1] if len(ranked) > 1 else 0.0
        from motor.core.matching import face_confidence, select_candidates
        face_layer = LayerScore(score=s1, confidence=face_confidence(s1, s2, best_sharp, cfg))
        from motor.core.fusion import CascadeContext, run_cascade
        ctx = _CascadeCtx(ruta, local_id, camara_id, cfg, store, face_scores,
                          query_pose, rep_item["path"], torso_path, rep_item["img"], rep_face,
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
        from motor.core.matching import face_confidence, select_candidates
        face_layer = LayerScore(score=s1, confidence=face_confidence(s1, s2, best_sharp, cfg))
        result.layer_scores = {"cara": face_layer}
        result.candidates = select_candidates(face_scores, cfg)

    if result.verdict in ("new", "uncertain") or result.person is None:
        # "new" y "uncertain" crean una persona NUEVA (duplicada): nunca se asigna
        # la foto a un candidato dudoso. "uncertain" además va a revisión manual.
        person = random_code()
    else:
        person = result.person

    # nombre de salida: stem representativo (+ "----" entrada/salida si hay >=2 fotos distintas)
    stems = [battery[idx]["file"].rsplit(".", 1)[0] for idx in item_idxs]
    stems_sorted = sorted(stems, key=lambda s: parse_timestamp(s + ".jpg") or 0)
    if len(stems_sorted) >= 2 and stems_sorted[0] != stems_sorted[-1]:
        nombre = f"{stems_sorted[0]}----{stems_sorted[-1]}"
    else:
        nombre = stems_sorted[0] if stems_sorted else battery[item_idxs[0]]["file"].rsplit(".", 1)[0]

    foto_id = random_code()
    out_dir = os.path.join(ruta, "motor/caras", local_id, camara_id, person)
    os.makedirs(out_dir, exist_ok=True)
    out_name = f"{nombre}_{foto_id}.jpg"
    out_path = os.path.join(out_dir, out_name)

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

    if os.path.exists(rep_item["path"]):
        os.remove(rep_item["path"])

    # refinar el diccionario (F1.2: admisión por cara — solo encodings que
    # individualmente confirman contra la persona asignada). P2: se etiquetan
    # con la proveniencia `foto_id` de la foto representativa de este sub-clúster.
    if result.verdict == "match":
        _store_add(store, person, item_idxs, battery, cfg, foto_id=foto_id)
    else:
        # "new" y "uncertain" (ENDURECIDO 2026-09-01): persona nueva/duplicada. El
        # sub-clúster es internamente coherente (split_coherent_clusters) -> se
        # construye su galería desde cero (new_person=True), sin contaminar a nadie.
        _store_add(store, person, item_idxs, battery, cfg, new_person=True, foto_id=foto_id)

    # F1/F3: la capa torso necesita galería de apariencia por persona.
    if cfg.torso_enabled and person:
        from motor.core.appearance import torso_descriptor
        desc = None
        if torso_path and os.path.exists(torso_path):
            img = cv2.imread(torso_path)
            if img is not None:
                h, w = img.shape[:2]
                desc = torso_descriptor(img, (0, 0, w, h))
        if desc is None:
            tb = torso_bbox_local(rep_face, rep_item["img"], cfg)
            if tb is not None:
                desc = torso_descriptor(rep_item["img"], tb)
        if desc is not None and desc.size > 0:
            store.add_appearance(person, desc, ts=rep_item["ts"] or time.time(),
                                 src=out_name)

    # UNCERTAIN: copia a cola de revisión manual (nunca duplicado en silencio)
    if result.verdict == "uncertain":
        _copy_to_revision(ruta, local_id, camara_id, out_dir, out_name, cfg)

    # feedback: registrar la decisión con features por capa
    if feedback is not None and cfg.feedback_enabled:
        from motor.core.feedback import embedding_hash
        feedback.log_decision({
            "local": local_id, "cam": camara_id,
            "verdict": result.verdict, "person": person,
            "top1": result.candidates[0] if result.candidates else None,
            "top2": result.candidates[1] if len(result.candidates) > 1 else None,
            "best": result.best_score, "second": result.second_score,
            "layers": result.layer_scores,
            "query_hash": embedding_hash(embs[0]),
            "stem": rep_stem,
            "pose": query_pose,
            "yaw": float(rep_face.yaw),
            "pitch": float(rep_face.pitch),
            "sharpness": best_sharp,
            "has_face": True,
        })

    # Persist an immutable, access-controlled audit sidecar. Attributes remain
    # potentially sensitive; PHP links it to the
    # eventual fotos.id using this classifier-generated correlation id.
    # Classification phase is derived by PHP from durable BD move events; no
    # mutable marker or journal participates in authority decisions.
    # Report the per-candidate attributes layer even when the cascade early-exits.
    if cfg.attributes_enabled and result.candidates:
        if ctx is not None:
            result.layer_scores["attributes"] = ctx.attributes_score(result.candidates[0])
        else:
            from motor.core.attributes import attributes_layer_score
            values = (store.person_attributes(result.candidates[0]) or {}).get("values", [])
            candidates = [attributes_layer_score(query_attributes, value) for value in values]
            candidates = [score for score in candidates if score.available]
            result.layer_scores["attributes"] = max(candidates, key=lambda score: score.score) if candidates else LayerScore(available=False)
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
    write_audit_queue(ruta, local_id, camara_id, foto_id, build_audit_record(
        foto_id, local_id, camara_id, result.verdict, person,
        layer_scores_json(result.layer_scores), attributes=query_attributes))

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


def _store_add(store: FaceStore, person: str, item_idxs, battery, cfg: Config,
               new_person: bool = False, foto_id: str | None = None) -> None:
    """Añade encodings a la galería de `person` con CONTROL DE ADMISIÓN (F1.2).

    - new_person=True (verdict "new"): el sub-clúster ya es internamente
      coherente (split_coherent_clusters) -> se añaden todas sus caras.
    - new_person=False (match/uncertain): cada cara se admite SOLO si su mejor
      similitud individual contra la persona asignada >= cfg.admission_cosine
      (pose-consciente si cfg.zones_enabled). Las caras que no confirmen NO
      entran en la galería: evita que una cara ajena agrupada por transitividad
      contamine la identidad y provoque falsos match posteriores (agregación max).

    P2 (proveniencia): todos los encodings de este sub-clúster se etiquetan con
    `foto_id` (el identificador_unico de la foto representativa) para que luego
    "mover foto"/"separar" pueda quitarlos de forma EXACTA (move_by_source).
    """
    from motor.core.quality import face_sharpness as _fs, pose_label as _pl
    from motor.core.matching import best_cosine, scores_per_person_pose_aware

    gal_encs = store.person_encodings(person)
    encs, quals, poses = [], [], []
    for idx in item_idxs:
        for f in battery[idx]["faces"]:
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
                encs.append(f.embedding)
                quals.append(_fs(battery[idx]["img"], f))
                poses.append(_pl(f, cfg.yaw_frontal, cfg.yaw_45, cfg.yaw_90, cfg.pitch_frontal))
    if encs:
        store.add(person, encs, quals, poses, sources=[foto_id] * len(encs))


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
