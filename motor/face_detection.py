import cv2
import numpy as np
import time
import os
import pickle
import _thread
from imutils import paths
import sys
import subprocess
import face_recognition


def printLog(*args, **kwargs):
    print(*args, **kwargs)
    # with open('output.out','a') as file:
    #     print(*args, **kwargs, file=file)

def anyade_datos(knownEncodings1,knownNames1):
    
    printLog('voy a anaydir datos al fichero')

    data = pickle.loads(open('face_enc', "rb").read())
    for ff in range(0,len(data["encodings"])):
        knownEncodings1.append(data["encodings"][ff])
        knownNames1.append(data["names"][ff])
        # printLog('Este ya estaba:'+data["names"][i])

    data = {"encodings": knownEncodings1, "names": knownNames1}
    f = open('face_enc', "wb")
    f.write(pickle.dumps(data))
    f.close()
    printLog('anyadidos!')   



modelFile = "models/res10_300x300_ssd_iter_140000.caffemodel"
configFile = "models/deploy.prototxt.txt"
net = cv2.dnn.readNetFromCaffe(configFile, modelFile)


contenido = os.listdir('/var/www/html/reconocimientoFacial/proyecto_definitivo/motor/tests/')

knownEncodings = []
knownNames = []

count=0
count2=100
for fichero in contenido:
    fichero="/var/www/html/reconocimientoFacial/proyecto_definitivo/motor/tests/"+fichero
    printLog("-------->paso:"+fichero)
    img = cv2.imread(fichero)
    # rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    height, width = img.shape[:2]
    blob = cv2.dnn.blobFromImage(cv2.resize(img, (300, 300)),1.0, (300, 300), (104.0, 117.0, 123.0))
    net.setInput(blob)
    faces3 = net.forward()
    for i in range(faces3.shape[2]):
        # printLog("cara:"+str(i))
        count=count+1
        count2=count2+1
        confidence = faces3[0, 0, i, 2]
        # printLog("confidence:"+str(confidence))
        if confidence > 0.15:
            printLog("confidence cumplida")
            box = faces3[0, 0, i, 3:7] * np.array([width, height, width, height])
            (x, y, x1, y1) = box.astype("int")
            # cv2.rectangle(img, (x, y), (x1, y1), (0, 0, 255), 2)

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



            # rostro = img[y-50:y1+50, x-50:x1+50]
            rostro = img[ydef:y1def, xdef:x1def]
            # rostro = cv2.resize(rostro, (150, 150), interpolation=cv2.INTER_CUBIC)
            
            # rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            # boxes = face_recognition.face_locations(rgb,model='hog')
            # encodings = face_recognition.face_encodings(rgb, boxes)
            # printLog("encodings1:"+str(len(encodings)))

            boxes = face_recognition.face_locations(rostro,model='hog')
            encodings = face_recognition.face_encodings(rostro, boxes)
            printLog("encodings2:"+str(len(encodings)))

            if(len(encodings)>0):
                name=str(count)
                printLog('La foto SI tiene caras, tiene este numero de caras:'+str(len(encodings)))
                for encoding in encodings:
                    printLog('Recorriendo cara')
                    data = pickle.loads(open('face_enc', "rb").read())
                    matches = face_recognition.compare_faces(data["encodings"],encoding)
                    if True in matches:
                        matchedIdxs = [m for (m, b) in enumerate(matches) if b]
                        counts = {}
                        printLog('Numero de matches true:'+str(len(matchedIdxs)))
                        for w in matchedIdxs:
                            name = data["names"][w]
                            # printLog('un match es con este nombre:'+name)
                            counts[name] = counts.get(name, 0) + 1
                            # printLog('y lleva este numero de coincidencias:'+str(counts[name]))
                        name = max(counts, key=counts.get)
                        printLog('le asigno este nombre pues, qe es el qe mas coincidencias tiene:'+name)
                    printLog('El nombre final asignado a esta imagen es:'+name)  
                    knownEncodings.append(encoding)
                    knownNames.append(name)
                    anyade_datos(knownEncodings,knownNames)
                    cv2.imwrite('/var/www/html/reconocimientoFacial/proyecto_definitivo/motor/tests2/'+name+'___'+str(count2)+'.jpg', rostro)

                    printLog("-----------------------------")




    
    


