
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

# https://towardsdatascience.com/face-landmark-detection-using-python-1964cb620837





UMBRAL_ENFOQUE=1000 #para considerar una foto desenfocada ya y al comparar 1 a 1 con todo el diccionario, ya pasaria a ver si las 2 tienen muxa diferencia de enfoque
#UMBRAL_ENFOQUE_MAXIMO=200 # mas de este desenfoque , se descartan
UMBRAL_ENFOQUE_MAXIMO=10


def printLog(*args, **kwargs):
    print(*args, **kwargs)
    
    with open('posicion_cara2.out','a') as file:
      print(*args, **kwargs, file=file)

printLog("paso0")


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


def modoNativo(imagePath,frame):
    
    #cv2.rectangle(frame,(x,y),(x+w,y+h),(255,0,0),2)


    font = cv2.FONT_HERSHEY_SIMPLEX
    fontScale = 0.5
    color = (255, 0, 0) #BGR
    thickness = 1
    


    printLog("-------------Analizando en modoNativo-------------")

    input = io.imread(imagePath)
    preds = fa.get_landmarks(input)

    es_frontal=False



    if preds is not None:

        printLog("Tiene caras1")

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

            
            printLog("0:(parte izquierda cara)"+"->"+str(x[0][0])+"/"+str(x[0][1]))
            #x=int(x[0][0])
            #y=int(x[0][1])
            #frame = cv2.putText(frame, "0", (x,y), font, fontScale, color, thickness, cv2.LINE_AA)

            printLog("16:(parte derecha cara)"+"->"+str(x[16][0])+"/"+str(x[16][1]))
            #frame = cv2.putText(frame, "16", (x[16][0],x[16][1]), font, fontScale, color, thickness, cv2.LINE_AA)

            printLog("7:(barbilla1)"+"->"+str(x[7][0])+"/"+str(x[7][1]))
            #frame = cv2.putText(frame, "7", (x[7][0],x[7][1]), font, fontScale, color, thickness, cv2.LINE_AA)

            printLog("8:(barbilla2)"+"->"+str(x[8][0])+"/"+str(x[8][1]))
            #frame = cv2.putText(frame, "8", (x[8][0],x[8][1]), font, fontScale, color, thickness, cv2.LINE_AA)

            printLog("9:(barbilla3)"+"->"+str(x[9][0])+"/"+str(x[9][1]))
            #frame = cv2.putText(frame, "9", (x[9][0],x[9][1]), font, fontScale, color, thickness, cv2.LINE_AA)

            printLog("27:(toxa arriba)"+"->"+str(x[27][0])+"/"+str(x[27][1]))
            #frame = cv2.putText(frame, "27", (x[27][0],x[27][1]), font, fontScale, color, thickness, cv2.LINE_AA)

            printLog("33:(punta toxa)"+"->"+str(x[33][0])+"/"+str(x[33][1]))
            #frame = cv2.putText(frame, "33", (x[33][0],x[33][1]), font, fontScale, color, thickness, cv2.LINE_AA)

            printLog("31:(izq toxa)"+"->"+str(x[31][0])+"/"+str(x[31][1]))
            #frame = cv2.putText(frame, "31", (x[31][0],x[31][1]), font, fontScale, color, thickness, cv2.LINE_AA)

            printLog("35:(der toxa)"+"->"+str(x[35][0])+"/"+str(x[35][1]))
            #frame = cv2.putText(frame, "35", (x[35][0],x[35][1]), font, fontScale, color, thickness, cv2.LINE_AA)

            printLog("36:(ojo izq fuera)"+"->"+str(x[36][0])+"/"+str(x[36][1]))
            #frame = cv2.putText(frame, "36", (x[36][0],x[36][1]), font, fontScale, color, thickness, cv2.LINE_AA)

            printLog("39:(ojo izq dentro)"+"->"+str(x[39][0])+"/"+str(x[39][1]))
            #frame = cv2.putText(frame, "39", (x[39][0],x[39][1]), font, fontScale, color, thickness, cv2.LINE_AA)

            printLog("45:(ojo der fuera)"+"->"+str(x[45][0])+"/"+str(x[45][1]))
            #frame = cv2.putText(frame, "45", (x[45][0],x[45][1]), font, fontScale, color, thickness, cv2.LINE_AA)

            printLog("42:(ojo der dentro)"+"->"+str(x[42][0])+"/"+str(x[42][1]))
            #frame = cv2.putText(frame, "42", (x[42][0],x[42][1]), font, fontScale, color, thickness, cv2.LINE_AA)

            printLog("48:(boca izq)"+"->"+str(x[48][0])+"/"+str(x[48][1]))
            #frame = cv2.putText(frame, "48", (x[48][0],x[48][1]), font, fontScale, color, thickness, cv2.LINE_AA)

            printLog("54:(boca der)"+"->"+str(x[54][0])+"/"+str(x[54][1]))
            #frame = cv2.putText(frame, "54", (x[54][0],x[54][1]), font, fontScale, color, thickness, cv2.LINE_AA)

            printLog("51:(boca arriba)"+"->"+str(x[51][0])+"/"+str(x[51][1]))
            #frame = cv2.putText(frame, "51", (x[51][0],x[51][1]), font, fontScale, color, thickness, cv2.LINE_AA)

            printLog("57:(boca abajo)"+"->"+str(x[57][0])+"/"+str(x[57][1]))
            #frame = cv2.putText(frame, "57", (x[57][0],x[57][1]), font, fontScale, color, thickness, cv2.LINE_AA)

            printLog("30:(posiblepuntatoxa)"+"->"+str(x[30][0])+"/"+str(x[30][1]))
			


            """
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
            """

    # return es_frontal
    return frame



def modoPredictor(imagePath,frame):


    font = cv2.FONT_HERSHEY_SIMPLEX
    fontScale = 0.5
    color = (0, 0, 255) #BGR
    thickness = 1


    printLog("-------------Analizando en modoPredictor-------------")

    PREDICTOR_PATH = "../../models/shape_predictor_68_face_landmarks.dat"
    detector = dlib.get_frontal_face_detector()
    predictor = dlib.shape_predictor(PREDICTOR_PATH)

    image = plt.imread(imagePath)
    orig = image
    image = imutils.resize(image, width=500)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    rects = detector(gray, 1)


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
        
            if pos==0:
                printLog("0), ("+str(x)+"/"+str(y))
                frame = cv2.putText(frame, str(pos), (x,y), font, fontScale, color, thickness, cv2.LINE_AA)

            if pos==16:
                printLog("16:(parte derecha cara)"+"->"+str(x)+"/"+str(y))
                frame = cv2.putText(frame, str(pos), (x,y), font, fontScale, color, thickness, cv2.LINE_AA)

            if pos==7:
                printLog("7:(barbilla1)"+"->"+str(x)+"/"+str(y))
                frame = cv2.putText(frame, str(pos), (x,y), font, fontScale, color, thickness, cv2.LINE_AA)

            if pos==8:
                printLog("8:(barbilla2)"+"->"+str(x)+"/"+str(y))
                frame = cv2.putText(frame, str(pos), (x,y), font, fontScale, color, thickness, cv2.LINE_AA)

            if pos==9:
                printLog("9:(barbilla3)"+"->"+str(x)+"/"+str(y))
                frame = cv2.putText(frame, str(pos), (x,y), font, fontScale, color, thickness, cv2.LINE_AA)

            if pos==27:
                printLog("27:(toxa arriba)"+"->"+str(x)+"/"+str(y))
                frame = cv2.putText(frame, str(pos), (x,y), font, fontScale, color, thickness, cv2.LINE_AA)

            if pos==33:   
                printLog("33:(punta toxa)"+"->"+str(x)+"/"+str(y))
                frame = cv2.putText(frame, str(pos), (x,y), font, fontScale, color, thickness, cv2.LINE_AA)

            if pos==31:
                printLog("31:(izq toxa)"+"->"+str(x)+"/"+str(y))
                frame = cv2.putText(frame, str(pos), (x,y), font, fontScale, color, thickness, cv2.LINE_AA)

            if pos==35:
                printLog("35:(der toxa)"+"->"+str(x)+"/"+str(y))
                frame = cv2.putText(frame, str(pos), (x,y), font, fontScale, color, thickness, cv2.LINE_AA)

            if pos==36:
                printLog("36:(ojo izq fuera)"+"->"+str(x)+"/"+str(y))
                frame = cv2.putText(frame, str(pos), (x,y), font, fontScale, color, thickness, cv2.LINE_AA)

            if pos==39:
                printLog("39:(ojo izq dentro)"+"->"+str(x)+"/"+str(y))
                frame = cv2.putText(frame, str(pos), (x,y), font, fontScale, color, thickness, cv2.LINE_AA)

            if pos==45:
                printLog("45:(ojo der fuera)"+"->"+str(x)+"/"+str(y))
                frame = cv2.putText(frame, str(pos), (x,y), font, fontScale, color, thickness, cv2.LINE_AA)

            if pos==42:
                printLog("42:(ojo der dentro)"+"->"+str(x)+"/"+str(y))
                frame = cv2.putText(frame, str(pos), (x,y), font, fontScale, color, thickness, cv2.LINE_AA)

            if pos==48:
                printLog("48:(boca izq)"+"->"+str(x)+"/"+str(y))
                frame = cv2.putText(frame, str(pos), (x,y), font, fontScale, color, thickness, cv2.LINE_AA)

            if pos==54:
                printLog("54:(boca der)"+"->"+str(x)+"/"+str(y))
                frame = cv2.putText(frame, str(pos), (x,y), font, fontScale, color, thickness, cv2.LINE_AA)

            if pos==51:
                printLog("51:(boca arriba)"+"->"+str(x)+"/"+str(y))
                frame = cv2.putText(frame, str(pos), (x,y), font, fontScale, color, thickness, cv2.LINE_AA)

            if pos==57:
                printLog("57:(boca abajo)"+"->"+str(x)+"/"+str(y))
                frame = cv2.putText(frame, str(pos), (x,y), font, fontScale, color, thickness, cv2.LINE_AA)


            """
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
            """

            pos=pos+1
    return frame




