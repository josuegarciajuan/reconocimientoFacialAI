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

import imutils
import cv2, time, pandas
from datetime import datetime, timedelta




# SENSIBILIDAD_ES_CARA=0.73
SENSIBILIDAD_ES_CARA=0.68

LOCAL_ID=sys.argv[1]
CAMARA_ID=sys.argv[2]

def printLog(*args, **kwargs):
    print(*args, **kwargs)
    
    # with open('motor/procesa_videosV3_'+CAMARA_ID+'.out','a') as file:
    #     print(*args, **kwargs, file=file)



def hay_cruce(x1_lin,y1_lin,x2_lin,y2_lin,x,y,w,h):

    cruce=False
    if x1_lin<=x2_lin:
        if x1_lin-19 < (x + w) < x2_lin+19:
            cruce=True
            printLog("paso0:"+str(x + w))
    else:
        if x2_lin-19 < (x + w) < x1_lin+19:
            cruce=True
            printLog("paso1")
    if cruce:
        cruce=False
        if y1_lin<=y2_lin:
            if y1_lin-19 < (y + h) < y2_lin+19:
                cruce=True
                printLog("paso2")
        else:
            if y2_lin-19 < (y + h) < y1_lin+19:
                cruce=True  
                printLog("paso3"+str(y + h))  
    else:
        cruce=False

    return cruce



modelFile = "motor/models/res10_300x300_ssd_iter_140000.caffemodel"
configFile = "motor/models/deploy.prototxt.txt"
net = cv2.dnn.readNetFromCaffe(configFile, modelFile)


"""
INI procesaro lineas
"""
fgbg = cv2.bgsegm.createBackgroundSubtractorMOG()
kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
"""
FIN procesaro lineas
"""



frame_rate = 10 #cuanto mas alto menos fluido va, osea mas delay, y detecta mas rapido

