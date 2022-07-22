# python3.7 motor/cruce_lineas_pruebas.py pruebas 6 6_2021-09-28_13:26:11.475085.avi
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
import dlib



LOCAL_ID=sys.argv[1]
CAMARA_ID=sys.argv[2]
FICHERO=sys.argv[3]

def printLog(*args, **kwargs):
    print(*args, **kwargs)
    
    with open('/var/www/html/reconocimientoFacial/proyecto_definitivo/motor/cruce_lineas_pruebas.txt','a') as file:
       print(*args, **kwargs, file=file)



def hay_cruce_bck(x1_lin,y1_lin,x2_lin,y2_lin,x,y,w,h):

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
                # printLog("paso2")
        else:
            if y2_lin-19 < (y + h) < y1_lin+19:
                cruce=True  
                # printLog("paso3"+str(y + h))  
    else:
        cruce=False

    return cruce


def hay_cruce(x1_lin,y1_lin,x2_lin,y2_lin,x,y,w,h):

    cruce=False

    printLog("Test hay_cruce x1_lin,y1_lin,x2_lin,y2_lin,x,y,w,h:::" + str(x1_lin)+"--"+str(y1_lin)+"--"+str(x2_lin)+"--"+str(y2_lin)+"--"+str(x)+"--"+str(y)+"--"+str(w)+"--"+str(h))


    if x1_lin<=x2_lin:
        izq=x1_lin
        der=x2_lin
    else:  #x2_lin<x1_lin
        izq=x2_lin
        der=x1_lin



    if y1_lin<=y2_lin:
        abajo=y1_lin
        arriba=y2_lin
    else:  #y2_lin<y1_lin
        arriba=y2_lin
        abajo=y1_lin


    printLog("izq:"+str(izq)+"--der:"+str(der)+"//////"+"abajo:"+str(abajo)+"--arriba:"+str(arriba))


    cruce_h=False
    i=izq-5
    while i<=(der+5):
        #printLog("i1:"+str(i))
        c=x
        while c<=(x+w):
            #printLog("c1:"+str(c))
            if c==i:
                cruce_h=True     
            c=c+1
        i=i+1


    cruce_v=False
    i=abajo-5
    while i<=(arriba+5):
        #printLog("i2:"+str(i))
        c=y
        while c<=(y+h):
            #printLog("c2:"+str(c))
            if c==i:
                cruce_v=True     
            c=c+1
        i=i+1


    if cruce_h and cruce_v:
        cruce=True
        printLog("Tenemos cruce")


    return cruce



modelFile = "/var/www/html/reconocimientoFacial/proyecto_definitivo/motor/models/res10_300x300_ssd_iter_140000.caffemodel"
configFile = "/var/www/html/reconocimientoFacial/proyecto_definitivo/motor/models/deploy.prototxt.txt"
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



aux=True

printLog("procesando...")



#-INI-procesamiento de lineas

printLog("php /var/www/html/reconocimientoFacial/proyecto_definitivo/ws.php listado_lineas "+CAMARA_ID)
proc = subprocess.Popen("php /var/www/html/reconocimientoFacial/proyecto_definitivo/ws.php listado_lineas "+CAMARA_ID, shell=True, stdout=subprocess.PIPE)
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

frame_cruce1=[]
frame_cruce2=[]

num_frame=0

tiene_lineas=False
for iii in range(longitud):
    if v_lineas[iii]!="":
        
        tiene_lineas=True

        LINEA_ID=v_lineas[iii]
        printLog("linea_id:"+LINEA_ID)
        proc = subprocess.Popen("php /var/www/html/reconocimientoFacial/proyecto_definitivo/ws.php coordenadas_linea "+LINEA_ID, shell=True, stdout=subprocess.PIPE)
        coordenadas = str(proc.stdout.read())
        coordenadas = coordenadas.replace("'", "")
        coordenadas = coordenadas.replace("b", "")

        v_coordenadas=coordenadas.split(",");

        aux=FICHERO.split('_')
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


        frame_cruce1.append(0)
        frame_cruce2.append(0)



    else:
        tiene_lineas=False
        printLog("Sin lineas en la camara no hago nada")    



#-FIN-procesamiento de lineas



aux=False

#name_file=os.path.join('/home/testuser/motor/videos/'+LOCAL_ID+'/'+CAMARA_ID+'/', FICHERO)
name_file=os.path.join('/home/testuser/motor/videos/'+LOCAL_ID+'/'+CAMARA_ID+'/', FICHERO)



printLog("tenemos este video:"+name_file)

cap = cv2.VideoCapture(name_file)
prev=0
segundos_ini=time.time()

cap.set(cv2.CAP_PROP_FRAME_WIDTH, 750)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 420)


