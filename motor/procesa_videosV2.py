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

LOCAL_ID=sys.argv[1]
CAMARA_ID=sys.argv[2]

UMBRAL=0.63
UMBRAL_DIFERENCIA_GANADORES=0.035


def printLog(*args, **kwargs):
    print(*args, **kwargs)
    with open('output.out','a') as file:
        print(*args, **kwargs, file=file)


def anyade_datos(knownEncodings1,knownNames1):
    
    printLog('voy a anaydir datos al fichero')


    data = pickle.loads(open('motor/bbdd_reconocimiento/'+LOCAL_ID+'/face_enc', "rb").read())
    for i in range(0,len(data["encodings"])):
        knownEncodings1.append(data["encodings"][i])
        knownNames1.append(data["names"][i])
        printLog('Este ya estaba:'+data["names"][i])

    data = {"encodings": knownEncodings1, "names": knownNames1}
    f = open('motor/bbdd_reconocimiento/'+LOCAL_ID+'/face_enc', "wb")
    f.write(pickle.dumps(data))
    f.close()
    printLog('anyadidos!')   


modelFile = "motor/models/res10_300x300_ssd_iter_140000.caffemodel"
configFile = "motor/models/deploy.prototxt.txt"
net = cv2.dnn.readNetFromCaffe(configFile, modelFile)

# if not os.path.exists('caras'):
#     print('Carpeta creada: caras')
#     os.makedirs('caras')
# if not os.path.exists('caras/aux'):
#     print('Carpeta creada: Rostros caras/aux')
#     os.makedirs('caras/aux')


frame_rate = 10 #cuanto mas alto menos fluido va, osea mas delay, y detecta mas rapido
count=1

