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



modelFile = "models/res10_300x300_ssd_iter_140000.caffemodel"
configFile = "models/deploy.prototxt.txt"
net = cv2.dnn.readNetFromCaffe(configFile, modelFile)

imagePaths = list(paths.list_images('./caras_juntas'))


for (t, imagePath) in enumerate(imagePaths):

    name_file = imagePath.split(os.path.sep)[-1]
    print('Nombre fichero:'+name_file)


    img = cv2.imread(imagePath)

    #img = cv2.resize(img, None, fx=0.25, fy=0.25)
    height, width = img.shape[:2]


    blob = cv2.dnn.blobFromImage(cv2.resize(img, (300, 300)),1.0, (300, 300), (104.0, 117.0, 123.0))
    net.setInput(blob)
    faces3 = net.forward()
    
    for i in range(faces3.shape[2]):
        confidence = faces3[0, 0, i, 2]
        if confidence > 0.15:

            print('cara encontrada en: '+name_file)

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
                print("fallo1 al leer rostro")
            else:
                try:
                    rostro = cv2.resize(rostro, (150, 150), interpolation=cv2.INTER_CUBIC)
                except Exception as e:
                    print("fallo2 al leer rostro")
                    print(str(e))
                    sigue=False


            if sigue:
                print("hay cara en "+name_file+" es la "+str(i))
                nombrefinal=name_file+'_'+str(i)
                cv2.imwrite('caras_juntas_clasificadas/'+nombrefinal+'.jpg', rostro)

    #cv2.imshow("dnn", img)
    print('----------------------------------------------------------');



         

cv2.destroyAllWindows()



    