def pinta1(imagePath,frame):



    font = cv2.FONT_HERSHEY_SIMPLEX
    fontScale = 0.5
    color = (0, 0, 255) #BGR
    thickness = 1
        
    frame = cv2.putText(frame, str(0), (146,218), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(16), (375,238), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(7), (234,387), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(8), (270,395), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(9), (303,391), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(27), (290,226), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(33), (286,299), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(31), (266,291), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(35), (303,295), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(36), (218,218), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(39), (254,226), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(45), (347,226), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(42), (311,226), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(48), (238,327), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(54), (319,331), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(51), (282,323), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(57), (282,339), font, fontScale, color, thickness, cv2.LINE_AA)


    return frame


def pinta2(imagePath,frame):



    font = cv2.FONT_HERSHEY_SIMPLEX
    fontScale = 0.5
    color = (0, 0, 255) #BGR
    thickness = 1
    
    frame = cv2.putText(frame, str(0), (168,219), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(16), (388,251), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(7), (268,391), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(8), (304,399), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(9), (332,395), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(27), (336,231), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(33), (328,303), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(31), (308,291), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(35), (344,299), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(36), (260,223), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(39), (296,227), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(45), (376,235), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(42), (348,235), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(48), (276,327), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(54), (348,339), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(51), (328,327), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(57), (324,343), font, fontScale, color, thickness, cv2.LINE_AA)


    return frame


def pinta3(imagePath,frame):



    font = cv2.FONT_HERSHEY_SIMPLEX
    fontScale = 0.5
    color = (0, 0, 255) #BGR
    thickness = 1
    
    frame = cv2.putText(frame, str(0), (171,230), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(16), (319,289), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(7), (249,415), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(8), (267,426), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(9), (286,426), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(27), (330,278), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(33), (319,341), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(31), (308,334), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(35), (315,337), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(36), (282,256), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(39), (297,267), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(45), (308,278), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(42), (312,274), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(48), (282,359), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(54), (297,367), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(51), (315,363), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(57), (308,378), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(30), (349,334), font, fontScale, color, thickness, cv2.LINE_AA)



    return frame




def pinta4(imagePath,frame):




    font = cv2.FONT_HERSHEY_SIMPLEX
    fontScale = 0.5
    color = (0, 0, 255) #BGR
    thickness = 1
    
    frame = cv2.putText(frame, str(0), (129,236), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(16), (355,224), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(7), (173,387), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(8), (200,395), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(9), (236,387), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(27), (196,220), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(33), (192,295), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(31), (177,287), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(35), (212,287), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(36), (149,224), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(39), (181,224), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(45), (272,220), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(42), (232,220), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(48), (165,327), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(54), (240,327), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(51), (192,319), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(57), (192,335), font, fontScale, color, thickness, cv2.LINE_AA)


    return frame




def pinta5(imagePath,frame):




    font = cv2.FONT_HERSHEY_SIMPLEX
    fontScale = 0.5
    color = (0, 0, 255) #BGR
    thickness = 1
    
    frame = cv2.putText(frame, str(0), (202,237), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(16), (389,163), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(7), (228,402), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(8), (245,407), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(9), (276,389), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(27), (184,215), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(33), (197,298), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(31), (202,298), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(35), (215,285), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(36), (206,228), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(39), (210,219), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(45), (250,193), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(42), (228,202), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(48), (223,337), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(54), (250,320), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(51), (206,320), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(57), (210,337), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(30), (162,285), font, fontScale, color, thickness, cv2.LINE_AA)


    return frame



def pinta6(imagePath,frame):


    font = cv2.FONT_HERSHEY_SIMPLEX
    fontScale = 0.5
    color = (0, 0, 255) #BGR
    thickness = 1
    
    frame = cv2.putText(frame, str(0), (267,209), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(16), (491,232), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(7), (327,249), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(8), (358,246), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(9), (392,252), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(27), (375,116), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(33), (364,156), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(31), (349,158), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(35), (380,158), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(36), (318,144), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(39), (347,136), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(45), (437,147), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(42), (403,136), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(48), (330,198), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(54), (400,201), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(51), (361,173), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(57), (361,187), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(30), (366,124), font, fontScale, color, thickness, cv2.LINE_AA)
    

    return frame




def pinta7(imagePath,frame):

    font = cv2.FONT_HERSHEY_SIMPLEX
    fontScale = 0.5
    color = (0, 0, 255) #BGR
    thickness = 1
    
    frame = cv2.putText(frame, str(0), (249,188), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(16), (511,202), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(7), (331,409), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(8), (373,423), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(9), (414,409), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(27), (387,275), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(33), (377,349), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(31), (359,340), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(35), (401,340), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(36), (304,252), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(39), (350,257), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(45), (460,257), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(42), (414,262), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(48), (331,363), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(54), (424,367), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(51), (377,372), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(57), (377,386), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(30), (382,349), font, fontScale, color, thickness, cv2.LINE_AA)


    return frame





def pinta8(imagePath,frame):


    font = cv2.FONT_HERSHEY_SIMPLEX
    fontScale = 0.5
    color = (0, 0, 255) #BGR
    thickness = 1

    frame = cv2.putText(frame, str(0), (281,178), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(16), (442,161), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(7), (308,292), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(8), (325,298), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(9), (348,292), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(27), (308,167), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(33), (308,219), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(31), (302,219), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(35), (322,216), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(36), (287,170), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(39), (305,167), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(45), (366,161), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(42), (337,164), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(48), (299,248), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(54), (340,242), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(51), (308,234), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(57), (308,254), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(30), (296,207), font, fontScale, color, thickness, cv2.LINE_AA)

    return frame




def pinta9(imagePath,frame):

    font = cv2.FONT_HERSHEY_SIMPLEX
    fontScale = 0.5
    color = (0, 0, 255) #BGR
    thickness = 1

    frame = cv2.putText(frame, str(0), (369,120), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(16), (473,115), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(7), (386,192), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(8), (399,194), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(9), (414,192), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(27), (393,111), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(33), (393,142), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(31), (386,142), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(35), (403,141), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(36), (375,111), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(39), (388,111), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(45), (430,109), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(42), (412,111), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(48), (380,161), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(54), (416,159), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(51), (392,154), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(57), (392,166), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(30), (388,133), font, fontScale, color, thickness, cv2.LINE_AA)

    return frame




def pinta10(imagePath,frame):

    font = cv2.FONT_HERSHEY_SIMPLEX
    fontScale = 0.5
    color = (0, 0, 255) #BGR
    thickness = 1

    frame = cv2.putText(frame, str(0), (308,173), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(16), (370,158), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(7), (313,248), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(8), (320,251), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(9), (328,245), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(27), (302,168), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(33), (302,203), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(31), (304,201), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(35), (308,199), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(36), (313,170), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(39), (313,170), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(45), (321,161), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(42), (314,165), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(48), (313,217), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(54), (318,213), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(51), (302,212), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(57), (306,225), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(30), (292,196), font, fontScale, color, thickness, cv2.LINE_AA)

    return frame


def pinta11(imagePath,frame):

    font = cv2.FONT_HERSHEY_SIMPLEX
    fontScale = 0.5
    color = (0, 0, 255) #BGR
    thickness = 1

    frame = cv2.putText(frame, str(0), (222,152), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(16), (315,121), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(7), (234,250), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(8), (246,253), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(9), (255,246), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(27), (217,143), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(33), (215,186), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(31), (217,186), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(35), (222,181), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(36), (229,145), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(39), (227,143), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(45), (241,131), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(42), (231,135), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(48), (224,214), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(54), (231,207), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(51), (210,203), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(57), (217,224), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(30), (200,176), font, fontScale, color, thickness, cv2.LINE_AA)

    return frame