while(True):

    aux=True

    printLog("procesando...")

    contenido = os.listdir('/home/testuser/motor/videos/'+LOCAL_ID+'/'+CAMARA_ID+'/')


    for fichero in contenido:
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
                count=count+1

                # cv2.imwrite('motor/caras/aux/f_'+str(count)+'.jpg', img)
                # printLog('La guardo provisional en aux con el nombre: f_'+str(count))


                #img = cv2.resize(img, None, fx=0.25, fy=0.25)
                height, width = img.shape[:2]
                #img2 = img.copy()
                time_elapsed = time.time() - prev

                # if time_elapsed > 1./frame_rate:
                # printLog('por time elapsed me toca analizarlo..')
                prev = time.time()
                blob = cv2.dnn.blobFromImage(cv2.resize(img, (300, 300)),1.0, (300, 300), (104.0, 117.0, 123.0))
                net.setInput(blob)
                faces3 = net.forward()
                
                for i in range(faces3.shape[2]):
                    confidence = faces3[0, 0, i, 2]
                    if confidence > 0.15:

                        printLog('cara encontrada en: '+name_file)

                        box = faces3[0, 0, i, 3:7] * np.array([width, height, width, height])
                        (x, y, x1, y1) = box.astype("int")
                        #cv2.rectangle(img2, (x, y), (x1, y1), (0, 0, 255), 2)


                        ydef=y-50
                        if ydef<0:
                            ydef=0
                        y1def=y1+50
                        if y1def>height:
                            y1def=height-1

                        xdef=x-50
                        if xdef<0:
                            xdef=0
                        x1def=x1+50
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
                        
                        
                            k_str = str(count)
                            #cv2.imwrite('Rostrosencontrados/rostro_'+k_str+'.jpg', rostro)
                            #cv2.putText(img2, 'dnn', (30, 30), font, 1, (255, 255, 0), 2, cv2.LINE_AA)

                            
                            knownEncodings = []
                            knownNames = []

                            cv2.imwrite('motor/caras/aux/aux_'+CAMARA_ID+'.jpg', rostro)

                            
                            #name=str(count)
                            proc = subprocess.Popen("php ws.php nombreunico", shell=True, stdout=subprocess.PIPE)
                            name = str(proc.stdout.read())




                            printLog('El name asignado inicialmente seria:'+name)
                            printLog('empieza el reconocimiento')



                            image = cv2.imread('motor/caras/aux/aux_'+CAMARA_ID+'.jpg')

                           

                            rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
                            boxes = face_recognition.face_locations(rgb,model='hog')
                            encodings = face_recognition.face_encodings(rgb, boxes)

                            veces={}
                            veces_supera={}
                            puntuaciones={}
                            puntuaciones_supera={}
                            ganadores=[]
                            ganador = ""
                            puntuacion = 999
                            segundo = ""
                            puntuacion_segundo = 999
                            veces_ganador=0
                            veces_segundo=0
                            veces_supera_ganador=0
                            veces_supera_segundo=0

                            if(len(encodings)>0):


                                for encoding in encodings:
                                    data = pickle.loads(open('motor/bbdd_reconocimiento/'+LOCAL_ID+'/face_enc', "rb").read())

                                    face_distances = face_recognition.face_distance(data["encodings"],encoding)

                                    for fa, face_distance in enumerate(face_distances):

                                        if data["names"][fa] in puntuaciones:
                                            # print("paso1")
                                            veces[data["names"][fa]]=veces[data["names"][fa]]+1
                                            puntuaciones[data["names"][fa]]=puntuaciones[data["names"][fa]]+face_distance

                                        else:
                                            # print("paso2:"+str(face_distance))
                                            puntuaciones[data["names"][fa]] = face_distance
                                            veces[data["names"][fa]] = 1

                                        if face_distance<UMBRAL:
                                            print("supera el umbral con este nombre:"+data["names"][fa])
                                            print("puntuacion:"+str(face_distance))



                                            if data["names"][fa] in puntuaciones_supera:
                                                # print("paso1")
                                                veces_supera[data["names"][fa]]=veces_supera[data["names"][fa]]+1
                                                puntuaciones_supera[data["names"][fa]]=puntuaciones_supera[data["names"][fa]]+face_distance

                                            else:
                                                # print("paso2:"+str(face_distance))
                                                puntuaciones_supera[data["names"][fa]] = face_distance
                                                veces_supera[data["names"][fa]] = 1



                                            if not data["names"][fa] in ganadores:
                                                print("Como no estaba en ganadores, lo anyado")    
                                                ganadores.append(data["names"][fa])
                                        print()

                                print("Voy a ver el ganador")
                                for g in ganadores:
                                    media=puntuaciones[g]/veces[g]
                                    media_supera=puntuaciones_supera[g]/veces_supera[g]
                                    definitivo=media/veces[g]
                                    print("el nombre:"+g+", tienes esta media:"+str(media)+" y aparece estas veces:"+str(veces[g]))
                                    print("el nombre:"+g+", tienes esta media_supera:"+str(media_supera)+" y supera estas veces:"+str(veces_supera[g]))
                                    print("ademas la puntuacion definitiva es (media/veces):"+str(definitivo))

                                    if media<UMBRAL:
                                        print("la media supera el umbral")
                                        if media<puntuacion:
                                            print("voy a actualizar el segundo con estos datos:"+ganador+" - "+str(puntuacion)+" - "+str(veces_ganador)+" - "+str(veces_supera_ganador))

                                            segundo=ganador
                                            puntuacion_segundo=puntuacion
                                            veces_segundo=veces_ganador
                                            veces_supera_segundo=veces_supera_ganador
                                            

                                            print("Es menor qe la puntuacion actual y lo guardo como ganador")
                                            ganador = g
                                            puntuacion = media
                                            veces_ganador=veces[g]
                                            veces_supera_ganador=veces_supera[g]




                                if puntuacion==999:
                                    proc = subprocess.Popen("php ws.php nombreunico", shell=True, stdout=subprocess.PIPE)
                                    name = str(proc.stdout.read())
                                    name = name.replace("'", "")
                                    print("No hay ganador es cara nueva, le asigno este nombre:"+name)
                                else:
                                    print("ganador:"+ganador+" - puntuacion:"+str(puntuacion)+", veces:"+str(veces_ganador)+", veces_supera:"+str(veces_supera_ganador))    
                                    print("segundo:"+segundo+" - puntuacion:"+str(puntuacion_segundo)+", veces:"+str(veces_segundo)+", veces_supera:"+str(veces_supera_segundo))        
                                    name=ganador
                                    if abs(puntuacion-puntuacion_segundo)<UMBRAL_DIFERENCIA_GANADORES:
                                        print("de diferenciuan de muy poco")
                                        aux_ganador=veces_ganador/veces_supera_ganador
                                        aux_segundo=veces_segundo/veces_supera_segundo
                                        print("tasa de supero ganador"+str(aux_ganador))
                                        print("tasa de supero segundo"+str(aux_segundo))

                                        if aux_segundo>aux_ganador:
                                            print("como el segundo tiene mas veces")
                                            name=segundo
                                    print("ganador definitivo:"+name)



                                knownEncodings = []
                                knownNames = []
                                knownEncodings.append(encoding)
                                knownNames.append(name)
                                anyade_datos(knownEncodings,knownNames)


                                if not os.path.exists('motor/caras/'+LOCAL_ID+'/'+name):
                                    os.makedirs('motor/caras/'+LOCAL_ID+'/'+name)
                                    printLog('creo el directorio:'+'motor/caras/'+LOCAL_ID+'/'+name)


                                segs_elapsed = time.time() - segundos_ini
                                nombrefinal=fichero+'_'+str(segs_elapsed)

                                cv2.imwrite('motor/caras/'+LOCAL_ID+'/'+name+'/'+nombrefinal+'.jpg', rostro)


                            os.remove("motor/caras/aux/aux_"+CAMARA_ID+".jpg")

               
                #cv2.imshow("dnn", img)
                printLog('----------------------------------------------------------');
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
            else:
                break
        cap.release()
        os.remove(name_file)        


    if cv2.waitKey(1) & 0xFF == ord('q'):
        break


    if aux:
        time.sleep(1)
         

cv2.destroyAllWindows()



    