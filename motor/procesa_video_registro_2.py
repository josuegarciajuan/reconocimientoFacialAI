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
from filelock import FileLock


import imutils
import cv2, time, pandas
from datetime import datetime, timedelta
import dlib

sys.path.append(".")
from facealigner import FaceAligner


LOCAL_ID=sys.argv[1]
HILO=sys.argv[2] #SIRVE PARA SABER DE QUE HILO VIENE ADEMAS DE QUE SEGUN CUAL CLASIFICA DEPENDIENDO DE LAS 3 ULTIMAS CIFRAS:
NOMBRE_UNICO=sys.argv[3]


CAMARA_ID="C0"
#RUTA_PROYECTO="/var/www/html/reconocimientoFacial/proyecto_definitivo/"
#RUTA_PROYECTO="/var/www/html/reconocimientofacialV2/"
RUTA_PROYECTO=sys.argv[4]


# UMBRAL_ENFOQUE_MAXIMO=120 # menos de este desenfoque , se descartan
# UMBRAL_ENFOQUE_MAXIMO_CARA=90 #menos de este enfoque se descartan ,pero solo actuando sobre la cara

# UMBRAL_ENFOQUE_MAXIMO=300 # menos de este desenfoque , se descartan
#UMBRAL_ENFOQUE_MAXIMO_CARA=120 #menos de este enfoque se descartan ,pero solo actuando sobre la cara
UMBRAL_ENFOQUE_MAXIMO_CARA=int(sys.argv[5])


"""
----------------------------------------------------------------------------------------------------------------------------------------------------------------------
Borrar las fotos no enfocadas ni centradas, y luego saca los encodings para guardarlos
----------------------------------------------------------------------------------------------------------------------------------------------------------------------
"""

IMAGENES_TOTAL=0
IMAGENES_DESENFOCADAS=0
IMAGENES_NOSEPUEDERECORTARCARA=0
IMAGENES_CONCARA=0




time_ini = time.time()


def printLog(*args, **kwargs):
    # print(*args, **kwargs)
    
    with open(RUTA_PROYECTO + 'motor/logs/procesa_videos_registro_2_' +  HILO + '.out','a') as file:
       print(*args, **kwargs, file=file)





def rect_to_bb(rect):

    x = rect.left()
    y = rect.top()
    w = rect.right() - x
    h = rect.bottom() - y

    # return a tuple of (x, y, w, h)
    return (x, y, w, h)

def variance_of_laplacian(image):
    # compute the Laplacian of the image and then return the focus
    # measure, which is simply the variance of the Laplacian
    return cv2.Laplacian(image, cv2.CV_64F).var()


detector = dlib.get_frontal_face_detector()
def comprueba_enfocada(imagePath,name_file):

    global IMAGENES_DESENFOCADAS
    global IMAGENES_NOSEPUEDERECORTARCARA

    printLog("Voy a comprobar si enfocada, y si pilla cara a la vez")

    image = cv2.imread(imagePath)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)


    recortada=False
    # rects = detector(gray, 2)
    rects = detector(gray, 1)
    for rect in rects:
        printLog("Tiene rect a analizar")
        (x, y, w, h) = rect_to_bb(rect)
        printLog("x:" + str(x))
        printLog("y:" + str(y))
        printLog("w:" + str(w))
        printLog("h:" + str(h))

        if (x + w)>100 and (y + h )>100 and x>0 and y>0:
            printLog("Se hace un recorte para analizar")
            recorte = imutils.resize(image[y:y + h, x:x + w], width=100)
            recortada=True
            cv2.imwrite(imagePath+"_tmp.jpg", recorte)


    devolver=0
    if recortada:
        printLog("SI se puede recortar la face")
        image = cv2.imread(imagePath+"_tmp.jpg")
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)        
        fm = variance_of_laplacian(gray)
        printLog("el fm de la imagen es: "+str(fm))
        # copyfile(imagePath+"_tmp.jpg" , RUTA_PROYECTO + "motor/removidas/tmp/"+name_file)
        os.remove(imagePath+"_tmp.jpg")
        if fm > UMBRAL_ENFOQUE_MAXIMO_CARA:    
            printLog("Ademas esta enfocada")
            devolver=fm
        else:
            printLog("Esta desenfocada")
            IMAGENES_DESENFOCADAS=IMAGENES_DESENFOCADAS+1
         
    else:
        fm = variance_of_laplacian(gray)
        #printLog("NO se puede recortar la face, por lo que aplico el umbral de la foto completa y su fm es:"+str(fm)+" y el umbral que considero:"+str(UMBRAL_ENFOQUE_MAXIMO))
        printLog("No se puede recortar la face")
        IMAGENES_NOSEPUEDERECORTARCARA = IMAGENES_NOSEPUEDERECORTARCARA+1
        """
        if fm > UMBRAL_ENFOQUE_MAXIMO:
           devolver=fm
        """   

    printLog("Lo que estoy devolviendo al final:"+str(devolver))
    return devolver