def pinta12(imagePath,frame):

    font = cv2.FONT_HERSHEY_SIMPLEX
    fontScale = 0.4
    color = (0, 0, 255) #BGR
    thickness = 1

    frame = cv2.putText(frame, str(0), (104,259), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(16), (288,276), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(7), (168,303), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(8), (196,303), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(9), (226,306), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(27), (196,186), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(33), (193,225), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(31), (179,228), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(35), (210,228), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(36), (140,212), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(39), (168,203), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(45), (249,206), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(42), (221,203), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(48), (165,259), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(54), (226,262), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(51), (193,239), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(57), (196,262), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(30), (193,203), font, fontScale, color, thickness, cv2.LINE_AA)
    return frame


def pinta13(imagePath,frame):

    font = cv2.FONT_HERSHEY_SIMPLEX
    fontScale = 0.4
    color = (0, 0, 255) #BGR
    thickness = 1

    frame = cv2.putText(frame, str(0), (104,259), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(16), (288,276), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(7), (168,303), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(8), (196,303), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(9), (226,306), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(27), (196,186), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(33), (193,225), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(31), (179,228), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(35), (210,228), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(36), (140,212), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(39), (168,203), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(45), (249,206), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(42), (221,203), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(48), (165,259), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(54), (226,262), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(51), (193,239), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(57), (196,262), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(30), (193,203), font, fontScale, color, thickness, cv2.LINE_AA)
    return frame

def pinta14(imagePath,frame):

    font = cv2.FONT_HERSHEY_SIMPLEX
    fontScale = 0.4
    color = (0, 0, 255) #BGR
    thickness = 1

    frame = cv2.putText(frame, str(0), (206,133), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(16), (364,153), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(7), (249,207), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(8), (275,212), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(9), (300,212), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(27), (285,97), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(33), (283,133), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(31), (267,130), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(35), (298,135), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(36), (239,105), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(39), (265,105), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(45), (334,115), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(42), (308,110), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(48), (244,161), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(54), (316,166), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(51), (280,143), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(57), (277,171), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(30), (283,115), font, fontScale, color, thickness, cv2.LINE_AA)
    return frame

def pinta15(imagePath,frame):


    font = cv2.FONT_HERSHEY_SIMPLEX
    fontScale = 0.4
    color = (0, 0, 255) #BGR
    thickness = 1

    frame = cv2.putText(frame, str(0), (245,137), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(16), (357,133), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(7), (286,191), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(8), (304,193), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(9), (322,189), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(27), (299,108), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(33), (301,139), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(31), (292,139), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(35), (312,139), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(36), (267,115), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(39), (285,113), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(45), (331,112), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(42), (313,112), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(48), (281,160), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(54), (324,157), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(51), (303,149), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(57), (303,167), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(30), (301,130), font, fontScale, color, thickness, cv2.LINE_AA)
    return frame

def pinta16(imagePath,frame):

    font = cv2.FONT_HERSHEY_SIMPLEX
    fontScale = 0.4
    color = (0, 0, 255) #BGR
    thickness = 1

    frame = cv2.putText(frame, str(0), (287,177), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(16), (441,167), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(7), (347,248), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(8), (373,251), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(9), (395,251), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(27), (365,132), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(33), (367,172), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(31), (355,172), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(35), (383,172), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(36), (319,142), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(39), (345,142), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(45), (410,142), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(42), (385,139), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(48), (332,205), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(54), (403,203), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(51), (370,185), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(57), (370,218), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(30), (367,155), font, fontScale, color, thickness, cv2.LINE_AA)
    return frame

def pinta17(imagePath,frame):


    font = cv2.FONT_HERSHEY_SIMPLEX
    fontScale = 0.4
    color = (0, 0, 255) #BGR
    thickness = 1

    frame = cv2.putText(frame, str(0), (236,160), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(16), (391,158), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(7), (287,187), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(8), (309,187), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(9), (334,187), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(27), (311,93), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(33), (311,122), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(31), (300,124), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(35), (325,124), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(36), (269,111), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(39), (291,107), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(45), (353,109), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(42), (331,107), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(48), (283,153), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(54), (340,153), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(51), (311,133), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(57), (311,153), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(30), (311,102), font, fontScale, color, thickness, cv2.LINE_AA)
    return frame

def pinta18(imagePath,frame):

    font = cv2.FONT_HERSHEY_SIMPLEX
    fontScale = 0.4
    color = (0, 0, 255) #BGR
    thickness = 1

    frame = cv2.putText(frame, str(0), (128,146), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(16), (275,143), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(7), (181,218), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(8), (205,221), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(9), (227,218), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(27), (201,102), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(33), (203,141), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(31), (188,141), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(35), (217,141), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(36), (159,114), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(39), (181,112), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(45), (244,112), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(42), (220,112), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(48), (172,175), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(54), (234,175), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(51), (203,155), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(57), (205,184), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(30), (203,126), font, fontScale, color, thickness, cv2.LINE_AA)
    return frame

def pinta19(imagePath,frame):

    font = cv2.FONT_HERSHEY_SIMPLEX
    fontScale = 0.4
    color = (0, 0, 255) #BGR
    thickness = 1

    frame = cv2.putText(frame, str(0), (233,204), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(16), (394,206), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(7), (290,265), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(8), (316,265), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(9), (341,267), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(27), (314,155), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(33), (314,194), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(31), (302,194), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(35), (329,194), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(36), (268,165), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(39), (292,162), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(45), (360,165), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(42), (333,162), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(48), (287,223), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(54), (343,226), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(51), (316,206), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(57), (316,226), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(30), (314,175), font, fontScale, color, thickness, cv2.LINE_AA)
    return frame


def pinta20(imagePath,frame):

    font = cv2.FONT_HERSHEY_SIMPLEX
    fontScale = 0.4
    color = (0, 0, 255) #BGR
    thickness = 1

    frame = cv2.putText(frame, str(0), (145,179), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(16), (303,176), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(7), (202,312), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(8), (227,323), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(9), (251,312), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(27), (224,220), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(33), (224,263), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(31), (213,258), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(35), (238,258), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(36), (175,211), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(39), (202,214), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(45), (271,211), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(42), (246,217), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(48), (200,279), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(54), (254,277), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(51), (227,274), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(57), (227,304), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(30), (224,260), font, fontScale, color, thickness, cv2.LINE_AA)
    return frame


def pinta21(imagePath,frame):

    font = cv2.FONT_HERSHEY_SIMPLEX
    fontScale = 0.4
    color = (0, 0, 255) #BGR
    thickness = 1

    frame = cv2.putText(frame, str(0), (133,187), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(16), (309,170), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(7), (200,333), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(8), (231,343), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(9), (258,330), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(27), (217,231), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(33), (221,279), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(31), (204,272), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(35), (238,272), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(36), (167,218), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(39), (197,221), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(45), (268,214), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(42), (241,221), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(48), (187,286), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(54), (265,279), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(51), (224,289), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(57), (228,313), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(30), (217,279), font, fontScale, color, thickness, cv2.LINE_AA)
    return frame


def pinta22(imagePath,frame):

    font = cv2.FONT_HERSHEY_SIMPLEX
    fontScale = 0.4
    color = (0, 0, 255) #BGR
    thickness = 1

    frame = cv2.putText(frame, str(0), (260,121), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(16), (368,127), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(7), (300,211), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(8), (315,217), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(9), (332,209), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(27), (324,149), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(33), (322,181), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(31), (311,177), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(35), (332,176), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(36), (288,144), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(39), (307,145), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(45), (354,142), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(42), (335,145), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(48), (294,181), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(54), (341,181), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(51), (320,187), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(57), (320,200), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(30), (324,181), font, fontScale, color, thickness, cv2.LINE_AA)
    return frame



def pinta23(imagePath,frame):

    font = cv2.FONT_HERSHEY_SIMPLEX
    fontScale = 0.4
    color = (0, 0, 255) #BGR
    thickness = 1

    frame = cv2.putText(frame, str(0), (234,171), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(16), (373,168), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(7), (286,284), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(8), (307,291), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(9), (328,284), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(27), (305,201), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(33), (305,244), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(31), (293,239), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(35), (314,239), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(36), (260,194), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(39), (283,197), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(45), (345,192), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(42), (321,197), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(48), (283,258), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(54), (328,258), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(51), (305,258), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(57), (305,269), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(30), (305,239), font, fontScale, color, thickness, cv2.LINE_AA)
    return frame



def pinta24(imagePath,frame):

    font = cv2.FONT_HERSHEY_SIMPLEX
    fontScale = 0.4
    color = (0, 0, 255) #BGR
    thickness = 1

    frame = cv2.putText(frame, str(0), (278,130), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(16), (362,156), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(7), (296,206), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(8), (310,213), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(9), (323,212), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(27), (326,158), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(33), (318,183), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(31), (312,178), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(35), (326,181), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(36), (298,149), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(39), (313,153), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(45), (349,160), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(42), (335,158), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(48), (296,183), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(54), (333,190), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(51), (318,187), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(57), (313,201), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(30), (321,180), font, fontScale, color, thickness, cv2.LINE_AA)
    return frame



