from imutils import paths
import face_recognition
import pickle
import cv2
import os
from shutil import copyfile
import random
import sys
# from datetime import datetime, timedelta
import time as t
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

RUTA_PROYECTO=sys.argv[1]
DEBUG=sys.argv[2]


# https://towardsdatascience.com/face-landmark-detection-using-python-1964cb620837

detector = dlib.get_frontal_face_detector()

def printLog(*args, **kwargs):
    if DEBUG=="1":
        print(*args, **kwargs)
    
        with open('devuelve_posicion_cara.out','a') as file:
            print(*args, **kwargs, file=file)


printLog("paso0")



def es_posicion_cara(imagePath,posicion):
    


    definitivo=0

    test = plt.imread(imagePath)
    test = imutils.resize(test, width=500)
    gray = cv2.cvtColor(test, cv2.COLOR_BGR2GRAY)
    rects = detector(test, 1)
    detecto_cara=False

    for (i, rect) in enumerate(rects):

        printLog("hay alguna cara")

        printLog("-------------Analizando en posicon_cara-------------")

        input = io.imread(imagePath)
        preds = fa.get_landmarks(input)

        
        if preds is not None:

            printLog("Tiene caras1")

            for (x) in preds:


                puntuacion=0
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
                
        printLog("Voy a reajustar la puntuacion:" + str(puntuacion))    
        printLog("Definitivo esta enb:" + str(definitivo))    
        if puntuacion>definitivo:
            definitivo=puntuacion
            printLog("Es > que definitivo, por lo que reajusto no se por que pero definitivo que es lo que devuelvo se queda en:" + str(definitivo))

    printLog("Finalmente devuelvo:" + str(definitivo))
    return definitivo




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

    if dif<margen:
        respuesta=True
    return respuesta





# path="/var/www/html/reconocimientoFacial/proyecto_definitivo/admin/files/videos_registro"
path=RUTA_PROYECTO + "admin/files/videos_registro"
path_imgs=path+"/"

printLog("path:" + path)
printLog("path_imgs:" + path_imgs)

while True:
    
    printLog("true")

    imagePaths = list(paths.list_images(path_imgs))
    for (i, imagePath) in enumerate(imagePaths):
        puntuacion=0

        printLog("Ruta_imagen:"+imagePath)

        basename = os.path.basename(imagePath)
        printLog("basename:"+basename)
        local_id = basename.split(".")[0]
        printLog("local_id:"+local_id)

        fileposicion=path+"_posiciones/"+local_id+".txt"

       
        with open(fileposicion) as f:
            posicion = f.readline()

        printLog("posicion:"+posicion)

        puntuacion=es_posicion_cara(imagePath,int(posicion))
        printLog("")        
        printLog("PUNTUACION:"+str(puntuacion))

        os.remove(imagePath)
        os.remove(fileposicion)

        fileresultado=path+"_resultados/"+local_id+".txt"

        f= open(fileresultado,"w+")
        f.write(str(puntuacion))
        f.close()


    t.sleep(1)