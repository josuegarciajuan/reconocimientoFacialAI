import cv2
import numpy as np
import os
import sys

URL_CONEXION=sys.argv[2]
CAMARA_ID=sys.argv[1]
RUTA_PROYECTO=sys.argv[3]

filename=RUTA_PROYECTO+"admin/fotos_camara/"+CAMARA_ID+".png"

if os.path.isfile(filename):
    os.remove(filename)


cap= cv2.VideoCapture(URL_CONEXION)
ret, frame = cap.read()
cv2.imwrite(filename,frame)
cap.release()
# headless: sin destroyAllWindows



# python3.7 /var/www/html/reconocimientoFacial/proyecto_definitivo/motor/dofoto.py 2 rtsp://admin:bakcAse4@nouesmalt.duckdns.org:777/cam/realmonitor?channel=1&subtype=0
# python3.7 motor/guarda_movimientos.py 46.249.32.179 testuser prueba123 'rtsp://admin:bakcAse4@nouesmalt.duckdns.org:777/cam/realmonitor?channel=1&subtype=0' 1 1
# python3.7 motor/guarda_movimientos.py 46.249.32.179 testuser prueba123 'rtsp://admin:bakcAse4@172.16.51.50:554/cam/realmonitor?channel=1&subtype=0' 1 1
# python3.7 /var/www/html/reconocimientoFacial/proyecto_definitivo/motor/dofoto.py 1 rtsp://admin:bakcAse4@nouesmalt.duckdns.org:778/cam/realmonitor?channel=1&subtype=0 kk