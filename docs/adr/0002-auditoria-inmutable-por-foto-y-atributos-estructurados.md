# ADR-0002: Auditoría inmutable por foto y atributos visibles separados

**Estado:** Aceptado
**Fecha:** 2026-09-01

## Contexto

La clasificación produce la imagen antes de que `clasificadorV2.php` cree la
fila de `fotos`. Necesitamos conservar qué capas participaron, enlazarlo con
`fotos.id`, y mantener la historia cuando un operador mueve una foto.
Además, los atributos visibles (gafas, gorro, mascarilla, barba/bigote, pelo,
accesorios y color de ropa) son evidencia débil y no deben convertirse en una
identidad.

## Decisión

- El clasificador escribe un sidecar JSON atómico, correlacionado por el
  `identificador_unico` generado para la foto.
- El ingestor PHP enlaza el sidecar a `fotos.id` después del `INSERT`; solo se
  actualiza ese FK, nunca el contenido de la auditoría.
- `foto_audit_events` es append-only para movimientos. Mover no reclasifica ni
  borra la auditoría original; un marcador de runtime permite distinguir
  clasificaciones posteriores como `post_move`.
- Los atributos usan contrato versionado y JSON estricto. Valores desconocidos
  no aportan evidencia y cualquier respuesta inválida queda no disponible.
- Los atributos se mantienen separados de embeddings y de la decisión de
  identidad; su peso prior es 0.02 y no forman parte de la escalada decisoria.

## Alternativas consideradas

### Insertar la auditoría directamente desde Python

Se descarta porque duplicaría credenciales/driver de BD en el motor y puede
crear filas huérfanas antes de que exista `fotos.id`.

### Sobrescribir la clasificación al mover

Se descarta porque destruye la evidencia original y hace imposible reconstruir
la decisión que tomó el sistema.

### Guardar atributos como texto libre del modelo

Se descarta por falta de estabilidad, privacidad y riesgo de persistir
razonamiento no controlado.

## Consecuencias

La correlación tolera el orden actual de ingesta y permite reintentos seguros.
La cola de sidecars requiere limpieza operativa de registros inválidos. El
historial crece de forma monotónica, pero permite auditoría y soporte. La
activación de VLM/OpenAI sigue gobernada por los flags existentes y degrada a
sin señal cuando el proveedor no está disponible.
