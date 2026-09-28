#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bandeja de REVISIÓN manual de caras — motor/revision.py

Tras el cambio "revision-only" (clasificador.py), las caras que el clasificador
no puede resolver con confianza se copian a `motor/revision/<local>/<cam>/` en
lugar de crear una identidad a ciegas. Este CLI es el brazo del panel para
resolverlas:

  - listar    : lista los pendientes (mtime desc) de un local.
  - aprobar   : crea una persona NUEVA con esa cara (galería + álbum).
  - asignar   : añade esa cara a una persona EXISTENTE (galería + álbum).
  - descartar : borra el pendiente sin tocar la galería.

La ingesta a BD NO se hace aquí: al escribir la imagen en
`motor/caras/<local>/<cam>/<cod>/`, el daemon `clasificadorV2.php`
(servicio rf-clasificador) crea persona/estancia/foto y publica la imagen en
`admin/caras_procesadas/`. Igual que hace el propio clasificador.

Uso:
    motor/venv/bin/python motor/revision.py listar <local> [--ruta .] [--json]
    motor/venv/bin/python motor/revision.py aprobar <local> <cam> <file> [--nombre N] [--ruta .] [--json]
    motor/venv/bin/python motor/revision.py asignar <local> <cam> <file> <cod_destino> [--ruta .] [--json]
    motor/venv/bin/python motor/revision.py descartar <local> <cam> <file> [--ruta .]

Seguridad: `ruta_revision_segura` es una función PURA (solo stdlib) que valida
los componentes y confina cualquier operación a `motor/revision/...`. Las
importaciones pesadas (cv2/insightface/FaceStore) son perezosas para poder
testear la validación sin cargar modelos.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys

# Alfabeto del motor (motor/clasificador.py:ALPHABET). Se replica para NO
# importar el módulo clasificador (carga insightface/multiprocessing) cuando
# solo queremos generar códigos: los códigos son indistinguibles para el
# daemon PHP, que solo mira el nombre de la carpeta.
ALFABETO = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
IMG_EXTS = (".jpg", ".jpeg", ".png")
_COMPONENTE_RE = re.compile(r"^[A-Za-z0-9._-]+$")


def random_code(n: int = 25) -> str:
    """Código interno aleatorio con el alfabeto del motor (mismo formato)."""
    return "".join(random.choice(ALFABETO) for _ in range(n))


def componente_valido(valor: str) -> bool:
    """Componente de ruta seguro: no vacío, no `.`/`..`, solo [A-Za-z0-9._-]."""
    return bool(valor) and valor not in (".", "..") and _COMPONENTE_RE.fullmatch(valor) is not None


def es_imagen(nombre: str) -> bool:
    return os.path.splitext(nombre)[1].lower() in IMG_EXTS


def ruta_revision_segura(ruta: str, local: str, cam: str, file: str) -> str | None:
    """Valida componentes y devuelve la ruta absoluta del fichero de revisión.

    Función PURA (solo stdlib, sin modelos ni BD): testeable en aislamiento.
    Devuelve None si:
      - algún componente es vacío, `.`/`..` o contiene caracteres fuera de
        `^[A-Za-z0-9._-]+$` (p. ej. `/` -> traversal),
      - el fichero no tiene extensión de imagen,
      - la ruta resuelta no queda ESTRICTAMENTE dentro de
        `motor/revision/<local>/<cam>/` (defensa extra ante symlinks).
    """
    if not (componente_valido(local) and componente_valido(cam) and componente_valido(file)):
        return None
    if not es_imagen(file):
        return None
    raiz = os.path.realpath(os.path.join(ruta, "motor", "revision"))
    base = os.path.realpath(os.path.join(raiz, local, cam))
    destino = os.path.realpath(os.path.join(base, file))
    # Debe colgar EXACTAMENTE de base (sin subdirectorios) y de raiz.
    if os.path.dirname(destino) != base:
        return None
    if not (destino == base or destino.startswith(base + os.sep)):
        return None
    if not (destino == raiz or destino.startswith(raiz + os.sep)):
        return None
    return destino


