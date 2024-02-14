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
import dlib

sys.path.append(".")
from facealigner import FaceAligner

#python3.7 motor/procesa_videosV6.py 2 7 7_2021-12-07_17:35:06.922148.avi

def rect_to_bb(rect):

    x = rect.left()
    y = rect.top()
    w = rect.right() - x
    h = rect.bottom() - y

    # return a tuple of (x, y, w, h)
    return (x, y, w, h)



LOCAL_ID=sys.argv[1]
CAMARA_ID=sys.argv[2]
FICHERO=sys.argv[3]
RUTA_PROYECTO=sys.argv[4]
SENSIBILIDAD_ES_CARA=float(sys.argv[5])
URL_FTP_BASE=sys.argv[6]

CONFIG_desiredFaceWidth=sys.argv[7]
CONFIG_margen_cruce_linea=sys.argv[8]
CONFIG_frame_rate=sys.argv[9]
CONFIG_redimensionVideoWidth=sys.argv[10]
CONFIG_redimensionVideoHeight=sys.argv[11]
CONFIG_analisisLineasImagenWidth=sys.argv[12]
CONFIG_analisisLineasImagenHeight=sys.argv[13]
CONFIG_margenGrosorLinea=sys.argv[14]
CONFIG_contornoAreaCruceLinea=sys.argv[15]
CONFIG_MinimoContornoConsiderarloCruce=sys.argv[16]
CONFIG_TiempoTrascurridoUltimoCruce=sys.argv[17]
CONFIG_TiempoDeCruce=sys.argv[18]
CONFIG_redimension_imagen_captura_caras_w=sys.argv[19]
CONFIG_redimension_imagen_captura_caras_h=sys.argv[20]
CONFIG_scale_factor=sys.argv[21]
CONFIG_resize_w=sys.argv[22]
CONFIG_resize_h=sys.argv[23]
CONFIG_mean1=sys.argv[24]
CONFIG_mean2=sys.argv[25]
CONFIG_mean3=sys.argv[26]
CONFIG_recuadro_tamanyo_rostro=sys.argv[27]
CONFIG_redimension_rostro=sys.argv[28]



detector = dlib.get_frontal_face_detector()
predictor = dlib.shape_predictor("./motor/models/shape_predictor_68_face_landmarks.dat")
#fa = FaceAligner(predictor, desiredFaceWidth=150)
fa = FaceAligner(predictor, desiredFaceWidth=int(CONFIG_desiredFaceWidth))


def printLog(*args, **kwargs):
    print(*args, **kwargs)
    
    #with open(RUTA_PROYECTO+'motor/logs/procesa_videosV6_'+CAMARA_ID+'.out','a') as file:
       #print(*args, **kwargs, file=file)



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
    # i=izq-5
    i=izq-int(CONFIG_margen_cruce_linea)
    # while i<=(der+5):
    while i<=(der+int(CONFIG_margen_cruce_linea)):
        #printLog("i1:"+str(i))
        c=x
        while c<=(x+w):
            #printLog("c1:"+str(c))
            if c==i:
                cruce_h=True     
                printLog("hay cruce horiznta")
            c=c+1
        i=i+1


    cruce_v=False
    # i=abajo-5
    i=abajo-int(CONFIG_margen_cruce_linea)
    # while i<=(arriba+5):
    while i<=(arriba+int(CONFIG_margen_cruce_linea)):    
        #printLog("i2:"+str(i))
        c=y
        while c<=(y+h):
            #printLog("c2:"+str(c))
            if c==i:
                cruce_v=True     
                printLog("hay cruce vertical")
            c=c+1
        i=i+1


    if cruce_h or cruce_v:
        cruce=True
        printLog("Tenemos cruce")


    return cruce





modelFile = RUTA_PROYECTO+"motor/models/res10_300x300_ssd_iter_140000.caffemodel"
configFile = RUTA_PROYECTO+"motor/models/deploy.prototxt.txt"
net = cv2.dnn.readNetFromCaffe(configFile, modelFile)


