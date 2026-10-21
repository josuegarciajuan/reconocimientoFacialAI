# Perfiles camaraip guardados para /ojos

> Objetivo: que la instancia `ojos` conserve, por cámara, la configuración
> efectiva que se ha ido ajustando (modelo, resolución, fps, rotación, controles
> de hardware y parámetros de análisis) y pueda usarla en el futuro aunque el
> bridge de camaraESP no esté disponible.

## Archivos

| Archivo | Papel |
|---|---|
| `config/camaraip_ojos_profiles.json` | Copia versionada por cámara (perfil + ajustes de Ojos) |
| `tools/export_camaraip_profiles.php` | Regenera la copia desde el bridge y la BD; solo `RF_INSTANCE=ojos` |
| `libs/camara_perfil.php` | Fallback PHP: bridge → copia guardada → BD |
| `motor/core/camara_perfil.py` | Fallback Python para captura/snapshots |

## Orden de precedencia

1. **Bridge en vivo** (`GET /camaraip/profile`): perfil efectivo y fps medido.
2. **Copia guardada** (`config/camaraip_ojos_profiles.json`): si el bridge no
   responde o tarda más de 0,8 s.
3. **BD `camaras`**: último recurso del llamador (fps/parámetros de análisis).

La copia guardada **no sustituye** al bridge: los controles UVC/serie siguen
aplicándose en el nodo de cámara por los agentes de camaraESP. Ojos guarda una
copia para no perder el contexto de cada cámara en el futuro.

## Contenido por cámara

- `camera_id`, `label`, `url_conexion`, `active`, `encendida`.
- `profile`: copia completa del perfil de camaraESP:
  - `model`, `sensor`, `kind`.
  - `stream`: ancho, alto, fps objetivo, calidad JPEG y **rotation**.
  - `device`: serie/UVC y controles del sensor.
- `ojos`:
  - `fps_objetivo` y `fps_efectivo` (medido en el momento del export).
  - `snapshot: latest.jpg`, `live: direct` (cómo consume Ojos).
  - `analysis`: `segundos_analizar`, `porcentaje_mov`, `dontCare`,
    `maximo_videos`, `redimesionframe`, `sensibilidad`, `threshold`, `blur`,
    `dilate`, `seg_antes`, `seg_despues`.

## Estado guardado (2026-10-21)

| ID | Modelo | Resolución | FPS obj./ef. | Rotación |
|---|---|---|---|---|
| `esp32-oficina` | AI-Thinker ESP32-CAM + OV3660 | 320×240 | 5 / 3 | 90° |
| `cam-oficina` | SiGma Micro USB Web Camera | 320×240 | 5 / 3 | 180° |
| `onx-josue` | ONX3248G035 + OV2640 | 320×240 | 2 / 2 | 0° |
| `cam-portatil` | UVC genérica | 320×240 | 2 / 2 | 0° |
| `esp32-josue` | AI-Thinker ESP32-CAM | 320×240 | 2 / 2 | 0° |

`fps_efectivo` es una foto del momento de exportar; el bridge lo recalcula en
vivo. Ojos usa el medido cuando hay frames.

## Regenerar la copia

Con el bridge levantado y desde la instancia `ojos`:

```bash
cd /root/reconocimientoFacial
php tools/export_camaraip_profiles.php
git diff config/camaraip_ojos_profiles.json
# revisar y commitear; desplegar solo la instancia ojos
bash deploy/ojos/deploy_ojos.sh
```

El script:
- exige `RF_INSTANCE=ojos`;
- lee `http://127.0.0.1:8111/camaraip/profiles`;
- cruza cada `camera=<id>` con la tabla `camaras`;
- escribe el JSON de forma atómica;
- no incluye claves ni credenciales.

## Verificar el fallback

```bash
cd /root/reconocimientoFacial
RF_CAMARA_PROFILE_URL=http://127.0.0.1:9/profile php tests/camara_perfil_test.php
motor/venv/bin/python -m pytest motor/tests/test_camara_perfil.py -q
```

Los tests comprueban que, sin bridge, `cam-oficina` conserva el modelo,
`rotation=180` y un fps válido desde la copia guardada.
