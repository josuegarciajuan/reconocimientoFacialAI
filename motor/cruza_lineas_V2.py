import cv2
import numpy as np
import imutils
import cv2, time, pandas
from datetime import datetime, timedelta
import sys
import os
import subprocess



# URL_CAMARA="rtsp://admin:bakcAse4@172.16.51.52:554/cam/realmonitor?channel=1&subtype=0"
LOCAL_ID=sys.argv[1]
CAMARA_ID=sys.argv[2]


def printLog(*args, **kwargs):
    #print("printLog")
    print(*args, **kwargs)
    # with open('motor/cruza_lineas.out','a') as file:
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





# cap = cv2.VideoCapture(URL_CAMARA)

fgbg = cv2.bgsegm.createBackgroundSubtractorMOG()
kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
car_counter = 0
car_counter_dir1 = 0
car_counter_dir2 = 0
time_inicio = time.time()

time_inicio_cruce1 = time.time()
time_inicio_cruce2 = time.time()
cruce_iniciado1 = False
cruce_iniciado2 = False
tiempo_cruce1=0
tiempo_cruce2=0


while True:

    # printLog("procesando...")

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

            LINEA_ID=v_lineas[iii]
            printLog("linea_id:"+LINEA_ID)
            # printLog("php ws.php coordenadas_linea "+CAMARA_ID)
            # print("php ws.php coordenadas_linea "+CAMARA_ID)
            proc = subprocess.Popen("php ws.php coordenadas_linea "+LINEA_ID, shell=True, stdout=subprocess.PIPE)
            coordenadas = str(proc.stdout.read())
            coordenadas = coordenadas.replace("'", "")
            coordenadas = coordenadas.replace("b", "")
            # printLog("coordenadas:"+coordenadas)
            # exit()


            v_coordenadas=coordenadas.split(",");

            X1=int(v_coordenadas[0])
            Y1=int(v_coordenadas[1])
            X2=int(v_coordenadas[2])
            Y2=int(v_coordenadas[3])

            X1_1=X1-10
            Y1_1=Y1-10
            X2_1=X2-10
            Y2_1=Y2-10

            X1_2=X1+10
            Y1_2=Y1+10
            X2_2=X2+10
            Y2_2=Y2+10



            contenido = os.listdir('/home/testuser/motor/videos_lineas/'+LOCAL_ID+'/'+CAMARA_ID+'/'+LINEA_ID+'/')
            # metodo para procesar, pienbsa qe el mismo video se va a procesar 1 vez por cada linea en esa camara, por lo qe no se puede borrar al final

            for fichero in contenido:

                name_file=os.path.join('/home/testuser/motor/videos_lineas/'+LOCAL_ID+'/'+CAMARA_ID+'/'+LINEA_ID+'/', fichero)
                cap = cv2.VideoCapture(name_file)
                segundos_ini=time.time()
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, 750)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 750)

                #printLog("fichero"+fichero)
                # if fichero=="3_2021-10-01_09:11:55.925966.avi" and LINEA_ID=="9":

                printLog("estamos en el fichero:"+fichero+" y tenemos la linea_id:"+LINEA_ID)


                printLog("(X1,Y1) , (X2,Y2): ("+str(X1)+","+str(Y1)+") , ("+str(X2)+","+str(Y2)+")")


                aux=fichero.split('_')

                camara_id=aux[0]
                printLog("camara_id:"+camara_id)

                fecha=aux[1]
                printLog("fecha:"+fecha)

                hora=aux[2]
                printLog("hora:"+hora)

                # segundos=aux[3]

                hora=hora.replace('.avi','')
                aux=hora.split('.')
                hora=aux[0]

                # segundos=segundos.replace('.jpg','')
                # aux=segundos.split('.')
                # segundos=aux[0]
                fecha_completa=fecha+' '+hora

                printLog("fecha_completa:"+fecha_completa)

                # 3_2021-08-30_16:06:05.551382.avi

                fecha_completa = datetime.strptime(fecha_completa, '%Y-%m-%d %H:%M:%S')

                ultima_creacion=time.time()

                while(cap.isOpened()):


                    # printLog("paso frame")
                    # printLog()
                    
                    segundos=0


                    ret, frame = cap.read()
                    frame_ini=frame
                    if ret == False: break


                    
                    frame = imutils.resize(frame, width=750)
                    
                    """
                    cv2.line(frame, (X1, Y1), (X2, Y2), (0, 255, 255), 1)
                    cv2.imshow('frame', frame)
                    k = cv2.waitKey(70) & 0xFF
                    if k ==27:
                        break
                    """

                    # Especificamos los puntos extremos del área a analizar 
                    # area_pts = np.array([[X1-120, Y1], [frame.shape[1]-80, Y1], [frame.shape[1]-80, Y2], [X2-120, Y2]])
                    area_pts = np.array([[X1-40, Y1], [X1+40, Y1], [X2+40, Y2], [X2-40, Y2]])

                    # Con ayuda de una imagen auxiliar, determinamos el área
                    # sobre la cual actuará el detector de movimiento
                    imAux = np.zeros(shape=(frame.shape[:2]), dtype= np.uint8)
                    imAux = cv2.drawContours(imAux, [area_pts], -1, (255), -1)
                    image_area = cv2.bitwise_and(frame, frame, mask=imAux)    

                    # aplicamos sustraccion de fondo
                    fgmask = fgbg.apply(image_area)
                    fgmask = cv2.morphologyEx(fgmask, cv2.MORPH_OPEN, kernel)
                    fgmask = cv2.morphologyEx(fgmask, cv2.MORPH_CLOSE, kernel)
                    fgmask = cv2.dilate(fgmask, None, iterations=5)

                    # Encontramos los contornos presentes de fgmask, para luego basándonos
                    # en su área poder determinar si existe movimiento (autos)
                    cnts = cv2.findContours(fgmask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[0]
                    for cnt in cnts:
                        printLog("paso1:"+str(cv2.contourArea(cnt)))
                        if cv2.contourArea(cnt) > 1500:
                            x, y, w, h = cv2.boundingRect(cnt)
                            cv2.rectangle(frame, (x,y), (x+w,y+h), (0,255,255), 1)   
                            

                            printLog("hay controno:(x,y)->("+str(x)+","+str(y)+") hasta ("+str(x+w)+","+str(y+h)+")")
                            printLog("aver qe debe cruzar->("+str(X1_1)+","+str(Y1_1)+") hasta ("+str(X2_1)+","+str(Y2_1)+")")


                            hay_doble_cruce=False
                            direccion=0


                            if hay_cruce(X1_1,Y1_1,X2_1,Y2_1,x,y,w,h) and not cruce_iniciado1:
                                printLog("se enciende la 1 a "+str(time.time()))
                                tiempo_cruce1=time.time()
                                cv2.line(frame, (X1_1, Y1_1), (X2_1, Y2_1), (0, 255, 0), 3)
                                time_elapsed_cruce = time.time() - time_inicio_cruce2
                                if cruce_iniciado2 and time_elapsed_cruce<0.2:
                                    #printLog("Ya se habia encendido la 2, por lo qe la direccion es 2 a 1 ")
                                    hay_doble_cruce=True
                                else:
                                    cruce_iniciado1=True
                                    time_inicio_cruce1=time.time()
                                    if time_elapsed_cruce>=0.2:
                                        cruce_iniciado2=False

                            if hay_cruce(X1_2,Y1_2,X2_2,Y2_2,x,y,w,h) and not hay_doble_cruce and not cruce_iniciado2:
                                printLog("se enciende la 2 a "+str(time.time()))
                                tiempo_cruce2=time.time()
                                cv2.line(frame, (X1_2, Y1_2), (X2_2, Y2_2), (0, 255, 0), 3)
                                time_elapsed_cruce = time.time() - time_inicio_cruce1
                                if cruce_iniciado1 and time_elapsed_cruce<0.2:
                                    #printLog("Ya se habia encendido la 1, por lo qe la direccion es 1 a 2 ")
                                    hay_doble_cruce=True
                                else:
                                    cruce_iniciado2=True
                                    time_inicio_cruce2=time.time()
                                    if time_elapsed_cruce>=0.2:
                                        cruce_iniciado1=False






                            if hay_doble_cruce:
                                printLog("posible doble cruce")
                                # time_elapsed = time.time() - time_inicio
                                time_elapsed = abs(tiempo_cruce1-tiempo_cruce2)
                                printLog("tiempocruce1:"+str(tiempo_cruce1)+" - tiempocruce2:"+str(tiempo_cruce2)+"time_elapsed:"+str(time_elapsed))

                                comprueba=time.time()

                                transcurrido=comprueba-ultima_creacion

                                printLog("comprueba:"+str(comprueba)+" ,ultima_creacion:"+str(ultima_creacion)+" ,transcurrido:"+str(transcurrido)+"")

                                if time_elapsed < 1 and transcurrido>2:

                                    ultima_creacion=time.time()
                                    
                                    printLog(fichero)

                                    printLog("cruce:"+str(x + w)+"--"+str(y + h))

                                    car_counter = car_counter + 1

                                    if tiempo_cruce1<tiempo_cruce2:
                                        direccion=1   #de derexa de la panatalla hacia la izquierda
                                    else:
                                        direccion=2   #de izquierda de la panatalla hacia la derexa


                                    tiempo_cruce1=0
                                    tiempo_cruce2=0


                                    if direccion == 1:
                                        car_counter_dir1 = car_counter_dir1 +1
                                        printLog("direccion1")
                                    if direccion == 2:
                                        car_counter_dir2 = car_counter_dir2 +1    
                                        printLog("direccion2")

                                    cv2.line(frame, (X1, Y1), (X2, Y2), (0, 255, 0), 3)
                                    time_inicio = time.time()
                                    cruce_iniciado1 = False
                                    cruce_iniciado2 = False


                                    segs_elapsed = time.time() - segundos_ini
                                    segundos_datetime = timedelta(0, int(segundos+segs_elapsed))
                                    fecha_datetime_definitiva = fecha_completa+segundos_datetime

                                    proc = subprocess.Popen("php ws.php lineas_identificadorunico", shell=True, stdout=subprocess.PIPE)
                                    numrandom = str(proc.stdout.read())
                                    numrandom = numrandom.replace("'", "")
                                    printLog("numrandom asignado:"+numrandom)


                                    cv2.imwrite("/var/www/html/reconocimientoFacial/proyecto_definitivo/motor/fotos_lineas/"+LINEA_ID+"/"+numrandom+".jpg",frame_ini)

                                    cmd="php ws.php guarda_cruce "+str(LINEA_ID)+" '"+str(fecha_datetime_definitiva)+"' "+str(direccion)+" "+str(x+w)+" "+str(y+h)+" "+str(numrandom)
                                    printLog(cmd)
                                    proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)

                                else:
                                    printLog("por tiempo no lo cuento:"+"time_elapsed:"+str(time_elapsed)+",transcurrido:"+str(transcurrido))

                                    


                                printLog()

                    

                cap.release()
                os.remove(name_file)



        else:
            print("Sin lineas en la camara no hago nada") 


    printLog("ronda")    
    # exit()



cap.release()
cv2.destroyAllWindows()

    