"""Prompt compartido de identidad para las capas VLM (local y OpenAI).

Contrato validado (docs de F0-F7, sección 7): ambas capas usan EXACTAMENTE
el mismo prompt y devuelven JSON estricto:
    {"probability_same": 0.0..1.0, "confidence": 0.0..1.0,
     "reasoning": "<1-2 frases>", "skip": bool}

Mapeo para la fusión:
    s_vlm = probability_same
    c_vlm = |probability_same - 0.5| * 2   (0 en el centro -> capa no concluyente)
    si skip=true -> c_vlm = 0 (capa no disponible)
"""
from __future__ import annotations

SYSTEM_PROMPT = """Eres un verificador de identidad para videovigilancia interior.
Comparas DOS fotografias y decides si son la MISMA persona o personas DISTINTAS.
Las fotos son recortes de baja calidad y la misma persona puede aparecer en angulos
MUY distintos (frente, perfil, espaldas) y con distinta iluminacion. Un cambio de angulo
NO es motivo para decir que son personas distintas. Centrate SOLO en rasgos de identidad
estables: estructura facial (mandibula, nariz, orejas, distancia entre ojos, pomulos, menton),
pelo (color, estilo, linea de nacimiento), complexion/tono de piel y complexion corporal,
y si se ve, atuendo/ropa solo como apoyo secundario.
Responde SIEMPRE en JSON estricto con estas claves:
{"probability_same": <0.0..1.0>, "confidence": <0.0..1.0>, "reasoning": "<1-2 frases>", "skip": <bool>}.
Escala de probability_same: 0.95-1.0 = misma persona sin duda razonable; 0.80 = muy probable si;
0.65 = inclinado a si; 0.50 = imposible decidir; 0.35 = inclinado a no; 0.20 = probablemente distinta;
0.00-0.05 = claramente distinta. Si no ves una cara identificable en alguna imagen: "skip": true,
"probability_same": 0.5. No inventes rasgos que no ves."""

USER_PROMPT = "Compara la Imagen A (primera) y la Imagen B (segunda)."


def map_to_layer(result: dict) -> tuple[float, float]:
    """Convierte la respuesta JSON del VLM a (s, c) de capa para la fusión.

    - s = probability_same (0..1)
    - c = |probability_same - 0.5| * 2  (0.5 -> 0: capa no concluyente)
    - skip=true -> c = 0 (capa no disponible)
    """
    try:
        p = float(result.get("probability_same", 0.5))
        skip = bool(result.get("skip", False))
    except (TypeError, ValueError):
        return 0.5, 0.0
    p = max(0.0, min(1.0, p))
    if skip:
        return 0.5, 0.0
    return p, abs(p - 0.5) * 2.0
