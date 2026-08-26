# ADR-0001: Paginado server-side para listados administrativos

## Estado

Aceptado — 2026-08-26

## Contexto

Los listados administrativos cargaban todas las filas en el HTML y dejaban el
paginado a DataTables en el navegador. Esto aumentaba memoria, tiempo de carga
y exposición de datos, además de favorecer consultas N+1.

## Decisión

Se adopta un endpoint JSON común (`admin/datatables.php`) con un parámetro de
listado explícito. Todos los listados usan `serverSide: true`, `processing: true`
y `pageLength: 100`. Los endpoints normalizan `draw`, `start` y `length`,
responden con el contrato DataTables, usan consultas preparadas, `COUNT`
separado, `LIMIT/OFFSET` y whitelist de columnas de ordenación.

Rutas pagina las estancias candidatas antes de construir cada recorrido; la
construcción completa continúa disponible para el reproductor bajo demanda.

## Alternativas consideradas

- Mantener paginado cliente: menor cambio, pero sigue descargando todos los datos.
- Crear un endpoint distinto por pantalla: separa responsabilidades, pero
  duplica contrato, validación y mantenimiento.
- Endpoint común con dispatch explícito: elegido por consistencia y menor
  coordinación, manteniendo SQL específico por dominio.

## Consecuencias

- Las tablas dejan de incluir filas de datos en la respuesta inicial.
- Las consultas de página son acotadas y los contadores son independientes.
- La representación HTML de algunas acciones históricas se simplifica en el
  primer corte; debe ampliarse en endpoints donde se requieran vídeos y acciones
  específicas adicionales.
- Los selectores de filtros siguen cargando sus opciones completas, al no ser
  tablas DataTables.
