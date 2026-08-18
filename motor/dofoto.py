import cv2
import numpy as np
import os
import sys

# Args: <camara_id> <url_rtsp> <ruta_proyecto>
URL_CONEXION = sys.argv[2]
CAMARA_ID = sys.argv[1]
RUTA_PROYECTO = sys.argv[3]

filename = RUTA_PROYECTO + "admin/fotos_camara/" + CAMARA_ID + ".png"

# RTSP sobre TCP (evita pérdidas UDP) y timeout de conexión razonable,
# para no colgarse cuando una cámara no responde.
os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp|timeout;5000000"

cap = cv2.VideoCapture(URL_CONEXION)
try:
    ret, frame = cap.read()
    if not ret or frame is None:
        # Sin señal: conservar el snapshot anterior (no borrar ni escribir basura)
        sys.exit(2)
    cv2.imwrite(filename, frame)
finally:
    cap.release()
# headless: sin destroyAllWindows
