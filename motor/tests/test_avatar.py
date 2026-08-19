"""Tests del avatar: máscara elíptica de cabeza y recorte PNG con alfa."""
import os

import cv2
import numpy as np

from motor.core.avatar import crop_head_png, generar_avatar, head_ellipse_mask


def _crop_sintetico(size=150):
    """Crop 150x150 con un 'rostro' claro en el centro (el resto oscuro)."""
    img = np.zeros((size, size, 3), dtype=np.uint8)
    cv2.circle(img, (size // 2, size // 2), size // 3, (200, 200, 200), -1)
    return img


def test_head_ellipse_mask_centro_opaco_bordes_transparentes():
    m = head_ellipse_mask(96)
    assert m.shape == (96, 96)
    assert m.dtype == np.float32
    # Centro de la elipse: alfa alto (opaco).
    assert m[48, 48] > 0.9
    # Esquinas: alfa bajo (transparente).
    assert m[0, 0] < 0.05 and m[95, 95] < 0.05
    # Rango válido.
    assert m.min() >= 0.0 and m.max() <= 1.0


def test_head_ellipse_mask_con_landmarks():
    # Landmarks simulando la cara en la mitad inferior (ojos/nariz/boca).
    lm = np.array([[70, 55], [80, 55], [75, 68], [68, 80], [82, 80]], dtype=np.float32)
    m = head_ellipse_mask(96, landmarks=lm)
    assert m.shape == (96, 96)
    # El centro de la elipse sube hacia la cabeza (por encima de los ojos).
    y_max = int(np.unravel_index(np.argmax(m), m.shape)[0])
    assert 20 <= y_max <= 55, f"centro de la cabeza inesperado: {y_max}"
    # Los píxeles del rostro (media de landmarks) quedan opacos.
    assert m[68, 75] > 0.5


def test_crop_head_png_bgra_con_alfa():
    bgra = crop_head_png(_crop_sintetico(), face=None, out_size=96)
    assert bgra is not None
    assert bgra.shape == (96, 96, 4)
    # Canal alfa no uniforme: hay transparencia en los bordes.
    alfa = bgra[:, :, 3]
    assert alfa.max() > 200 and alfa.min() < 80


def test_generar_avatar_escribe_png(tmp_path):
    out = str(tmp_path / "avatar.png")
    ruta = generar_avatar(7, "/no/existe.jpg", out)
    assert ruta is None  # fuente inexistente -> None

    # Fuente válida -> PNG escrito y con alfa.
    src = str(tmp_path / "crop.jpg")
    cv2.imwrite(src, _crop_sintetico())
    ruta = generar_avatar(7, src, out, out_size=64)
    assert ruta == out and os.path.exists(out)
    img = cv2.imread(out, cv2.IMREAD_UNCHANGED)
    assert img is not None and img.shape[2] == 4
