"""Super-resolución de caras — motor/core/superres.py

Real-ESRGAN **standalone** (solo torch, sin basicsr/realesrgan, que arrastraban
numpy 2 / opencv no-headless y rompían insightface/onnxruntime). Dos modelos
oficiales, seleccionables por `Config.sr_model`:

- "compact" (por defecto): `realesr-general-x4v3` (SRVGGNetCompact, 32 convs).
  ~2-5 s/cara en CPU. Calidad muy buena y viable con N daemons de cámara.
- "x4plus": `RealESRGAN_x4plus` (RRDBNet, 23 bloques). Mejor calidad pero
  ~30-45 s/cara en CPU (solo para cargas bajas).

Los pesos se descargan automáticamente la 1ª vez a `motor/models/` (fuera de
git: git = código, no datos). `enhance(img, cfg)` devuelve SIEMPRE BGR uint8:

- Crop pequeño (lado mayor < cfg.sr_min_side): SR x4 nativo si hay modelo.
- Sin modelo / falla / deshabilitado: la imagen se deja intacta (sin reescalar).
- YA NO se fuerza el top-up LANCZOS4 a cfg.sr_target_side (512): ese reescalado
  artificial pixelaba las caras lejanas (~46 px -> 512 px, ~11x). La salida
  queda al tamaño natural del SR x4.

La restauración facial con prior generativo está en `restore_face()` (usa
`motor/core/gfpgan.py`): SR x4 + GFPGAN para producir caras NATURALES de 512 px
desde recortes pequeños, sin pixelado.

Además `enhance_embedding(img, face, cfg)` aplica SR-before-embedding: para
caras pequeñas (< cfg.sr_embed_min_face) recalcula el embedding ArcFace sobre
el recorte super-resuelto, mejorando el matching (no solo el aspecto).

Singleton lazy con lock (patrón motor/core/model.py). Importable sin torch
(SR se degrada sin romper nada).

Uso:
    from motor.core.config import Config
    from motor.core.superres import enhance
    out = enhance(img_bgr, Config())
"""
from __future__ import annotations

import os
import shutil
import threading
import urllib.request

import cv2
import numpy as np

# Pesos oficiales (públicos, licencia BSD-3-Clause de Real-ESRGAN)
MODELS = {
    "compact": {
        "url": "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesr-general-x4v3.pth",
        "file": "realesr-general-x4v3.pth",
    },
    "x4plus": {
        "url": "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth",
        "file": "RealESRGAN_x4plus.pth",
    },
}

_lock = threading.Lock()
_models: dict[str, object] = {}    # nombre -> torch nn.Module cargado
_sr_available: bool | None = None  # None = aún no comprobado

# torch se importa de forma segura: si falta, el módulo sigue siendo importable
# y `enhance()` deja la imagen sin tocar (nunca rompe).
try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    _TORCH_OK = True
except Exception:  # noqa: BLE001
    torch = None
    nn = None
    F = None
    _TORCH_OK = False


