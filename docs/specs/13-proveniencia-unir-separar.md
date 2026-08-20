# Spec 13 — Proveniencia de encodings: unir/separar exacto

> Estado: implementado (2026-08-20). Objetivo: que las correcciones manuales del
> panel ("Unir", "mover foto", "separar") se apliquen de forma EXACTA y completa
> sobre `face_enc_v2` + BD, y alimenten la calibración (F3).

## Problema

La galería `face_enc_v2` guardaba por persona `encodings/quality/poses/added_at`
pero SIN enlace a la foto que originó cada encoding. Consecuencia: al "mover foto"
(`cambiar_foto.py`) se re-embebía la foto y se quitaba de origen el encoding más
parecido por coseno (1 solo) → quedaba residuo de la cara intrusa en la persona
equivocada, que seguía atrayendo más caras de la persona real.

## Clave: el identificador ya existe

`clasificador.py` escribe la foto como `{nombre}_{foto_id}.jpg` (foto_id = código
aleatorio de 25 chars, uno por sub-clúster) y `clasificadorV2.php` lo guarda en
`fotos.identificador_unico`. Solo faltaba grabar ese `foto_id` junto a cada
encoding.

## Cambios

### P1 — Esquema del store (`motor/core/store.py`)
- Lista paralela `sources` (str|None) por persona; `VERSION` 3→4 con relleno
  retrocompatible en `_read_raw` (`_aligned_lists`: personas V3 sin `sources` se
  leen con `[None]*n`). `add`, `merge`, `merge_undoable`, `_prune`,
  `reembed_person`, `remove_closest` mantienen `sources` alineado.

### P2 — Grabar provenance al crear
- `clasificador.py::_store_add` etiqueta cada encoding del sub-clúster con el
  `foto_id` de su foto representativa.
- `enrolamiento.py` usa id sintético `enroll:<cod>`.

### P3 — Primitivas exactas
- `FaceStore.move_by_source(src, dst, source_id)`: mueve TODOS los encodings con
  esa proveniencia (sin adivinar por coseno).
- `FaceStore.move_matching(src, dst, query_embs, min_cosine=0.45)`: fallback por
  coseno para encodings legacy (`sources` None).

### P4 — mover foto / separar usan proveniencia
- `motor/core/provenance.py::move_foto`: 1) source exacta → 2) coseno (legacy) →
  3) re-embed si la cara ya no está en origen. Etiqueta el destino con la
  proveniencia si se conoce.
- `motor/cambiar_foto.py`: reescrito sobre `move_foto` (sin modelo cuando hay
  provenance; emite `label_move` impostor).
- `motor/separar_personas.py` (nuevo): bulk multi-foto con snapshot F6 + journal
  + `label_move` por foto.
- Panel: `acciones.php` con `separar=<csv>&aeste=<destino>`; `edit.php` con
  checkboxes + "Mover seleccionadas a..." (confirmación ligera + overlay).

### P5 — Unir atómico
- `juntar_personas_v2.py` ahora hace TODO en un proceso síncrono: F6 snapshot
  (store + `db_snapshot.sql`) → merge conservando `sources` → `UPDATE estancias` +
  `DELETE personas` → `label_merge` genuino. Sin ventana inconsistente (antes la
  BD se actualizaba en PHP y la galería en async). `acciones.php` invoca síncrono
  con confirmación y overlay de carga.

## Decisiones
- Sin job nocturno automático: la corrección la hace el humano y el sistema
  aprende de ella (`reagrupar.py`/`detectar_mezclados.py` quedan manuales).
- Sin backfill: los encodings actuales (sin `sources`) se mueven por coseno como
  fallback; se irán etiquetando con data nueva (la galería actual será borrada en
  una sesión posterior).
- Umbral fallback `--min-cosine` 0.45 (configurable); la misma cara coincide
  ~0.5-0.9.

## Verificación
- `motor/tests/test_proveniencia.py` (12 tests): roundtrip sources, retrocompat
  V3, move_by_source exacto, move_matching fallback, merge conserva sources,
  prune alineado, move_foto vía source/missing.
- Suite completa: 170 passed, 1 skipped. `php -l` OK en los 4 ficheros PHP.