def pinta25_mas(imagePath,frame):

    font = cv2.FONT_HERSHEY_SIMPLEX
    fontScale = 0.4
    color = (0, 0, 255) #BGR
    thickness = 1

    frame = cv2.putText(frame, str(0), (342,253), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(16), (662,292), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(7), (488,525), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(8), (502,535), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(9), (575,525), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(27), (478,389), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(33), (502,486), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(31), (483,482), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(35), (527,477), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(36), (391,380), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(39), (444,375), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(45), (585,351), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(42), (527,360), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(48), (488,491), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(54), (565,501), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(51), (507,511), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(57), (512,525), font, fontScale, color, thickness, cv2.LINE_AA)
    frame = cv2.putText(frame, str(30), (483,482), font, fontScale, color, thickness, cv2.LINE_AA)
    return frame




def es_posicion_cara(imagePath,posicion):
    

    printLog("-------------Analizando en posicon_cara-------------")

    input = io.imread(imagePath)
    preds = fa.get_landmarks(input)


    puntuacion=0
    if preds is not None:

        printLog("Tiene caras1")

        for (x) in preds:


            
            printLog("0:(parte izquierda cara)"+"->"+str(x[0][0])+"/"+str(x[0][1]))
            printLog("16:(parte derecha cara)"+"->"+str(x[16][0])+"/"+str(x[16][1]))
            printLog("7:(barbilla1)"+"->"+str(x[7][0])+"/"+str(x[7][1]))
            printLog("8:(barbilla2)"+"->"+str(x[8][0])+"/"+str(x[8][1]))
            printLog("9:(barbilla3)"+"->"+str(x[9][0])+"/"+str(x[9][1]))
            printLog("27:(entrecejo)"+"->"+str(x[27][0])+"/"+str(x[27][1]))
            printLog("30:(toxa punta)"+"->"+str(x[30][0])+"/"+str(x[30][1]))
            printLog("33:(toxa abajo)"+"->"+str(x[33][0])+"/"+str(x[33][1]))
            printLog("31:(izq toxa)"+"->"+str(x[31][0])+"/"+str(x[31][1]))
            printLog("35:(der toxa)"+"->"+str(x[35][0])+"/"+str(x[35][1]))
            printLog("36:(ojo izq fuera)"+"->"+str(x[36][0])+"/"+str(x[36][1]))
            printLog("39:(ojo izq dentro)"+"->"+str(x[39][0])+"/"+str(x[39][1]))
            printLog("45:(ojo der fuera)"+"->"+str(x[45][0])+"/"+str(x[45][1]))
            printLog("42:(ojo der dentro)"+"->"+str(x[42][0])+"/"+str(x[42][1]))
            printLog("48:(boca izq)"+"->"+str(x[48][0])+"/"+str(x[48][1]))
            printLog("54:(boca der)"+"->"+str(x[54][0])+"/"+str(x[54][1]))
            printLog("51:(boca arriba)"+"->"+str(x[51][0])+"/"+str(x[51][1]))
            printLog("57:(boca abajo)"+"->"+str(x[57][0])+"/"+str(x[57][1]))




            oreja_izq_X=x[0][0]
            oreja_izq_Y=x[0][1]

            oreja_der_X=x[16][0]
            oreja_der_Y=x[16][1]

            barbila_izq_X=x[7][0]
            barbila_izq_Y=x[7][1]

            barbilla_centro_X=x[8][0]
            barbilla_centro_Y=x[8][1]

            barbilla_der_X=x[9][0]
            barbilla_der_Y=x[9][1]

            entrecejo_X=x[27][0]
            entrecejo_Y=x[27][1]

            nariz_bottom_X=x[33][0]
            nariz_bottom_Y=x[33][1]

            nariz_izq_X=x[31][0]
            nariz_izq_Y=x[31][1]

            nariz_der_X=x[35][0]
            nariz_der_Y=x[35][1]

            nariz_centro_X=x[30][0]
            nariz_centro_Y=x[30][1]

            ojoext_izq_X=x[36][0]
            ojoext_izq_Y=x[36][1]


            lacrimal_izq_X=x[39][0]
            lacrimal_izq_Y=x[39][1]

            ojoext_der_X=x[45][0]
            ojoext_der_Y=x[45][1]

            lacrimal_der_X=x[42][0]
            lacrimal_der_Y=x[42][1]

            boca_izq_X=x[48][0]
            boca_izq_Y=x[48][1]

            boca_der_X=x[54][0]
            boca_der_Y=x[54][1]

            boca_top_X=x[51][0]
            boca_top_Y=x[51][1]

            boca_bot_X=x[57][0]
            boca_bot_Y=x[57][1]

            



            
            if posicion == 1: #de frente
                num_puebas=12
                sumatorio=100/num_puebas

                if alineados(1,"V",x[27][0],x[27][1],x[33][0],x[33][1],10):
                    puntuacion=puntuacion+sumatorio
                    printLog(".............SUPERO prueba 1")
                printLog("")

                if alineados(2,"V",x[57][0],x[57][1],x[8][0],x[8][1],10):
                    puntuacion=puntuacion+sumatorio
                    printLog(".............SUPERO prueba 2")
                printLog("")

                if alineados(3,"H",x[36][0],x[36][1],x[45][0],x[45][1],10):
                    puntuacion=puntuacion+sumatorio
                    printLog(".............SUPERO prueba 3")
                printLog("")

                """
                if alineados(4,"H",x[36][0],x[36][1],x[39][0],x[39][1],10):
                    puntuacion=puntuacion+sumatorio
                    printLog(".............SUPERO prueba 4")
                printLog("")
                """

                if alineados(5,"H",x[0][0],x[0][1],x[16][0],x[16][1],10):
                    puntuacion=puntuacion+sumatorio
                    printLog(".............SUPERO prueba 5")
                printLog("")

                if alineados(6,"H",x[48][0],x[48][1],x[54][0],x[54][1],10):
                    puntuacion=puntuacion+sumatorio
                    printLog(".............SUPERO prueba 6")
                printLog("")

                if enmedio(7,"H",x[27][0],x[27][1],x[36][0],x[36][1],x[45][0],x[45][1],10):
                    puntuacion=puntuacion+sumatorio
                    printLog(".............SUPERO prueba 7")
                printLog("")

                if enmedio(8,"H",x[27][0],x[27][1],x[0][0],x[0][1],x[16][0],x[16][1],10):
                    puntuacion=puntuacion+sumatorio
                    printLog(".............SUPERO prueba 8")
                printLog("")

                if enmedio(9,"H",x[33][0],x[33][1],x[0][0],x[0][1],x[16][0],x[16][1],10):
                    puntuacion=puntuacion+sumatorio
                    printLog(".............SUPERO prueba 9")
                printLog("")

                if distancias_similares(10,"H",x[0][0],x[0][1],x[36][0],x[36][1],x[45][0],x[45][1],x[16][0],x[16][1],12):
                    puntuacion=puntuacion+sumatorio
                    printLog(".............SUPERO prueba 10")
                printLog("")

                if posicionado(11,"B",x[8][0],x[8][1],x[7][0],x[7][1]): 
                    puntuacion=puntuacion+sumatorio
                    printLog(".............SUPERO prueba 11")
                printLog("")

                """
                if posicionado(12,"B",x[8][0],x[8][1],x[9][0],x[9][1]): 
                    puntuacion=puntuacion+sumatorio    
                    printLog(".............SUPERO prueba 12")
                printLog("")
                """
            
                if alineados(13,"H",x[0][0],x[0][1],x[36][0],x[36][1],10):
                    puntuacion=puntuacion+sumatorio
                    printLog(".............SUPERO prueba 13")
                printLog("")

                if alineados(14,"H",x[45][0],x[45][1],x[16][0],x[16][1],10):
                    puntuacion=puntuacion+sumatorio
                    printLog(".............SUPERO prueba 14")
                printLog("")

            elif posicion == 2: #derecha 45
                num_puebas=11
                sumatorio=100/num_puebas

                if alineados(1,"V",x[27][0],x[27][1],x[33][0],x[33][1],10):
                    puntuacion=puntuacion+sumatorio
                    printLog(".............SUPERO prueba 1")
                printLog("")

                if alineados(2,"H",x[36][0],x[36][1],x[45][0],x[45][1],10):
                    puntuacion=puntuacion+sumatorio
                    printLog(".............SUPERO prueba 2")
                printLog("")

                if posicionado(3,"L",x[30][0],x[30][1],x[16][0],x[16][1]): 
                    puntuacion=puntuacion+sumatorio
                    printLog(".............SUPERO prueba 3")
                printLog("")

                if posicionado(4,"B",x[8][0],x[8][1],x[7][0],x[7][1]): 
                    puntuacion=puntuacion+sumatorio
                    printLog(".............SUPERO prueba 4")
                printLog("")

                if posicionado(5,"B",x[8][0],x[8][1],x[9][0],x[9][1]): 
                    puntuacion=puntuacion+sumatorio    
                    printLog(".............SUPERO prueba 5")
                printLog("")

                if distacia_superior(6,"H",x[0][0],x[0][1],x[36][0],x[36][1],x[45][0],x[45][1],x[16][0],x[16][1],3):
                    puntuacion=puntuacion+sumatorio    
                    printLog(".............SUPERO prueba 6")
                printLog("")

                if distacia_superior(7,"H",x[36][0],x[36][1],x[39][0],x[39][1],x[42][0],x[42][1],x[45][0],x[45][1],1.5):
                    puntuacion=puntuacion+sumatorio    
                    printLog(".............SUPERO prueba 7")
                printLog("")

                if distacia_superior(8,"H",x[31][0],x[31][1],x[30][0],x[30][1],x[30][0],x[30][1],x[35][0],x[35][1],1.2):
                    puntuacion=puntuacion+sumatorio    
                    printLog(".............SUPERO prueba 8")
                printLog("")

                if distacia_superior(9,"H",x[48][0],x[48][1],x[51][0],x[51][1],x[51][0],x[51][1],x[54][0],x[54][1],1.2):
                    puntuacion=puntuacion+sumatorio    
                    printLog(".............SUPERO prueba 9")
                printLog("")

                if distacia_superior(10,"H",x[7][0],x[7][1],x[8][0],x[8][1],x[8][0],x[8][1],x[9][0],x[9][1],1.2):
                    puntuacion=puntuacion+sumatorio    
                    printLog(".............SUPERO prueba 10")
                printLog("")

                if distacia_superior(11,"H",x[0][0],x[0][1],x[48][0],x[48][1],x[54][0],x[54][1],x[16][0],x[16][1],2):
                    puntuacion=puntuacion+sumatorio    
                    printLog(".............SUPERO prueba 11")
                printLog("")


            
            elif posicion == 3: #derecha 90

                num_puebas=11
                sumatorio=100/num_puebas

                if posicionado(1,"R",x[30][0],x[30][1],x[16][0],x[16][1]):
                    puntuacion=puntuacion+sumatorio
                    printLog(".............SUPERO prueba 1")
                printLog("")

                if distacia_superior(2,"H",x[0][0],x[0][1],x[36][0],x[36][1],x[45][0],x[45][1],x[16][0],x[16][1],4):
                    puntuacion=puntuacion+sumatorio    
                    printLog(".............SUPERO prueba 2")
                printLog("")

                if alineados(3,"V",x[27][0],x[27][1],x[33][0],x[33][1],12):
                    puntuacion=puntuacion+sumatorio
                    printLog(".............SUPERO prueba 3")
                printLog("")

                if alineados(4,"V",x[36][0],x[36][1],x[48][0],x[48][1],15):
                    puntuacion=puntuacion+sumatorio
                    printLog(".............SUPERO prueba 4")
                printLog("")

                if posicionado(5,"B",x[8][0],x[8][1],x[7][0],x[7][1]): 
                    puntuacion=puntuacion+sumatorio
                    printLog(".............SUPERO prueba 5")
                printLog("")

                if posicionado(6,"B",x[8][0],x[8][1],x[9][0],x[9][1]): 
                    puntuacion=puntuacion+sumatorio    
                    printLog(".............SUPERO prueba 6")
                printLog("")

                if posicionado(7,"L",x[16][0],x[16][1],x[27][0],x[27][1]): 
                    puntuacion=puntuacion+sumatorio    
                    printLog(".............SUPERO prueba 7")
                printLog("")

                if posicionado(8,"L",x[54][0],x[54][1],x[51][0],x[51][1]): 
                    puntuacion=puntuacion+sumatorio    
                    printLog(".............SUPERO prueba 8")
                printLog("")

                if distacia_superior(9,"H",x[36][0],x[36][1],x[39][0],x[39][1],x[42][0],x[42][1],x[45][0],x[45][1],1.5):
                    puntuacion=puntuacion+sumatorio    
                    printLog(".............SUPERO prueba 9")
                printLog("")

                if distancia_entrepuntos(10,x[33][0],x[33][1],x[35][0],x[35][1],10):
                    puntuacion=puntuacion+sumatorio
                    printLog(".............SUPERO prueba 10")
                printLog("")

                if posicionado(11,"R",x[57][0],x[57][1],x[8][0],x[8][1]): 
                    puntuacion=puntuacion+sumatorio    
                    printLog(".............SUPERO prueba 11")
                printLog("")



            elif posicion == 4: #izquierda 45

                num_puebas=11
                sumatorio=100/num_puebas

                if alineados(1,"V",x[27][0],x[27][1],x[33][0],x[33][1],10):
                    puntuacion=puntuacion+sumatorio
                    printLog(".............SUPERO prueba 1")
                printLog("")

                if alineados(2,"H",x[36][0],x[36][1],x[45][0],x[45][1],10):
                    puntuacion=puntuacion+sumatorio
                    printLog(".............SUPERO prueba 2")
                printLog("")

                if posicionado(3,"R",x[30][0],x[30][1],x[0][0],x[0][1]): 
                    puntuacion=puntuacion+sumatorio
                    printLog(".............SUPERO prueba 3")
                printLog("")

                if posicionado(4,"B",x[8][0],x[8][1],x[7][0],x[7][1]): 
                    puntuacion=puntuacion+sumatorio
                    printLog(".............SUPERO prueba 4")
                printLog("")

                if posicionado(5,"B",x[8][0],x[8][1],x[9][0],x[9][1]): 
                    puntuacion=puntuacion+sumatorio    
                    printLog(".............SUPERO prueba 5")
                printLog("")

                if distacia_superior(6,"H",x[45][0],x[45][1],x[16][0],x[16][1],x[0][0],x[0][1],x[36][0],x[36][1],3):
                    puntuacion=puntuacion+sumatorio    
                    printLog(".............SUPERO prueba 6")
                printLog("")

                if distacia_superior(7,"H",x[42][0],x[42][1],x[45][0],x[45][1],x[36][0],x[36][1],x[39][0],x[39][1],1.5):
                    puntuacion=puntuacion+sumatorio    
                    printLog(".............SUPERO prueba 7")
                printLog("")

                if distacia_superior(8,"H",x[30][0],x[30][1],x[35][0],x[35][1],x[31][0],x[31][1],x[30][0],x[30][1],1.2):
                    puntuacion=puntuacion+sumatorio    
                    printLog(".............SUPERO prueba 8")
                printLog("")

                if distacia_superior(9,"H",x[51][0],x[51][1],x[54][0],x[54][1],x[48][0],x[48][1],x[51][0],x[51][1],1.2):
                    puntuacion=puntuacion+sumatorio    
                    printLog(".............SUPERO prueba 9")
                printLog("")

                if distacia_superior(10,"H",x[8][0],x[8][1],x[9][0],x[9][1],x[7][0],x[7][1],x[8][0],x[8][1],1.2):
                    puntuacion=puntuacion+sumatorio    
                    printLog(".............SUPERO prueba 10")
                printLog("")

                if distacia_superior(11,"H",x[54][0],x[54][1],x[16][0],x[16][1],x[0][0],x[0][1],x[48][0],x[48][1],2):
                    puntuacion=puntuacion+sumatorio    
                    printLog(".............SUPERO prueba 11")
                printLog("")


            elif posicion == 5: #izquierda 90
                num_puebas=11
                sumatorio=100/num_puebas

                if posicionado(1,"L",x[30][0],x[30][1],x[0][0],x[0][1]):
                    puntuacion=puntuacion+sumatorio
                    printLog(".............SUPERO prueba 1")
                printLog("")

                if distacia_superior(2,"H",x[45][0],x[45][1],x[16][0],x[16][1],x[0][0],x[0][1],x[36][0],x[36][1],4):
                    puntuacion=puntuacion+sumatorio    
                    printLog(".............SUPERO prueba 2")
                printLog("")

                if alineados(3,"V",x[27][0],x[27][1],x[33][0],x[33][1],12):
                    puntuacion=puntuacion+sumatorio
                    printLog(".............SUPERO prueba 3")
                printLog("")

                if alineados(4,"V",x[45][0],x[45][1],x[54][0],x[54][1],15):
                    puntuacion=puntuacion+sumatorio
                    printLog(".............SUPERO prueba 4")
                printLog("")

                if posicionado(5,"B",x[8][0],x[8][1],x[7][0],x[7][1]): 
                    puntuacion=puntuacion+sumatorio
                    printLog(".............SUPERO prueba 5")
                printLog("")

                if posicionado(6,"B",x[8][0],x[8][1],x[9][0],x[9][1]): 
                    puntuacion=puntuacion+sumatorio    
                    printLog(".............SUPERO prueba 6")
                printLog("")
 
                if posicionado(7,"R",x[0][0],x[0][1],x[27][0],x[27][1]): 
                    puntuacion=puntuacion+sumatorio    
                    printLog(".............SUPERO prueba 7")
                printLog("")

                if posicionado(8,"R",x[48][0],x[48][1],x[51][0],x[51][1]): 
                    puntuacion=puntuacion+sumatorio    
                    printLog(".............SUPERO prueba 8")
                printLog("")

                if distacia_superior(9,"H",x[42][0],x[42][1],x[45][0],x[45][1],x[36][0],x[36][1],x[39][0],x[39][1],1.5):
                    puntuacion=puntuacion+sumatorio    
                    printLog(".............SUPERO prueba 9")
                printLog("")

                if distancia_entrepuntos(10,x[33][0],x[33][1],x[35][0],x[35][1],10):
                    puntuacion=puntuacion+sumatorio
                    printLog(".............SUPERO prueba 10")
                printLog("")

                if posicionado(11,"L",x[57][0],x[57][1],x[8][0],x[8][1]): 
                    puntuacion=puntuacion+sumatorio    
                    printLog(".............SUPERO prueba 11")
                printLog("")


            elif posicion == 6: #arriba
                num_puebas=12
                sumatorio=100/num_puebas

                """
                if posicionado(1,"T",x[8][0],x[8][1],x[7][0],x[7][1]): 
                    puntuacion=puntuacion+sumatorio
                    printLog(".............SUPERO prueba 1")
                printLog("")

                if posicionado(2,"T",x[8][0],x[8][1],x[9][0],x[9][1]): 
                    puntuacion=puntuacion+sumatorio    
                    printLog(".............SUPERO prueba 2")
                printLog("")

                if posicionado(3,"T",x[57][0],x[57][1],x[48][0],x[48][1]): 
                    puntuacion=puntuacion+sumatorio
                    printLog(".............SUPERO prueba 3")
                printLog("")

                if posicionado(4,"T",x[57][0],x[57][1],x[54][0],x[54][1]): 
                    puntuacion=puntuacion+sumatorio    
                    printLog(".............SUPERO prueba 4")
                printLog("")
                """

                if alineados(5,"V",x[57][0],x[57][1],x[8][0],x[8][1],10):
                    puntuacion=puntuacion+sumatorio
                    printLog(".............SUPERO prueba 5")
                printLog("")

                if alineados(6,"H",x[36][0],x[36][1],x[45][0],x[45][1],10): 
                    puntuacion=puntuacion+sumatorio
                    printLog(".............SUPERO prueba 6")
                printLog("")

                if alineados(7,"H",x[0][0],x[0][1],x[16][0],x[16][1],10):
                    puntuacion=puntuacion+sumatorio
                    printLog(".............SUPERO prueba 7")
                printLog("")

                if posicionado(8,"T",x[27][0],x[27][1],x[39][0],x[39][1]): 
                    puntuacion=puntuacion+sumatorio
                    printLog(".............SUPERO prueba 8")
                printLog("")

                if posicionado(9,"T",x[27][0],x[27][1],x[42][0],x[42][1]): 
                    puntuacion=puntuacion+sumatorio    
                    printLog(".............SUPERO prueba 9")
                printLog("")

                """
                if posicionado(10,"T",x[30][0],x[30][1],x[39][0],x[39][1]): 
                    puntuacion=puntuacion+sumatorio
                    printLog(".............SUPERO prueba 10")
                printLog("")

                if posicionado(11,"T",x[30][0],x[30][1],x[42][0],x[42][1]): 
                    puntuacion=puntuacion+sumatorio    
                    printLog(".............SUPERO prueba 11")
                printLog("")
                
                if alineados(12,"H",x[0][0],x[0][1],x[48][0],x[48][1],10):
                    puntuacion=puntuacion+sumatorio
                    printLog(".............SUPERO prueba 12")
                printLog("")

                if alineados(13,"H",x[16][0],x[16][1],x[54][0],x[54][1],10):
                    puntuacion=puntuacion+sumatorio
                    printLog(".............SUPERO prueba 13")
                printLog("")
                """

                if enmedio(14,"H",x[57][0],x[57][1],x[0][0],x[0][1],x[16][0],x[16][1],10): 
                    puntuacion=puntuacion+sumatorio
                    printLog(".............SUPERO prueba 14")
                printLog("")

                if posicionado(15,"T",x[30][0],x[30][1],x[0][0],x[0][1],15): 
                    puntuacion=puntuacion+sumatorio
                    printLog(".............SUPERO prueba 15")
                printLog("")

                if posicionado(16,"T",x[30][0],x[30][1],x[16][0],x[16][1],15): 
                    puntuacion=puntuacion+sumatorio
                    printLog(".............SUPERO prueba 16")
                printLog("")

                if posicionado(17,"T",x[27][0],x[27][1],x[39][0],x[39][1]): 
                    puntuacion=puntuacion+sumatorio
                    printLog(".............SUPERO prueba 17")
                printLog("")

                if posicionado(18,"T",x[27][0],x[27][1],x[42][0],x[42][1]): 
                    puntuacion=puntuacion+sumatorio
                    printLog(".............SUPERO prueba 18")
                printLog("")

                if posicionado(19,"B",x[0][0],x[0][1],x[36][0],x[36][1]): 
                    puntuacion=puntuacion+sumatorio
                    printLog(".............SUPERO prueba 19")
                printLog("")

                if posicionado(20,"B",x[16][0],x[16][1],x[45][0],x[45][1]): 
                    puntuacion=puntuacion+sumatorio
                    printLog(".............SUPERO prueba 20")
                printLog("")


            elif posicion == 7: #abajo
                num_puebas=11
                sumatorio=100/num_puebas

                if posicionado(1,"B",x[8][0],x[8][1],x[7][0],x[7][1]): 
                    puntuacion=puntuacion+sumatorio
                    printLog(".............SUPERO prueba 1")
                printLog("")

                if posicionado(2,"B",x[8][0],x[8][1],x[9][0],x[9][1]): 
                    puntuacion=puntuacion+sumatorio    
                    printLog(".............SUPERO prueba 2")
                printLog("")

                if alineados(3,"H",x[36][0],x[36][1],x[45][0],x[45][1],10): 
                    puntuacion=puntuacion+sumatorio
                    printLog(".............SUPERO prueba 3")
                printLog("")

                if alineados(4,"V",x[57][0],x[57][1],x[8][0],x[8][1],10):
                    puntuacion=puntuacion+sumatorio
                    printLog(".............SUPERO prueba 4")
                printLog("")

                if posicionado(5,"T",x[0][0],x[0][1],x[36][0],x[36][1],15):
                    puntuacion=puntuacion+sumatorio
                    printLog(".............SUPERO prueba 5")
                printLog("")

                if posicionado(6,"T",x[16][0],x[16][1],x[45][0],x[45][1],15):
                    puntuacion=puntuacion+sumatorio
                    printLog(".............SUPERO prueba 6")
                printLog("")

                if alineados(7,"H",x[0][0],x[0][1],x[16][0],x[16][1],10):
                    puntuacion=puntuacion+sumatorio
                    printLog(".............SUPERO prueba 7")
                printLog("")

                if enmedio(8,"H",x[57][0],x[57][1],x[0][0],x[0][1],x[16][0],x[16][1],10):
                    puntuacion=puntuacion+sumatorio
                    printLog(".............SUPERO prueba 8")
                printLog("")

                if distancia_entrepuntos(9,x[30][0],x[30][1],x[33][0],x[33][1],10):
                    puntuacion=puntuacion+sumatorio
                    printLog(".............SUPERO prueba 9")
                printLog("")

                if posicionado(10,"B",x[27][0],x[27][1],x[39][0],x[39][1]):
                    puntuacion=puntuacion+sumatorio
                    printLog(".............SUPERO prueba 10")
                printLog("")

                if posicionado(11,"B",x[27][0],x[27][1],x[42][0],x[42][1]):
                    puntuacion=puntuacion+sumatorio
                    printLog(".............SUPERO prueba 11")
                printLog("")


            else: 
                printLog("Esto no puede pasar")
            


    return puntuacion