if _TORCH_OK:

    # ------------------------------------------------------- RRDBNet (x4plus)

    class _ResidualDenseBlock5C(nn.Module):
        """Bloque denso residual de 5 convs (RRDB) — claves `rdb1/rdb2/rdb3`."""

        def __init__(self, num_feat: int = 64, num_grow_ch: int = 32):
            super().__init__()
            self.conv1 = nn.Conv2d(num_feat, num_grow_ch, 3, 1, 1)
            self.conv2 = nn.Conv2d(num_feat + num_grow_ch, num_grow_ch, 3, 1, 1)
            self.conv3 = nn.Conv2d(num_feat + 2 * num_grow_ch, num_grow_ch, 3, 1, 1)
            self.conv4 = nn.Conv2d(num_feat + 3 * num_grow_ch, num_grow_ch, 3, 1, 1)
            self.conv5 = nn.Conv2d(num_feat + 4 * num_grow_ch, num_feat, 3, 1, 1)
            self.lrelu = nn.LeakyReLU(negative_slope=0.2, inplace=True)

        def forward(self, x):
            x1 = self.lrelu(self.conv1(x))
            x2 = self.lrelu(self.conv2(torch.cat((x, x1), 1)))
            x3 = self.lrelu(self.conv3(torch.cat((x, x1, x2), 1)))
            x4 = self.lrelu(self.conv4(torch.cat((x, x1, x2, x3), 1)))
            x5 = self.conv5(torch.cat((x, x1, x2, x3, x4), 1))
            return x5 * 0.2 + x

    class _RRDB(nn.Module):
        """Residual in Residual Dense Block — claves `body.N`."""

        def __init__(self, num_feat: int = 64, num_grow_ch: int = 32):
            super().__init__()
            self.rdb1 = _ResidualDenseBlock5C(num_feat, num_grow_ch)
            self.rdb2 = _ResidualDenseBlock5C(num_feat, num_grow_ch)
            self.rdb3 = _ResidualDenseBlock5C(num_feat, num_grow_ch)

        def forward(self, x):
            out = self.rdb1(x)
            out = self.rdb2(out)
            out = self.rdb3(out)
            return out * 0.2 + x

    class _RRDBNet(nn.Module):
        """Red principal de Real-ESRGAN x4plus (num_block=23, num_grow_ch=32)."""

        def __init__(self, num_in_ch: int = 3, num_out_ch: int = 3, num_feat: int = 64,
                     num_block: int = 23, num_grow_ch: int = 32, scale: int = 4):
            super().__init__()
            self.scale = scale
            self.conv_first = nn.Conv2d(num_in_ch, num_feat, 3, 1, 1)
            self.body = nn.Sequential(*[_RRDB(num_feat, num_grow_ch) for _ in range(num_block)])
            self.conv_body = nn.Conv2d(num_feat, num_feat, 3, 1, 1)
            self.conv_up1 = nn.Conv2d(num_feat, num_feat, 3, 1, 1)
            self.conv_up2 = nn.Conv2d(num_feat, num_feat, 3, 1, 1)
            self.conv_hr = nn.Conv2d(num_feat, num_feat, 3, 1, 1)
            self.conv_last = nn.Conv2d(num_feat, num_out_ch, 3, 1, 1)
            self.lrelu = nn.LeakyReLU(negative_slope=0.2, inplace=True)

        def forward(self, x):
            feat = self.conv_first(x)
            body_feat = self.conv_body(self.body(feat))
            feat = feat + body_feat
            feat = self.lrelu(self.conv_up1(F.interpolate(feat, scale_factor=2, mode="nearest")))
            feat = self.lrelu(self.conv_up2(F.interpolate(feat, scale_factor=2, mode="nearest")))
            out = self.conv_last(self.lrelu(self.conv_hr(feat)))
            return out

    # ------------------------------------------------ SRVGGNetCompact (compact)

    class _SRVGGNetCompact(nn.Module):
        """Red compacta de realesr-general-x4v3 (convs en índices pares, PReLU en
        impares, conv final 64->48, PixelShuffle x4 y residuo nearest)."""

        def __init__(self, num_in_ch: int = 3, num_out_ch: int = 3, num_feat: int = 64,
                     num_conv: int = 32, upscale: int = 4):
            super().__init__()
            self.upscale = upscale
            self.body = nn.ModuleList()
            self.body.append(nn.Conv2d(num_in_ch, num_feat, 3, 1, 1))
            self.body.append(nn.PReLU(num_parameters=num_feat))
            for _ in range(num_conv):
                self.body.append(nn.Conv2d(num_feat, num_feat, 3, 1, 1))
                self.body.append(nn.PReLU(num_parameters=num_feat))
            self.body.append(nn.Conv2d(num_feat, num_out_ch * upscale * upscale, 3, 1, 1))
            self.upsampler = nn.PixelShuffle(upscale)

        def forward(self, x):
            out = x
            for layer in self.body:
                out = layer(out)
            out = self.upsampler(out)
            # residuo: la red aprende la diferencia sobre el upscale nearest
            base = F.interpolate(x, scale_factor=self.upscale, mode="nearest")
            return out + base

else:

    class _RRDBNet:  # stub: solo para que get_model() falle limpiamente
        def __init__(self, *args, **kwargs):
            raise RuntimeError("torch no disponible para super-resolución")

    class _SRVGGNetCompact:  # stub
        def __init__(self, *args, **kwargs):
            raise RuntimeError("torch no disponible para super-resolución")


# ------------------------------------------------------------------ infraestructura

def _models_dir() -> str:
    # raíz del proyecto = abuelo de motor/core/ -> motor/models/
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "motor", "models"))


def _model_path(name: str) -> str:
    return os.path.join(_models_dir(), MODELS[name]["file"])


def _download_model(name: str) -> str | None:
    """Descarga los pesos oficiales la 1ª vez. Devuelve la ruta o None."""
    path = _model_path(name)
    if os.path.exists(path):
        return path
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".part"
    url = MODELS[name]["url"]
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "reconocimientoFacial-superres"})
        with urllib.request.urlopen(req, timeout=300) as resp, open(tmp, "wb") as fh:
            shutil.copyfileobj(resp, fh, 1024 * 1024)
        os.replace(tmp, path)
        print(f"[superres] pesos descargados: {path}", flush=True)
        return path
    except Exception as e:  # noqa: BLE001
        print(f"[superres] descarga de pesos fallida ({name}): {e}", flush=True)
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except OSError:
            pass
        return None


