# -*- coding: utf-8 -*-
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



LOCAL_ID="1"
CAMARA_ID="1"



modelFile = "motor/models/res10_300x300_ssd_iter_140000.caffemodel"
configFile = "motor/models/deploy.prototxt.txt"
net = cv2.dnn.readNetFromCaffe(configFile, modelFile)


frame_rate = 10 #cuanto mas alto menos fluido va, osea mas delay, y detecta mas rapido



aux=True

print("procesando...")

contenido = os.listdir('motor/videos/'+LOCAL_ID)


for fichero in contenido:
    aux=False
    name_file=os.path.join('motor/videos/'+LOCAL_ID+'/', fichero)
    print("tenemos este video:"+name_file)

    cap = cv2.VideoCapture(name_file)
    prev=0
    segundos_ini=time.time()
    while(cap.isOpened()):
        print('voy leyendo el video..')
        ret, img = cap.read()
        if ret == True:
            print('tenemos frame k lo guardo ..')


            #img = cv2.resize(img, None, fx=0.25, fy=0.25)
            height, width = img.shape[:2]
            #img2 = img.copy()
            time_elapsed = time.time() - prev

            # if time_elapsed > 1./frame_rate:
            # print('por time elapsed me toca analizarlo..')
            prev = time.time()
            blob = cv2.dnn.blobFromImage(cv2.resize(img, (300, 300)),1.0, (300, 300), (104.0, 117.0, 123.0))
            net.setInput(blob)
            faces3 = net.forward()
            
            for i in range(faces3.shape[2]):
                confidence = faces3[0, 0, i, 2]
                if confidence > 0.7:

                    print('cara encontrada en: '+name_file)

                    box = faces3[0, 0, i, 3:7] * np.array([width, height, width, height])
                    (x, y, x1, y1) = box.astype("int")
                    #cv2.rectangle(img2, (x, y), (x1, y1), (0, 0, 255), 2)


                    ydef=y-100
                    if ydef<0:
                        ydef=0
                    y1def=y1+100
                    if y1def>height:
                        y1def=height-1

                    xdef=x-100
                    if xdef<0:
                        xdef=0
                    x1def=x1+100
                    if x1def>width:
                        x1def=width-1    


                    rostro = img[ydef:y1def, xdef:x1def]
                    # rostro = img[y-50:y1+50, x-50:x1+50]


                    sigue=True
                    if(type(rostro) == type(None)):
                        sigue=False
                    else:
                        try:
                            rostro = cv2.resize(rostro, (150, 150), interpolation=cv2.INTER_CUBIC)
                        except Exception as e:
                            print(str(e))
                            sigue=False


                    if sigue:
                        segs_elapsed = time.time() - segundos_ini
                        nombrefinal=fichero+'_'+str(segs_elapsed)
                        cv2.imwrite('motor/caras/sinclasificar/'+LOCAL_ID+'/'+CAMARA_ID+'/'+nombrefinal+'.jpg', rostro)
                        print("cara guardada en /"+str(LOCAL_ID)+"/"+str(CAMARA_ID)+"/"+nombrefinal+".jpg con esta confidence:"+str(confidence))

            #cv2.imshow("dnn", img)

    cap.release()

cv2.destroyAllWindows()



    