while(cap.isOpened()):
    #printLog('voy leyendo el video..')
    ret, img = cap.read()
    if ret == True:
        #printLog('tenemos frame k lo guardo ..')
        num_frame=num_frame+1


        #img = cv2.resize(img, None, fx=0.25, fy=0.25)
        height, width = img.shape[:2]
        height1, width1 = img.shape[:2]
        #img2 = img.copy()
        time_elapsed = time.time() - prev
        prev = time.time()


        img_original=img





        #-INI-procesamiento de lineas
        if tiene_lineas:

            frame_ini=img
            
            img = imutils.resize(img, width=750)
            img = imutils.resize(img, height=420)



            for ii in range(0,len(lineas_ids)):


                printLog("Analizando linea_id:"+str(lineas_ids[ii]))

                X1=int(v_x1[ii])
                Y1=int(v_y1[ii])

                X2=int(v_x2[ii])
                Y2=int(v_y2[ii])


                X1_1=X1-3
                Y1_1=Y1-3
                X1_2=X1+3
                Y1_2=Y1+3


                X2_1=X2-3
                Y2_1=Y2-3
                X2_2=X2+3
                Y2_2=Y2+3


                
                cv2.line(img, (X1, Y1), (X2, Y2), (0, 255, 255), 1)
                #cv2.imshow('frame', img)
                """
                k = cv2.waitKey(70) & 0xFF
                if k ==27:
                    break
                """

                #cv2.line(img, (X1_1, Y1_1), (X2_1, Y2_1), (0, 255, 255), 1)
                #cv2.imshow('frame', img)
                #cv2.line(img, (X1_2, Y1_2), (X2_2, Y2_2), (0, 255, 255), 1)
                #cv2.imshow('frame', img)

                
                if time.time() - time_inicio_cruce1[ii] > 2:
                    cruce_iniciado1[ii]=False  
                if time.time() - time_inicio_cruce2[ii] > 2:
                    cruce_iniciado2[ii]=False        


                """
                printLog(lineas_ids[ii]+"-start:"+str(X1-5)+","+str(Y1-5))
                printLog(lineas_ids[ii]+"-end:"+str(X2+5)+","+str(Y2+5))
                color=(255, 0, 0)
                thickness=3
                cv2.rectangle(img, (int(X1)-5, int(Y1)-5), (int(X2)+5, int(Y2)+5), color, thickness)
                #cv2.rectangle(img, (271,125), (379,131), (0, 0, 100), 3)
                """



                
                area_pts = np.array([[X1-5, Y1-5], [X1+5, Y1+5], [X2+5, Y2+5], [X2-5, Y2-5]])

                imAux = np.zeros(shape=(img.shape[:2]), dtype= np.uint8)

                imAux = cv2.drawContours(imAux, [area_pts], -1, (255), -1)
                image_area = cv2.bitwise_and(img, img, mask=imAux)    

                fgmask = fgbg.apply(image_area)
                fgmask = cv2.morphologyEx(fgmask, cv2.MORPH_OPEN, kernel)
                fgmask = cv2.morphologyEx(fgmask, cv2.MORPH_CLOSE, kernel)
                fgmask = cv2.dilate(fgmask, None, iterations=5)



                #imAux = cv.cvtColor(imAux, cv.COLOR_BGR2GRAY)
                #ret11, imAux = cv.threshold(imAux, 127, 255, 0)



                cnts = cv2.findContours(fgmask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[0]
                for cnt in cnts:
                    #printLog("paso1:"+str(cv2.contourArea(cnt)))
                    if cv2.contourArea(cnt) > 1500:
                        x, y, w, h = cv2.boundingRect(cnt)
                        cv2.rectangle(img, (x,y), (x+w,y+h), (0,100,100), 1)   

                        printLog("hay controno:(x,y)->("+str(x)+","+str(y)+") hasta ("+str(x+w)+","+str(y+h)+")")
                        printLog("a ver qe debe cruzar->("+str(X1_1)+","+str(Y1_1)+") hasta ("+str(X2_1)+","+str(Y2_1)+")")


                        if hay_cruce(X1_1,Y1_1,X2_1,Y2_1,x,y,w,h) and not cruce_iniciado1[ii]:
                            printLog("se enciende la 1 a "+str(time.time()))
                            tiempo_cruce1[ii]=time.time()
                            frame_cruce1[ii]=num_frame
                            cv2.line(img, (X1_1, Y1_1), (X2_1, Y2_1), (0, 255, 255), 3)
                            time_inicio_cruce1[ii]=time.time()

                            if cruce_iniciado2[ii]:
                                printLog("Ya se habia encendido la 2, por lo qe la direccion es 2 a 1 ")
                                hay_doble_cruce[ii]=True
                            else:
                                cruce_iniciado1[ii]=True
                                time_elapsed_cruce[ii]=time_inicio_cruce1[ii]-time_inicio_cruce2[ii]
                                if time_elapsed_cruce[ii]>=1:
                                    cruce_iniciado2[ii]=False


                        #if hay_cruce(X1_2,Y1_2,X2_2,Y2_2,x,y,w,h) and not hay_doble_cruce[ii] and not cruce_iniciado2[ii]:
                        if hay_cruce(X1_2,Y1_2,X2_2,Y2_2,x,y,w,h) and not cruce_iniciado2[ii]:
                            printLog("se enciende la 2 a "+str(time.time()))
                            tiempo_cruce2[ii]=time.time()
                            frame_cruce2[ii]=num_frame
                            cv2.line(img, (X1_2, Y1_2), (X2_2, Y2_2), (255, 255, 0), 3)
                            time_inicio_cruce2[ii]=time.time()

                            if cruce_iniciado1[ii]:
                                printLog("Ya se habia encendido la 1, por lo qe la direccion es 1 a 2 ")
                                hay_doble_cruce[ii]=True
                            else:
                                cruce_iniciado2[ii]=True
                                time_elapsed_cruce[ii]=time_inicio_cruce2[ii]-time_inicio_cruce1[ii]
                                if time_elapsed_cruce[ii]>=1:
                                    cruce_iniciado1[ii]=False


                        if hay_doble_cruce[ii]:

                            printLog("posible doble cruce en linea_id:"+str(lineas_ids[ii]))
                            # time_elapsed = time.time() - time_inicio
                            time_elapsed = abs(tiempo_cruce1[ii]-tiempo_cruce2[ii])

                            printLog("Timelapsed cruce almacenado en array:"+str(time_elapsed_cruce[ii])+", frame_cruce_1:"+str(frame_cruce1[ii])+", frame_cruce_2:"+str(frame_cruce2[ii]))


                            transcurrido=0
                            printLog("->ultima_creacion["+str(ii)+"]:"+str(ultima_creacion[ii]))

                            if ultima_creacion[ii]>0:
                                transcurrido=time.time()-ultima_creacion[ii]
                            printLog("transcurrido:"+str(transcurrido)+"")


                            #if (transcurrido>=3 or transcurrido==0) and frame_cruce1[ii]>5 and time_elapsed_cruce[ii]>0.01:
                            if (transcurrido>=3 or transcurrido==0) and time_elapsed_cruce[ii]>1:
                                
                                ultima_creacion[ii]=time.time()
                                printLog("asiganado a ultima_creacion["+str(ii)+"]:"+str(ultima_creacion[ii]))

                                # printLog(fichero)

                                printLog("CRUCE, en "+str(name_file)+"!!:"+str(x + w)+"--"+str(y + h)+"-----linea_id:"+str(lineas_ids[ii]))

                                #car_counter = car_counter + 1

                                if tiempo_cruce1[ii]<tiempo_cruce2[ii]:
                                    direccion=1   #de derexa de la panatalla hacia la izquierda
                                    printLog("primero cruce1 luego cruce2")
                                else:
                                    direccion=2   #de izquierda de la panatalla hacia la derexa
                                    printLog("primero cruce2 luego cruce1")


                                tiempo_cruce1[ii]=0
                                tiempo_cruce2[ii]=0
                                cruce_iniciado1[ii] = False
                                cruce_iniciado2[ii] = False
                                time_inicio_cruce1[ii] = 0
                                time_inicio_cruce2[ii] = 0

                                if direccion == 1:
                                    # car_counter_dir1 = car_counter_dir1 +1
                                    printLog("direccion1")
                                if direccion == 2:
                                    # car_counter_dir2 = car_counter_dir2 +1    
                                    printLog("direccion2")

                                cv2.line(img, (X1, Y1), (X2, Y2), (0, 255, 0), 3)
                                # time_inicio = time.time()



                                segs_elapsed = time.time() - segundos_ini
                                # segundos_datetime = timedelta(0, int(segundos+segs_elapsed))
                                segundos_datetime = timedelta(0, int(segs_elapsed))
                                fecha_datetime_definitiva = fechas[ii]+segundos_datetime

                                printLog("El cruce a sido a estos segundos1:"+str(segundos_datetime))
                                printLog("El cruce a sido a estos segundos2:"+str(segs_elapsed))

                                proc = subprocess.Popen("php /var/www/html/reconocimientoFacial/proyecto_definitivo/ws.php lineas_identificadorunico", shell=True, stdout=subprocess.PIPE)
                                numrandom = str(proc.stdout.read())
                                numrandom = numrandom.replace("'", "")
                                printLog("numrandom asignado:"+numrandom)


                                cv2.imwrite("/var/www/html/reconocimientoFacial/proyecto_definitivo/motor/fotos_lineas/"+lineas_ids[ii]+"/"+numrandom+".jpg",frame_ini)

                                cmd="php /var/www/html/reconocimientoFacial/proyecto_definitivo/ws.php guarda_cruce "+str(lineas_ids[ii])+" '"+str(fecha_datetime_definitiva)+"' "+str(direccion)+" "+str(x+w)+" "+str(y+h)+" "+str(numrandom)
                                printLog(cmd)
                                proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)

                            else:
                                printLog("por tiempo no lo cuento:"+"time_elapsed:"+str(time_elapsed)+",transcurrido:"+str(transcurrido))



                            printLog()
                
                cv2.imshow('frame', img)
        #-FIN-procesamiento de lineas

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    else:
        break
cap.release()
cv2.destroyAllWindows()

printLog("Llego al final!")
    