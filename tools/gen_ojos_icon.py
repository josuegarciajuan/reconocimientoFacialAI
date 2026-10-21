#!/usr/bin/env python3
"""Genera los iconos PWA de la instancia `ojos`.

Dibuja un robot amigable con dos ojos enormes, pensado para leerse bien a 192 px
en la pantalla de inicio de Android. Solo usa Pillow (ya instalado).

Uso:
    python3 tools/gen_ojos_icon.py
    python3 tools/gen_ojos_icon.py --out /ruta/a/admin/files/branding

Salidas (por defecto en admin/files/branding/):
    icon-192.png            -> icono normal
    icon-512.png            -> icono normal
    icon-1024.png           -> icono normal (alta resolución)
    icon-maskable-512.png   -> variante con zona segura para Android
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps

REPO = Path(__file__).resolve().parents[1]
DEFAULT_OUT = REPO / "admin" / "files" / "branding"

BASE = 1024
SS = 4  # supersampling (se dibuja a 4096 px y se reduce)

# Paleta (robot amigable y colorido sobre el fondo oscuro de la marca).
BG = (11, 10, 14)
GLOW = (42, 33, 64)
HEAD_TOP = (138, 152, 255)
HEAD_BOTTOM = (90, 104, 232)
HEAD_OUTLINE = (46, 53, 112)
VISOR = (27, 33, 66)
VISOR_OUTLINE = (58, 66, 112)
SCLERA = (255, 255, 255)
SCLERA_OUTLINE = (16, 20, 43)
IRIS_OUTER = (31, 181, 170)
IRIS_MID = (46, 211, 198)
IRIS_INNER = (99, 232, 219)
PUPIL = (16, 19, 42)
EARS = (255, 201, 60)
EARS_OUTLINE = (201, 143, 30)
CORAL = (255, 107, 107)
CORAL_OUTLINE = (196, 74, 74)
CHEEK = (255, 143, 163)
MOUTH = (127, 232, 220)


def sc(value: float) -> int:
    return int(round(value * SS))


def _rounded_gradient(size, box, radius, top, bottom):
    """Rectángulo redondeado con degradado vertical, en una capa RGBA."""
    x0, y0, x1, y1 = (sc(v) for v in box)
    width, height = x1 - x0, y1 - y0
    gradient = Image.linear_gradient("L").resize((width, height), Image.LANCZOS)
    layer = ImageOps.colorize(gradient, top, bottom).convert("RGBA")
    mask = Image.new("L", (width, height), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [0, 0, width - 1, height - 1], radius=sc(radius), fill=255
    )
    layer.putalpha(mask)
    canvas = Image.new("RGBA", size, (0, 0, 0, 0))
    canvas.paste(layer, (x0, y0), layer)
    return canvas


def _background(size):
    """Fondo oscuro con un halo suave detrás del robot."""
    canvas = Image.new("RGBA", size, BG + (255,))
    radial = Image.radial_gradient("L").resize(size, Image.LANCZOS)
    alpha = ImageOps.invert(radial).point(lambda p: int(p * 0.55))
    halo = Image.new("RGBA", size, GLOW + (255,))
    halo.putalpha(alpha)
    canvas.alpha_composite(halo)
    return canvas


def _circle(cx, cy, radius):
    return [sc(cx - radius), sc(cy - radius), sc(cx + radius), sc(cy + radius)]


def _draw_eye(draw: ImageDraw.ImageDraw, cx: float, cy: float, rx: float, ry: float) -> None:
    """Ojo grande: esclerótica blanca, iris turquesa y doble brillo."""
    draw.ellipse(
        [sc(cx - rx), sc(cy - ry), sc(cx + rx), sc(cy + ry)],
        fill=SCLERA + (255,),
        outline=SCLERA_OUTLINE + (255,),
        width=sc(8),
    )
    iris = ry * 0.60
    draw.ellipse(_circle(cx, cy, iris + 6), fill=IRIS_OUTER + (255,))
    draw.ellipse(_circle(cx, cy, iris), fill=IRIS_MID + (255,))
    draw.ellipse(_circle(cx, cy, iris * 0.72), fill=IRIS_INNER + (255,))
    draw.ellipse(_circle(cx, cy, iris * 0.46), fill=PUPIL + (255,))
    draw.ellipse(
        _circle(cx - iris * 0.34, cy - iris * 0.36, iris * 0.20),
        fill=(255, 255, 255, 255),
    )
    draw.ellipse(
        _circle(cx + iris * 0.24, cy + iris * 0.22, iris * 0.09),
        fill=(255, 255, 255, 255),
    )


def _draw_art(size):
    """Capa transparente con el robot completo."""
    art = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(art)

    # Antena (detrás de la cabeza).
    draw.line(
        [(sc(512), sc(250)), (sc(512), sc(158))],
        fill=HEAD_OUTLINE + (255,),
        width=sc(20),
    )
    draw.ellipse(
        _circle(512, 126, 44),
        fill=CORAL + (255,),
        outline=CORAL_OUTLINE + (255,),
        width=sc(8),
    )
    draw.ellipse(_circle(498, 112, 12), fill=(255, 255, 255, 235))

    # Orejas / altavoces laterales (quedan parcialmente bajo la cabeza).
    for x0, x1 in ((122, 176), (848, 902)):
        draw.rounded_rectangle(
            [sc(x0), sc(430), sc(x1), sc(610)],
            radius=sc(24),
            fill=EARS + (255,),
            outline=EARS_OUTLINE + (255,),
            width=sc(10),
        )
        slit_x = (x0 + x1) / 2
        draw.rounded_rectangle(
            [sc(slit_x - 7), sc(475), sc(slit_x + 7), sc(565)],
            radius=sc(7),
            fill=EARS_OUTLINE + (255,),
        )

    # Cabeza con degradado y contorno.
    art.alpha_composite(
        _rounded_gradient(size, (170, 245, 854, 770), 130, HEAD_TOP, HEAD_BOTTOM)
    )
    draw.rounded_rectangle(
        [sc(170), sc(245), sc(854), sc(770)],
        radius=sc(130),
        outline=HEAD_OUTLINE + (255,),
        width=sc(16),
    )

    # Visor oscuro: da contraste a los ojos blancos.
    draw.rounded_rectangle(
        [sc(232), sc(318), sc(792), sc(720)],
        radius=sc(90),
        fill=VISOR + (255,),
        outline=VISOR_OUTLINE + (255,),
        width=sc(10),
    )

    # Mejillas.
    for cx in (300, 724):
        draw.ellipse([sc(cx - 40), sc(640), sc(cx + 40), sc(688)], fill=CHEEK + (255,))

    # Dos ojos enormes.
    _draw_eye(draw, 382, 500, 100, 122)
    _draw_eye(draw, 642, 500, 100, 122)

    # Sonrisa LED.
    draw.arc(
        [sc(452), sc(612), sc(572), sc(700)],
        start=20,
        end=160,
        fill=MOUTH + (255,),
        width=sc(14),
    )

    return art


def render(px: int, maskable: bool = False) -> Image.Image:
    size = (BASE * SS, BASE * SS)
    background = _background(size)
    art = _draw_art(size)
    if maskable:
        # 790/1024 deja el robot dentro del círculo seguro del 80 % de Android.
        side = sc(790)
        art = art.resize((side, side), Image.LANCZOS)
        background.alpha_composite(
            art,
            ((size[0] - side) // 2, (size[1] - side) // 2),
        )
    else:
        background.alpha_composite(art)
    return background.convert("RGB").resize((px, px), Image.LANCZOS)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    outputs = {
        "icon-192.png": render(192),
        "icon-512.png": render(512),
        "icon-1024.png": render(1024),
        "icon-maskable-512.png": render(512, maskable=True),
    }
    for name, image in outputs.items():
        path = args.out / name
        image.save(path, "PNG", optimize=True)
        print(f"[iconos] {path} ({image.width}x{image.height})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