def escara(imagePath):

    frontal=False


    
    face1 = RUTA_PROYECTO + "motor/models/haarcascade_frontalface2.xml"
    face2 = RUTA_PROYECTO + "motor/models/haarcascade_frontalface_alt.xml"
    face3 = RUTA_PROYECTO + "motor/models/haarcascade_frontalface_alt2.xml"
    face4 = RUTA_PROYECTO + "motor/models/haarcascade_frontalface_alt_tree.xml"
    face5 = RUTA_PROYECTO + "motor/models/haarcascade_frontalface_default.xml"
    face6 = RUTA_PROYECTO + "motor/models/haarcascade_profileface.xml"
    face7 = RUTA_PROYECTO + "motor/cosas_en_la_cara/models/haarcascade_frontalface_default.xml"

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
            printLog("paso6")  
            faces6 = face_cascade6.detectMultiScale(gray, 1.01,50)
            for (x,y,w,h) in faces6:
                frontal=True
                printLog("Es frontal6")

        if not frontal:
            printLog("paso7")  
            faces7 = face_cascade7.detectMultiScale(gray, 1.01,50)
            for (x,y,w,h) in faces7:
                frontal=True
                printLog("Es frontal7")

    return frontal





def anyade_datos(knownEncodings1,knownNames1,knownPoints1,ganador_name,knownIdentificadorunico1,knownEnfoque1):

    count=0
    maximo=0
    for ff in range(0,len(knownEncodings1)):
        #printLog("nuevo encoding pasado qe se va a anyadir:"+knownEncodings1[ff])
        anyade_datos_def(maximo,count,knownEncodings1[ff],knownNames1[ff],knownPoints1[ff],ganador_name,knownIdentificadorunico1[ff],knownEnfoque1[ff])





def anyade_datos_def(maximo,count,knownEncoding,knownName,knownPoint,ganador_name,knownIdentificadorunic,knownEnfoque):

    # printLog("anyade_datos_def, count:"+str(count))

    knownEncodings_def=[]
    knownNames_def=[]
    knownPoints_def=[]
    knownIdentificadorunico_def=[]
    knownEnfoque_def=[]

    #printLog("cokmo count < MAXIMAS_REPETICIONES_GUARDADO("+str(MAXIMAS_REPETICIONES_GUARDADO)+")")
    knownEncodings_def.append(knownEncoding)
    knownNames_def.append(knownName)
    knownPoints_def.append(knownPoint)
    knownIdentificadorunico_def.append(knownIdentificadorunic)
    knownEnfoque_def.append(knownEnfoque)

    printLog("pruebas")
    for ff in range(0,len(knownNames_def)):
        printLog("este name"+knownNames_def[ff]+", y el enfoque:"+str(knownEnfoque_def[ff]))



    data = pickle.loads(open(RUTA_PROYECTO + 'motor/bbdd_reconocimiento/'+LOCAL_ID+'/face_enc', "rb").read())

    for ff in range(0,len(data["encodings"])):
        knownEncodings_def.append(data["encodings"][ff])
        knownNames_def.append(data["names"][ff])
        knownPoints_def.append(data["points"][ff])
        knownIdentificadorunico_def.append(data["identificadoresunicos"][ff])
        knownEnfoque_def.append(data["enfoque"][ff])
        printLog("anyado encoding q ya abia de este name"+data["names"][ff]+", y el enfoque:"+str(data["enfoque"][ff]))


    #printLog("anyado todo lo recabado")
    data = {"encodings": knownEncodings_def, "names": knownNames_def, "points": knownPoints_def, "identificadoresunicos": knownIdentificadorunico_def, "enfoque": knownEnfoque_def}
    with FileLock(RUTA_PROYECTO + 'motor/bbdd_reconocimiento/'+LOCAL_ID+'/face_enc'):
        f = open(RUTA_PROYECTO + 'motor/bbdd_reconocimiento/'+LOCAL_ID+'/face_enc', "wb")
        f.write(pickle.dumps(data))
        f.close()