def _build_model(name: str):
    """Construye la arquitectura correspondiente (sin pesos)."""
    if name == "x4plus":
        return _RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64, num_block=23, num_grow_ch=32, scale=4)
    return _SRVGGNetCompact(num_in_ch=3, num_out_ch=3, num_feat=64, num_conv=32, upscale=4)


def get_model(name: str = "compact"):
    """Singleton lazy del modelo pedido (None si no está disponible: torch o pesos)."""
    global _sr_available
    if _models.get(name) is not None:
        return _models[name]
    with _lock:
        if _models.get(name) is not None:
            return _models[name]
        if name not in MODELS:
            _sr_available = False
            print(f"[superres] modelo desconocido '{name}', fallback activo", flush=True)
            return None
        if not _TORCH_OK:
            _sr_available = False
            print("[superres] torch no disponible, fallback activo", flush=True)
            return None
        path = _model_path(name)
        if not os.path.exists(path):
            path = _download_model(name)
        if not path:
            _sr_available = False
            return None
        try:
            model = _build_model(name)
            ck = torch.load(path, map_location="cpu")
            state = ck["params_ema"] if isinstance(ck, dict) and "params_ema" in ck else ck
            state = state["params"] if isinstance(state, dict) and "params" in state else state
            model.load_state_dict(state)
            model.eval()
            _models[name] = model
            _sr_available = True
            print(f"[superres] modelo '{name}' cargado (CPU)", flush=True)
            return model
        except Exception as e:  # noqa: BLE001
            _sr_available = False
            print(f"[superres] carga de modelo '{name}' fallida, fallback activo: {e}", flush=True)
            return None


# ---------------------------------------------------------------------- inferencia

def _sr_infer(model, img: np.ndarray) -> np.ndarray:
    """Forward x4 sobre la imagen BGR. Parea al múltiplo de 4 para evitar artefactos de borde."""
    h, w = img.shape[:2]
    pad_h = (-h) % 4
    pad_w = (-w) % 4
    if pad_h or pad_w:
        img = cv2.copyMakeBorder(img, 0, pad_h, 0, pad_w, cv2.BORDER_REFLECT)
    t = torch.from_numpy(np.ascontiguousarray(img.transpose(2, 0, 1)[None])).float().div_(255.0)
    with torch.no_grad():
        out = model(t)
    out = out.clamp_(0.0, 1.0).mul_(255.0).round().byte()
    res = out[0].permute(1, 2, 0).cpu().numpy()
    return np.ascontiguousarray(res[: h * 4, : w * 4])


def _fallback_upscale(img: np.ndarray, target_side: int) -> np.ndarray:
    """LANCZOS4 + unsharp mask hasta alcanzar el lado mínimo (sin nueva dependencia).

    NO se usa en el pipeline actual: reescalar caras pequeñas hasta 512 px era
    la causa del pixelado. Se conserva por si un caller externo la importa.
    """
    h, w = img.shape[:2]
    if max(h, w) >= target_side:
        return img
    scale = target_side / max(h, w)
    nw, nh = max(1, int(round(w * scale))), max(1, int(round(h * scale)))
    up = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_LANCZOS4)
    blur = cv2.GaussianBlur(up, (0, 0), 3.0)
    return cv2.addWeighted(up, 1.5, blur, -0.5, 0)


# ------------------------------------------------------------------- API pública

