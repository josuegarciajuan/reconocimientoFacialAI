"""Auditoría y evaluación del motor de reconocimiento facial (Fase 0).

Instrumentos **read-only** para medir la fragmentación de identidades y la
contaminación de galerías del store `face_enc_v2`, más un banco de evaluación
etiquetado para calcular TAR/FAR por umbral.

Módulos:
    - ``auditar_identidades``: analizador de un store ``face_enc_v2``.
    - ``banco_eval``: partición referencia/queries y métricas TAR/FAR.

Ninguno de estos módulos accede a MySQL, a red ni escribe sobre el store.
"""