def _error(msg: str, as_json: bool) -> int:
    if as_json:
        print(json.dumps({"ok": False, "error": msg}, ensure_ascii=False))
    else:
        print(f"error: {msg}", file=sys.stderr)
    return 1


# ---------------------------------------------------------------------------
# Subcomandos
# ---------------------------------------------------------------------------

def cmd_listar(args) -> int:
    """Lista `motor/revision/<local>/*/*` (solo imágenes), mtime desc."""
    if not componente_valido(args.local):
        return _error("local inválido", args.json)
    base = os.path.join(args.ruta, "motor", "revision", args.local)
    items: list[dict] = []
    if os.path.isdir(base):
        for cam in sorted(os.listdir(base)):
            cam_dir = os.path.join(base, cam)
            if not componente_valido(cam) or not os.path.isdir(cam_dir):
                continue
            for f in os.listdir(cam_dir):
                if not componente_valido(f) or not es_imagen(f):
                    continue
                p = os.path.join(cam_dir, f)
                if not os.path.isfile(p):
                    continue
                st = os.stat(p)
                items.append({
                    "cam": cam,
                    "file": f,
                    "rel": f"{args.local}/{cam}/{f}",
                    "mtime": int(st.st_mtime),
                    "size": int(st.st_size),
                })
    items.sort(key=lambda x: x["mtime"], reverse=True)
    print(json.dumps(items, ensure_ascii=False))
    return 0


def _resolver_y_cargar(args):
    """(ruta_fichero, img, cfg) o lanza ValueError con mensaje claro."""
    import cv2  # import perezoso: mantiene ligero el helper puro

    from motor.core.config import Config

    ruta_fichero = ruta_revision_segura(args.ruta, args.local, args.cam, args.file)
    if ruta_fichero is None:
        raise ValueError("ruta de revisión inválida o fuera de motor/revision")
    if not os.path.isfile(ruta_fichero):
        raise ValueError("la imagen de revisión ya no existe")
    cfg = Config.from_env(args.ruta)
    img = cv2.imread(ruta_fichero)
    if img is None:
        raise ValueError("no se pudo leer la imagen de revisión")
    return ruta_fichero, img, cfg


def _procesar(args, cod_destino: str | None) -> int:
    """Cuerpo común de aprobar/asignar: galería + publicación en el álbum."""
    import cv2

    from motor.core.model import analyze
    from motor.core.quality import face_sharpness, pose_label, pose_valida
    from motor.core.store import FaceStore
    from motor.core.threads import limit_threads
    from motor.core.zones import silhouette_descriptor

    try:
        ruta_fichero, img, cfg = _resolver_y_cargar(args)
    except ValueError as e:
        return _error(str(e), args.json)

    limit_threads()

    faces = analyze(img, det_size=(cfg.crop_det_size, cfg.crop_det_size),
                    min_score=cfg.min_det_score)
    if not faces:
        return _error("no se ha detectado ninguna cara en la imagen de revisión", args.json)
    face = max(faces, key=lambda f: f.det_score)

    # Embedding nativo + SR-before-embedding cuando procede (caras pequeñas).
    emb = face.embedding
    try:
        from motor.core.superres import enhance_embedding
        emb = enhance_embedding(img, face, cfg)
    except Exception as e:  # noqa: BLE001 — nunca romper la aprobación manual
        print(f"[revision] enhance_embedding falló, uso embedding nativo: {e}", file=sys.stderr)
        emb = face.embedding

    sharp = face_sharpness(img, face)
    pose = pose_label(face, cfg.yaw_frontal, cfg.yaw_45, cfg.yaw_90, cfg.pitch_frontal)
    if not pose_valida(face, cfg):
        # La pose no es fiable: se conserva la etiqueta (como el clasificador)
        # pero queda registrado para diagnóstico.
        print(f"[revision] pose no fiable ({face.pose}); se conserva igualmente", file=sys.stderr)
    sil = silhouette_descriptor(face)

    store = FaceStore(
        os.path.join(args.ruta, "motor/bbdd_reconocimiento", args.local, "face_enc_v2"),
        max_per_person=cfg.max_encodings_per_person,
    )

    if cod_destino is None:
        cod = random_code()
    else:
        cod = cod_destino
        if store.person(cod) is None:
            return _error(f"la persona destino '{cod}' no existe en la galería", args.json)

    store.add(cod, [emb], [sharp], [pose],
              sources=[f"revision:{args.file}"], sils=[sil])

    # Publicar en el álbum del local/cámara. El daemon PHP ingiere el JPEG y
    # crea persona/estancia/foto; el nombre termina en el foto_id para que
    # `fotos.identificador_unico` y la proveniencia queden coherentes.
    foto_id = random_code()
    stem = os.path.splitext(os.path.basename(ruta_fichero))[0]
    dest_dir = os.path.join(args.ruta, "motor", "caras", args.local, args.cam, cod)
    os.makedirs(dest_dir, exist_ok=True)
    dest_path = os.path.join(dest_dir, f"{stem}_{foto_id}.jpg")
    if not cv2.imwrite(dest_path, img, [cv2.IMWRITE_JPEG_QUALITY, 95]):
        return _error("no se pudo escribir la imagen en el álbum", args.json)

    try:
        os.remove(ruta_fichero)
    except OSError as e:
        print(f"[revision] no se pudo borrar el pendiente: {e}", file=sys.stderr)

    album = os.path.relpath(dest_dir, args.ruta).replace(os.sep, "/")
    print(json.dumps({"ok": True, "cod": cod, "album": album}, ensure_ascii=False))
    return 0