def alineados(numprueba,sentido,x1,y1,x2,y2,margen):
    printLog("Numero prueba:"+str(numprueba))

    if sentido=="H":
        dif=abs(y1-y2)
    else: # sentido=="V"    
        dif=abs(x1-x2)


    printLog("La diferencia es:"+str(dif))
    printLog("El margen pedido es:"+str(margen))
    respuesta=False
    if dif<=margen:
        respuesta=True

    return respuesta


def enmedio(numprueba,sentido,x,y,x1,y1,x2,y2,margen):
    printLog("Numero prueba:"+str(numprueba))

    if sentido=="V":
        centro=(abs(y1+y2))/2
        printLog("el centro vertical esta en:"+str(centro))
        dif=abs(y-centro)
    else: # sentido=="H"   
        printLog("la x1 es:"+str(x1))
        printLog("la x2 es:"+str(x2))
        centro=(abs(x1+x2))/2
        printLog("el centro horizontal esta en:"+str(centro))
        printLog("la x es:"+str(x))
        dif=abs(x-centro)

    printLog("La diferencia es:"+str(dif))
    printLog("El margen pedido es:"+str(margen))

    respuesta=False
    if dif<=margen:
        respuesta=True

    return respuesta

def distancias_similares(numprueba,sentido,x1,y1,x2,y2,x3,y3,x4,y4,margen):
    printLog("Numero prueba:"+str(numprueba))

    if sentido=="H":
        dif1=abs(y1-y2)
        dif2=abs(y3-y3)
    else: # sentido=="V"    
        dif1=abs(x1-x2)
        dif2=abs(x3-x4)

    respuesta=False
    dist=abs(dif1-dif2)

    printLog("La distancia es:"+str(dist))
    printLog("El margen pedido es:"+str(margen))

    if dist<=margen:
        respuesta=True

    return respuesta


