import cv2
import numpy as np
import time
import os
import pickle
import face_recognition
import _thread
from imutils import paths
import sys
import subprocess
from shutil import copyfile
from filelock import FileLock


import imutils
import cv2, time, pandas
from datetime import datetime, timedelta
import dlib

sys.path.append(".")
from facealigner import FaceAligner



LOCAL_ID=sys.argv[1]
FICHERO=sys.argv[2]
HILO=sys.argv[3]
CAMARA_ID="0"
#RUTA_PROYECTO="/var/www/html/reconocimientoFacial/proyecto_definitivo/"
#RUTA_PROYECTO="/var/www/html/reconocimientofacialV2/"
RUTA_PROYECTO=sys.argv[4]
fecha_aux=sys.argv[5]
CADACUANTOSFRAMESSECOGEUNOPARAVERSIHAYCARA=sys.argv[6]
SENSIBILIDAD_ES_CARA=float(sys.argv[7])
PORCENTAJECARASCOJO=float(sys.argv[8])

time_ini = time.time()


def printLog(*args, **kwargs):
    # print(*args, **kwargs)
    
    with open(RUTA_PROYECTO + 'motor/logs/procesa_videos_registro_1_' + HILO + '.out','a') as file:
       print(*args, **kwargs, file=file)


"""
----------------------------------------------------------------------------------------------------------------------------------------------------------------------
sacar imagenes con posibles caras de un video
----------------------------------------------------------------------------------------------------------------------------------------------------------------------
"""




modelFile = RUTA_PROYECTO + "motor/models/res10_300x300_ssd_iter_140000.caffemodel"
configFile = RUTA_PROYECTO + "motor/models/deploy.prototxt.txt"
net = cv2.dnn.readNetFromCaffe(configFile, modelFile)


name_file=os.path.join(RUTA_PROYECTO + 'admin/files/videos_registro_videos_partidos/', FICHERO)


printLog("tenemos este video:"+name_file)
cap = cv2.VideoCapture(name_file)

prev=0
segundos_ini=time.time()
num_frame=0



caras_cogidas=0
while(cap.isOpened()):
    printLog('voy(' + HILO + ') leyendo el video..')
    ret, img = cap.read()
    if ret == True:
        printLog('tenemos(' + HILO + ') frame k lo guardo ..')
        num_frame=num_frame+1

        if num_frame % int(CADACUANTOSFRAMESSECOGEUNOPARAVERSIHAYCARA) == 0:


            #img = cv2.resize(img, None, fx=0.25, fy=0.25)
            height, width = img.shape[:2]
            height1, width1 = img.shape[:2]
            time_elapsed = time.time() - prev
            prev = time.time()

            img_original=img
            img_test=img



            # blob = cv2.dnn.blobFromImage(cv2.resize(img_original, (300, 300)),1.0, (353, 353), (104.0, 117.0, 123.0))
            blob = cv2.dnn.blobFromImage(img_original,1.0)
            net.setInput(blob)
            faces3 = net.forward()
            
            for i in range(faces3.shape[2]):
                confidence = faces3[0, 0, i, 2]
                if confidence > SENSIBILIDAD_ES_CARA:

                    caras_cogidas=caras_cogidas+1
                    coger=False
                    if caras_cogidas==PORCENTAJECARASCOJO:
                        caras_cogidas=0
                        coger=True

                    if coger:
                        printLog('cara encontrada en: '+name_file)

                        box = faces3[0, 0, i, 3:7] * np.array([width1, height1, width1, height1])
                        (x, y, x1, y1) = box.astype("int")
                        #cv2.rectangle(img2, (x, y), (x1, y1), (0, 0, 255), 2)


                        ydef=y-100
                        if ydef<0:
                            ydef=0
                        y1def=y1+100
                        if y1def>height1:
                            y1def=height1-1

                        xdef=x-100
                        if xdef<0:
                            xdef=0
                        x1def=x1+100
                        if x1def>width1:
                            x1def=width1-1    


                        #asdrostro = img_original[ydef:y1def, xdef:x1def]
                        rostro = img_original



                        sigue=True
                        #asdif(type(rostro) == type(None)):
                        #asd    sigue=False
                        #asdelse:
                            
                            #asd try:
                                # rostro = cv2.resize(rostro, (150, 150), interpolation=cv2.INTER_CUBIC)
                            #asd     rostro = cv2.resize(rostro, (250, 250), interpolation=cv2.INTER_CUBIC)
                            #asd except Exception as e:
                            #asd     printLog(str(e))
                            #asd     sigue=False



                        if sigue:
                            segs_elapsed = time.time() - segundos_ini
                            # nombrefinal=FICHERO+"_"+HILO+'_'+str(segs_elapsed)

                            aux = str(datetime.now())
                            lastsix_fecha=aux[-6:]
                            now=fecha_aux+"."+lastsix_fecha


                            nombrefinal='0_'+now+'.avi_'+str(segs_elapsed)


                            cv2.imwrite(RUTA_PROYECTO + 'motor/caras/sinclasificar_videos/'+nombrefinal+'.jpg', rostro)
                                

                            printLog("cara guardada en /"+nombrefinal+".jpg con esta confidence:"+str(confidence))

            
        # cv2.imshow("dnn", img)
        #printLog('----------------------------------------------------------');
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    else:
        break
cap.release()
cv2.destroyAllWindows()


os.remove(name_file)

printLog("Llego al final y remuevo el video!")
    

time_elapsed = time.time() - time_ini
printLog("Tiempo de analizar el video:" + str(time_elapsed))


