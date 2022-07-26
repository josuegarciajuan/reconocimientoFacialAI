import cv2, time, pandas
from datetime import datetime
import pysftp
import os
import _thread
import sys

sys.path.append(".")
from fifo import fifo


# python3.7 motor/guarda_movimientos.py camaras.vps.webdock.io testuser prueba123 'rtsp://admin:bakcAse4@172.16.51.52:554/cam/realmonitor?channel=1&subtype=0' 2 6 KszrR2H1snGs

#URL_CONEXION='rtsp://admin:bakcAse4@nouesmalt.duckdns.org:778/cam/realmonitor?channel=1&subtype=0'

URL_CONEXION='rtsp://admin:bakcAse4@172.16.51.52:554/cam/realmonitor?channel=1&subtype=0'

#URL_CONEXION=1


# Capturing video
#video = cv2.VideoCapture(1)
#video = cv2.VideoCapture('rtsp://admin:bakcAse4@172.16.51.52:554/cam/realmonitor?channel=1&subtype=0')
video = cv2.VideoCapture(URL_CONEXION)

if not (video.isOpened()):
    print("Could not open video device")
else:
    print("video opened")
# exit()


video.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
video.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

while True:
    check, frame = video.read()

    cv2.imshow("Color Frame", frame)

    key = cv2.waitKey(80)
    if key == ord('q'):
        break


video.release()
cv2.destroyAllWindows()

