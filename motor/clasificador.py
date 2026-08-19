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
  - cfg.zones_enabled (F2): en veredicto "uncertain" ENRIQUECE la galería con
    la nueva pose (fix del bucle de fragmentación) y copia a revisión manual.
  - En zona gris tras la cascada: UNCERTAIN -> motor/revision/, NUNCA se crea
    persona duplicada en silencio.

Uso (daemon, como antes):
    motor/venv/bin/python motor/clasificador.py <local> <cam>
Uso (una pasada, para tests/calibración):
    motor/venv/bin/python motor/clasificador.py <local> <cam> --once
"""
from __future__ import annotations

import argparse
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
from motor.core.superres import enhance_embedding, zoom_photo      # noqa: E402

ALPHABET = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
IMG_EXTS = (".jpg", ".jpeg", ".png")


def log(*args):
    print(*args, flush=True)


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


class _CascadeCtx:
    """Proveedores de capas superiores (L1b/L1c/L2/L3) para la fusión."""

    def __init__(self, ruta, local_id, camara_id, cfg, store, face_scores,
                 query_pose, rep_face_crop, rep_torso_path, rep_img, rep_face):
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
        if self.rep_face is not None and getattr(self.rep_face, "landmarks", None) is not None:
            cand_face = self._candidate_face(cod)
            if cand_face is not None and getattr(cand_face, "landmarks", None) is not None:
                a = silhouette_descriptor(self.rep_face)
                b = silhouette_descriptor(cand_face)
                sil = silhouette_sim(a, b) if a.size and b.size else 0.5
        c = float(np.clip(0.6 * pconf + 0.4 * sil, 0.0, 1.0))
        return LayerScore(score=float(s_face), confidence=c, available=True)

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
                    store: FaceStore, feedback=None, torso_map: dict[str, str] | None = None):
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
                                cfg, store, feedback, torso_map)


def _process_subcluster(sub, face_list, battery, ruta: str, local_id: str,
                        camara_id: str, cfg: Config, store: FaceStore,
                        feedback=None, torso_map: dict[str, str] | None = None) -> None:
    """Clasifica un sub-clúster coherente de caras y actualiza galería/álbum."""
    item_idxs = sorted({face_list[i][1] for i in sub})
    embs = [face_list[i][0] for i in sub]

    # foto representativa = la más enfocada del sub-clúster
    best = None
    best_sharp = -1.0
    for idx in item_idxs:
        it = battery[idx]
        for f in it["faces"]:
            sh = face_sharpness(it["img"], f)
            if sh > best_sharp:
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

    # F2 fix: en veredicto "uncertain" también se enriquece la galería
    enrich_on_uncertain = cfg.zones_enabled

    if cfg.cascade_enabled:
        face_scores = _face_scores(embs, store, cfg, query_pose)
        ranked = sorted(face_scores.items(), key=lambda kv: kv[1], reverse=True)
        s1 = ranked[0][1] if ranked else 0.0
        s2 = ranked[1][1] if len(ranked) > 1 else 0.0
        from motor.core.matching import face_confidence, select_candidates
        face_layer = LayerScore(score=s1, confidence=face_confidence(s1, s2, best_sharp, cfg))
        from motor.core.fusion import CascadeContext, run_cascade
        ctx = _CascadeCtx(ruta, local_id, camara_id, cfg, store, face_scores,
                          query_pose, rep_item["path"], torso_path, rep_item["img"], rep_face)
        cc = CascadeContext(torso=ctx.torso_score, zonas=ctx.zonas_score,
                            vlm=ctx.vlm_score, openai=ctx.openai_score)
        result = run_cascade(face_scores, cc, cfg, face_layer)
    else:
        result = match_group(embs, store, cfg)
        # pose-consciente (F2) sin cascada: se activa con zones_enabled
        if cfg.zones_enabled:
            result = match_group(embs, store, cfg, sharpness=best_sharp, pose=query_pose)

    if result.verdict == "new" or result.person is None:
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
    # Auto-zoom hacia la cara + super-resolución (solo visual; embeddings intactos)
    final_img = zoom_photo(rep_item["img"], rep_face.bbox, cfg)
    cv2.imwrite(os.path.join(out_dir, out_name), final_img, [cv2.IMWRITE_JPEG_QUALITY, 95])
    if os.path.exists(rep_item["path"]):
        os.remove(rep_item["path"])

    # refinar el diccionario (F1.2: admisión por cara — solo encodings que
    # individualmente confirman contra la persona asignada)
    if result.verdict == "match":
        _store_add(store, person, item_idxs, battery, cfg)
    elif result.verdict == "new":
        # F1.3: el sub-clúster es internamente coherente (split_coherent_clusters):
        # identidad nueva creada solo con caras de la misma persona real.
        _store_add(store, person, item_idxs, battery, cfg, new_person=True)
    elif result.verdict == "uncertain" and enrich_on_uncertain and person != "":
        # F2 fix: el veredicto "uncertain" asigna persona pero NO enriquecía
        # la galería -> bucle de fragmentación (perfil↔frontal). Ahora sí, con
        # admisión por cara para no contaminar.
        _store_add(store, person, item_idxs, battery, cfg)

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
        })

    # eliminar el resto de fotos del sub-clúster (ya procesadas)
    for idx in item_idxs:
        p = battery[idx]["path"]
        if os.path.exists(p):
            os.remove(p)

    # consumir el crop de torso compañero (ya no hace falta)
    if torso_path and os.path.exists(torso_path):
        os.remove(torso_path)

    log(f"[{result.verdict}] {len(item_idxs)} foto(s) -> {person} (best={result.best_score:.3f})")


def torso_bbox_local(face, img, cfg):
    from motor.procesa_video import torso_bbox
    if img is None:
        return None
    h, w = img.shape[:2]
    return torso_bbox(face, w, h, cfg)


def _store_add(store: FaceStore, person: str, item_idxs, battery, cfg: Config,
               new_person: bool = False) -> None:
    """Añade encodings a la galería de `person` con CONTROL DE ADMISIÓN (F1.2).

    - new_person=True (verdict "new"): el sub-clúster ya es internamente
      coherente (split_coherent_clusters) -> se añaden todas sus caras.
    - new_person=False (match/uncertain): cada cara se admite SOLO si su mejor
      similitud individual contra la persona asignada >= cfg.admission_cosine
      (pose-consciente si cfg.zones_enabled). Las caras que no confirmen NO
      entran en la galería: evita que una cara ajena agrupada por transitividad
      contamine la identidad y provoque falsos match posteriores (agregación max).
    """
    from motor.core.quality import face_sharpness as _fs, pose_label as _pl
    from motor.core.matching import best_cosine, scores_per_person_pose_aware

    gal_encs = store.person_encodings(person)
    encs, quals, poses = [], [], []
    for idx in item_idxs:
        for f in battery[idx]["faces"]:
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
        store.add(person, encs, quals, poses)


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
        result = run_cascade(face_scores, ctx, cfg, face_layer)

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
        focused = [fc for fc in faces if face_sharpness(img, fc) >= cfg.min_sharpness]
        if not focused:
            shutil.move(p, os.path.join(nopasafiltros, f))
            continue
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
        process_battery(bat, ruta, local_id, camara_id, cfg, store, feedback, torso_map)
        n += 1
    return n


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

    log(f"clasificador {args.local_id}/{args.camara_id} — face_enc_v2 con {len(store.persons())} personas"
        f" | cascada={cfg.cascade_enabled} torso={cfg.torso_enabled} zonas={cfg.zones_enabled}"
        f" vlm={cfg.vlm_enabled} openai={cfg.openai_enabled}")
    while True:
        try:
            n = process_once(args.ruta, args.local_id, args.camara_id, cfg, store, feedback)
            nb = process_body_once(args.ruta, args.local_id, args.camara_id, cfg, store)
            if n or nb:
                log(f"procesadas {n} batería(s) de caras, {nb} de cuerpos")
            if args.once:
                return 0
            time.sleep(1)
        except KeyboardInterrupt:
            return 0


if __name__ == "__main__":
    sys.exit(main())
