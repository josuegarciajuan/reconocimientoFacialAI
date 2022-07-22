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


DIFERENCIA_ANCHO_OJOS=7
DIFERENCIA_ALTURAS=100
UMBRAL_BRILLO=1000



def printLog(*args, **kwargs):
    print(*args, **kwargs)
    # with open('motor/decara_o_perfil2.out','a') as file:
    #     print(*args, **kwargs, file=file)

def esfrontal(imagePath):

    frontal=False

    PREDICTOR_PATH = "motor/models/shape_predictor_68_face_landmarks.dat"
    detector = dlib.get_frontal_face_detector()
    predictor = dlib.shape_predictor(PREDICTOR_PATH)
    face6 = "motor/models/haarcascade_profileface.xml"
    face_cascade6 = cv2.CascadeClassifier(face6)
    eye1 = "motor/models/haarcascade_eye.xml"
    eye2 = "motor/models/haarcascade_eye_tree_eyeglasses.xml"
    eye_cascade1 = cv2.CascadeClassifier(eye1)
    eye_cascade2 = cv2.CascadeClassifier(eye2)

    img = cv2.imread(imagePath)
    img = imutils.resize(img, width=500)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) # convert to grayscale    


    eslateral=False
    faces6 = face_cascade6.detectMultiScale(gray, 1.01,50)
    for (x,y,w,h) in faces6:
        eslateral=True
    if eslateral:
        printLog("es lateral 1")
        # copyfile(imagePath, 'caras/pruebas_res/nocara/'+name_file)
        josue=1
    else:
        printLog("es frontal de mommento")     
        flipped = cv2.flip(gray, 1)
        faces6 = face_cascade6.detectMultiScale(flipped, 1.01,50)
        for (x,y,w,h) in faces6:
            eslateral=True
        if eslateral:
            printLog("es lateral 2")     
            #copyfile(imagePath, 'caras/pruebas_res/nocara/'+name_file)
            josue=1
        else:
            printLog("es frontal 1")     
            # copyfile(imagePath, 'caras/pruebas_res/escara/'+name_file)
            frontal=True
   
    ojos_detectado=False
    
    if eslateral:
        printLog("afirmo qe es lateral")  
        # ----------------------------------
        
        #if not ojos_detectado:
        image2 = cv2.imread(imagePath)
        image2 = imutils.resize(image2, width=500)
        gray2 = cv2.cvtColor(image2, cv2.COLOR_BGR2GRAY)
        rects = detector(gray2, 1)

        for (w, rect) in enumerate(rects):
          printLog("ultim algoritmo hay cara")     
          shape = predictor(gray, rect)
          shape = face_utils.shape_to_np(shape)
         
          ojos=0
          for (name, (z, j)) in face_utils.FACIAL_LANDMARKS_IDXS.items():
            if name=="right_eye":
              ojos=ojos+1
            if name=="left_eye":
              ojos=ojos+1

          printLog("ojos_1_3:"+str(ojos))
          if ojos==2:
            printLog("es frontal 2")
            # copyfile(imagePath, 'caras/pruebas_res/escara/'+name_file)
            ojos_detectado=True
            frontal=True
        if not frontal:
            printLog("Es lateral!")

    return frontal