def cmd_aprobar(args) -> int:
    return _procesar(args, cod_destino=None)


def cmd_asignar(args) -> int:
    if not componente_valido(args.cod_destino):
        return _error("cod_destino inválido", args.json)
    return _procesar(args, cod_destino=args.cod_destino)


def cmd_descartar(args) -> int:
    ruta_fichero = ruta_revision_segura(args.ruta, args.local, args.cam, args.file)
    if ruta_fichero is None:
        return _error("ruta de revisión inválida o fuera de motor/revision", args.json)
    if not os.path.isfile(ruta_fichero):
        return _error("la imagen de revisión ya no existe", args.json)
    try:
        os.remove(ruta_fichero)
    except OSError as e:
        return _error(f"no se pudo borrar el pendiente: {e}", args.json)
    print(json.dumps({"ok": True, "descartado": args.file}, ensure_ascii=False))
    return 0


def _ruta_default() -> str:
    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _add_comunes(sp: argparse.ArgumentParser) -> None:
    sp.add_argument("--ruta", default=_ruta_default(),
                    help="raíz del proyecto (default: raíz del repo)")
    sp.add_argument("--json", action="store_true", help="salida JSON (máquina)")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Bandeja de revisión manual de caras")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_list = sub.add_parser("listar", help="lista pendientes del local")
    p_list.add_argument("local")
    _add_comunes(p_list)
    p_list.set_defaults(func=cmd_listar)

    p_apr = sub.add_parser("aprobar", help="aprueba como persona nueva")
    p_apr.add_argument("local")
    p_apr.add_argument("cam")
    p_apr.add_argument("file")
    p_apr.add_argument("--nombre", default=None, help="(informativo; el nombre lo fija el panel)")
    _add_comunes(p_apr)
    p_apr.set_defaults(func=cmd_aprobar)

    p_asg = sub.add_parser("asignar", help="asigna a una persona existente")
    p_asg.add_argument("local")
    p_asg.add_argument("cam")
    p_asg.add_argument("file")
    p_asg.add_argument("cod_destino")
    _add_comunes(p_asg)
    p_asg.set_defaults(func=cmd_asignar)

    p_des = sub.add_parser("descartar", help="borra el pendiente sin tocar la galería")
    p_des.add_argument("local")
    p_des.add_argument("cam")
    p_des.add_argument("file")
    _add_comunes(p_des)
    p_des.set_defaults(func=cmd_descartar)

    args = ap.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.path.insert(0, _ruta_default())
    sys.exit(main())