while(True):

    aux=True

    printLog("procesando...")

    contenido = os.listdir('/home/testuser/motor/videos/'+LOCAL_ID+'/'+CAMARA_ID+'/')



    procesar=[]
    pesos=[]
    for fichero in contenido:
        name_file=os.path.join('/home/testuser/motor/videos/'+LOCAL_ID+'/'+CAMARA_ID+'/', fichero)
        file_size = os.path.getsize(name_file)

        procesar.append(fichero)
        pesos.append(file_size)

    time.sleep(5)

    procesar_definitivo=[]
    for (i, fichero) in enumerate(procesar):
        name_file=os.path.join('/home/testuser/motor/videos/'+LOCAL_ID+'/'+CAMARA_ID+'/', fichero)
        file_size = os.path.getsize(name_file)
        if file_size==pesos[i]:
            procesar_definitivo.append(fichero)
            printLog("Procesar:"+fichero)
        else:
            printLog("A medias:"+fichero)

    # exit()


    # for fichero in procesar_definitivo:
    for (josue, fichero) in enumerate(procesar_definitivo):
        aux=False
        name_file=os.path.join('/home/testuser/motor/videos/'+LOCAL_ID+'/'+CAMARA_ID+'/', fichero)
        printLog("tenemos este video:"+name_file)

        cap = cv2.VideoCapture(name_file)
        prev=0
        segundos_ini=time.time()



        
        while(cap.isOpened()):
            printLog('voy leyendo el video..')
            ret, img = cap.read()
            if ret == True:
                printLog('tenemos frame k lo guardo ..')


                #img = cv2.resize(img, None, fx=0.25, fy=0.25)
                height, width = img.shape[:2]
                #img2 = img.copy()
                time_elapsed = time.time() - prev

                # if time_elapsed > 1./frame_rate:
                # print('por time elapsed me toca analizarlo..')
                prev = time.time()
                # blob = cv2.dnn.blobFromImage(cv2.resize(img, (300, 300)),1.0, (300, 300), (104.0, 117.0, 123.0))
                #blob = cv2.dnn.blobFromImage(cv2.resize(img, (300, 300)),1.0, (323, 323), (104.0, 117.0, 123.0))
                blob = cv2.dnn.blobFromImage(cv2.resize(img, (300, 300)),1.0, (353, 353), (104.0, 117.0, 123.0))
                #blob = cv2.dnn.blobFromImage(cv2.resize(img, (300, 300)),1.0, (351, 353), (104.0, 117.0, 123.0))
                net.setInput(blob)
                faces3 = net.forward()
                
                for i in range(faces3.shape[2]):
                    confidence = faces3[0, 0, i, 2]
                    if confidence > SENSIBILIDAD_ES_CARA:

                        printLog('cara encontrada en: '+name_file)

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
                                printLog(str(e))
                                sigue=False


                        if sigue:
                            segs_elapsed = time.time() - segundos_ini
                            nombrefinal=fichero+'_'+str(segs_elapsed)
                            cv2.imwrite('motor/caras/sinclasificar/'+LOCAL_ID+'/'+CAMARA_ID+'/'+nombrefinal+'.jpg', rostro)
                            printLog("cara guardada en /"+str(LOCAL_ID)+"/"+str(CAMARA_ID)+"/"+nombrefinal+".jpg con esta confidence:"+str(confidence))

                #cv2.imshow("dnn", img)
                printLog('----------------------------------------------------------');
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
            else:
                break
        cap.release()
        
        


        #INI  - aki procesaria las lineas del video
        """
        printLog("php ws.php listado_lineas "+CAMARA_ID)
        proc = subprocess.Popen("php ws.php listado_lineas "+CAMARA_ID, shell=True, stdout=subprocess.PIPE)
        lineas = str(proc.stdout.read())
        lineas = lineas.replace("'", "")
        lineas = lineas.replace("b", "")
        v_lineas=lineas.split(",");
        longitud = len(v_lineas)
        printLog("longitud lineas: "+str(longitud))
        for iii in range(longitud):
            if v_lineas[iii]!="":
                printLog("copiar video a:"+'/home/testuser/motor/videos_lineas/'+LOCAL_ID+'/'+CAMARA_ID+'/'+v_lineas[iii]+"/"+fichero)
                copyfile(name_file, '/home/testuser/motor/videos_lineas/'+LOCAL_ID+'/'+CAMARA_ID+'/'+v_lineas[iii]+"/"+fichero)
            else:
                printLog("Sin lineas en la camara no hago nada")    
        os.remove(name_file)
        """

        printLog("php ws.php listado_lineas "+CAMARA_ID)
        proc = subprocess.Popen("php ws.php listado_lineas "+CAMARA_ID, shell=True, stdout=subprocess.PIPE)
        lineas = str(proc.stdout.read())
        lineas = lineas.replace("'", "")
        lineas = lineas.replace("b", "")
        v_lineas=lineas.split(",");
        longitud = len(v_lineas)
        printLog("longitud lineas: "+str(longitud))


        lineas_ids=[]
        v_x1=[]
        v_y1=[]
        v_x2=[]
        v_y2=[]
        fechas=[]
        ultima_creacion=[]
        hay_doble_cruce=[]

        time_inicio_cruce1=[]
        time_inicio_cruce2=[]
        cruce_iniciado1=[]
        cruce_iniciado2=[]
        tiempo_cruce1=[]
        tiempo_cruce2=[]
        time_elapsed_cruce=[]

        for iii in range(longitud):
            if v_lineas[iii]!="":
                
                LINEA_ID=v_lineas[iii]
                printLog("linea_id:"+LINEA_ID)
                proc = subprocess.Popen("php ws.php coordenadas_linea "+LINEA_ID, shell=True, stdout=subprocess.PIPE)
                coordenadas = str(proc.stdout.read())
                coordenadas = coordenadas.replace("'", "")
                coordenadas = coordenadas.replace("b", "")

                v_coordenadas=coordenadas.split(",");

                aux=name_file.split('_')
                camara_id=aux[0]
                fecha=aux[1]
                hora=aux[2]
                hora=hora.replace('.avi','')
                aux=hora.split('.')
                hora=aux[0]
                fecha_completa=fecha+' '+hora
                printLog("fecha_completa:"+fecha_completa)
                fecha_completa = datetime.strptime(fecha_completa, '%Y-%m-%d %H:%M:%S')

                lineas_ids.append(LINEA_ID)
                v_x1.append(v_coordenadas[0])
                v_y1.append(v_coordenadas[1])
                v_x2.append(v_coordenadas[2])
                v_y2.append(v_coordenadas[3])
                fechas.append(fecha_completa)
                #ultima_creacion.append(time.time())
                ultima_creacion.append(0)
                hay_doble_cruce.append(False)

                printLog("(X1,Y1) , (X2,Y2): ("+str(v_coordenadas[0])+","+str(v_coordenadas[1])+") , ("+str(v_coordenadas[2])+","+str(v_coordenadas[3])+")")

                time_inicio_cruce1.append(time.time())
                time_inicio_cruce2.append(time.time())
                cruce_iniciado1.append(False)
                cruce_iniciado2.append(False)
                tiempo_cruce1.append(0)
                tiempo_cruce2.append(0)
                time_elapsed_cruce.append(0)


            else:
                printLog("Sin lineas en la camara no hago nada")    


        cap = cv2.VideoCapture(name_file)
        segundos_ini=time.time()
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 750)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 420)

        while(cap.isOpened()):
            # printLog("frame")    
            segundos=0
            ret, frame = cap.read()
            frame_ini=frame
            if ret == False: break
            
            frame = imutils.resize(frame, width=750)
            frame = imutils.resize(frame, height=420)

            for ii in range(0,len(lineas_ids)):


                X1=int(v_x1[ii])
                X2=int(v_x2[ii])
                Y1=int(v_y1[ii])
                Y2=int(v_y2[ii])

                X1_1=X1-10
                Y1_1=Y1-10
                X2_1=X2-10
                Y2_1=Y2-10

                X1_2=X1+10
                Y1_2=Y1+10
                X2_2=X2+10
                Y2_2=Y2+10



                """
                cv2.line(frame, (X1, Y1), (X2, Y2), (0, 255, 255), 1)
                cv2.imshow('frame', frame)
                k = cv2.waitKey(70) & 0xFF
                if k ==27:
                    break
                """



                # printLog("(X1,Y1) , (X2,Y2): ("+str(X1)+","+str(Y1)+") , ("+str(X2)+","+str(Y2)+")")

                area_pts = np.array([[X1-40, Y1], [X1+40, Y1], [X2+40, Y2], [X2-40, Y2]])

                imAux = np.zeros(shape=(frame.shape[:2]), dtype= np.uint8)
                imAux = cv2.drawContours(imAux, [area_pts], -1, (255), -1)
                image_area = cv2.bitwise_and(frame, frame, mask=imAux)    

                fgmask = fgbg.apply(image_area)
                fgmask = cv2.morphologyEx(fgmask, cv2.MORPH_OPEN, kernel)
                fgmask = cv2.morphologyEx(fgmask, cv2.MORPH_CLOSE, kernel)
                fgmask = cv2.dilate(fgmask, None, iterations=5)

                cnts = cv2.findContours(fgmask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[0]
                for cnt in cnts:
                    printLog("paso1:"+str(cv2.contourArea(cnt)))
                    if cv2.contourArea(cnt) > 1500:
                        x, y, w, h = cv2.boundingRect(cnt)
                        cv2.rectangle(frame, (x,y), (x+w,y+h), (0,255,255), 1)   
                        

                        printLog("hay controno:(x,y)->("+str(x)+","+str(y)+") hasta ("+str(x+w)+","+str(y+h)+")")
                        printLog("aver qe debe cruzar->("+str(X1_1)+","+str(Y1_1)+") hasta ("+str(X2_1)+","+str(Y2_1)+")")


                        hay_doble_cruce[ii]=False
                        direccion=0


                        if hay_cruce(X1_1,Y1_1,X2_1,Y2_1,x,y,w,h) and not cruce_iniciado1[ii]:
                            printLog("se enciende la 1 a "+str(time.time()))
                            tiempo_cruce1[ii]=time.time()
                            cv2.line(frame, (X1_1, Y1_1), (X2_1, Y2_1), (0, 255, 0), 3)
                            time_elapsed_cruce[ii] = time.time() - time_inicio_cruce2[ii]
                            #if cruce_iniciado2[ii] and time_elapsed_cruce[ii]<0.2:
                            if cruce_iniciado2[ii] and time_elapsed_cruce[ii]<0.5 and time_elapsed_cruce[ii]>0.1:
                                #printLog("Ya se habia encendido la 2, por lo qe la direccion es 2 a 1 ")
                                hay_doble_cruce[ii]=True
                            else:
                                cruce_iniciado1[ii]=True
                                time_inicio_cruce1[ii]=time.time()
                                if time_elapsed_cruce[ii]>=0.2:
                                    cruce_iniciado2[ii]=False

                        if hay_cruce(X1_2,Y1_2,X2_2,Y2_2,x,y,w,h) and not hay_doble_cruce[ii] and not cruce_iniciado2[ii]:
                            printLog("se enciende la 2 a "+str(time.time()))
                            tiempo_cruce2[ii]=time.time()
                            cv2.line(frame, (X1_2, Y1_2), (X2_2, Y2_2), (0, 255, 0), 3)
                            time_elapsed_cruce[ii] = time.time() - time_inicio_cruce1[ii]
                            #if cruce_iniciado1[ii] and time_elapsed_cruce[ii]<0.2:
                            if cruce_iniciado1[ii] and time_elapsed_cruce[ii]<0.5 and time_elapsed_cruce[ii]>0.1:
                                #printLog("Ya se habia encendido la 1, por lo qe la direccion es 1 a 2 ")
                                hay_doble_cruce[ii]=True
                            else:
                                cruce_iniciado2[ii]=True
                                time_inicio_cruce2[ii]=time.time()
                                if time_elapsed_cruce[ii]>=0.2:
                                    cruce_iniciado1[ii]=False


                        if hay_doble_cruce[ii]:
                            printLog("posible doble cruce")
                            # time_elapsed = time.time() - time_inicio
                            time_elapsed = abs(tiempo_cruce1[ii]-tiempo_cruce2[ii])
                            printLog("tiempocruce1:"+str(tiempo_cruce1[ii])+" - tiempocruce2:"+str(tiempo_cruce2[ii])+"time_elapsed:"+str(time_elapsed))

                            comprueba=time.time()

                            transcurrido=0
                            if ultima_creacion[ii]>0:
                                transcurrido=comprueba-ultima_creacion[ii]
                            printLog("comprueba:"+str(comprueba)+" ,transcurrido:"+str(transcurrido)+"")

                            # if time_elapsed < 2 and (transcurrido>5 or transcurrido==0):
                            if transcurrido>3 or transcurrido==0:
                                
                                ultima_creacion[ii]=time.time()
                                
                                # printLog(fichero)

                                printLog("CRUCE, en "+str(name_file)+"!!:"+str(x + w)+"--"+str(y + h))

                                #car_counter = car_counter + 1

                                if tiempo_cruce1[ii]<tiempo_cruce2[ii]:
                                    direccion=1   #de derexa de la panatalla hacia la izquierda
                                else:
                                    direccion=2   #de izquierda de la panatalla hacia la derexa


                                tiempo_cruce1[ii]=0
                                tiempo_cruce2[ii]=0


                                if direccion == 1:
                                    # car_counter_dir1 = car_counter_dir1 +1
                                    printLog("direccion1")
                                if direccion == 2:
                                    # car_counter_dir2 = car_counter_dir2 +1    
                                    printLog("direccion2")

                                cv2.line(frame, (X1, Y1), (X2, Y2), (0, 255, 0), 3)
                                # time_inicio = time.time()
                                cruce_iniciado1[ii] = False
                                cruce_iniciado2[ii] = False


                                segs_elapsed = time.time() - segundos_ini
                                # segundos_datetime = timedelta(0, int(segundos+segs_elapsed))
                                segundos_datetime = timedelta(0, int(segs_elapsed))
                                fecha_datetime_definitiva = fechas[ii]+segundos_datetime

                                proc = subprocess.Popen("php ws.php lineas_identificadorunico", shell=True, stdout=subprocess.PIPE)
                                numrandom = str(proc.stdout.read())
                                numrandom = numrandom.replace("'", "")
                                printLog("numrandom asignado:"+numrandom)


                                cv2.imwrite("/var/www/html/reconocimientoFacial/proyecto_definitivo/motor/fotos_lineas/"+lineas_ids[ii]+"/"+numrandom+".jpg",frame_ini)

                                cmd="php ws.php guarda_cruce "+str(lineas_ids[ii])+" '"+str(fecha_datetime_definitiva)+"' "+str(direccion)+" "+str(x+w)+" "+str(y+h)+" "+str(numrandom)
                                printLog(cmd)
                                proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)

                            else:
                                printLog("por tiempo no lo cuento:"+"time_elapsed:"+str(time_elapsed)+",transcurrido:"+str(transcurrido))

                                


                            printLog()


        cap.release()
        ## FIN procesar lineas del video

        os.remove(name_file)




        #exit() 



    if cv2.waitKey(1) & 0xFF == ord('q'):
        break


    if aux:
        time.sleep(1)
       

    # exit()     

cv2.destroyAllWindows()



    