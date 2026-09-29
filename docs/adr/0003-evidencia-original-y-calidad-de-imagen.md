# ADR-0003: Evidencia original separada del retrato procesado

**Estado:** Aceptado  
**Fecha:** 2026-09-29

## Contexto

El worker HQ publica una mejora progresiva y el panel mostraba únicamente ese
retrato. Además, durante la escritura temporal del HQ el ingestor podía ver un
JPEG incompleto. El retrato procesado no debe sustituir la evidencia nativa de
la cámara ni sugerir resolución capturada por un reescalado de presentación.

## Decisión

- El worker/clasificador conserva el frame completo de mayor resolución del
  grupo en `motor/photo_evidence/<local>/<camara>/<correlación>.jpg`.
- `clasificadorV2.php` mueve esa evidencia a
  `admin/fotos_originales/<fotos.id>.jpg` al crear la fila; el panel muestra
  ambas imágenes y sus dimensiones.
- La cola HQ solo admite el nombre final `.jpg.hq`; los temporales
  `.hq.tmp.jpg` se excluyen explícitamente.
- La metadata de dimensiones, nitidez acotada, calidad, SR y reescalado se
  persiste en `fotos` mediante la migración versionada.
- Se elimina el top-up LANCZOS4 automático del pipeline de imagen; el CSS puede
  adaptar el layout, pero solo SR cuenta como aumento de resolución.

## Alternativas y trade-offs

- **Sobrescribir y conservar solo el retrato:** menos disco y UI más simple,
  pero destruye evidencia forense y oculta recortes/artefactos.
- **Guardar todos los frames:** más evidencia, pero coste de almacenamiento y
  mayor complejidad; el frame máximo cubre la necesidad operativa actual.
- **Metadata solo en JSON:** evita migración, pero no es consultable junto a
  `fotos` y puede quedar huérfana; se mantiene el sidecar como transporte y se
  persiste un resumen validado en SQL.

## Consecuencias

Las instalaciones requieren aplicar `sql/2026-09-29-fotos-imagen-provenance.sql`.
El almacenamiento runtime aumenta por una imagen nativa por foto. Las fotos
históricas sin evidencia quedan soportadas y el panel conserva su fallback.