def posicionado(numprueba,haciadonde,x1,y1,x2,y2,minimo=0): # haciadonde: L,R,T,B  p1 + haciadonde que p2
    printLog("Numero prueba:"+str(numprueba))
    printLog("prueba de posicionado")
    printLog("punto 1:"+str(x1)+"/"+str(y1))
    printLog("punto 2:"+str(x2)+"/"+str(y2))
    printLog("minimo:"+str(minimo))

    respuesta=False
    if haciadonde=="L":
        printLog("El punto 1 tiene que estar mas a la izquierda que el 2")
        if x1<x2:
            printLog("Lo esta")
            if minimo!=0:
                printLog("Como el minimo es > 0")
                dif=x2-x1
                printLog("La diferencia es:"+str(dif))
                if dif>minimo:
                    respuesta=True    
                    printLog("La diferencia es > que el minimo, superaria")
                else:
                    printLog("La diferencia es < que minimo. NO supera")
            else:    
                respuesta=True
                printLog("El minimo es 0, por lo que superaria")
        else:
            printLog("NO lo esta")
    elif haciadonde == "R":
        printLog("El punto 1 tiene que estar mas a la derecha que el 2")
        if x1>x2:
            printLog("Lo esta")
            if minimo!=0:
                printLog("Como el minimo es > 0")
                dif=x1-x2
                printLog("La diferencia es:"+str(dif))
                if dif>minimo:
                    respuesta=True
                    printLog("La diferencia es > que el minimo, superaria")
                else:
                    printLog("La diferencia es < que minimo. NO supera")
            else:    
                respuesta=True
                printLog("El minimo es 0, por lo que superaria")
        else:
            printLog("NO lo esta")
    elif haciadonde == "T":
        printLog("El punto 1 tiene que estar mas arriba que el 2")
        if y1<y2:
            printLog("Lo esta")
            if minimo!=0:
                printLog("Como el minimo es > 0")
                dif=y2-y1
                printLog("La diferencia es:"+str(dif))
                if dif>minimo:
                    respuesta=True    
                    printLog("La diferencia es > que el minimo, superaria")
                else:
                    printLog("La diferencia es < que minimo. NO supera")
            else:    
                respuesta=True
                printLog("La diferencia es > que el minimo, superaria")
        else:
            printLog("NO lo esta")
    elif haciadonde == "B":    
        printLog("El punto 1 tiene que estar mas abajo que el 2")
        if y1>y2:
            printLog("Lo esta")
            if minimo!=0:
                printLog("Como el minimo es > 0")
                dif=y1-y2
                printLog("La diferencia es:"+str(dif))
                if dif>minimo:
                    respuesta=True    
                    printLog("La diferencia es > que el minimo, superaria")
                else:
                    printLog("La diferencia es < que minimo. NO supera")
            else:    
                respuesta=True
                printLog("La diferencia es > que el minimo, superaria")
        else:
            printLog("NO lo esta")
    return respuesta


