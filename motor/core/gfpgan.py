"""GFPGAN v1.4 standalone — motor/core/gfpgan.py

Restauración facial con prior generativo (GFPGAN), portada **sin `basicsr`**:
usa la arquitectura "clean" (`GFPGANv1Clean` + `StyleGAN2GeneratorClean`), que
solo necesita operaciones PyTorch puras (`nn.Conv2d`, `nn.Linear`, `F.interpolate`,
`nn.LeakyReLU`). No arrastra `basicsr` (que rompía insightface/onnxruntime con
numpy 2 / opencv no-headless), igual que `superres.py` hizo con Real-ESRGAN.

A diferencia de Real-ESRGAN (SR genérico), GFPGAN usa priors faciales (ojos,
boca, identidad) y produce caras naturales desde recortes muy pequeños (~40 px),
que es justo lo que evita el aspecto "plastificado"/pixelado tipo 16-bit.

Los pesos `GFPGANv1.4.pth` (~340 MB, oficial, BSD-3-Clause) se descargan la 1ª
vez a `motor/models/` (gitignored: git = código, no datos).

Importable sin torch: si falta, `get_gfpgan()` devuelve None y el pipeline
degrada al fallback (nunca rompe).

Uso:
    from motor.core.gfpgan import get_gfpgan, restore
    model = get_gfpgan()
    out_bgr = restore(img_bgr, model)  # BGR uint8, 512x512 natural
"""
from __future__ import annotations

import math
import os
import random
import shutil
import threading
import urllib.request

import cv2
import numpy as np

MODEL_URL = "https://github.com/TencentARC/GFPGAN/releases/download/v1.3.0/GFPGANv1.4.pth"
MODEL_FILE = "GFPGANv1.4.pth"

_lock = threading.Lock()
_model = None          # GFPGANv1Clean cargado (o None)
_checked = False       # ya intentamos cargar (evita re-descargas/errores en bucle)

try:
    import torch
    from torch import nn
    from torch.nn import functional as F
    _TORCH_OK = True
except Exception:  # noqa: BLE001
    torch = None
    nn = None
    F = None
    _TORCH_OK = False


# ======================================================================
# StyleGAN2 "clean" (sin extensiones CUDA compiladas) — motor/core/gfpgan.py
# Adaptado de gfpgan/archs/stylegan2_clean_arch.py (TencentARC, BSD-3-Clause).
# Se eliminan los imports de basicsr y las llamadas a default_init_weights
# (solo inicializan; los pesos se cargan del checkpoint).
# ======================================================================

class NormStyleCode(nn.Module):

    def forward(self, x):
        return x * torch.rsqrt(torch.mean(x ** 2, dim=1, keepdim=True) + 1e-8)


class ModulatedConv2d(nn.Module):
    """Modulated Conv2d usado en StyleGAN2 (versión clean, sin upfirdn2d)."""

    def __init__(self, in_channels, out_channels, kernel_size, num_style_feat,
                 demodulate=True, sample_mode=None, eps=1e-8):
        super(ModulatedConv2d, self).__init__()
        self.in_channels = in_channels
        self.out_channels = out_channels
        self.kernel_size = kernel_size
        self.demodulate = demodulate
        self.sample_mode = sample_mode
        self.eps = eps

        self.modulation = nn.Linear(num_style_feat, in_channels, bias=True)
        self.weight = nn.Parameter(
            torch.randn(1, out_channels, in_channels, kernel_size, kernel_size) /
            math.sqrt(in_channels * kernel_size ** 2))
        self.padding = kernel_size // 2

    def forward(self, x, style):
        b, c, h, w = x.shape

        style = self.modulation(style).view(b, 1, c, 1, 1)
        weight = self.weight * style

        if self.demodulate:
            demod = torch.rsqrt(weight.pow(2).sum([2, 3, 4]) + self.eps)
            weight = weight * demod.view(b, self.out_channels, 1, 1, 1)

        weight = weight.view(b * self.out_channels, c, self.kernel_size, self.kernel_size)

        if self.sample_mode == 'upsample':
            x = F.interpolate(x, scale_factor=2, mode='bilinear', align_corners=False)
        elif self.sample_mode == 'downsample':
            x = F.interpolate(x, scale_factor=0.5, mode='bilinear', align_corners=False)

        b, c, h, w = x.shape
        x = x.view(1, b * c, h, w)
        out = F.conv2d(x, weight, padding=self.padding, groups=b)
        out = out.view(b, self.out_channels, *out.shape[2:4])
        return out