def esfrontal2(imagePath):

    frontal=False

    PREDICTOR_PATH = "motor/models/shape_predictor_68_face_landmarks.dat"
    detector = dlib.get_frontal_face_detector()
    predictor = dlib.shape_predictor(PREDICTOR_PATH)
    face6 = "motor/models/haarcascade_profileface.xml"
    face_cascade6 = cv2.CascadeClassifier(face6)
    eye1 = "motor/models/haarcascade_eye.xml"
    eye2 = "motor/models/haarcascade_eye_tree_eyeglasses.xml"
    eye_cascade1 = cv2.CascadeClassifier(eye1)
    eye_cascade2 = cv2.CascadeClassifier(eye2)

    img = cv2.imread(imagePath)
    img = imutils.resize(img, width=500)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) # convert to grayscale    



    image2 = cv2.imread(imagePath)
    image2 = imutils.resize(image2, width=500)
    gray2 = cv2.cvtColor(image2, cv2.COLOR_BGR2GRAY)
    rects = detector(gray2, 1)

    for (w, rect) in enumerate(rects):
      printLog("hay cara")     
      shape = predictor(gray, rect)
      shape = face_utils.shape_to_np(shape)
     
      ojos=0
      for (name, (z, j)) in face_utils.FACIAL_LANDMARKS_IDXS.items():
        if name=="right_eye":
          ojos=ojos+1
        if name=="left_eye":
          ojos=ojos+1

      printLog("ojos:"+str(ojos))
      if ojos>=2 and ojos<=4:
        printLog("es frontal 2")
        # copyfile(imagePath, 'caras/pruebas_res/escara/'+name_file)
        frontal=True

    if not frontal:
        printLog("Es lateral de momento")


        eslateral=False
        faces6 = face_cascade6.detectMultiScale(gray, 1.01,50)
        for (x,y,w,h) in faces6:
            eslateral=True
        if eslateral:
            printLog("es lateral 1")
            # copyfile(imagePath, 'caras/pruebas_res/nocara/'+name_file)
            josue=1
        else:
            printLog("es frontal de mommento")     
            flipped = cv2.flip(gray, 1)
            faces6 = face_cascade6.detectMultiScale(flipped, 1.01,50)
            for (x,y,w,h) in faces6:
                eslateral=True
            if eslateral:
                printLog("es lateral 2")     
                #copyfile(imagePath, 'caras/pruebas_res/nocara/'+name_file)
                josue=1
            else:
                printLog("es frontal 1")     
                # copyfile(imagePath, 'caras/pruebas_res/escara/'+name_file)
                frontal=True
  
    return frontal







def esfrontal3(imagePath):

    frontal=False

    PREDICTOR_PATH = "motor/models/shape_predictor_68_face_landmarks.dat"
    detector = dlib.get_frontal_face_detector()
    predictor = dlib.shape_predictor(PREDICTOR_PATH)
    face6 = "motor/models/haarcascade_profileface.xml"
    face_cascade6 = cv2.CascadeClassifier(face6)
    eye1 = "motor/models/haarcascade_eye.xml"
    eye2 = "motor/models/haarcascade_eye_tree_eyeglasses.xml"
    eye_cascade1 = cv2.CascadeClassifier(eye1)
    eye_cascade2 = cv2.CascadeClassifier(eye2)


    face1 = "motor/models/haarcascade_frontalface2.xml"
    face2 = "motor/models/haarcascade_frontalface_alt.xml"
    face3 = "motor/models/haarcascade_frontalface_alt2.xml"
    face4 = "motor/models/haarcascade_frontalface_alt_tree.xml"
    face5 = "motor/models/haarcascade_frontalface_default.xml"
    face6 = "motor/models/haarcascade_profileface.xml"

    face_cascade1 = cv2.CascadeClassifier(face1)
    face_cascade2 = cv2.CascadeClassifier(face2)
    face_cascade3 = cv2.CascadeClassifier(face3)
    face_cascade4 = cv2.CascadeClassifier(face4)
    face_cascade5 = cv2.CascadeClassifier(face5)
    face_cascade6 = cv2.CascadeClassifier(face6)

    img = cv2.imread(imagePath)
    img = imutils.resize(img, width=500)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) # convert to grayscale    



    image2 = cv2.imread(imagePath)
    image2 = imutils.resize(image2, width=500)
    gray2 = cv2.cvtColor(image2, cv2.COLOR_BGR2GRAY)
    rects = detector(gray2, 1)

    for (w, rect) in enumerate(rects):
      printLog("hay cara")     
      shape = predictor(gray, rect)
      shape = face_utils.shape_to_np(shape)
     
      ojos=0
      for (name, (z, j)) in face_utils.FACIAL_LANDMARKS_IDXS.items():
        if name=="right_eye":
          ojos=ojos+1
        if name=="left_eye":
          ojos=ojos+1

      printLog("ojos:"+str(ojos))
      if ojos>=2 and ojos<=4:
        printLog("es frontal 2")
        # copyfile(imagePath, 'caras/pruebas_res/escara/'+name_file)
        frontal=True


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

    return frontal







