import cv2
import os
import sys

# Args: <camara_id> <url_rtsp> <ruta_proyecto> [ancho]
# Snapshot LIGERO para la rejilla "Cámaras en directo":
#   - reescala a `ancho` px (def. 640, como el live MJPEG) manteniendo proporción;
#   - guarda JPEG (def. q80) en admin/fotos_camara/<id>.jpg;
#   - escritura atómica (.tmp.jpg -> os.replace) para que el navegador nunca
#     lea un fichero a medias.
# Antes se guardaba PNG a resolución completa (varios MB): la rejilla se
# re-descargaba entera cada 15 s y tardaba muchísimo en pintarse.
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

filename = RUTA_PROYECTO + "admin/fotos_camara/" + CAMARA_ID + ".jpg"

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
    tmp = filename + ".tmp.jpg"
    if not cv2.imwrite(tmp, frame, [cv2.IMWRITE_JPEG_QUALITY, CALIDAD]):
        sys.exit(3)
    os.replace(tmp, filename)  # atómico en el mismo sistema de ficheros
finally:
    cap.release()
# headless: sin destroyAllWindows