"""
INI procesaro lineas
"""
fgbg = cv2.bgsegm.createBackgroundSubtractorMOG()
kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
"""
FIN procesaro lineas
"""







#frame_rate = 10 #cuanto mas alto menos fluido va, osea mas delay, y detecta mas rapido
frame_rate = CONFIG_frame_rate #cuanto mas alto menos fluido va, osea mas delay, y detecta mas rapido



aux=True

printLog("procesando...")




# exit()


#-INI-procesamiento de lineas

printLog("VOY A INICIALIZAR LAS LINEAS")

printLog("php "+RUTA_PROYECTO+"ws.php listado_lineas "+CAMARA_ID)
proc = subprocess.Popen("php "+RUTA_PROYECTO+"ws.php listado_lineas "+CAMARA_ID, shell=True, stdout=subprocess.PIPE)
lineas = str(proc.stdout.read())
lineas = lineas.replace("'", "")
lineas = lineas.replace("b", "")
v_lineas=lineas.split(",");
longitud = len(v_lineas)
printLog("numero de lineas: "+str(longitud))


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
        proc = subprocess.Popen("php "+RUTA_PROYECTO+"ws.php coordenadas_linea "+LINEA_ID, shell=True, stdout=subprocess.PIPE)
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




aux=False
name_file=os.path.join(URL_FTP_BASE+'motor/videos/'+LOCAL_ID+'/'+CAMARA_ID+'/', FICHERO)
printLog("tenemos este video:"+name_file)

cap = cv2.VideoCapture(name_file)
prev=0
segundos_ini=time.time()


#cap.set(cv2.CAP_PROP_FRAME_WIDTH, 750)
#cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 420)
#cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 562)


# probando
cap.set(cv2.CAP_PROP_FRAME_WIDTH, int(CONFIG_redimensionVideoWidth))
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, int(CONFIG_redimensionVideoHeight))


