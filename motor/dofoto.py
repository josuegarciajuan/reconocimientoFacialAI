import cv2
import os
import sys
import urllib.request

import numpy as np

# Args: <camara_id> <url_rtsp> <ruta_proyecto> [ancho]
# Snapshot LIGERO para la rejilla "Cámaras en directo":
#   - camaraip: descarga `latest.jpg` del bridge (sin reencode si no hay resize);
#   - RTSP: mantiene VideoCapture y reescala a `ancho`;
#   - guarda JPEG (def. q80) en admin/fotos_camara/<id>.jpg;
#   - escritura atómica (.tmp.jpg -> os.replace).
CAMARA_ID = sys.argv[1]
URL_CONEXION = sys.argv[2]
RUTA_PROYECTO = sys.argv[3]
try:
    ANCHO = int(sys.argv[4])
except (IndexError, ValueError):
    ANCHO = 640
if ANCHO < 160:
    ANCHO = 640
CALIDAD = int(os.environ.get("RF_SNAP_QUALITY", "80"))

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from motor.core.camara_perfil import camera_id_from_url, latest_jpeg_url  # noqa: E402

filename = RUTA_PROYECTO + "admin/fotos_camara/" + CAMARA_ID + ".jpg"
tmp = filename + ".tmp.jpg"


def _guardar_bytes(data):
    if not (len(data) > 4 and data[:2] == b"\xff\xd8" and data[-2:] == b"\xff\xd9"):
        return 2
    with open(tmp, "wb") as fh:
        fh.write(data)
    os.replace(tmp, filename)
    return 0


def _guardar_latest(url):
    """Descarga el último JPEG del bridge y lo guarda sin abrir el stream."""
    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            data = response.read()
    except Exception:
        return 2
    if not (len(data) > 4 and data[:2] == b"\xff\xd8" and data[-2:] == b"\xff\xd9"):
        return 2

    # Si no hay que reducir, se copia el JPEG tal cual: conserva la calidad y
    # el tamaño que ya ha fijado el perfil de camaraESP.
    frame = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
    if frame is None:
        return 2
    alto, ancho_orig = frame.shape[:2]
    if ancho_orig <= ANCHO:
        return _guardar_bytes(data)

    alto_dst = max(1, int(round(alto * ANCHO / ancho_orig)))
    frame = cv2.resize(frame, (ANCHO, alto_dst), interpolation=cv2.INTER_AREA)
    if not cv2.imwrite(tmp, frame, [cv2.IMWRITE_JPEG_QUALITY, CALIDAD]):
        return 3
    os.replace(tmp, filename)
    return 0


# camaraip: usar el frame ya capturado por el bridge. Evita abrir un stream
# nuevo con OpenCV y el frame negro inicial.
if camera_id_from_url(URL_CONEXION):
    url_latest = latest_jpeg_url(URL_CONEXION)
    if not url_latest:
        sys.exit(2)
    sys.exit(_guardar_latest(url_latest))

# RTSP sobre TCP (evita pérdidas UDP) y timeout de conexión razonable,
# para no colgarse cuando una cámara no responde.
os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp|timeout;5000000"

cap = cv2.VideoCapture(URL_CONEXION)
try:
    ret, frame = cap.read()
    if not ret or frame is None:
        # Sin señal: conservar el snapshot anterior (no borrar ni escribir basura)
        sys.exit(2)
    alto, ancho_orig = frame.shape[:2]
    if ancho_orig > ANCHO:
        alto_dst = max(1, int(round(alto * ANCHO / ancho_orig)))
        frame = cv2.resize(frame, (ANCHO, alto_dst), interpolation=cv2.INTER_AREA)
    # .tmp.jpg (no .tmp): cv2.imwrite infiere el formato por la extensión.
    if not cv2.imwrite(tmp, frame, [cv2.IMWRITE_JPEG_QUALITY, CALIDAD]):
        sys.exit(3)
    os.replace(tmp, filename)  # atómico en el mismo sistema de ficheros
finally:
    cap.release()
# headless: sin destroyAllWindows