def esfrontal3_1(imagePath):

    frontal=False

    PREDICTOR_PATH = "motor/models/shape_predictor_68_face_landmarks.dat"
    detector = dlib.get_frontal_face_detector()
    predictor = dlib.shape_predictor(PREDICTOR_PATH)
    face6 = "motor/models/haarcascade_profileface.xml"
    face_cascade6 = cv2.CascadeClassifier(face6)
    eye1 = "motor/models/haarcascade_eye.xml"
    eye2 = "motor/models/haarcascade_eye_tree_eyeglasses.xml"
    eye_cascade1 = cv2.CascadeClassifier(eye1)
    eye_cascade2 = cv2.CascadeClassifier(eye2)


    face1 = "motor/models/haarcascade_frontalface2.xml"
    face2 = "motor/models/haarcascade_frontalface_alt.xml"
    face3 = "motor/models/haarcascade_frontalface_alt2.xml"
    face4 = "motor/models/haarcascade_frontalface_alt_tree.xml"
    face5 = "motor/models/haarcascade_frontalface_default.xml"
    face6 = "motor/models/haarcascade_profileface.xml"

    face_cascade1 = cv2.CascadeClassifier(face1)
    face_cascade2 = cv2.CascadeClassifier(face2)
    face_cascade3 = cv2.CascadeClassifier(face3)
    face_cascade4 = cv2.CascadeClassifier(face4)
    face_cascade5 = cv2.CascadeClassifier(face5)
    face_cascade6 = cv2.CascadeClassifier(face6)

    img = cv2.imread(imagePath)
    img = imutils.resize(img, width=500)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) # convert to grayscale    



    image2 = cv2.imread(imagePath)
    image2 = imutils.resize(image2, width=500)
    gray2 = cv2.cvtColor(image2, cv2.COLOR_BGR2GRAY)
    rects = detector(gray2, 1)

    for (w, rect) in enumerate(rects):
      printLog("hay cara")     
      shape = predictor(gray, rect)
      shape = face_utils.shape_to_np(shape)
     
      ojos=0
      for (name, (z, j)) in face_utils.FACIAL_LANDMARKS_IDXS.items():
        if name=="right_eye":
          ojos=ojos+1
        if name=="left_eye":
          ojos=ojos+1

      printLog("ojos:"+str(ojos))
      if ojos>=2 and ojos<=4:
        printLog("es frontal 2")
        # copyfile(imagePath, 'caras/pruebas_res/escara/'+name_file)
        frontal=True


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

    return frontal







def esfrontal3_2(imagePath):

    frontal=False


    face1 = "motor/models/haarcascade_frontalface2.xml"
    face2 = "motor/models/haarcascade_frontalface_alt.xml"
    face3 = "motor/models/haarcascade_frontalface_alt2.xml"
    face4 = "motor/models/haarcascade_frontalface_alt_tree.xml"
    face5 = "motor/models/haarcascade_frontalface_default.xml"
    face6 = "motor/models/haarcascade_profileface.xml"

    face_cascade1 = cv2.CascadeClassifier(face1)
    face_cascade2 = cv2.CascadeClassifier(face2)
    face_cascade3 = cv2.CascadeClassifier(face3)
    face_cascade4 = cv2.CascadeClassifier(face4)
    face_cascade5 = cv2.CascadeClassifier(face5)
    face_cascade6 = cv2.CascadeClassifier(face6)

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

    return frontal



























def esfrontal_AnalizandoOjos(imagePath):

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
        esFrontal=esfrontal3_2(imagePath)


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

    if fm < UMBRAL_BRILLO:
        enfocada=True

    return enfocada




path_imgs="motor/caras/test"
imagePaths = list(paths.list_images(path_imgs))

for (i, imagePath) in enumerate(imagePaths):
    name_file = imagePath.split(os.path.sep)[-1]

    printLog("Analizar fichero:"+imagePath)


    if comprueba_enfocada(imagePath):
        if esfrontal_AnalizandoOjos(imagePath):
            printLog('ES FRONTAL')
            copyfile(imagePath, 'motor/caras/frontal2/'+name_file)
        else:
            printLog('ES LATERAL')
            copyfile(imagePath, 'motor/caras/lateral2/'+name_file)
    else:
        printLog('DESENFOCADA')
        copyfile(imagePath, 'motor/caras/desenfocadas2/'+name_file)


    printLog()

