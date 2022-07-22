
from imutils import paths
import face_recognition
import pickle
import cv2
import os
from shutil import copyfile
import random
import sys
# from datetime import datetime, timedelta
import time
from datetime import datetime, date, time, timedelta
import subprocess
from filelock import FileLock
from skimage import io

import dlib
import numpy as np
import requests
from imutils import face_utils
import imutils
import matplotlib.pyplot as plt




import face_alignment
fa = face_alignment.FaceAlignment(face_alignment.LandmarksType._2D, flip_input=False, device='cpu')



#DIFERENCIA_ANCHO_OJOS=8
#DIFERENCIA_ANCHO_OJOS=9
DIFERENCIA_ANCHO_OJOS=12
DIFERENCIA_ALTURAS=300


UMBRAL_ENFOQUE=1000 #para considerar una foto desenfocada ya y al comparar 1 a 1 con todo el diccionario, ya pasaria a ver si las 2 tienen muxa diferencia de enfoque
UMBRAL_ENFOQUE_MAXIMO=200 # mas de este desenfoque , se descartan



def printLog(*args, **kwargs):
    print(*args, **kwargs)
    
    with open('motor/decara_o_perfil.out','a') as file:
    # with open('motor/procesa_fotos_def_XX.out','a') as file:
      print(*args, **kwargs, file=file)
        

printLog("paso0")




def esfrontal2(imagePath):

    frontal=False


    
    face1 = "motor/models/haarcascade_frontalface2.xml"
    face2 = "motor/models/haarcascade_frontalface_alt.xml"
    face3 = "motor/models/haarcascade_frontalface_alt2.xml"
    face4 = "motor/models/haarcascade_frontalface_alt_tree.xml"
    face5 = "motor/models/haarcascade_frontalface_default.xml"
    face6 = "motor/models/haarcascade_profileface.xml"
    face7 = "motor/cosas_en_la_cara/models/haarcascade_frontalface_default.xml"

    face_cascade1 = cv2.CascadeClassifier(face1)
    face_cascade2 = cv2.CascadeClassifier(face2)
    face_cascade3 = cv2.CascadeClassifier(face3)
    face_cascade4 = cv2.CascadeClassifier(face4)
    face_cascade5 = cv2.CascadeClassifier(face5)
    face_cascade6 = cv2.CascadeClassifier(face6)
    face_cascade7 = cv2.CascadeClassifier(face7)

    img = cv2.imread(imagePath)
    img = imutils.resize(img, width=500)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) # convert to grayscale    



    image2 = cv2.imread(imagePath)
    image2 = imutils.resize(image2, width=500)
    gray2 = cv2.cvtColor(image2, cv2.COLOR_BGR2GRAY)


    if not frontal:
        printLog("Es lateral de momento")


        if not frontal:
            printLog("paso1")  
            faces1 = face_cascade1.detectMultiScale(gray, 1.01,50)
            for (x,y,w,h) in faces1:
                frontal=True
                printLog("Es frontal1")

        if not frontal:
            printLog("paso2")  
            faces2 = face_cascade2.detectMultiScale(gray, 1.01,50)
            for (x,y,w,h) in faces2:
                frontal=True
                printLog("Es frontal2")

        if not frontal:
            printLog("paso3")  
            faces3 = face_cascade3.detectMultiScale(gray, 1.01,50)
            for (x,y,w,h) in faces3:
                frontal=True
                printLog("Es frontal3")

        if not frontal:
            printLog("paso4")  
            faces4 = face_cascade4.detectMultiScale(gray, 1.01,50)
            for (x,y,w,h) in faces4:
                frontal=True
                printLog("Es frontal4")

        if not frontal:
            printLog("paso5")  
            faces5 = face_cascade5.detectMultiScale(gray, 1.01,50)
            for (x,y,w,h) in faces5:
                frontal=True
                printLog("Es frontal5")

        if not frontal:
            printLog("paso7")  
            faces7 = face_cascade7.detectMultiScale(gray, 1.01,50)
            for (x,y,w,h) in faces7:
                frontal=True
                printLog("Es frontal7")

    return frontal