def distacia_superior(numprueba,sentido,x1,y1,x2,y2,x3,y3,x4,y4,cuantomayor): 
    printLog("Numero prueba:"+str(numprueba))

    if sentido=="H":
        dif1=abs(y1-y2)
        dif2=abs(y3-y3)
    else: # sentido=="V"    
        dif1=abs(x1-x2)
        dif2=abs(x3-x4)

    respuesta=False
    
    dif1=dif1/cuantomayor

    printLog("La diferencia es:"+str(dif1))
    printLog("El margen pedido es:"+str(cuantomayor))
    if dif1>dif2:
        respuesta=True

    return respuesta

def distancia_entrepuntos(numprueba,x1,y1,x2,y2,margen):
    printLog("Numero prueba:"+str(numprueba))

    dif=0
    dif=dif+(abs(x2-x1))
    dif=dif+(abs(y2-y1))

    respuesta=False

    printLog("La diferencia es:"+str(dif))
    printLog("El margen pedido es:"+str(margen))

    if dif<=margen:
        respuesta=True
    return respuesta


"""
i=1
while i <= 7:
    puntuacion=es_posicion_cara("prueba0"+str(i)+".jpg",i)
    printLog("Puntuacion final("+str(i)+"):"+str(puntuacion))
    printLog("-----------------")
    printLog("-----------------")
    printLog("")
    printLog("")
    i=i+1
"""



"""
path_imgs='/home/camaras/Descargas/caretos/a_frente/'
imagePaths = list(paths.list_images(path_imgs))
printLog("00000000000000000000000000000000000000000000000000000")
printLog(path_imgs)
printLog("00000000000000000000000000000000000000000000000000000")
for (i, imagePath) in enumerate(imagePaths):
    name_file = imagePath.split(os.path.sep)[-1]
    printLog('analizando:'+name_file)
    puntuacion=es_posicion_cara(path_imgs+name_file,1)
    printLog("-------------------_>Puntuacion final(1):"+str(puntuacion))
    printLog("-----------------")
    printLog("-----------------")


    printLog("######################################################")
    printLog("######################################################")
    printLog("######################################################")
    printLog("######################################################")
    printLog("")
    printLog("")
    printLog("")

path_imgs='/home/camaras/Descargas/caretos/a_45/der/'
imagePaths = list(paths.list_images(path_imgs))
printLog("00000000000000000000000000000000000000000000000000000")
printLog(path_imgs)
printLog("00000000000000000000000000000000000000000000000000000")
for (i, imagePath) in enumerate(imagePaths):
    name_file = imagePath.split(os.path.sep)[-1]
    printLog('analizando:'+name_file)
    puntuacion=es_posicion_cara(path_imgs+name_file,2)
    printLog("-------------------_>Puntuacion final(2):"+str(puntuacion))
    printLog("-----------------")
    printLog("-----------------")


    printLog("######################################################")
    printLog("######################################################")
    printLog("######################################################")
    printLog("######################################################")
    printLog("")
    printLog("")
    printLog("")

path_imgs='/home/camaras/Descargas/caretos/a_90/der/'
imagePaths = list(paths.list_images(path_imgs))
printLog("00000000000000000000000000000000000000000000000000000")
printLog(path_imgs)
printLog("00000000000000000000000000000000000000000000000000000")
for (i, imagePath) in enumerate(imagePaths):
    name_file = imagePath.split(os.path.sep)[-1]
    printLog('analizando:'+name_file)
    puntuacion=es_posicion_cara(path_imgs+name_file,3)
    printLog("-------------------_>Puntuacion final(3):"+str(puntuacion))
    printLog("-----------------")
    printLog("-----------------")


    printLog("######################################################")
    printLog("######################################################")
    printLog("######################################################")
    printLog("######################################################")
    printLog("")
    printLog("")
    printLog("")

path_imgs='/home/camaras/Descargas/caretos/a_45/izq/'
imagePaths = list(paths.list_images(path_imgs))
printLog("00000000000000000000000000000000000000000000000000000")
printLog(path_imgs)
printLog("00000000000000000000000000000000000000000000000000000")
for (i, imagePath) in enumerate(imagePaths):
    name_file = imagePath.split(os.path.sep)[-1]
    printLog('analizando:'+name_file)
    puntuacion=es_posicion_cara(path_imgs+name_file,4)
    printLog("-------------------_>Puntuacion final(4):"+str(puntuacion))
    printLog("-----------------")
    printLog("-----------------")


    printLog("######################################################")
    printLog("######################################################")
    printLog("######################################################")
    printLog("######################################################")
    printLog("")
    printLog("")
    printLog("")

path_imgs='/home/camaras/Descargas/caretos/a_90/izq/'
imagePaths = list(paths.list_images(path_imgs))
printLog("00000000000000000000000000000000000000000000000000000")
printLog(path_imgs)
printLog("00000000000000000000000000000000000000000000000000000")
for (i, imagePath) in enumerate(imagePaths):
    name_file = imagePath.split(os.path.sep)[-1]
    printLog('analizando:'+name_file)
    puntuacion=es_posicion_cara(path_imgs+name_file,5)
    printLog("-------------------_>Puntuacion final(5):"+str(puntuacion))
    printLog("-----------------")
    printLog("-----------------")


    printLog("######################################################")
    printLog("######################################################")
    printLog("######################################################")
    printLog("######################################################")
    printLog("")
    printLog("")
    printLog("")

path_imgs='/home/camaras/Descargas/caretos/a_arriba/'
imagePaths = list(paths.list_images(path_imgs))
printLog("00000000000000000000000000000000000000000000000000000")
printLog(path_imgs)
printLog("00000000000000000000000000000000000000000000000000000")
for (i, imagePath) in enumerate(imagePaths):
    name_file = imagePath.split(os.path.sep)[-1]
    printLog('analizando:'+name_file)
    puntuacion=es_posicion_cara(path_imgs+name_file,6)
    printLog("-------------------_>Puntuacion final(6):"+str(puntuacion))
    printLog("-----------------")
    printLog("-----------------")


    printLog("######################################################")
    printLog("######################################################")
    printLog("######################################################")
    printLog("######################################################")
    printLog("")
    printLog("")
    printLog("")

path_imgs='/home/camaras/Descargas/caretos/a_abajo/'
imagePaths = list(paths.list_images(path_imgs))
printLog("00000000000000000000000000000000000000000000000000000")
printLog(path_imgs)
printLog("00000000000000000000000000000000000000000000000000000")
for (i, imagePath) in enumerate(imagePaths):
    name_file = imagePath.split(os.path.sep)[-1]
    printLog('analizando:'+name_file)
    puntuacion=es_posicion_cara(path_imgs+name_file,7)
    printLog("-------------------_>Puntuacion final(7):"+str(puntuacion))
    printLog("-----------------")
    printLog("-----------------")


    printLog("######################################################")
    printLog("######################################################")
    printLog("######################################################")
    printLog("######################################################")
    printLog("")
    printLog("")
    printLog("")
"""



