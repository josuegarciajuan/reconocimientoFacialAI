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

    contenido = os.listdir('/home/testuser/motor/videos/'+LOCAL_ID+'/')


    for fichero in contenido:
        aux=False
        name_file=os.path.join('/home/testuser/motor/videos/'+LOCAL_ID+'/', fichero)
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
                printLog('por time elapsed me toca analizarlo..')
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
                        rostro = cv2.resize(rostro, (150, 150), interpolation=cv2.INTER_CUBIC)
                        
                        k_str = str(count)
                        #cv2.imwrite('Rostrosencontrados/rostro_'+k_str+'.jpg', rostro)
                        #cv2.putText(img2, 'dnn', (30, 30), font, 1, (255, 255, 0), 2, cv2.LINE_AA)

                        
                        knownEncodings = []
                        knownNames = []

                        cv2.imwrite('motor/caras/aux/aux_'+LOCAL_ID+'.jpg', rostro)

                        
                        #name=str(count)
                        proc = subprocess.Popen("php ws.php nombreunico", shell=True, stdout=subprocess.PIPE)
                        name = str(proc.stdout.read())



                        printLog('El name asignado inicialmente seria:'+name)
                        printLog('empieza el reconocimiento')

                        image = cv2.imread('motor/caras/aux/aux_'+LOCAL_ID+'.jpg')

                        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)



                        # cv2.imwrite('motor/caras/aux/'+name+'.jpg', rostro)
                        # printLog('La guardo provisional en aux con el nombre:'+name)



                        boxes = face_recognition.face_locations(rgb,model='hog')
                        encodings = face_recognition.face_encodings(rgb, boxes)
                        # encodings = face_recognition.face_encodings(rostro)

                        if(len(encodings)>0):
                            printLog('La foto SI tiene caras, tiene este numero de caras:'+str(len(encodings)))
                            for encoding in encodings:
                                #count_p=count_p+1

                                printLog('Recorriendo cara')
                                data = pickle.loads(open('motor/bbdd_reconocimiento/'+LOCAL_ID+'/face_enc', "rb").read())
                                matches = face_recognition.compare_faces(data["encodings"],encoding)
                                printLog('el diccionario tiene ahora este numero de pos:'+str(len(matches)))
                                if True in matches:
                                    printLog('tiene matches trues')
                                    matchedIdxs = [m for (m, b) in enumerate(matches) if b]
                                    counts = {}
                                    printLog('Numero de matches true:'+str(len(matchedIdxs)))
                                    for w in matchedIdxs:
                                        name = data["names"][w]
                                        printLog('un match es con este nombre:'+name)
                                        counts[name] = counts.get(name, 0) + 1
                                        printLog('y lleva este numero de coincidencias:'+str(counts[name]))
                                    name = max(counts, key=counts.get)
                                    printLog('le asigno este nombre pues, qe es el qe mas coincidencias tiene:'+name)
                                printLog('El nombre final asignado a esta imagen es:'+name)  

                                knownEncodings.append(encoding)
                                knownNames.append(name)

                                printLog('voy a anyadir datos al fichero')  
                                anyade_datos(knownEncodings,knownNames)
                                #_thread.start_new_thread(anyade_datos, (knownEncodings,knownNames))

                                if not os.path.exists('motor/caras/'+LOCAL_ID+'/'+name):
                                    os.makedirs('motor/caras/'+LOCAL_ID+'/'+name)
                                    printLog('creo el directorio:'+'motor/caras/'+LOCAL_ID+'/'+name)
                                #cv2.imwrite('Rostrosencontradosendirecto2/'+name+'/'+str(count_p)+'.jpg', rostro)

                                segs_elapsed = time.time() - segundos_ini
                                nombrefinal=fichero+'_'+str(segs_elapsed)
                                cv2.imwrite('motor/caras/'+LOCAL_ID+'/'+name+'/'+nombrefinal+'.jpg', rostro)
                        else:
                            printLog('La foto no tiene caras conocidas!')

                        os.remove("motor/caras/aux/aux_"+LOCAL_ID+".jpg")

               
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



    