path_imgs=RUTA_PROYECTO + 'motor/caras/sinclasificar_videos/'



imagePaths = list(paths.list_images(path_imgs))


printLog("--->" + path_imgs)


knownEncodings = []
knownNames = []
knownPoints = []
knownIdentificadorunico = []
knownEnfoque = []

"""
proc = subprocess.Popen("php " + RUTA_PROYECTO + "ws.php nombreunico", shell=True, stdout=subprocess.PIPE)
ganador_name = str(proc.stdout.read())
ganador_name = ganador_name.replace("'", "")
printLog("Como es nuevo, le voy a asignar un random: "+ganador_name)
"""

ganador_name = NOMBRE_UNICO


for (i, imagePath) in enumerate(imagePaths):
    name_file = imagePath.split(os.path.sep)[-1]

    
    printLog("-------------------")    

    printLog('analizando:'+name_file)

    lastseven=name_file[-9:]

    printLog('ultimos 7:'+lastseven)

    antesp=int(lastseven[0:1])
    primero=int(lastseven[1:2])
    segundo=int(lastseven[2:3])
    tercero=int(lastseven[3:4])
    cuarto=int(lastseven[4:5])




    continua=False
    if antesp%2 == 0 and primero%2 == 0 and segundo%2 == 0 and tercero%2 == 0 and cuarto%2 == 0 and HILO=="1":
        continua=True
        printLog("paso1!!")
    if antesp%2 == 0 and primero%2 == 0 and segundo%2 == 0 and tercero%2 == 0 and cuarto%2 == 1 and HILO=="2":
        continua=True
        printLog("paso2!!")
    if antesp%2 == 0 and primero%2 == 0 and segundo%2 == 0 and tercero%2 == 1 and cuarto%2 == 0 and HILO=="3":
        continua=True
        printLog("paso3!!")
    if antesp%2 == 0 and primero%2 == 0 and segundo%2 == 0 and tercero%2 == 1 and cuarto%2 == 1 and HILO=="4":
        continua=True
        printLog("paso4!!")
    if antesp%2 == 0 and primero%2 == 0 and segundo%2 == 1 and tercero%2 == 0 and cuarto%2 == 0 and HILO=="5":
        continua=True
        printLog("paso5!!")
    if antesp%2 == 0 and primero%2 == 0 and segundo%2 == 1 and tercero%2 == 0 and cuarto%2 == 1 and HILO=="6":
        continua=True
        printLog("paso6!!")
    if antesp%2 == 0 and primero%2 == 0 and segundo%2 == 1 and tercero%2 == 1 and cuarto%2 == 0 and HILO=="7":
        continua=True
        printLog("paso7!!")
    if antesp%2 == 0 and primero%2 == 0 and segundo%2 == 1 and tercero%2 == 1 and cuarto%2 == 1 and HILO=="8":
        continua=True
        printLog("paso8!!")
    if antesp%2 == 0 and primero%2 == 1 and segundo%2 == 0 and tercero%2 == 0 and cuarto%2 == 0 and HILO=="9":
        continua=True
        printLog("paso9!!")
    if antesp%2 == 0 and primero%2 == 1 and segundo%2 == 0 and tercero%2 == 0 and cuarto%2 == 1 and HILO=="10":
        continua=True
        printLog("paso10!!")
    if antesp%2 == 0 and primero%2 == 1 and segundo%2 == 0 and tercero%2 == 1 and cuarto%2 == 0 and HILO=="11":
        continua=True
        printLog("paso11!!")
    if antesp%2 == 0 and primero%2 == 1 and segundo%2 == 0 and tercero%2 == 1 and cuarto%2 == 1 and HILO=="12":
        continua=True
        printLog("paso12!!")
    if antesp%2 == 0 and primero%2 == 1 and segundo%2 == 1 and tercero%2 == 0 and cuarto%2 == 0 and HILO=="13":
        continua=True
        printLog("paso13!!")
    if antesp%2 == 0 and primero%2 == 1 and segundo%2 == 1 and tercero%2 == 0 and cuarto%2 == 1 and HILO=="14":
        continua=True
        printLog("paso14!!")
    if antesp%2 == 0 and primero%2 == 1 and segundo%2 == 1 and tercero%2 == 1 and cuarto%2 == 0 and HILO=="15":
        continua=True
        printLog("paso15!!")
    if antesp%2 == 0 and primero%2 == 1 and segundo%2 == 1 and tercero%2 == 1 and cuarto%2 == 1 and HILO=="16":
        continua=True
        printLog("paso16!!")
    if antesp%2 == 1 and primero%2 == 0 and segundo%2 == 0 and tercero%2 == 0 and cuarto%2 == 0 and HILO=="17":
        continua=True
        printLog("paso17!!")
    if antesp%2 == 1 and primero%2 == 0 and segundo%2 == 0 and tercero%2 == 0 and cuarto%2 == 1 and HILO=="18":
        continua=True
        printLog("paso18!!")
    if antesp%2 == 1 and primero%2 == 0 and segundo%2 == 0 and tercero%2 == 1 and cuarto%2 == 0 and HILO=="19":
        continua=True
        printLog("paso19!!")
    if antesp%2 == 1 and primero%2 == 0 and segundo%2 == 0 and tercero%2 == 1 and cuarto%2 == 1 and HILO=="20":
        continua=True
        printLog("paso20!!")
    if antesp%2 == 1 and primero%2 == 0 and segundo%2 == 1 and tercero%2 == 0 and cuarto%2 == 0 and HILO=="21":
        continua=True
        printLog("paso21!!")
    if antesp%2 == 1 and primero%2 == 0 and segundo%2 == 1 and tercero%2 == 0 and cuarto%2 == 1 and HILO=="22":
        continua=True
        printLog("paso22!!")
    if antesp%2 == 1 and primero%2 == 0 and segundo%2 == 1 and tercero%2 == 1 and cuarto%2 == 0 and HILO=="23":
        continua=True
        printLog("paso23!!")
    if antesp%2 == 1 and primero%2 == 0 and segundo%2 == 1 and tercero%2 == 1 and cuarto%2 == 1 and HILO=="24":
        continua=True
        printLog("paso24!!")
    if antesp%2 == 1 and primero%2 == 1 and segundo%2 == 0 and tercero%2 == 0 and cuarto%2 == 0 and HILO=="25":
        continua=True
        printLog("paso25!!")
    if antesp%2 == 1 and primero%2 == 1 and segundo%2 == 0 and tercero%2 == 0 and cuarto%2 == 1 and HILO=="26":
        continua=True
        printLog("paso26!!")
    if antesp%2 == 1 and primero%2 == 1 and segundo%2 == 0 and tercero%2 == 1 and cuarto%2 == 0 and HILO=="27":
        continua=True
        printLog("paso27!!")
    if antesp%2 == 1 and primero%2 == 1 and segundo%2 == 0 and tercero%2 == 1 and cuarto%2 == 1 and HILO=="28":
        continua=True
        printLog("paso28!!")
    if antesp%2 == 1 and primero%2 == 1 and segundo%2 == 1 and tercero%2 == 0 and cuarto%2 == 0 and HILO=="29":
        continua=True
        printLog("paso29!!")
    if antesp%2 == 1 and primero%2 == 1 and segundo%2 == 1 and tercero%2 == 0 and cuarto%2 == 1 and HILO=="30":
        continua=True
        printLog("paso30!!")
    if antesp%2 == 1 and primero%2 == 1 and segundo%2 == 1 and tercero%2 == 1 and cuarto%2 == 0 and HILO=="31":
        continua=True
        printLog("paso31!!")
    if antesp%2 == 1 and primero%2 == 1 and segundo%2 == 1 and tercero%2 == 1 and cuarto%2 == 1 and HILO=="32":
        continua=True
        printLog("paso32!!")



    
    if continua:
        printLog("deberia a continua")        
        IMAGENES_TOTAL=IMAGENES_TOTAL+1

        insertada=False
        enfoque=comprueba_enfocada(imagePath,name_file)
        # enfoque=100
        if enfoque>0:
            printLog('Es enfocada de momento:'+imagePath)
            #if escara(imagePath):

            printLog('es cara1 y enfocada:'+imagePath)

            image = cv2.imread(imagePath)
            rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            boxes = face_recognition.face_locations(rgb,model='cnn')
            encodings = face_recognition.face_encodings(rgb, boxes)

            if len(encodings)>0:
                printLog("Esta imagen SI tiene caras reconocibles por que tiene encodings")

                if cv2.haveImageReader (imagePath):
                    printLog("Esta imagen SI tiene caras2!!!")
                    IMAGENES_CONCARA=IMAGENES_CONCARA+1

                    if(len(encodings)>1):
                        printLog("Esto no puede pasar, hay mas de 1 cara en la imagen")
                    else:
                        printLog("Perfecto, supera todos los filtros")
                        insertada=True

                        for encoding in encodings:    
                            knownEncodings.append(encoding)  

                            
                        proc = subprocess.Popen("php " + RUTA_PROYECTO + "ws.php fotos_identificadorunico", shell=True, stdout=subprocess.PIPE)
                        fotos_identificadorunico = str(proc.stdout.read())
                        fotos_identificadorunico = fotos_identificadorunico.replace("'", "")

                        knownNames.append(ganador_name)
                        knownPoints.append(9999)
                        knownIdentificadorunico.append(fotos_identificadorunico)
                        knownEnfoque.append(enfoque)

                        


                else:
                    printLog("Esta imagen no tiene caras2 por haveImageReader")
            else:
                printLog("Esta imagen no tiene caras1 por que no tiene encodings")
            # else:
            #    printLog("Esta imagen no tiene caras3 por la funcion escara")
        else:
            printLog("NO ESTA ENFOCADA1")



        if not insertada:
            printLog('remuevo la imagen pues no supero los filtros y no se va a usar: '+imagePath)
            copyfile(imagePath , RUTA_PROYECTO + "motor/removidas/nopasafiltros/"+name_file)
        else:
            printLog('La imagen es buena, voy a ponerla en su correspondiente carpeta, para conservarla: '+imagePath)

            if not os.path.exists(RUTA_PROYECTO + 'motor/caras/'+LOCAL_ID+'/'+CAMARA_ID+'/'+ganador_name):
                printLog("No existe y la voy a crear:" + RUTA_PROYECTO + 'motor/caras/'+LOCAL_ID+'/'+CAMARA_ID+'/'+ganador_name)
                os.makedirs(RUTA_PROYECTO + 'motor/caras/'+LOCAL_ID+'/'+CAMARA_ID+'/'+ganador_name)
            else:
                printLog("Ya existia la ruta:" + RUTA_PROYECTO + 'motor/caras/'+LOCAL_ID+'/'+CAMARA_ID+'/'+ganador_name)

            copyfile(imagePath, RUTA_PROYECTO + 'motor/caras/'+LOCAL_ID+'/'+CAMARA_ID+'/'+ganador_name+'/'+name_file+'_'+fotos_identificadorunico+".jpg") 
            printLog("He copiado de aki: "+imagePath+ " a aki: "+ganador_name+'/'+name_file+'_'+fotos_identificadorunico+".jpg")
        os.remove(imagePath)





anyade_datos(knownEncodings,knownNames,knownPoints,ganador_name,knownIdentificadorunico,knownEnfoque)


cadena=str(IMAGENES_TOTAL)+";;"+str(IMAGENES_DESENFOCADAS)+";;"+str(IMAGENES_NOSEPUEDERECORTARCARA)+";;"+str(IMAGENES_CONCARA)+";;"+ganador_name+";;"+fotos_identificadorunico
with open(RUTA_PROYECTO + 'aux/procesa_video_registro_resultado_' +  LOCAL_ID + '_' +  HILO + '.txt','a') as file:
   print(cadena, file=file)


time_elapsed = time.time() - time_ini
printLog("Tiempo de analizar el video:" + str(time_elapsed))