while(cap.isOpened()):
    # printLog('voy leyendo el video..')
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
        img_test=img


        #-INI-procesamiento de lineas
        if tiene_lineas:

            frame_ini=img
            
            img = cv2.resize(img, (int(CONFIG_analisisLineasImagenWidth),int(CONFIG_analisisLineasImagenHeight)))


            """
            height, width, channels = img.shape
            printLog("------------>height:"+str(height)+" - width:"+str(width)+" - channels:"+str(channels))
            """


            for ii in range(0,len(lineas_ids)):


                X1=int(v_x1[ii])
                Y1=int(v_y1[ii])

                X2=int(v_x2[ii])
                Y2=int(v_y2[ii])

                """
                X1_1=X1-3
                Y1_1=Y1-3
                X1_2=X1+3
                Y1_2=Y1+3


                X2_1=X2-3
                Y2_1=Y2-3
                X2_2=X2+3
                Y2_2=Y2+3
                """
                X1_1=X1-int(CONFIG_margenGrosorLinea)
                Y1_1=Y1-int(CONFIG_margenGrosorLinea)
                X1_2=X1+int(CONFIG_margenGrosorLinea)
                Y1_2=Y1+int(CONFIG_margenGrosorLinea)


                X2_1=X2-int(CONFIG_margenGrosorLinea)
                Y2_1=Y2-int(CONFIG_margenGrosorLinea)
                X2_2=X2+int(CONFIG_margenGrosorLinea)
                Y2_2=Y2+int(CONFIG_margenGrosorLinea)

                cv2.line(img, (X1, Y1), (X2, Y2), (0, 255, 255), 1)
                


                if time.time() - time_inicio_cruce1[ii] > 2:
                    cruce_iniciado1[ii]=False  
                if time.time() - time_inicio_cruce2[ii] > 2:
                    cruce_iniciado2[ii]=False  




                # printLog("(X1,Y1) , (X2,Y2): ("+str(X1)+","+str(Y1)+") , ("+str(X2)+","+str(Y2)+")")

                # area_pts = np.array([[X1-5, Y1-5], [X1+5, Y1+5], [X2+5, Y2+5], [X2-5, Y2-5]])
                area_pts = np.array([[X1-int(CONFIG_contornoAreaCruceLinea), Y1-int(CONFIG_contornoAreaCruceLinea)], [X1+int(CONFIG_contornoAreaCruceLinea), Y1+int(CONFIG_contornoAreaCruceLinea)], [X2+int(CONFIG_contornoAreaCruceLinea), Y2+int(CONFIG_contornoAreaCruceLinea)], [X2-int(CONFIG_contornoAreaCruceLinea), Y2-int(CONFIG_contornoAreaCruceLinea)]])

                imAux = np.zeros(shape=(img.shape[:2]), dtype= np.uint8)

                imAux = cv2.drawContours(imAux, [area_pts], -1, (255), -1)
                image_area = cv2.bitwise_and(img, img, mask=imAux)    

                fgmask = fgbg.apply(image_area)
                fgmask = cv2.morphologyEx(fgmask, cv2.MORPH_OPEN, kernel)
                fgmask = cv2.morphologyEx(fgmask, cv2.MORPH_CLOSE, kernel)
                fgmask = cv2.dilate(fgmask, None, iterations=5)





                cnts = cv2.findContours(fgmask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[0]
                for cnt in cnts:
                    printLog("contourArea:"+str(cv2.contourArea(cnt)))
                    #if cv2.contourArea(cnt) > 1500:
                    if cv2.contourArea(cnt) > int(CONFIG_MinimoContornoConsiderarloCruce):
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
                            #if (transcurrido>=3 or transcurrido==0) and time_elapsed_cruce[ii]>1:
                            #if (transcurrido>=3 or transcurrido==0) and time_elapsed_cruce[ii]>0.15:
                            if (transcurrido>=int(CONFIG_TiempoTrascurridoUltimoCruce) or transcurrido==0) and time_elapsed_cruce[ii]>float(CONFIG_TiempoDeCruce):
                                
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

                                proc = subprocess.Popen("php "+RUTA_PROYECTO+"ws.php lineas_identificadorunico", shell=True, stdout=subprocess.PIPE)
                                numrandom = str(proc.stdout.read())
                                numrandom = numrandom.replace("'", "")
                                printLog("numrandom asignado:"+numrandom)


                                cv2.imwrite(RUTA_PROYECTO+"motor/fotos_lineas/"+lineas_ids[ii]+"/"+numrandom+".jpg",frame_ini)

                                cmd="php "+RUTA_PROYECTO+"ws.php guarda_cruce "+str(lineas_ids[ii])+" '"+str(fecha_datetime_definitiva)+"' "+str(direccion)+" "+str(x+w)+" "+str(y+h)+" "+str(numrandom)
                                printLog(cmd)
                                proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)

                            else:
                                printLog("por tiempo no lo cuento:"+"time_elapsed:"+str(time_elapsed)+",transcurrido:"+str(transcurrido))


                            printLog()

        #-FIN-procesamiento de lineas


        printLog('Ya se han procesado las lineas, ahora a por las caras')


        # if time_elapsed > 1./frame_rate:
        # print('por time elapsed me toca analizarlo..')
        
        # blob = cv2.dnn.blobFromImage(cv2.resize(img, (300, 300)),1.0, (300, 300), (104.0, 117.0, 123.0))
        #blob = cv2.dnn.blobFromImage(cv2.resize(img, (300, 300)),1.0, (323, 323), (104.0, 117.0, 123.0))
        # blob = cv2.dnn.blobFromImage(cv2.resize(img_original, (300, 300)),1.0, (353, 353), (104.0, 117.0, 123.0))
        blob = cv2.dnn.blobFromImage(cv2.resize(img_original, (int(CONFIG_redimension_imagen_captura_caras_w), int(CONFIG_redimension_imagen_captura_caras_h))),float(CONFIG_scale_factor), (int(CONFIG_resize_w), int(CONFIG_resize_h)), (float(CONFIG_mean1), float(CONFIG_mean2), float(CONFIG_mean3)))
        #blob = cv2.dnn.blobFromImage(cv2.resize(img, (300, 300)),1.0, (351, 353), (104.0, 117.0, 123.0))
        net.setInput(blob)
        faces3 = net.forward()
        
        for i in range(faces3.shape[2]):
            # printLog('buclillo de caras que no se que es')
            confidence = faces3[0, 0, i, 2]
            printLog('con este confidence'+str(confidence))

            if confidence > SENSIBILIDAD_ES_CARA:

                printLog('cara encontrada en: '+name_file)

                box = faces3[0, 0, i, 3:7] * np.array([width1, height1, width1, height1])
                (x, y, x1, y1) = box.astype("int")


                #cv2.rectangle(img, (x, y), (x1, y1), (0, 0, 255), 2)


                """
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
                """
                ydef=y-int(CONFIG_recuadro_tamanyo_rostro)
                if ydef<0:
                    ydef=0
                y1def=y1+int(CONFIG_recuadro_tamanyo_rostro)
                if y1def>height1:
                    y1def=height1-1

                xdef=x-int(CONFIG_recuadro_tamanyo_rostro)
                if xdef<0:
                    xdef=0
                x1def=x1+int(CONFIG_recuadro_tamanyo_rostro)
                if x1def>width1:
                    x1def=width1-1    



                # rostro = img_original[ydef:y1def, xdef:x1def]
                rostro = img[y-50:y1+50, x-50:x1+50]
                #rostro = img_original

                sigue=True
                if(type(rostro) == type(None)):
                    sigue=False
                else:
                    try:
                        # rostro = cv2.resize(rostro, (150, 150), interpolation=cv2.INTER_CUBIC)
                        rostro = cv2.resize(rostro, (int(CONFIG_redimension_rostro), int(CONFIG_redimension_rostro)), interpolation=cv2.INTER_CUBIC)
                    except Exception as e:
                        printLog(str(e))
                        sigue=False


                if sigue:
                    segs_elapsed = time.time() - segundos_ini
                    nombrefinal=FICHERO+'_'+str(segs_elapsed)

                    alineado=False


                    """
                    image = rostro
                    image = imutils.resize(image, width=800)
                    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
                    #cv2.imshow("Input", image)
                    rects = detector(gray, 2)
                    #print("paso0")
                    # loop over the face detections
                    for rect in rects:
                        printLog("Voy a alinear")
                        alineado=True
                        (x, y, w, h) = rect_to_bb(rect)
                        faceOrig = imutils.resize(image[y:y + h, x:x + w], width=256)
                        faceAligned = fa.align(image, gray, rect)
                        # display the output images
                        #cv2.imshow("Original", faceOrig)
                        #cv2.imshow("Aligned", faceAligned)

                        cv2.imwrite('/var/www/html/reconocimientoFacial/proyecto_definitivo/motor/caras/sinclasificar/'+LOCAL_ID+'/'+CAMARA_ID+'/'+nombrefinal+'.jpg', faceAligned)
                    

                    """
                    if not alineado:
                        printLog("No se puede alinear")
                        cv2.imwrite(RUTA_PROYECTO+'motor/caras/sinclasificar/'+LOCAL_ID+'/'+CAMARA_ID+'/'+nombrefinal+'.jpg', rostro)
                    


                    printLog("cara guardada en /"+str(LOCAL_ID)+"/"+str(CAMARA_ID)+"/"+nombrefinal+".jpg con esta confidence:"+str(confidence))


        # cv2.imshow("dnn", img)
        #printLog('----------------------------------------------------------');
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    else:
        break
cap.release()



os.remove(name_file)
os.remove(RUTA_PROYECTO+"aux/"+FICHERO+".txt")




cv2.destroyAllWindows()


printLog("Llego al final!")

