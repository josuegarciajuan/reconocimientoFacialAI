"""Reparación de identidades ``face_enc_v2``: fragmentación y contaminación.

Este paquete implementa el flujo en dos fases del plan de saneamiento:

- ``proponer_reparacion``: **solo lectura**. A partir de las etiquetas
  ground-truth del usuario (``[{id, cod_interno, persona}]``) y del store,
  propone (a) fusiones de fragmentos de la misma persona real y (b)
  movimientos/purgas de encodings contaminados de otra persona. Nunca escribe.
- ``aplicar_reparacion``: aplica una propuesta con **dry-run por defecto**,
  snapshot completo del store, journal JSONL y reversibilidad
  (``FaceStore.merge_undoable`` + ``restore_person``).

Reglas de seguridad del proyecto (AGENTS.md):

- Los datos vivos (store, ``caras/``, BD) viven **solo en producción**. Este
  código se limita a leer/proponer en dev y a aplicar en producción.
- Nada se ejecuta sin ``--si``; sin él, ``aplicar_reparacion`` es dry-run.
- Toda mutación deja backup en ``motor/backups/reparacion/<ts>/`` (gitignored).
"""
from __future__ import annotations

__all__ = ["proponer_reparacion", "aplicar_reparacion"]