class StyleConv(nn.Module):
    """Style conv usado en StyleGAN2 (clean)."""

    def __init__(self, in_channels, out_channels, kernel_size, num_style_feat,
                 demodulate=True, sample_mode=None):
        super(StyleConv, self).__init__()
        self.modulated_conv = ModulatedConv2d(
            in_channels, out_channels, kernel_size, num_style_feat,
            demodulate=demodulate, sample_mode=sample_mode)
        self.weight = nn.Parameter(torch.zeros(1))  # inyección de ruido
        self.bias = nn.Parameter(torch.zeros(1, out_channels, 1, 1))
        self.activate = nn.LeakyReLU(negative_slope=0.2, inplace=True)

    def forward(self, x, style, noise=None):
        out = self.modulated_conv(x, style) * 2 ** 0.5
        if noise is None:
            b, _, h, w = out.shape
            noise = out.new_empty(b, 1, h, w).normal_()
        out = out + self.weight * noise
        out = out + self.bias
        out = self.activate(out)
        return out


class ToRGB(nn.Module):
    """To RGB (espacio imagen) desde features (clean)."""

    def __init__(self, in_channels, num_style_feat, upsample=True):
        super(ToRGB, self).__init__()
        self.upsample = upsample
        self.modulated_conv = ModulatedConv2d(
            in_channels, 3, kernel_size=1, num_style_feat=num_style_feat,
            demodulate=False, sample_mode=None)
        self.bias = nn.Parameter(torch.zeros(1, 3, 1, 1))

    def forward(self, x, style, skip=None):
        out = self.modulated_conv(x, style)
        out = out + self.bias
        if skip is not None:
            if self.upsample:
                skip = F.interpolate(skip, scale_factor=2, mode='bilinear', align_corners=False)
            out = out + skip
        return out


class ConstantInput(nn.Module):

    def __init__(self, num_channel, size):
        super(ConstantInput, self).__init__()
        self.weight = nn.Parameter(torch.randn(1, num_channel, size, size))

    def forward(self, batch):
        return self.weight.repeat(batch, 1, 1, 1)


