# -*- coding: utf-8 -*-

#   motor/python3.7 motor/procesa_videosV4.py LOCAL_ID CAMARA_ID CAMARA_ID_ENLOCAL


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


LOCAL_ID=sys.argv[1]
CAMARA_ID=sys.argv[2]
CAMARA_ID_ENLOCAL=sys.argv[3]



modelFile = "motor/models/res10_300x300_ssd_iter_140000.caffemodel"
configFile = "motor/models/deploy.prototxt.txt"
net = cv2.dnn.readNetFromCaffe(configFile, modelFile)


frame_rate = 10 #cuanto mas alto menos fluido va, osea mas delay, y detecta mas rapido

while(True):

    aux=True

    print("procesando...")

    contenido = os.listdir('/home/testuser/motor/videos/'+LOCAL_ID+'/')


    for fichero in contenido:
        aux=False
        name_file=os.path.join('/home/testuser/motor/videos/'+LOCAL_ID+'/', fichero)
        print("tenemos este video:"+name_file)

        # nombre final como se tiene qe qedar en sin clasificar 3_2021-07-21_10:58:14.268470.avi_1.2.jpg
        # el nombre del video como viene aki: HCVR_ch1_main_20210726000000_20210726015959.dav

        aux=fichero.split('_')
        camara_fichero=aux[1]
        camara_fichero=segundos.replace('ch','')
        fecha_video=aux[3]
        yyyy=fecha_video[0,4]
        mm=fecha_video[4,6]
        dd=fecha_video[6,8]
        hh=fecha_video[8,10]
        mi=fecha_video[10,12]
        ss=fecha_video[12,14]

        nombre_def=CAMARA_ID+"_"+yyyy+"-"+mm+"-"+dd+"_"+hh+":"+mi+":"+ss+".000000.avi"



        if camara_fichero==CAMARA_ID_ENLOCAL:        

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
                        if confidence > 0.20:

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
                                nombrefinal=nombre_def+'_'+str(segs_elapsed)
                                cv2.imwrite('motor/caras/sinclasificar/'+LOCAL_ID+'/'+CAMARA_ID+'/'+nombrefinal+'.jpg', rostro)
                                print("cara guardada en /"+str(LOCAL_ID)+"/"+str(CAMARA_ID)+"/"+nombrefinal+".jpg con esta confidence:"+str(confidence))

                    #cv2.imshow("dnn", img)
                    print('----------------------------------------------------------');
                    if cv2.waitKey(1) & 0xFF == ord('q'):
                        break
                else:
                    break
            cap.release()


            print("php ws.php listado_lineas "+CAMARA_ID)
            proc = subprocess.Popen("php ws.php listado_lineas "+CAMARA_ID, shell=True, stdout=subprocess.PIPE)
            lineas = str(proc.stdout.read())
            lineas = lineas.replace("'", "")
            lineas = lineas.replace("b", "")
            v_lineas=lineas.split(",");
            longitud = len(v_lineas)
            print("longitud lineas: "+str(longitud))
            for iii in range(longitud):
                if v_lineas[iii]!="":
                    print("copiar video a:"+'/home/testuser/motor/videos_lineas/'+LOCAL_ID+'/'+CAMARA_ID+'/'+v_lineas[iii]+"/"+fichero)
                    copyfile(name_file, '/home/testuser/motor/videos_lineas/'+LOCAL_ID+'/'+CAMARA_ID+'/'+v_lineas[iii]+"/"+fichero)
                else:
                    print("Sin lineas en la camara no hago nada")    
            os.remove(name_file)


    if cv2.waitKey(1) & 0xFF == ord('q'):
        break


    if aux:
        time.sleep(1)
         

cv2.destroyAllWindows()



    