def esfrontal(imagePath):

    printLog("comprobando si es frontal")
    esFrontal=False

    PREDICTOR_PATH = "motor/models/shape_predictor_68_face_landmarks.dat"
    detector = dlib.get_frontal_face_detector()
    predictor = dlib.shape_predictor(PREDICTOR_PATH)

    # load the input image, resize it, and convert it to grayscale
    #image = plt.imread('motor/caras/frontal/1_2021-07-14_00:19:3.370305.avi_1.121212.jpg')
    image = plt.imread(imagePath)
    orig = image
    image = imutils.resize(image, width=500)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # detect faces in the grayscale image
    rects = detector(gray, 1)

    x1=0
    x2=0
    x3=0
    x4=0
    y1=0
    y2=0
    y3=0
    y4=0

    detecto_cara=False

    # loop over the face detections
    for (i, rect) in enumerate(rects):
        # determine the facial landmarks for the face region, then
        # convert the facial landmark (x, y)-coordinates to a NumPy
        # array

        detecto_cara=True
        printLog("hay alguna cara")

        shape = predictor(gray, rect)
        shape = face_utils.shape_to_np(shape)

        # loop over the (x, y)-coordinates for the facial landmarks
        # and draw them on the image
        pos=0


        for (x, y) in shape:
        
            # print("pos:"+str(pos))
            esojo=False
            if pos==36:
              printLog("x,y (37)"+str(x)+","+str(y))
              esojo=True
              x1=x
              y1=y
            if pos==39:
              printLog("x,y (40)"+str(x)+","+str(y))
              esojo=True
              x2=x
              y2=y
            if pos==42:
              printLog("x,y (43)"+str(x)+","+str(y))
              esojo=True
              x3=x
              y3=y
            if pos==45:
              printLog("x,y (46)"+str(x)+","+str(y))
              esojo=True
              x4=x
              y4=y

            pos=pos+1

    if x1>0 and x2>0 and x3>0 and x4>0:
        ancho1=x2-x1
        printLog("ancho ojo 1:"+str(ancho1))
        ancho2=x4-x3
        printLog("ancho ojo 2:"+str(ancho2))

        maxim=0
        minim=9999
        if y1>maxim:
            maxim=y1
        if y1<minim:
            minim=y1

        if y2>maxim:
            maxim=y2
        if y2<minim:
            minim=y2
          
        if y3>maxim:
            maxim=y3
        if y3<minim:
            minim=y3
          
        if y4>maxim:
            maxim=y4
        if y4<minim:
            minim=y4                


        diff1=abs(ancho2-ancho1)
        printLog("Diferencia ojos ancho:"+str(diff1))
        diff2=abs(maxim-minim)
        printLog("Diferencia entre alturas:"+str(diff2))


        if diff1<=DIFERENCIA_ANCHO_OJOS and diff2<=DIFERENCIA_ALTURAS:
            esFrontal=True

    if not detecto_cara:
        esFrontal=esfrontal2(imagePath)

    return(esFrontal)


def variance_of_laplacian(image):
    # compute the Laplacian of the image and then return the focus
    # measure, which is simply the variance of the Laplacian
    return cv2.Laplacian(image, cv2.CV_64F).var()

def comprueba_enfocada(imagePath):

    enfocada=False

    image = cv2.imread(imagePath)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    fm = variance_of_laplacian(gray)

    printLog("el fm de la imagen es: "+str(fm))

    devolver=0
    #if fm < UMBRAL_ENFOQUE_MAXIMO:
    if fm > UMBRAL_ENFOQUE_MAXIMO:    
        enfocada=True
        devolver=fm

    return devolver



def enfocar_imagen(image, kernel_size=(7, 7), sigma=2.0, amount=1.5, threshold=0):
    """Return a sharpened version of the image, using an unsharp mask."""
    blurred = cv2.GaussianBlur(image, kernel_size, sigma)
    sharpened = float(amount + 1) * image - float(amount) * blurred
    sharpened = np.maximum(sharpened, np.zeros(sharpened.shape))
    sharpened = np.minimum(sharpened, 255 * np.ones(sharpened.shape))
    sharpened = sharpened.round().astype(np.uint8)
    if threshold > 0:
        low_contrast_mask = np.absolute(image - blurred) < threshold
        np.copyto(sharpened, image, where=low_contrast_mask)
    return sharpened






def es_frontal_new(imagePath):
    
    input = io.imread(imagePath)
    preds = fa.get_landmarks(input)

    es_frontal=False



    if preds is not None:

        for (x) in preds:

            izq=x[0][0]
            der=x[16][0]
            toxa=x[30][0]
            centro=(izq+der)/2
            #mar_izq=izq+2
            #mar_der=der-2
            mar_izq=((izq+centro)/2)
            mar_der=((der+centro)/2)
            toxa_y=x[30][1]
            barbilla_y=x[8][1]
            toxa_x=x[30][0]
            barbilla_x=x[8][0]


            printLog("izq:"+str(izq))
            printLog("der:"+str(der))
            printLog("toxa:"+str(toxa))
            printLog("centro:"+str(centro))
            printLog("mar_izq:"+str(mar_izq))
            printLog("mar_izq:"+str(mar_izq))
            printLog("toxa_x:"+str(toxa_x))
            printLog("toxa_y:"+str(toxa_y))
            printLog("barbilla_x:"+str(barbilla_x))
            printLog("barbilla_y:"+str(barbilla_y))


            if mar_izq<toxa and toxa<mar_der:
                es_frontal=True
            else:
                if izq<toxa and toxa<der and (abs(toxa_y-barbilla_y)>5 and abs(toxa_x-barbilla_x)<20):
                    es_frontal=True


    return es_frontal




path_imgs='motor/tests/'


count_global=0
sigue=True

imagePaths = list(paths.list_images(path_imgs))


for (i, imagePath) in enumerate(imagePaths):
    name_file = imagePath.split(os.path.sep)[-1]
    printLog('analizando:'+name_file)


    pasaprimerosfiltros=False
    enfoque=comprueba_enfocada(imagePath)
    if enfoque>0:
        printLog('Es enfocada de momento:'+imagePath)
        #if esfrontal(imagePath):
        if es_frontal_new(imagePath):
            printLog('es frontal y enfocada:'+imagePath)
            copyfile(imagePath , "./motor/removidas/cara/"+name_file)
        else:
            printLog("Es lateral")
            copyfile(imagePath , "./motor/removidas/perfil/"+name_file)    

    else:
        printLog('Es desenfocada:'+imagePath)
        copyfile(imagePath , "./motor/removidas/desenfocada/"+name_file)

    printLog()