def frame_face(img: np.ndarray, bbox, face_fill: float, min_pad: int) -> np.ndarray:
    """Reencuadra alrededor de la cara para que ocupe ~face_fill del encuadre.

    bbox = (x1, y1, x2, y2) en coordenadas de `img`. Recorte centrado en la cara
    con ventana (fw/face_fill, fh/face_fill), piso de min_pad px alrededor, y
    clamp a los bordes de la imagen. La cara ya queda centrada por el recorte
    simétrico, así que el zoom centrado es seguro (auto-zoom de captura).
    """
    h, w = img.shape[:2]
    x1, y1, x2, y2 = (int(round(v)) for v in bbox)
    fw, fh = max(1, x2 - x1), max(1, y2 - y1)
    crop_w = min(max(int(round(fw / face_fill)), fw + 2 * min_pad), w)
    crop_h = min(max(int(round(fh / face_fill)), fh + 2 * min_pad), h)
    if crop_w == w and crop_h == h:
        return img
    cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
    x1c = max(0, min(cx - crop_w // 2, w - crop_w))
    y1c = max(0, min(cy - crop_h // 2, h - crop_h))
    return img[y1c:y1c + crop_h, x1c:x1c + crop_w]


def zoom_photo(img: np.ndarray, bbox, cfg) -> np.ndarray:
    """Auto-zoom hacia la cara + SR + restauración facial (GFPGAN).

    1. `frame_face`: reencuadre para que la cara ocupe ~cfg.face_fill del encuadre.
    2. `restore_face`: SR x4 (si la cara es pequeña) + GFPGAN (prior facial).
       Una cara lejana de ~46 px acaba en una foto de 512 px NATURAL (reconstruida
       por GFPGAN), no en un reescalado LANCZOS4 pixelado.
    Devuelve SIEMPRE BGR uint8.
    """
    z = frame_face(img, bbox, cfg.face_fill, cfg.face_min_pad)
    return restore_face(z, cfg)


def enhance(img: np.ndarray, cfg) -> np.ndarray:
    """Mejora una imagen de cara (SOLO SR genérico). Devuelve SIEMPRE BGR uint8.

    - Crop pequeño (lado mayor < cfg.sr_min_side): SR x4 nativo si hay modelo
      (cfg.sr_model: "compact" | "x4plus"); si no, se deja intacto.
    - YA NO se fuerza el top-up LANCZOS4 hasta cfg.sr_target_side: ese reescalado
      artificial (46 px -> 512 px, ~11x) era la causa del pixelado/posterizado en
      caras pequeñas. La salida queda al tamaño natural del SR (x4) y la
      restauración facial (GFPGAN) se aplica aparte en `restore_face()`.
    """
    h, w = img.shape[:2]
    if h < 1 or w < 1:
        return img
    if cfg.sr_enabled and max(h, w) < cfg.sr_min_side:
        model = get_model(cfg.sr_model)
        if model is not None:
            try:
                img = _sr_infer(model, img)
            except Exception as e:  # noqa: BLE001
                print(f"[superres] SR falló, fallback activo: {e}", flush=True)
    return img


def restore_face(img: np.ndarray, cfg) -> np.ndarray:
    """Restauración facial completa para la foto final de la persona.

    1. Si la cara es pequeña (< cfg.sr_min_side): SR genérico x4 (Real-ESRGAN).
    2. GFPGAN (prior facial): produce una cara natural de 512x512 sin pixelado.

    Devuelve SIEMPRE BGR uint8. Si GFPGAN no está disponible, devuelve el
    resultado del SR genérico (nunca None, nunca rompe el pipeline).
    """
    img = enhance(img, cfg)
    if cfg.sr_face_enabled:
        from . import gfpgan  # import tardío: evita acoplar torch/gfpgan
        out = gfpgan.restore(img, weight=cfg.sr_face_weight)
        if out is not None:
            return out
    return img


def enhance_embedding(img: np.ndarray, face, cfg) -> np.ndarray:
    """SR-before-embedding: embedding ArcFace recalculado sobre la cara SR.

    Para caras pequeñas (lado mayor < cfg.sr_embed_min_face) el embedding nativo
    se calcula sobre muy pocos píxeles y es poco fiable para el matching. Aquí:
      1. recorta la cara con margen del frame original,
      2. SR x4 + top-up (`enhance`) sobre ese recorte,
      3. re-embebe con el modelo de RECONOCIMIENTO (ArcFace) usando los 5
         keypoints originales escalados al recorte mejorado. NO se re-detecta
         con RetinaFace: medido, Real-ESRGAN produce caras tan "plastificadas"
         que el detector pierde la cara en crops pequeños.

    Degradación segura: sin kps, sin modelo o fallo -> embedding original
    (nunca None, nunca rompe el pipeline).
    """
    from .model import reembed_face  # import tardío: evita acoplar insightface

    fw = face.bbox[2] - face.bbox[0]
    fh = face.bbox[3] - face.bbox[1]
    if max(fw, fh) >= cfg.sr_embed_min_face:
        return face.embedding
    kps = getattr(face, "kps", None)
    if kps is None or len(kps) < 5:
        return face.embedding
    h, w = img.shape[:2]
    x1, y1, x2, y2 = face.bbox
    pad = int(0.35 * max(fw, fh)) + 10
    x1, y1 = max(0, x1 - pad), max(0, y1 - pad)
    x2, y2 = min(w, x2 + pad), min(h, y2 + pad)
    crop = img[y1:y2, x1:x2]
    if crop.size == 0:
        return face.embedding
    up = enhance(crop, cfg)
    scale_x = up.shape[1] / max(1, crop.shape[1])
    scale_y = up.shape[0] / max(1, crop.shape[0])
    kps_up = (np.asarray(kps, dtype=np.float32) - np.array([x1, y1], dtype=np.float32))
    kps_up = kps_up * np.array([scale_x, scale_y], dtype=np.float32)
    emb = reembed_face(up, kps_up)
    if emb is None:
        return face.embedding
    return emb