class StyleGAN2GeneratorClean(nn.Module):
    """Generador StyleGAN2 clean (sin extensiones CUDA compiladas)."""

    def __init__(self, out_size, num_style_feat=512, num_mlp=8, channel_multiplier=2, narrow=1):
        super(StyleGAN2GeneratorClean, self).__init__()
        self.num_style_feat = num_style_feat

        style_mlp_layers = [NormStyleCode()]
        for _ in range(num_mlp):
            style_mlp_layers.extend(
                [nn.Linear(num_style_feat, num_style_feat, bias=True),
                 nn.LeakyReLU(negative_slope=0.2, inplace=True)])
        self.style_mlp = nn.Sequential(*style_mlp_layers)

        channels = {
            '4': int(512 * narrow),
            '8': int(512 * narrow),
            '16': int(512 * narrow),
            '32': int(512 * narrow),
            '64': int(256 * channel_multiplier * narrow),
            '128': int(128 * channel_multiplier * narrow),
            '256': int(64 * channel_multiplier * narrow),
            '512': int(32 * channel_multiplier * narrow),
            '1024': int(16 * channel_multiplier * narrow)
        }
        self.channels = channels

        self.constant_input = ConstantInput(channels['4'], size=4)
        self.style_conv1 = StyleConv(channels['4'], channels['4'], kernel_size=3,
                                     num_style_feat=num_style_feat, demodulate=True, sample_mode=None)
        self.to_rgb1 = ToRGB(channels['4'], num_style_feat, upsample=False)

        self.log_size = int(math.log(out_size, 2))
        self.num_layers = (self.log_size - 2) * 2 + 1
        self.num_latent = self.log_size * 2 - 2

        self.style_convs = nn.ModuleList()
        self.to_rgbs = nn.ModuleList()
        self.noises = nn.Module()

        in_channels = channels['4']
        for layer_idx in range(self.num_layers):
            resolution = 2 ** ((layer_idx + 5) // 2)
            self.noises.register_buffer(f'noise{layer_idx}', torch.randn(1, 1, resolution, resolution))

        for i in range(3, self.log_size + 1):
            out_channels = channels[f'{2 ** i}']
            self.style_convs.append(
                StyleConv(in_channels, out_channels, kernel_size=3, num_style_feat=num_style_feat,
                          demodulate=True, sample_mode='upsample'))
            self.style_convs.append(
                StyleConv(out_channels, out_channels, kernel_size=3, num_style_feat=num_style_feat,
                          demodulate=True, sample_mode=None))
            self.to_rgbs.append(ToRGB(out_channels, num_style_feat, upsample=True))
            in_channels = out_channels

    def forward(self, styles, input_is_latent=False, noise=None, randomize_noise=True,
                truncation=1, truncation_latent=None, inject_index=None, return_latents=False):
        if not input_is_latent:
            styles = [self.style_mlp(s) for s in styles]
        if noise is None:
            if randomize_noise:
                noise = [None] * self.num_layers
            else:
                noise = [getattr(self.noises, f'noise{i}') for i in range(self.num_layers)]
        if truncation < 1:
            style_truncation = []
            for style in styles:
                style_truncation.append(truncation_latent + truncation * (style - truncation_latent))
            styles = style_truncation

        if len(styles) == 1:
            inject_index = self.num_latent
            if styles[0].ndim < 3:
                latent = styles[0].unsqueeze(1).repeat(1, inject_index, 1)
            else:
                latent = styles[0]
        elif len(styles) == 2:
            if inject_index is None:
                inject_index = random.randint(1, self.num_latent - 1)
            latent1 = styles[0].unsqueeze(1).repeat(1, inject_index, 1)
            latent2 = styles[1].unsqueeze(1).repeat(1, self.num_latent - inject_index, 1)
            latent = torch.cat([latent1, latent2], 1)

        out = self.constant_input(latent.shape[0])
        out = self.style_conv1(out, latent[:, 0], noise=noise[0])
        skip = self.to_rgb1(out, latent[:, 1])

        i = 1
        for conv1, conv2, noise1, noise2, to_rgb in zip(self.style_convs[::2], self.style_convs[1::2],
                                                        noise[1::2], noise[2::2], self.to_rgbs):
            out = conv1(out, latent[:, i], noise=noise1)
            out = conv2(out, latent[:, i + 1], noise=noise2)
            skip = to_rgb(out, latent[:, i + 2], skip)
            i += 2

        image = skip
        if return_latents:
            return image, latent
        return image, None


class StyleGAN2GeneratorCSFT(StyleGAN2GeneratorClean):
    """StyleGAN2 Generator con modulación SFT (Spatial Feature Transform)."""

    def __init__(self, out_size, num_style_feat=512, num_mlp=8, channel_multiplier=2, narrow=1, sft_half=False):
        super(StyleGAN2GeneratorCSFT, self).__init__(
            out_size, num_style_feat=num_style_feat, num_mlp=num_mlp,
            channel_multiplier=channel_multiplier, narrow=narrow)
        self.sft_half = sft_half

    def forward(self, styles, conditions, input_is_latent=False, noise=None,
                randomize_noise=True, truncation=1, truncation_latent=None,
                inject_index=None, return_latents=False):
        if not input_is_latent:
            styles = [self.style_mlp(s) for s in styles]
        if noise is None:
            if randomize_noise:
                noise = [None] * self.num_layers
            else:
                noise = [getattr(self.noises, f'noise{i}') for i in range(self.num_layers)]
        if truncation < 1:
            style_truncation = []
            for style in styles:
                style_truncation.append(truncation_latent + truncation * (style - truncation_latent))
            styles = style_truncation

        if len(styles) == 1:
            inject_index = self.num_latent
            if styles[0].ndim < 3:
                latent = styles[0].unsqueeze(1).repeat(1, inject_index, 1)
            else:
                latent = styles[0]
        elif len(styles) == 2:
            if inject_index is None:
                inject_index = random.randint(1, self.num_latent - 1)
            latent1 = styles[0].unsqueeze(1).repeat(1, inject_index, 1)
            latent2 = styles[1].unsqueeze(1).repeat(1, self.num_latent - inject_index, 1)
            latent = torch.cat([latent1, latent2], 1)

        out = self.constant_input(latent.shape[0])
        out = self.style_conv1(out, latent[:, 0], noise=noise[0])
        skip = self.to_rgb1(out, latent[:, 1])

        i = 1
        for conv1, conv2, noise1, noise2, to_rgb in zip(self.style_convs[::2], self.style_convs[1::2],
                                                        noise[1::2], noise[2::2], self.to_rgbs):
            out = conv1(out, latent[:, i], noise=noise1)
            if i < len(conditions):
                if self.sft_half:
                    out_same, out_sft = torch.split(out, int(out.size(1) // 2), dim=1)
                    out_sft = out_sft * conditions[i - 1] + conditions[i]
                    out = torch.cat([out_same, out_sft], dim=1)
                else:
                    out = out * conditions[i - 1] + conditions[i]
            out = conv2(out, latent[:, i + 1], noise=noise2)
            skip = to_rgb(out, latent[:, i + 2], skip)
            i += 2

        image = skip
        if return_latents:
            return image, latent
        return image, None


class ResBlock(nn.Module):
    """Bloque residual con up/down bilineal (clean)."""

    def __init__(self, in_channels, out_channels, mode='down'):
        super(ResBlock, self).__init__()
        self.conv1 = nn.Conv2d(in_channels, in_channels, 3, 1, 1)
        self.conv2 = nn.Conv2d(in_channels, out_channels, 3, 1, 1)
        self.skip = nn.Conv2d(in_channels, out_channels, 1, bias=False)
        self.scale_factor = 0.5 if mode == 'down' else 2

    def forward(self, x):
        out = F.leaky_relu_(self.conv1(x), negative_slope=0.2)
        out = F.interpolate(out, scale_factor=self.scale_factor, mode='bilinear', align_corners=False)
        out = F.leaky_relu_(self.conv2(out), negative_slope=0.2)
        x = F.interpolate(x, scale_factor=self.scale_factor, mode='bilinear', align_corners=False)
        skip = self.skip(x)
        return out + skip


class GFPGANv1Clean(nn.Module):
    """GFPGAN v1.4 clean: UNet + decoder StyleGAN2 con SFT."""

    def __init__(self, out_size, num_style_feat=512, channel_multiplier=2,
                 decoder_load_path=None, fix_decoder=False, num_mlp=8,
                 input_is_latent=False, different_w=False, narrow=1, sft_half=False):
        super(GFPGANv1Clean, self).__init__()
        self.input_is_latent = input_is_latent
        self.different_w = different_w
        self.num_style_feat = num_style_feat

        unet_narrow = narrow * 0.5
        channels = {
            '4': int(512 * unet_narrow),
            '8': int(512 * unet_narrow),
            '16': int(512 * unet_narrow),
            '32': int(512 * unet_narrow),
            '64': int(256 * channel_multiplier * unet_narrow),
            '128': int(128 * channel_multiplier * unet_narrow),
            '256': int(64 * channel_multiplier * unet_narrow),
            '512': int(32 * channel_multiplier * unet_narrow),
            '1024': int(16 * channel_multiplier * unet_narrow)
        }

        self.log_size = int(math.log(out_size, 2))
        first_out_size = 2 ** (int(math.log(out_size, 2)))

        self.conv_body_first = nn.Conv2d(3, channels[f'{first_out_size}'], 1)

        in_channels = channels[f'{first_out_size}']
        self.conv_body_down = nn.ModuleList()
        for i in range(self.log_size, 2, -1):
            out_channels = channels[f'{2 ** (i - 1)}']
            self.conv_body_down.append(ResBlock(in_channels, out_channels, mode='down'))
            in_channels = out_channels

        self.final_conv = nn.Conv2d(in_channels, channels['4'], 3, 1, 1)

        in_channels = channels['4']
        self.conv_body_up = nn.ModuleList()
        for i in range(3, self.log_size + 1):
            out_channels = channels[f'{2 ** i}']
            self.conv_body_up.append(ResBlock(in_channels, out_channels, mode='up'))
            in_channels = out_channels

        self.toRGB = nn.ModuleList()
        for i in range(3, self.log_size + 1):
            self.toRGB.append(nn.Conv2d(channels[f'{2 ** i}'], 3, 1))

        if different_w:
            linear_out_channel = (int(math.log(out_size, 2)) * 2 - 2) * num_style_feat
        else:
            linear_out_channel = num_style_feat
        self.final_linear = nn.Linear(channels['4'] * 4 * 4, linear_out_channel)

        self.stylegan_decoder = StyleGAN2GeneratorCSFT(
            out_size=out_size, num_style_feat=num_style_feat, num_mlp=num_mlp,
            channel_multiplier=channel_multiplier, narrow=narrow, sft_half=sft_half)

        if decoder_load_path:
            self.stylegan_decoder.load_state_dict(
                torch.load(decoder_load_path, map_location=lambda storage, loc: storage)['params_ema'])
        if fix_decoder:
            for _, param in self.stylegan_decoder.named_parameters():
                param.requires_grad = False

        self.condition_scale = nn.ModuleList()
        self.condition_shift = nn.ModuleList()
        for i in range(3, self.log_size + 1):
            out_channels = channels[f'{2 ** i}']
            sft_out_channels = out_channels if sft_half else out_channels * 2
            self.condition_scale.append(
                nn.Sequential(
                    nn.Conv2d(out_channels, out_channels, 3, 1, 1), nn.LeakyReLU(0.2, True),
                    nn.Conv2d(out_channels, sft_out_channels, 3, 1, 1)))
            self.condition_shift.append(
                nn.Sequential(
                    nn.Conv2d(out_channels, out_channels, 3, 1, 1), nn.LeakyReLU(0.2, True),
                    nn.Conv2d(out_channels, sft_out_channels, 3, 1, 1)))

    def forward(self, x, return_latents=False, return_rgb=True, randomize_noise=True, **kwargs):
        conditions = []
        unet_skips = []
        out_rgbs = []

        feat = F.leaky_relu_(self.conv_body_first(x), negative_slope=0.2)
        for i in range(self.log_size - 2):
            feat = self.conv_body_down[i](feat)
            unet_skips.insert(0, feat)
        feat = F.leaky_relu_(self.final_conv(feat), negative_slope=0.2)

        style_code = self.final_linear(feat.view(feat.size(0), -1))
        if self.different_w:
            style_code = style_code.view(style_code.size(0), -1, self.num_style_feat)

        for i in range(self.log_size - 2):
            feat = feat + unet_skips[i]
            feat = self.conv_body_up[i](feat)
            scale = self.condition_scale[i](feat)
            conditions.append(scale.clone())
            shift = self.condition_shift[i](feat)
            conditions.append(shift.clone())
            if return_rgb:
                out_rgbs.append(self.toRGB[i](feat))

        image, _ = self.stylegan_decoder([style_code], conditions,
                                         return_latents=return_latents,
                                         input_is_latent=self.input_is_latent,
                                         randomize_noise=randomize_noise)
        return image, out_rgbs


# ======================================================================
# Infraestructura de carga (singleton lazy + descarga, patrón superres.py)
# ======================================================================

def _models_dir() -> str:
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "motor", "models"))


def _model_path() -> str:
    return os.path.join(_models_dir(), MODEL_FILE)


def _download() -> str | None:
    path = _model_path()
    if os.path.exists(path):
        return path
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".part"
    try:
        req = urllib.request.Request(MODEL_URL, headers={"User-Agent": "reconocimientoFacial-gfpgan"})
        with urllib.request.urlopen(req, timeout=600) as resp, open(tmp, "wb") as fh:
            shutil.copyfileobj(resp, fh, 1024 * 1024)
        os.replace(tmp, path)
        print(f"[gfpgan] pesos descargados: {path}", flush=True)
        return path
    except Exception as e:  # noqa: BLE001
        print(f"[gfpgan] descarga de pesos fallida: {e}", flush=True)
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except OSError:
            pass
        return None


def _build() -> GFPGANv1Clean:
    """GFPGANv1.4 (clean), parámetros oficiales de GFPGANer (channel_multiplier=2)."""
    return GFPGANv1Clean(
        out_size=512,
        num_style_feat=512,
        channel_multiplier=2,
        decoder_load_path=None,
        fix_decoder=False,
        num_mlp=8,
        input_is_latent=True,
        different_w=True,
        narrow=1,
        sft_half=True,
    )


def get_gfpgan():
    """Singleton lazy del modelo GFPGAN. None si no hay torch, pesos o falla la carga."""
    global _model, _checked
    if _model is not None:
        return _model
    with _lock:
        if _model is not None:
            return _model
        if _checked:
            return None
        _checked = True
        if not _TORCH_OK:
            print("[gfpgan] torch no disponible, GFPGAN deshabilitado", flush=True)
            return None
        path = _model_path()
        if not os.path.exists(path):
            path = _download()
        if not path:
            return None
        try:
            model = _build()
            ck = torch.load(path, map_location="cpu")
            state = ck["params_ema"] if isinstance(ck, dict) and "params_ema" in ck else ck
            state = state["params"] if isinstance(state, dict) and "params" in state else state
            model.load_state_dict(state, strict=True)
            model.eval()
            _model = model
            print("[gfpgan] modelo GFPGANv1.4 cargado (CPU)", flush=True)
            return model
        except Exception as e:  # noqa: BLE001
            print(f"[gfpgan] carga de modelo fallida, GFPGAN deshabilitado: {e}", flush=True)
            return None


# ======================================================================
# Inferencia
# ======================================================================

def _img_to_tensor(img_bgr: np.ndarray):
    """BGR uint8 -> tensor (1,3,H,W) normalizado a [-1,1]."""
    rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    t = torch.from_numpy(rgb.astype(np.float32) / 255.0).permute(2, 0, 1).unsqueeze(0)
    return (t - 0.5) / 0.5


def _tensor_to_img(t) -> np.ndarray:
    """Tensor (1,3,H,W) en [-1,1] -> BGR uint8."""
    t = (t + 1.0) / 2.0
    t = t.clamp(0.0, 1.0)
    rgb = t.squeeze(0).permute(1, 2, 0).detach().cpu().numpy()
    rgb = (rgb * 255.0).round().astype(np.uint8)
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)


def restore(img_bgr: np.ndarray, model=None, weight: float | None = 0.5) -> np.ndarray | None:
    """Restaura una cara con GFPGAN. Entrada BGR uint8 -> salida BGR uint8 (512x512).

    `weight` en (0,1) mezcla la salida de GFPGAN con la entrada reescalada a 512
    (preserva identidad); None = salida pura de GFPGAN.
    """
    if img_bgr is None or img_bgr.size == 0:
        return None
    if model is None:
        model = get_gfpgan()
    if model is None:
        return None
    inp = cv2.resize(img_bgr, (512, 512), interpolation=cv2.INTER_LINEAR)
    t = _img_to_tensor(inp)
    try:
        with torch.no_grad():
            out, _ = model(t, return_rgb=False)
    except Exception as e:  # noqa: BLE001
        print(f"[gfpgan] inferencia fallida: {e}", flush=True)
        return None
    restored = _tensor_to_img(out)
    if weight is not None and 0.0 < weight < 1.0:
        restored = cv2.addWeighted(restored, weight, inp, 1.0 - weight, 0)
    return restored
