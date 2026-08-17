# Set de evaluación etiquetado

Esta carpeta está **gitignored** (son datos, no código).

## Cómo poblar el set

Estructura:

```
motor/eval/data/
  <persona_id>/            # un directorio por persona real
    juan_f.jpg             # frente
    juan_pi.jpg            # perfil izquierdo (90°)
    juan_pd.jpg            # perfil derecho (90°)
    juan_m45i.jpg          # (opcional) 45° izquierdo
    juan_m45d.jpg          # (opcional) 45° derecho
    juan_arr.jpg           # (opcional) arriba
    juan_aba.jpg           # (opcional) abajo
```

- Sufijos de pose: `_f` (frente), `_pi` (perfil izq), `_pd` (perfil der),
  `_m45i`, `_m45d`, `_arr`, `_aba`.
- Sin sufijo = pose desconocida (cuenta como genuino genérico, no en frente↔perfil).
- **Mínimo viable**: 3 personas × 3 poses (frente + 2 perfiles) = 9 imágenes.
  Con eso ya se obtienen métricas significativas.
- **Recomendado**: 5+ personas × 5 poses.

## Cómo generar imágenes de prueba

1. Con el panel (registro multi-pose) — cuando Fase 1 lo active.
2. Con cámara RTSP: `motor/venv/bin/python motor/dofoto.py <cam> <rtsp> <ruta>` y renombrar.
3. Imágenes sueltas existentes del repo (p. ej. `motor/inicial/prueba1.jpg`) como semilla.

## Ejecución

```bash
motor/venv/bin/python -m motor.eval.eval --data-dir motor/eval/data
```

La caché de embeddings se guarda en `motor/eval/.cache_eval.pkl` (gitignored).