printLog("pinta25_mas_1")
imagePath="/var/www/html/reconocimientoFacial/proyecto_definitivo/admin/files/videos_registro_pruebas/4.jpg"
printLog("pinta25_mas_2")
frame17_ = cv2.imread(imagePath)
printLog("pinta25_mas_3")
frame17_ = pinta25_mas(imagePath,frame17_)
printLog("pinta25_mas_4")
# frame17_=modoNativo(imagePath,frame17_)
cv2.imshow('Test25_', frame17_)
printLog("pinta25_mas_5")

cv2.waitKey()
cv2.destroyAllWindows()
"""

# josue puntos en la cara

imagePath="prueba01.jpg"
frame = cv2.imread(imagePath)
frame = pinta1(imagePath,frame)
cv2.imshow('Test', frame)

imagePath="prueba02.jpg"
frame2 = cv2.imread(imagePath)
frame2 = pinta2(imagePath,frame2)
cv2.imshow('Test2', frame2)

imagePath="prueba03.jpg"
frame3 = cv2.imread(imagePath)
frame3 = pinta3(imagePath,frame3)
cv2.imshow('Test3', frame3)

imagePath="prueba04.jpg"
frame4 = cv2.imread(imagePath)
frame4 = pinta4(imagePath,frame4)
cv2.imshow('Test4', frame4)

imagePath="prueba05.jpg"
frame5 = cv2.imread(imagePath)
frame5 = pinta5(imagePath,frame5)
cv2.imshow('Test5', frame5)


imagePath="prueba06.jpg"
frame6 = cv2.imread(imagePath)
frame6 = pinta6(imagePath,frame6)
cv2.imshow('Test6', frame6)



imagePath="prueba07.jpg"
frame7 = cv2.imread(imagePath)
frame7 = pinta7(imagePath,frame7)
cv2.imshow('Test7', frame7)

# cv2.waitKey()
# cv2.destroyAllWindows()

printLog("Paso2")



# paletos puntos en la cara
imagePath="/home/camaras/Descargas/caretos/a_45/izq/istockphoto-618033536-612x612.jpg"
frame1_ = cv2.imread(imagePath)
frame1_ = pinta8(imagePath,frame1_)
# frame1=modoNativo(imagePath,frame1)
cv2.imshow('Test1_', frame1_)



imagePath="/home/camaras/Descargas/caretos/a_45/izq/istockphoto-1209165252-612x612.jpg"
frame2_ = cv2.imread(imagePath)
frame2_ = pinta9(imagePath,frame2_)
# frame2=modoNativo(imagePath,frame2)
cv2.imshow('Test2_', frame2_)


imagePath="/home/camaras/Descargas/caretos/a_90/izq/istockphoto-930148076-612x612.jpg"
frame3_ = cv2.imread(imagePath)
frame3_ = pinta10(imagePath,frame3_)
# frame3=modoNativo(imagePath,frame3)
cv2.imshow('Test3_', frame3_)



imagePath="/home/camaras/Descargas/caretos/a_90/izq/istockphoto-1142003969-612x612.jpg"
frame4_ = cv2.imread(imagePath)
frame4_ = pinta11(imagePath,frame4_)
# frame4=modoNativo(imagePath,frame4)
cv2.imshow('Test4_', frame4_)

printLog("Paso3")




imagePath="/home/camaras/Descargas/caretos/a_arriba/istockphoto-114281258-612x612.jpg"
frame5_ = cv2.imread(imagePath)
frame5_ = pinta12(imagePath,frame5_)
# frame5_=modoNativo(imagePath,frame5_)
cv2.imshow('Test5_', frame5_)

imagePath="/home/camaras/Descargas/caretos/a_arriba/istockphoto-114281258-612x612.jpg"
frame6_ = cv2.imread(imagePath)
frame6_ = pinta13(imagePath,frame6_)
# frame6_=modoNativo(imagePath,frame6_)
cv2.imshow('Test6_', frame6_)

imagePath="/home/camaras/Descargas/caretos/a_arriba/istockphoto-521072353-612x612.jpg"
frame7_ = cv2.imread(imagePath)
frame7_ = pinta14(imagePath,frame7_)
# frame7_=modoNativo(imagePath,frame7_)
cv2.imshow('Test7_', frame7_)

imagePath="/home/camaras/Descargas/caretos/a_arriba/istockphoto-600684152-612x612.jpg"
frame8_ = cv2.imread(imagePath)
frame8_ = pinta15(imagePath,frame8_)
# frame8_=modoNativo(imagePath,frame8_)
cv2.imshow('Test1_', frame8_)

imagePath="/home/camaras/Descargas/caretos/a_arriba/istockphoto-831926286-612x612.jpg"
frame9_ = cv2.imread(imagePath)
frame9_ = pinta16(imagePath,frame9_)
# frame9_=modoNativo(imagePath,frame9_)
cv2.imshow('Test9_', frame9_)

imagePath="/home/camaras/Descargas/caretos/a_arriba/istockphoto-1135785922-612x612.jpg"
frame10_ = cv2.imread(imagePath)
frame10_ = pinta17(imagePath,frame10_)
# frame10_=modoNativo(imagePath,frame10_)
cv2.imshow('Test10_', frame10_)

imagePath="/home/camaras/Descargas/caretos/a_arriba/istockphoto-1147122384-612x612.jpg"
frame11_ = cv2.imread(imagePath)
frame11_ = pinta18(imagePath,frame11_)
# frame11_=modoNativo(imagePath,frame11_)
cv2.imshow('Test11_', frame11_)

imagePath="/home/camaras/Descargas/caretos/a_arriba/istockphoto-1192304271-612x612.jpg"
frame12_ = cv2.imread(imagePath)
frame12_ = pinta19(imagePath,frame12_)
# frame12_=modoNativo(imagePath,frame12_)
cv2.imshow('Test12_', frame12_)




imagePath="/home/camaras/Descargas/caretos/a_abajo/istockphoto-119066243-612x612.jpg"
frame13_ = cv2.imread(imagePath)
frame13_ = pinta20(imagePath,frame13_)
# frame13_=modoNativo(imagePath,frame13_)
cv2.imshow('Test13_', frame13_)

imagePath="/home/camaras/Descargas/caretos/a_abajo/istockphoto-154961395-612x612.jpg"
frame14_ = cv2.imread(imagePath)
frame14_ = pinta21(imagePath,frame14_)
# frame14_=modoNativo(imagePath,frame14_)
cv2.imshow('Test14_', frame14_)

imagePath="/home/camaras/Descargas/caretos/a_abajo/istockphoto-155427889-612x612.jpg"
frame15_ = cv2.imread(imagePath)
frame15_ = pinta22(imagePath,frame15_)
# frame15_=modoNativo(imagePath,frame15_)
cv2.imshow('Test15_', frame15_)

imagePath="/home/camaras/Descargas/caretos/a_abajo/istockphoto-685675600-612x612.jpg"
frame16_ = cv2.imread(imagePath)
frame16_ = pinta23(imagePath,frame16_)
# frame16_=modoNativo(imagePath,frame16_)
cv2.imshow('Test16_', frame16_)

imagePath="/home/camaras/Descargas/caretos/a_abajo/istockphoto-911955596-612x612.jpg"
frame17_ = cv2.imread(imagePath)
frame17_ = pinta24(imagePath,frame17_)
# frame17_=modoNativo(imagePath,frame17_)
cv2.imshow('Test17_', frame17_)







cv2.waitKey()
cv2.destroyAllWindows()

"""





"""
imagePath="prueba07.jpg"
frame = cv2.imread(imagePath)

enfoque=comprueba_enfocada(imagePath)
if enfoque>0:
    printLog('Es enfocada de momento:'+imagePath)

    
    
    frame=modoNativo(imagePath,frame)
    printLog("---------------------------------------")
    #frame=modoPredictor(imagePath,frame)


cv2.imshow('Test', frame)
cv2.waitKey()
cv2.destroyAllWindows()

"""