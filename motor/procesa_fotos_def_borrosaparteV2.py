# -ok-recorro las fotos sin clasificar del local_id, camara_id
# -ok-las qe estan juntas en el tiempo, osea qe entre una y la siguiente haya menos de 5segundos, las trata como una bateria a procesar juntas
# -ok-saca el encoder de cada foto de toda la bateria
# -ok-(cuidado pueden haber caras mezcladas en la misma bateria) las proximas entre si, las considera como la misma cara 
# --las qe se consideran la misma cara ya las comprao con el diccionario, a la qe mas se parezcan pos esa es ya la meto en su carpeta con su nombre random correpondiente si es nueva o existe..

# python3.7 motor/procesa_fotos_def_pruebas.py 3 1


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


sys.path.append(".")
from facealigner import FaceAligner




#umbral_parecidosentresi=0.29        # cuando va a clasificar las fotos y los que son parecidos entre si para decir qe esla misma persona
umbral_parecidosentresi=float(sys.argv[3])        # cuando va a clasificar las fotos y los que son parecidos entre si para decir qe esla misma persona

umbral=float(sys.argv[4])                   # umbral para comprara foto a foto y ver con cual supera y el qe se usa para recompara cuando ya se tiene la media
umbral_solounaodos=float(sys.argv[5])            # para comparar con las medias pero solo hay 1 o 2 fotos
umbral_delasmedias=float(sys.argv[6])             # umbral cuando se a exo las medias
umbral_segurisimo=float(sys.argv[7])              # si 1 foto supera esto es ese
veces_umbral_medias_augmenta=float(sys.argv[8])     # si se hay mas de X vces influya en los 2 umbrales de abajo
umbral_junto=float(sys.argv[9])                 # la media de los qe superan y los qe no para esa persona qe se comparó
umbral_junto2=float(sys.argv[10])                # la media de los qe superan y los qe no para esa persona qe se comparó
porcentaje_veces_supera=float(sys.argv[11])          # si de todas las veces no supera este porcentaje de veces supera 

umbral_enfocado=float(sys.argv[12])  # umbral para comprara foto a foto y ver con cual supera y el qe se usa para recompara cuando ya se tiene la media
umbral_solounaodos_enfocado=float(sys.argv[13]) # para comparar con las medias pero solo hay 1 o 2 fotos
umbral_delasmedias_enfocado=float(sys.argv[14])  # umbral cuando se a exo las medias
umbral_segurisimo_enfocado=float(sys.argv[15])  # si 1 foto supera esto es ese
veces_umbral_medias_augmenta_enfocado=float(sys.argv[16])  # si se hay mas de X vces influya en los 2 umbrales de abajo
umbral_junto_enfocado=float(sys.argv[17])   # la media de los qe superan y los qe no para esa persona qe se comparó
umbral_junto2_enfocado=float(sys.argv[18])  # la media de los qe superan y los qe no para esa persona qe se comparó
porcentaje_veces_supera_enfocado=float(sys.argv[19])

umbral_desenfocado=float(sys.argv[20])
umbral_solounaodos_desenfocado=float(sys.argv[21])
umbral_delasmedias_desenfocado=float(sys.argv[22])
umbral_segurisimo_desenfocado=float(sys.argv[23])
veces_umbral_medias_augmenta_desenfocado=float(sys.argv[24])
umbral_junto_desenfocado=float(sys.argv[25])
umbral_junto2_desenfocado=float(sys.argv[26])
porcentaje_veces_supera_desenfocado=float(sys.argv[27])

umbral_desenfocado_globales=float(sys.argv[28])
umbral_solounaodos_desenfocado_globales=float(sys.argv[29])
umbral_delasmedias_desenfocado_globales=float(sys.argv[30])
umbral_segurisimo_desenfocado_globales=float(sys.argv[31])
veces_umbral_medias_augmenta_desenfocado_globales=float(sys.argv[32])
umbral_junto_desenfocado_globales=float(sys.argv[33])
umbral_junto2_desenfocado_globales=float(sys.argv[34])
porcentaje_veces_supera_desenfocado_globales=float(sys.argv[35])


DIFERENCIA_PROMERO_Y_SEGUNDO=float(sys.argv[36])   # en los ganadores la diferencia qe tienen qe tener para qe alomejor sea el 2º
MAXIMAS_REPETICIONES_GUARDADO=float(sys.argv[37])   # 
#DIFERENCIA_ANCHO_OJOS=8
DIFERENCIA_ANCHO_OJOS=float(sys.argv[38])
DIFERENCIA_ALTURAS=float(sys.argv[39])


UMBRAL_ENFOQUE=float(sys.argv[40]) #para considerar una foto desenfocada ya y al comparar 1 a 1 con todo el diccionario, ya pasaria a ver si las 2 tienen muxa diferencia de enfoque
UMBRAL_ENFOQUE_MAXIMO=float(sys.argv[41]) # menos de este desenfoque , se descartan
UMBRAL_ENFOQUE_MAXIMO_CARA=float(sys.argv[42]) #menos de este enfoque se descartan ,pero solo actuando sobre la cara

UMBRAL_DIFERENCIA_ENFOQUE=float(sys.argv[43])  #al comparar una a una si alguna de las 2 esta desenfocada, la de muestra y la del diccionario, comprar si hay muxa diferencia, para aplicar los umbrales restrictivos    (solo afecta a umbral y umbral segurisimo)
UMBRAL_ENFOQUE_GLOBALES=float(sys.argv[44]) #para considrar una foto desenfocada despues de haber comparado con todas, ya pra el calculo de las medias




cinco_segundos = timedelta(0, 10)

LOCAL_ID=sys.argv[1]
CAMARA_ID=sys.argv[2]


def printLog(*args, **kwargs):
    print(*args, **kwargs)
    
    with open('motor/procesa_fotos_def_borrosaparte'+CAMARA_ID+'.out','a') as file:
    # with open('motor/procesa_fotos_def_XX.out','a') as file:
      print(*args, **kwargs, file=file)
        

printLog("paso0")


def anyade_datos_def(maximo,count,knownEncoding,knownName,knownPoint,ganador_name,knownIdentificadorunic,knownEnfoque):

    printLog("anyade_datos_def, count:"+str(count))

    knownEncodings_def=[]
    knownNames_def=[]
    knownPoints_def=[]
    knownIdentificadorunico_def=[]
    knownEnfoque_def=[]

    data = pickle.loads(open('motor/bbdd_reconocimiento/'+LOCAL_ID+'/face_enc', "rb").read())


    if count<MAXIMAS_REPETICIONES_GUARDADO:
        printLog("cokmo count < MAXIMAS_REPETICIONES_GUARDADO("+str(MAXIMAS_REPETICIONES_GUARDADO)+")")
        knownEncodings_def.append(knownEncoding)
        knownNames_def.append(knownName)
        knownPoints_def.append(knownPoint)
        knownIdentificadorunico_def.append(knownIdentificadorunic)
        knownEnfoque_def.append(knownEnfoque)

        printLog("anyado el encoding pasado, y el enfoque pasado:"+str(knownEnfoque))

        for ff in range(0,len(data["encodings"])):
            knownEncodings_def.append(data["encodings"][ff])
            knownNames_def.append(data["names"][ff])
            knownPoints_def.append(data["points"][ff])
            knownIdentificadorunico_def.append(data["identificadoresunicos"][ff])
            knownEnfoque_def.append(data["enfoque"][ff])
            printLog("anyado encoding q ya abia de este name"+data["names"][ff]+", y el enfoque:"+data["enfoque"][ff])

    else:
        if knownPoint >= maximo:      
            for ff in range(0,len(data["encodings"])):
                knownEncodings_def.append(data["encodings"][ff])
                knownNames_def.append(data["names"][ff])
                knownPoints_def.append(data["points"][ff])
                knownIdentificadorunico_def.append(data["identificadoresunicos"][ff])
                knownEnfoque_def.append(data["enfoque"][ff])
        else:
            knownEncodings_def.append(knownEncoding)
            knownNames_def.append(knownName)
            knownPoints_def.append(knownPoint)
            knownIdentificadorunico_def.append(knownIdentificadorunic)

            for ff in range(0,len(data["encodings"])):
                if data["names"][ff]==ganador_name:
                    if data["points"][ff]<maximo:
                        knownEncodings_def.append(data["encodings"][ff])
                        knownNames_def.append(data["names"][ff])
                        knownPoints_def.append(data["points"][ff])
                        knownIdentificadorunico_def.append(data["identificadoresunicos"][ff])
                        knownEnfoque_def.append(data["enfoque"][ff])
                else:
                    knownEncodings_def.append(data["encodings"][ff])
                    knownNames_def.append(data["names"][ff])
                    knownPoints_def.append(data["points"][ff])
                    knownIdentificadorunico_def.append(data["identificadoresunicos"][ff])
                    knownEnfoque_def.append(data["enfoque"][ff])


    printLog("anyado todo lo recabado")
    data = {"encodings": knownEncodings_def, "names": knownNames_def, "points": knownPoints_def, "identificadoresunicos": knownIdentificadorunico_def, "enfoque": knownEnfoque_def}
    with FileLock('motor/bbdd_reconocimiento/'+LOCAL_ID+'/face_enc'):
        f = open('motor/bbdd_reconocimiento/'+LOCAL_ID+'/face_enc', "wb")
        f.write(pickle.dumps(data))
        f.close()

def anyade_datos(knownEncodings1,knownNames1,knownPoints1,ganador_name,knownIdentificadorunico1,knownEnfoque1):

    printLog("blokeado fichero y anyade_datos de "+ganador_name)

    count=0
    maximo=0

    data = pickle.loads(open('motor/bbdd_reconocimiento/'+LOCAL_ID+'/face_enc', "rb").read())
    for ff in range(0,len(data["encodings"])):
        if data["names"][ff]==ganador_name:
            printLog("ya tenia encoding")
            count=count+1
            if data["points"][ff]>maximo:
                maximo=data["points"][ff]
                printLog("este es el maximo de momento:"+str(maximo))
        
    printLog("maximo definitivo:"+str(maximo))

    for ff in range(0,len(knownEncodings1)):
        printLog("nuevo encoding pasado qe se va a anyadir:"+knownEncodings1[ff])
        anyade_datos_def(maximo,count,knownEncodings1[ff],knownNames1[ff],knownPoints1[ff],ganador_name,knownIdentificadorunico1[ff],knownEnfoque1[ff])
    printLog("Finalmente fichero desbloekado")

def rect_to_bb(rect):

    x = rect.left()
    y = rect.top()
    w = rect.right() - x
    h = rect.bottom() - y

    # return a tuple of (x, y, w, h)
    return (x, y, w, h)

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


detector = dlib.get_frontal_face_detector()
def comprueba_enfocada(imagePath,name_file):

    image = cv2.imread(imagePath)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)


    recortada=False
    rects = detector(gray, 2)
    for rect in rects:
        (x, y, w, h) = rect_to_bb(rect)
        printLog("x:" + str(x))
        printLog("y:" + str(y))
        printLog("w:" + str(w))
        printLog("h:" + str(h))

        if (x + w)>100 and (y + h )>100 and x>0 and y>0:
            recorte = imutils.resize(image[y:y + h, x:x + w], width=100)
            recortada=True
            cv2.imwrite(imagePath+"_tmp.jpg", recorte)

    devolver=0

    if recortada:
        printLog("se puede recortar la face")
        image = cv2.imread(imagePath+"_tmp.jpg")
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)        
        fm = variance_of_laplacian(gray)
        printLog("el fm de la imagen es: "+str(fm))
        copyfile(imagePath+"_tmp.jpg" , "./motor/removidas/tmp/"+name_file)
        os.remove(imagePath+"_tmp.jpg")
        if fm > UMBRAL_ENFOQUE_MAXIMO_CARA:    
            devolver=fm
    else:
        fm = variance_of_laplacian(gray)
        printLog("NO se puede recortar la face, por lo que aplico el umbral de la foto completa y su fm es:"+str(fm)+" y el umbral que considero:"+str(UMBRAL_ENFOQUE_MAXIMO))
        if fm > UMBRAL_ENFOQUE_MAXIMO:
           devolver=fm

    printLog("Lo que estoy devolviendo al final:"+str(devolver))
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
            printLog("mar_der:"+str(mar_der))
            printLog("toxa_x:"+str(toxa_x))
            printLog("toxa_y:"+str(toxa_y))
            printLog("barbilla_x:"+str(barbilla_x))
            printLog("barbilla_y:"+str(barbilla_y))



            if mar_izq<toxa and toxa<mar_der:
                es_frontal=True
                printLog("Es frontal por 1")

            else:
                if izq<toxa and toxa<der and (abs(toxa_y-barbilla_y)>5 and abs(toxa_x-barbilla_x)<17):
                    # es_frontal=True
                    printLog("Es frontal por 2, pero igual descarto")


    return es_frontal

printLog("paso1")


path_imgs='motor/caras/sinclasificar/'+LOCAL_ID+"/"+CAMARA_ID+"/"
#path_imgs="/home/testuser/motor/pruebas/"


printLog("paso2")
count_global=0
sigue=True
while sigue:
    printLog("INI procesando......")


    #vale esto es para 

    printLog("recojo ficheros disponibles..")

    imagePaths = list(paths.list_images(path_imgs))

    ficheros = []
    ficheros_path = []
    ficheros_enfoque = []
    for (i, imagePath) in enumerate(imagePaths):
        name_file = imagePath.split(os.path.sep)[-1]
        printLog('analizando:'+name_file)

        # image = cv2.imread(imagePath)
        # sharpened_image = enfocar_imagen(image)
        # cv2.imwrite(imagePath, sharpened_image)

        pasaprimerosfiltros=False
        enfoque=comprueba_enfocada(imagePath,name_file)
        if enfoque>0:
            printLog('Es enfocada de momento:'+imagePath)
            #if esfrontal(imagePath):
            # if es_frontal_new(imagePath):
            if True:
                ficheros.append(name_file)
                ficheros_path.append(imagePath)
                ficheros_enfoque.append(enfoque)
                printLog('en ficheros anyado:'+name_file)
                printLog('es frontal y enfocada:'+imagePath)
                pasaprimerosfiltros=True
                printLog("test")
            



        if not pasaprimerosfiltros:
            copyfile(imagePath , "./motor/removidas/nopasafiltros/"+name_file)
            os.remove(imagePath)
            printLog('remuevo:'+imagePath)




        
        printLog("buclend")
        printLog()
        """
        ficheros.append(name_file)
        ficheros_path.append(imagePath)
        """
        # printLog('en ficheros anyado:'+name_file)
        # printLog('en ficheros_path anyado:'+imagePath)
        
    printLog("Llego")    
    # exit()


    """
    printLog()
    printLog()
    printLog()
    printLog()
    printLog("-----------------")
    printLog()
    printLog()
    printLog()
    printLog()
    """

    #ficheros=sorted(ficheros)
    #ficheros, ficheros_enfoque = (list(t) for t in zip(*sorted(zip(ficheros, ficheros_enfoque))))
    #ficheros_path=sorted(ficheros_path)


    index = list(range(len(ficheros)))
    index.sort(key = ficheros.__getitem__)
    ficheros[:] = [ficheros[i] for i in index]
    ficheros_enfoque[:] = [ficheros_enfoque[i] for i in index]
    ficheros_path[:] = [ficheros_path[i] for i in index]



    baterias = []
    baterias_ficheros = []
    encoders = []
    baterias_enfoques = []
    count = 0

    iniciado=False


    printLog("ordenando ficheros por proximidad")
    for (i, fichero) in enumerate(ficheros):
        """
        printLog("->i:"+str(i))
        printLog('ordenando ficheros por proximidad,   Nombre fichero:'+fichero) 
        printLog('Pero este Path?:'+ficheros_path[i]) 
        """
        printLog('ordenando ficheros por proximidad,   Nombre fichero:'+fichero) 


        aux=fichero.split('_')
        camara_id=aux[0]
        fecha=aux[1]
        hora=aux[2]
        segundos=aux[3]

        hora=hora.replace('.avi','')
        aux=hora.split('.')
        hora=aux[0]

        segundos=segundos.replace('.jpg','')
        aux=segundos.split('.')
        segundos=aux[0]

       
        """
        printLog("camara_id:"+camara_id)
        printLog("fecha:"+fecha)
        printLog("hora:"+hora)
        printLog("segundos:"+segundos)
        """

        fecha_completa=fecha+' '+hora

        printLog("fecha_completa:"+str(fecha_completa))
        

        fecha_datetime = datetime.strptime(fecha_completa, '%Y-%m-%d %H:%M:%S')
        segundos_datetime = timedelta(0, int(segundos))

        printLog("segundos:"+segundos)
        printLog("segundos_datetime:"+str(segundos_datetime))

        fecha_datetime_definitiva = fecha_datetime+segundos_datetime

        printLog("fecha_datetime_definitiva:"+str(fecha_datetime_definitiva))
        


        image = cv2.imread(ficheros_path[i])
        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        boxes = face_recognition.face_locations(rgb,model='cnn')
        encodings = face_recognition.face_encodings(rgb, boxes)


        if len(encodings)>0:
            printLog("tiene encodings")
            if iniciado:

                diferencia=fecha_datetime_definitiva-anterior

                printLog("Ya no es el 1º en analizar, y la diferencia con el anterior es "+str(diferencia)+" - pues el anterior es:"+str(anterior)+" - y la actual es:"+str(fecha_datetime_definitiva))

                if diferencia<=cinco_segundos:
                    printLog("pertenece al mismo grupo pues la diferencia es < 5 segs con el anterior")
                    printLog("lo anyado a:"+str(count-1))

                    baterias[count-1].append(fecha_datetime_definitiva)
                    baterias_ficheros[count-1].append(fichero)
                    encoders[count-1].append(encodings[0])
                    baterias_enfoques[count-1].append(ficheros_enfoque[i])
                else:
                    printLog("El grupo es nuevo por que la diferencia es >5segs con el anterior")

                    new_bateria=[fecha_datetime_definitiva]
                    baterias.append(new_bateria)

                    new_bateria_ficheros=[fichero]
                    baterias_ficheros.append(new_bateria_ficheros)

                    new_bateria_encoders=[encodings[0]]
                    encoders.append(new_bateria_encoders)

                    new_bateria_enfoques=[ficheros_enfoque[i]]
                    baterias_enfoques.append(new_bateria_enfoques)

                    printLog("lo anyado a:"+str(count))

                    count=count+1

            else:
                printLog("Es el 1º en analizar")
                iniciado=True

                new_bateria=[fecha_datetime_definitiva]
                baterias.append(new_bateria)

                new_bateria_ficheros=[fichero]
                baterias_ficheros.append(new_bateria_ficheros)

                new_bateria_encoders=[encodings[0]]
                encoders.append(new_bateria_encoders)


                new_bateria_enfoques=[ficheros_enfoque[i]]
                baterias_enfoques.append(new_bateria_enfoques)

                count=count+1


            anterior=fecha_datetime_definitiva
        else:
            printLog("Esta imagen no tiene caras1")
            copyfile(ficheros_path[i] , "./motor/removidas/notienecaras/"+fichero)
            os.remove(ficheros_path[i])
            printLog("imagen removida:"+ficheros_path[i])

        printLog()    
        printLog()    


    
    printLog("Ficheros ordenados por proximidad:")
    printLog(baterias_ficheros)
    printLog()
    printLog()
    
    printLog()
    printLog('----')
    printLog("creo array de comparacion ")
    

    comparaciones = []

    i=0
    for b in baterias:
        comparaciones.append([[0 for x in range(len(baterias[i]))] for y in range(len(baterias[i]))] ) 
        j=0
        for b2 in baterias[i]: 
            k=0
            for b3 in baterias[i]: 
                comparaciones[i][j][k]=face_recognition.face_distance([encoders[i][j]],encoders[i][k])[0]
                k=k+1
            j=j+1    
        i=i+1                       

    
    
    printLog("Array bateria fechas")
    printLog(baterias)

    printLog()
    printLog()
    printLog()
    
    printLog("Array comparaciones")
    printLog(comparaciones)

    printLog()
    printLog()
    printLog()
    

    printLog("veo cuales superan")    
    superan = []
    i=0
    for b in comparaciones:
        superan.append([[] for x in range(len(comparaciones[i]))] ) 
        j=0
        for b2 in comparaciones[i]: 
            k=0
            for b3 in comparaciones[i][j]: 
                if comparaciones[i][j][k]<=umbral_parecidosentresi:
                    superan[i][j].append(k)
                k=k+1
            j=j+1    
        i=i+1                       
        
    
    printLog("Array superan")
    printLog(superan)
    printLog()
    printLog()
    printLog()
    
    printLog("Ara ya creo grupos de la misma hora y de mismas personas")



    grupos = []
    veces = []
    i=0
    for b in superan:
        grupos.append([[] for x in range(len(superan[i]))] ) 
        veces.append([[] for x in range(len(superan[i]))] ) 
        j=0
        for b2 in superan[i]: 
            k=0

            if j==0:
                printLog("estoy en el j=0,preparo qe tenemos 1 grupo")
                num_grupos=1
            else:    
                printLog("estamos en j="+str(j)+", por lo qe preparo a ver si este o alguno de sus compañeros los meto donde")
                esta_alguno=False
                encual=0


            for b3 in superan[i][j]: 
                if j==0:
                    printLog("para superan de i,j:"+str(i)+","+str(j)+"anyado elemento a grupo inicial")
                    grupos[i][num_grupos-1].append(superan[i][j][k])
                    veces[i][num_grupos-1].append(1)
                else:
                    printLog("Ya no estoy en el j inicial de este grupo de imgs:"+str(i)+", por lo qe voy a ver donde los meto, tenemos:"+str(superan[i][j][k]))

                    
                    h=0
                    for b4 in grupos[i]: 
                        w=0
                        for b5 in grupos[i][h]: 
                            printLog("recorriendo los grupos, tenemos ("+str(i)+","+str(h)+","+str(w)+") :"+str(grupos[i][h][w]))

                            if superan[i][j][k]==grupos[i][h][w]:
                                printLog("como ya estaba metido, marco como qe esta y ara metere a todos sus compañeros meto todos sus compañeros:")
                                esta_alguno=True
                                encual=h
                                veces[i][h][w]=veces[i][h][w]+1

                            w=w+1
                        h=h+1
                k=k+1    

            if j>0:
                if not esta_alguno:
                    #creo nuevo grupo
                    printLog("no habia ninguno metido, por lo qe creo nuevo grupo con estos")

                    l=0
                    num_grupos=num_grupos+1
                    for b3 in superan[i][j]: 
                        printLog("Voy a anyadir:"+str(superan[i][j][l]))
                        grupos[i][num_grupos-1].append(superan[i][j][l])
                        veces[i][num_grupos-1].append(1)
                        l=l+1
                    
                else:
                    printLog("ya habia alguno metido por lo qe los demas los meto en el grupo en el cual habia alguno")

                    l=0
                    for b6 in superan[i][j]: 
                        printLog("trato de meter "+str(superan[i][j][l]))
                        if not superan[i][j][l] in grupos[i][encual]:
                            grupos[i][encual].append(superan[i][j][l])
                            veces[i][encual].append(1)
                            printLog("como no estaba, lo meto")
                        else:
                            printLog("ya estaba")    
                            josue=True # sentencia auxiliar para no dejar el else vacio qe sino peta
                        l=l+1
                
            j=j+1 
            printLog("traceando2:")
            printLog(grupos)   
        i=i+1  
    
    
    printLog("grupos") 
    printLog(grupos) 
    printLog("veces") 
    printLog(veces) 
    printLog('-----------------------------------------------------------------------')    
    # exit()


    """
    i=0
    for b in grupos:
        j=0
        for b2 in grupos[i]: 
            if len(grupos[i][j])>0:
                k=0
                printLog()
                printLog()
                printLog()
                printLog("tenemos grupo de imagenes qe son supuestamente la misma persona")

                for b3 in grupos[i][j]: 
                    printLog("--------------------->"+baterias_ficheros[i][grupos[i][j][k]])
                    k=k+1
            j=j+1
        i=i+1            

    exit()
    """




    i=0
    for b in grupos:
        j=0
        for b2 in grupos[i]: 
            if len(grupos[i][j])>0:
                k=0
                printLog()
                printLog()
                printLog()
                printLog("tenemos grupo de imagenes qe son supuestamente la misma persona")


                kien_veces={}
                kien_puntuaciones={}
                kien_k={}
                kien_encodings={}
                losencodings=[]
                kien_lista_puntuaciones={}


                ganador_idx=0
                ganador_vec=0

                hay_cara=False



                veces2={}
                veces_supera={}
                puntuaciones={}
                puntuaciones_supera={}
                listado_puntuaciones={}

                ganadores=[]
                ganadores_enfoques=[]
                ganador = ""
                puntuacion = 999
                segundo = ""
                puntuacion_segundo = 999
                veces_ganador=0
                veces_segundo=0
                veces_supera_ganador=0
                veces_supera_segundo=0

                veces_segurisimo=0

                segundo_def=""
                tercero_def=""
                segundo_k=0
                tercero_k=0
                primero_k=0

                primero_punt=0
                segundo_punt=0
                tercero_punt=0

                primero_lapuntuacionnuevaquemeinvento=999
                segundo_lapuntuacionnuevaquemeinvento=999
                tercero_lapuntuacionnuevaquemeinvento=999
                lapuntuacionnuevaquemeinvento=999
                lapuntuaciondefinitiva=999


                enfoque_total=0
                numero_enfoques=0

                nombre_fichero_final=""
                nombre_inicializado=False
                nombre_puesto=False
                for b3 in grupos[i][j]: 
                    printLog("----------------------->"+baterias_ficheros[i][grupos[i][j][k]])
                    printLog("enfoque del fichero-->"+str(baterias_enfoques[i][grupos[i][j][k]]))


                    if k==(len(grupos[i][j])-1):
                        if k==0:
                            nombre_fichero_final=baterias_ficheros[i][grupos[i][j][k]]
                        else:
                            nombre_fichero_final=nombre_fichero_final+"----"+baterias_ficheros[i][grupos[i][j][k]]
                        nombre_puesto=True



                    name_file=baterias_ficheros[i][grupos[i][j][k]]
                    enfoque=baterias_enfoques[i][grupos[i][j][k]]


                    """                    
                    if enfoque<=UMBRAL_ENFOQUE:
                        #cojo el enfocado
                        umbral=umbral_enfocado
                        umbral_solounaodos=umbral_solounaodos_enfocado
                        umbral_delasmedias=umbral_delasmedias_enfocado
                        umbral_segurisimo=umbral_segurisimo_enfocado
                        veces_umbral_medias_augmenta=veces_umbral_medias_augmenta_enfocado
                        umbral_junto=umbral_junto_enfocado
                        umbral_junto2=umbral_junto2_enfocado
                        porcentaje_veces_supera=porcentaje_veces_supera_enfocado
                    else:
                        #cojo el desenfocado
                        umbral=umbral_desenfocado
                        umbral_solounaodos=umbral_solounaodos_desenfocado
                        umbral_delasmedias=umbral_delasmedias_desenfocado
                        umbral_segurisimo=umbral_segurisimo_desenfocado
                        veces_umbral_medias_augmenta=veces_umbral_medias_augmenta_desenfocado
                        umbral_junto=umbral_junto_desenfocado
                        umbral_junto2=umbral_junto2_desenfocado
                        porcentaje_veces_supera=porcentaje_veces_supera_desenfocado
                    """

                    
                    if cv2.haveImageReader (path_imgs+name_file):


                        enfoque_total=enfoque_total+enfoque
                        numero_enfoques=numero_enfoques+1

                        image = cv2.imread(path_imgs+name_file)
                        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
                        #boxes = face_recognition.face_locations(rgb,model='hog')
                        boxes = face_recognition.face_locations(rgb,model='cnn')
                        encodings = face_recognition.face_encodings(rgb, boxes)

                        printLog("analizando esta imagen:"+path_imgs+name_file)

                        if(len(encodings)>1):
                            printLog("Esto no puede pasar")

                        if(len(encodings)>0):

                            if not nombre_inicializado and not nombre_puesto:
                                nombre_fichero_final=baterias_ficheros[i][grupos[i][j][k]]
                                nombre_inicializado=True

                            if veces[i][j][k]>ganador_vec:
                                ganador_idx=k
                                ganador_vec=veces[i][j][k]
                                printLog("ganador_idx:"+str(ganador_idx))

                            hay_cara=True 



                            umbral_aux=umbral_enfocado
                            umbral_solounaodos_aux=umbral_solounaodos_enfocado
                            umbral_delasmedias_aux=umbral_delasmedias_enfocado
                            umbral_segurisimo_aux=umbral_segurisimo_enfocado
                            veces_umbral_medias_augmenta_aux=veces_umbral_medias_augmenta_enfocado
                            umbral_junto_aux=umbral_junto_enfocado
                            umbral_junto2_aux=umbral_junto2_enfocado
                            porcentaje_veces_supera_aux=porcentaje_veces_supera_enfocado


                            for encoding in encodings:
                                data = pickle.loads(open('motor/bbdd_reconocimiento/'+LOCAL_ID+'/face_enc', "rb").read())

                                printLog("numero encodings")
                                printLog(len(encodings))
                                printLog()
                                printLog()
                                printLog("encodings guardados")
                                printLog(data["encodings"])
                                printLog()
                                printLog()
                                printLog("encoding actual")
                                printLog(encoding)
                                printLog()
                                printLog()

                                face_distances = face_recognition.face_distance(data["encodings"],encoding)

                                losencodings.append(encoding)

                                printLog("Voy a analizar las facedistances con todos los qe hay ya")


                                for fa, face_distance in enumerate(face_distances):

                                    printLog()
                                    printLog("para este name:"+data["names"][fa]+", es "+str(face_distance))
                                    printLog("el enfoque es:"+str(data["enfoque"][fa]))
                                    printLog("Y el actual es:"+enfoque)
                                    printLog("para este name:"+data["names"][fa]+", su enfoque era: "+str(data["enfoque"][fa])+", y la img que estoy analizando:"+str(enfoque))


                                    if data["names"][fa] in puntuaciones:
                                        printLog("paso1")
                                        veces2[data["names"][fa]]=veces2[data["names"][fa]]+1
                                        puntuaciones[data["names"][fa]]=puntuaciones[data["names"][fa]]+face_distance

                                    else:
                                        printLog("paso2:"+str(face_distance))
                                        puntuaciones[data["names"][fa]] = face_distance
                                        veces2[data["names"][fa]] = 1


                                    if not data["names"][fa] in listado_puntuaciones:
                                        listado_puntuaciones[data["names"][fa]] = []
                                    listado_puntuaciones[data["names"][fa]].append(face_distance)
                                    

                                    #si las 2 comparadas son enfocadas
                                    #if enfoque<=UMBRAL_ENFOQUE and data["enfoque"][fa]<=UMBRAL_ENFOQUE:
                                    if enfoque>UMBRAL_ENFOQUE and data["enfoque"][fa]>UMBRAL_ENFOQUE:
                                        #cojo el enfocado
                                        printLog("Las 2 son enfocadas")
                                        umbral=umbral_enfocado
                                        umbral_solounaodos=umbral_solounaodos_enfocado
                                        umbral_delasmedias=umbral_delasmedias_enfocado
                                        umbral_segurisimo=umbral_segurisimo_enfocado
                                        veces_umbral_medias_augmenta=veces_umbral_medias_augmenta_enfocado
                                        umbral_junto=umbral_junto_enfocado
                                        umbral_junto2=umbral_junto2_enfocado
                                        porcentaje_veces_supera=porcentaje_veces_supera_enfocado
                                    else:
                                        printLog("alguna de las 2 esta desenfocada")
                                        #si la diferencia de las 2 del enfoque es < UMBRAL_DIFERENCIA_ENFOQUE
                                        diferencia_enfoque=abs(enfoque - data["enfoque"][fa])
                                        if diferencia_enfoque<=UMBRAL_DIFERENCIA_ENFOQUE:
                                            printLog("hay muy poca diferencia entre el enfoque de de las 2, la diferencia es:"+str(diferencia_enfoque))
                                            umbral=umbral_enfocado
                                            umbral_solounaodos=umbral_solounaodos_enfocado
                                            umbral_delasmedias=umbral_delasmedias_enfocado
                                            umbral_segurisimo=umbral_segurisimo_enfocado
                                            veces_umbral_medias_augmenta=veces_umbral_medias_augmenta_enfocado
                                            umbral_junto=umbral_junto_enfocado
                                            umbral_junto2=umbral_junto2_enfocado
                                            porcentaje_veces_supera=porcentaje_veces_supera_enfocado
                                        else:
                                            printLog("la diferencia de enfoque entre las 2 es muy grande, la diferencia es:"+str(diferencia_enfoque))
                                            #cojo el desenfocado
                                            umbral=umbral_desenfocado
                                            umbral_solounaodos=umbral_solounaodos_desenfocado
                                            umbral_delasmedias=umbral_delasmedias_desenfocado
                                            umbral_segurisimo=umbral_segurisimo_desenfocado
                                            veces_umbral_medias_augmenta=veces_umbral_medias_augmenta_desenfocado
                                            umbral_junto=umbral_junto_desenfocado
                                            umbral_junto2=umbral_junto2_desenfocado
                                            porcentaje_veces_supera=porcentaje_veces_supera_desenfocado




                                    if face_distance<umbral_segurisimo or face_distance<umbral:

                                        if face_distance<umbral_segurisimo:                                    
                                            veces_segurisimo=veces_segurisimo+1
                                            elnombresegurisimo=data["names"][fa]
                                            puntuacion_segurisimo=face_distance
                                            printLog("supera el umbral de segurisimo que es:"+str(umbral_segurisimo))
                                        else:
                                            printLog("supera el umbral normal qe es que es:"+str(umbral))
                                    

                                        if data["names"][fa] in puntuaciones_supera:
                                            printLog("paso1")
                                            veces_supera[data["names"][fa]]=veces_supera[data["names"][fa]]+1
                                            puntuaciones_supera[data["names"][fa]]=puntuaciones_supera[data["names"][fa]]+face_distance

                                        else:
                                            printLog("paso2:"+str(face_distance))
                                            puntuaciones_supera[data["names"][fa]] = face_distance
                                            veces_supera[data["names"][fa]] = 1



                                        if not data["names"][fa] in ganadores:
                                            printLog("Como no estaba en ganadores, lo anyado")    
                                            ganadores.append(data["names"][fa])


                                        printLog("!!!!!!!supera el umbral con este nombre:"+data["names"][fa])
                                        printLog("puntuacion:"+str(face_distance))
                                    #else:
                                        printLog("No supera los umbrales de que es la misma")    
                                    printLog("veces superado:"+str(veces_supera[data["names"][fa]]))

                                    printLog()

                        else:   
                            printLog("No tiene caras esta imagen joder!")  
                            losencodings.append('') 

                    else:
                        printLog("No tiene caras esta imagen joder2!")  

                    k=k+1    


                    


                printLog()
                printLog()
                printLog("Voy a analizar de los ganadores a ver ahora si superan los umbrales:")
                

                enfoque=enfoque_total/numero_enfoques



                #if enfoque<=UMBRAL_ENFOQUE_GLOBALES:
                if enfoque>UMBRAL_ENFOQUE_GLOBALES:
                    #cojo el enfocado
                    umbral=umbral_enfocado
                    umbral_solounaodos=umbral_solounaodos_enfocado
                    umbral_delasmedias=umbral_delasmedias_enfocado
                    umbral_segurisimo=umbral_segurisimo_enfocado
                    veces_umbral_medias_augmenta=veces_umbral_medias_augmenta_enfocado
                    umbral_junto=umbral_junto_enfocado
                    umbral_junto2=umbral_junto2_enfocado
                    porcentaje_veces_supera=porcentaje_veces_supera_enfocado
                    printLog("Cojo umbrales1")
                else:
                    #cojo el desenfocado_globales
                    umbral=umbral_desenfocado_globales
                    umbral_solounaodos=umbral_solounaodos_desenfocado_globales
                    umbral_delasmedias=umbral_delasmedias_desenfocado_globales
                    umbral_segurisimo=umbral_segurisimo_desenfocado_globales
                    veces_umbral_medias_augmenta=veces_umbral_medias_augmenta_desenfocado_globales
                    umbral_junto=umbral_junto_desenfocado_globales
                    umbral_junto2=umbral_junto2_desenfocado_globales
                    porcentaje_veces_supera=porcentaje_veces_supera_desenfocado_globales
                    printLog("Cojo umbrales2")


                for g in ganadores: 

                    # si no supera un % de veces incremental ni se calcula
                    printLog("el nombre:"+g+", si no supera un % (de veces incremental ni se calcula. Tenemos estas veces:"+str(veces2[g])+", y estas veces_supera:"+str(veces_supera[g]))
                    sigue_analizando=False
                    if veces2[g]<=2:
                        sigue_analizando=True
                        printLog("Como es < qe 2 veces lo qe aparece este posible ganador")
                    else:
                        porcentaje_relativo=(veces_supera[g]*100)/veces2[g]
                        if porcentaje_relativo>porcentaje_veces_supera:
                            sigue_analizando=True
                            printLog("Supero el porcentaje qe es:"+str(porcentaje_relativo))
                        else:
                            printLog("NO supero el porcentaje qe es:"+str(porcentaje_relativo)+", ni sigo analizando")


                    if sigue_analizando:

                        media=puntuaciones[g]/veces2[g]
                        media_supera=puntuaciones_supera[g]/veces_supera[g]
                        # definitivo=media/veces2[g]
                        printLog("el nombre:"+g+", tienes esta media:"+str(media)+" y aparece estas veces:"+str(veces2[g]))
                        printLog("el nombre:"+g+", tienes esta media_supera:"+str(media_supera)+" y supera estas veces:"+str(veces_supera[g]))
                        printLog("ademas la puntuacion definitiva es (media/veces):"+str(definitivo))

                        printLog("Pero Voy a recalcular las medias con el metodo de eliminar el ruido:")

                        m1=0 #supera
                        m2=0
                        max1=0
                        min1=9999
                        max2=0
                        min2=9999
                        count_supera=0
                        for r1 in range(0,len(listado_puntuaciones[g])):

                            printLog("efectivamente es lista:"+str(listado_puntuaciones[g][r1]))

                            m1=m1+listado_puntuaciones[g][r1]
                            if listado_puntuaciones[g][r1]>max1:
                                max1=listado_puntuaciones[g][r1]
                            if listado_puntuaciones[g][r1]<min1:
                                min1=listado_puntuaciones[g][r1]
                            if listado_puntuaciones[g][r1]<umbral:
                                m2=m2+listado_puntuaciones[g][r1]        
                                count_supera=count_supera+1
                                if listado_puntuaciones[g][r1]>max2:
                                    max2=listado_puntuaciones[g][r1]
                                if listado_puntuaciones[g][r1]<min2:
                                    min2=listado_puntuaciones[g][r1]    

                        mediana=(max1+min1)/2
                        media1=m1/len(listado_puntuaciones[g])
                        mediana_supera=(max2+min2)/2
                        if count_supera==0:
                            media_supera1=0    
                        else:
                            media_supera1=m2/count_supera

                        rango_min=media1-(mediana/2)
                        rango_max=media1+(mediana/2)
                        rango_min_supera=media_supera1-(mediana_supera/2)
                        rango_max_supera=media_supera1+(mediana_supera/2)


                        """
                        printLog("A mitad de recalculado:")
                        printLog("El min de todas las puntuaciones:"+str(min1))
                        printLog("El max de todas las puntuaciones:"+str(max1))
                        printLog("El min de las puntuaciones q supera:"+str(min2))
                        printLog("El max de las puntuaciones q supera:"+str(max2))
                        printLog("La mediana de todas:"+str(mediana))
                        printLog("La mediana de las qe supera:"+str(mediana_supera))
                        printLog("La media de todas(debe coincidir con la de arriba):"+str(media1))
                        printLog("La media de las qe supera(debe coincidir con la de arriba):"+str(media_supera1))
                        printLog("rango min de todas:"+str(rango_min))
                        printLog("rango max de todas:"+str(rango_max))
                        printLog("rango min de las qe supera:"+str(rango_min_supera))
                        printLog("rango max de las qe supera:"+str(rango_max_supera))
                        """


                        umbral_def=umbral_solounaodos
                        if len(listado_puntuaciones[g])>2:
                            umbral_def=umbral

                        media=0
                        media_supera=0
                        v_media=0
                        v_media_supera=0
                        for r1 in range(0,len(listado_puntuaciones[g])):
                            if listado_puntuaciones[g][r1]>rango_min and listado_puntuaciones[g][r1]<rango_max:
                                media=media+listado_puntuaciones[g][r1]
                                v_media=v_media+1
                            if listado_puntuaciones[g][r1]<umbral_def:
                                if listado_puntuaciones[g][r1]>rango_min_supera and listado_puntuaciones[g][r1]<rango_max_supera: 
                                    media_supera=media_supera+listado_puntuaciones[g][r1]
                                    v_media_supera=v_media_supera+1


                        if v_media_supera>-1:

                            if v_media>0:
                                media=media/v_media
                            else:
                                media=0

                            if v_media_supera>0:
                                media_supera=media_supera/v_media_supera
                            else:
                                media_supera=0

                            printLog("")
                            printLog("La media definitiva limpia:"+str(media))
                            printLog("La media supera definitiva limpia:"+str(media_supera))



                            
                            printLog("aki calculare los numeros definitivos que se basa en estas medias y ademas en las veces que supera.. es un peqño retoke..");
                            printLog("Tenemos num_veces: "+str(veces2[g])+", veces_supera:"+str(veces_supera[g])+" , media:"+str(media)+" , media_supera:"+str(media_supera))
                            porcetaje_superacion_veces=veces_supera[g]*100/veces2[g]
                            porcetaje_superacion_puntuaciones=media_supera*100/media
                            printLog("tenemos: porcetaje_superacion_veces:"+str(porcetaje_superacion_veces)+" y porcetaje_superacion_puntuaciones:"+str(porcetaje_superacion_puntuaciones))
                            lapuntuaciondefinitiva=porcetaje_superacion_puntuaciones/porcetaje_superacion_veces
                            printLog("por lo que la lapuntuaciondefinitiva que buscamos es:"+str(lapuntuaciondefinitiva))




                            if veces_segurisimo>0:
                                printLog("estoy segurisimo de que el ganador fue:"+str(elnombresegurisimo)+", con esta puntuacion:"+str(puntuacion_segurisimo)+", y estas veces:"+str(veces_segurisimo))

                                ganador=elnombresegurisimo
                                puntuacion=puntuacion_segurisimo
                                veces_ganador=veces_segurisimo
                                veces_supera_ganador=veces_segurisimo

                                lapuntuacionnuevaquemeinvento=0

                            else: 
                                activate=False

                                if veces2[g]>veces_umbral_medias_augmenta:
                                    printLog("se activa veces_umbral_medias_augmenta")
                                    if media_supera<umbral_def and media<umbral_junto2:
                                        activate=True
                                        printLog("supera umbral_junto2:media:"+str(media)+",umbral_junto2:"+str(umbral_junto2)+",media_supera:"+str(media_supera)+",umbral:"+str(umbral_def))
                                else:
                                    if media_supera<umbral_def and media<umbral_junto:
                                        activate=True
                                        printLog("supera umbral_junto:media:"+str(media)+",umbral_junto:"+str(umbral_junto)+",media_supera:"+str(media_supera)+",umbral:"+str(umbral_def))


                                if activate:
                                    printLog("la media supera el umbral con esta media:"+str(media)+", y esta puntuacion qe supera:"+str(puntuacion))
                                    #if media<puntuacion:
                                    if lapuntuaciondefinitiva<puntuacion:
                                        printLog("voy a actualizar el segundo con estos datos:"+ganador+" - "+str(puntuacion)+" - "+str(veces_ganador)+" - "+str(veces_supera_ganador))


                                        tercero_def=segundo
                                        tercero_k=segundo_k
                                        tercero_punt=segundo_punt
                                        tercero_lapuntuacionnuevaquemeinvento=segundo_lapuntuacionnuevaquemeinvento

                                        segundo=ganador
                                        puntuacion_segundo=puntuacion
                                        veces_segundo=veces_ganador
                                        veces_supera_segundo=veces_supera_ganador
                                        segundo_k=primero_k
                                        segundo_punt=primero_punt
                                        segundo_lapuntuacionnuevaquemeinvento=primero_lapuntuacionnuevaquemeinvento

                                        segundo_def=segundo



                                        printLog("Es menor qe la puntuacion actual y lo guardo como ganador")
                                        printLog()
                                        printLog()
                                        ganador = g
                                        puntuacion = media
                                        veces_ganador=veces2[g]
                                        veces_supera_ganador=veces_supera[g]
                                        primero_k=k
                                        primero_punt=media
                                        primero_lapuntuacionnuevaquemeinvento=lapuntuaciondefinitiva
                                        lapuntuacionnuevaquemeinvento=lapuntuaciondefinitiva
                                else:
                                    printLog("la media NO1 supera el umbral")

                        else:
                            printLog("no supera ni una vez el umbral!")



                printLog("ya analizadas las medias, voy a qedarme con el gnaador")

                # if puntuacion==999:
                if lapuntuacionnuevaquemeinvento==999:
                    # name=str(random.randint(1000,9999))
                    name="NUEVO"
                    printLog("No hay ganador es cara nueva, le asigno este nombre:"+name)
                else:

                    # en base al numero de veces qe se ha encontrado, la media, la diferencia con el segundo


                    printLog("ganador:"+ganador+" - puntuacion:"+str(puntuacion)+", veces:"+str(veces_ganador)+", veces_supera:"+str(veces_supera_ganador)+"y la puntuacion nueva que me he inventado es:"+str(lapuntuacionnuevaquemeinvento))    
                    printLog("segundo:"+segundo+" - puntuacion:"+str(puntuacion_segundo)+", veces:"+str(veces_segundo)+", veces_supera:"+str(veces_supera_segundo)+"y la puntuacion nueva que me he inventado es:"+str(segundo_lapuntuacionnuevaquemeinvento))        
                    name=ganador
                    #if abs(puntuacion-puntuacion_segundo)<DIFERENCIA_PROMERO_Y_SEGUNDO:
                    if abs(lapuntuacionnuevaquemeinvento-segundo_lapuntuacionnuevaquemeinvento)<DIFERENCIA_PROMERO_Y_SEGUNDO and veces_segurisimo==0:

                        printLog("se diferencian de muy poco")


                        if veces_supera_ganador *2 < veces_supera_segundo:
                            printLog("el segundo aparece el doble de veces qe el primero de superado")    
                            name=segundo
                            lapuntuacionnuevaquemeinvento=segundo_lapuntuacionnuevaquemeinvento
                        else:
                            aux_ganador=veces_supera_ganador*100/veces_ganador
                            aux_segundo=veces_supera_segundo*100/veces_segundo
                            printLog("tasa de supero ganador"+str(aux_ganador))
                            printLog("tasa de supero segundo"+str(aux_segundo))

                            if aux_segundo>aux_ganador and veces_supera_segundo>3:
                                printLog("como el segundo la tasa de superacion es mas veces")
                                name=segundo
                                lapuntuacionnuevaquemeinvento=segundo_lapuntuacionnuevaquemeinvento
                    printLog("ganador definitivo:"+name)




                
                if not name in kien_puntuaciones:
                    kien_veces[name]=1
                    kien_puntuaciones[name]=lapuntuacionnuevaquemeinvento
                    kien_k[name]=k

                    kien_lista_puntuaciones[name]=[]
                    kien_lista_puntuaciones[name].append(lapuntuacionnuevaquemeinvento)


                    kien_encodings[name]=[]
                    kien_encodings[name].append(encoding)

                    printLog("Todavia no tenemos este name: "+name+" asi qe lo guardo con esta puntuacion:"+str(lapuntuacionnuevaquemeinvento))
                else:
                    kien_veces[name]=kien_veces[name]+1
                    kien_puntuaciones[name]=kien_puntuaciones[name]+lapuntuacionnuevaquemeinvento
                    printLog("Este name: "+name+" ya se tenia asi qe incremento su puntuacion y sus veces. Puntuacion:"+kien_puntuaciones[name]+", veces: "+kien_veces[name])
                    
                        


                printLog("img analizada!!!!!!!!!!!!!!!!!!!!!!!!!")
                printLog()

                #k=k+1



                printLog("la imagen representativa de estas sera:"+baterias_ficheros[i][grupos[i][j][ganador_idx]])
                fichero_a_mover=baterias_ficheros[i][grupos[i][j][ganador_idx]]


                if hay_cara:
                    """
                    printLog("Una vez analizadas todas las imagenes del grupo, voy a tomar decisiones: de a kien de los nombres almacenados pertenece la cara")


                    for name in kien_puntuaciones:
                        media=kien_puntuaciones[name]/kien_veces[name]
                        printLog("para este nombre:"+name+" tenemos esta puntuacion:"+str(kien_puntuaciones[name])+", y estas veces:"+str(kien_veces[name])+", la media al final es:"+str(media))
                        kien_puntuaciones[name]=media


                    printLog("Voy a ver el ganador")


                    """
                    printLog("Voy a sacar los 3 mejores encodings para guaraar para este usuario")

                    ganador_name=name
                    ganador_pts=9999
                    hay_ganador=False
                    
                    
                    encoding1=""
                    encoding2=""
                    encoding3=""

                    puntuacion1=9999
                    puntuacion2=9999
                    puntuacion3=9999
                    




                    for name in kien_puntuaciones:
                        printLog("para este nombre:"+name+", la puntuacion es:"+str(kien_puntuaciones[name]))
                        # if kien_puntuaciones[name]<ganador_pts:
                            
                        """
                        ganador_pts=kien_puntuaciones[name]
                        ganador_name=name
                        hay_ganador=True
                        printLog("De momento el ganador es:"+ganador_name+", con estos puntos"+str(ganador_pts))
                        """

                        #aki cogeria los encodings con mejor puntuacio 1º,2º,3º de este name
                        encoding1=""
                        encoding2=""
                        encoding3=""

                        puntuacion1=9999
                        puntuacion2=9999
                        puntuacion3=9999


                        t1=0
                        while t1<len(kien_lista_puntuaciones[name]):
                            if kien_lista_puntuaciones[name][t1]<puntuacion1:
                                puntuacion1=kien_lista_puntuaciones[name][t1]
                                encoding1=kien_encodings[name][t1]
                            t1=t1+1

                        t1=0
                        while t1<len(kien_lista_puntuaciones[name]):
                            if kien_lista_puntuaciones[name][t1]<puntuacion2 and kien_lista_puntuaciones[name][t1]!=puntuacion1:
                                puntuacion2=kien_lista_puntuaciones[name][t1]
                                encoding2=kien_encodings[name][t1]
                            t1=t1+1

                        t1=0
                        while t1<len(kien_lista_puntuaciones[name]):
                            if kien_lista_puntuaciones[name][t1]<puntuacion3 and kien_lista_puntuaciones[name][t1]!=puntuacion1  and kien_lista_puntuaciones[name][t1]!=puntuacion2:
                                puntuacion3=kien_lista_puntuaciones[name][t1]
                                encoding3=kien_encodings[name][t1]
                            t1=t1+1

                    printLog("Las 3 mejores puntuaciones a guardar son: #"+str(puntuacion1)+"# - #"+str(puntuacion2)+"# - #"+str(puntuacion3)+"#")
                    


                    if hay_ganador:
                        printLog("Hay ganador con estos puntos: "+ganador_pts+" y el umbral de las medias es: "+umbral_delasmedias)
                        #if ganador_pts>umbral_delasmedias:
                        printLog("Hay ganador con estos puntos: "+str(lapuntuaciondefinitiva)+" y el umbral de las medias es: "+str(umbral_delasmedias))
                        if puntuacion>umbral_delasmedias:
                            printLog("No se cumple el umbral de las medias, por lo qe lo considero nuevo,"+str(ganador_pts)+"--"+str(umbral_delasmedias))
                            ganador_name="NUEVO"
                        else:
                            printLog("Tambien se cumple el umbral de las medias!")
                    
    
                    if ganador_name=="NUEVO":
                        # ganador_name=str(random.randint(10000,99999))

                        proc = subprocess.Popen("php ws.php nombreunico", shell=True, stdout=subprocess.PIPE)
                        ganador_name = str(proc.stdout.read())
                        ganador_name = ganador_name.replace("'", "")
                        printLog("Como es nuevo, le voy a asignar un random: "+ganador_name)



                    printLog("el nombre definitivo asignado es:"+str(ganador_name))


                    # encoding=losencodings[ganador_idx]
                    
                    
                    printLog("el encoding qe voy a guardar al final para esta imagen es:")
                    printLog(encoding1)
                    printLog("qe sale de es este ganador_idx:"+str(ganador_idx))
                    printLog()


                    proc = subprocess.Popen("php ws.php fotos_identificadorunico", shell=True, stdout=subprocess.PIPE)
                    fotos_identificadorunico = str(proc.stdout.read())
                    fotos_identificadorunico = fotos_identificadorunico.replace("'", "")
                    #fotos_identificadorunico= str(random.randint(10000,99999))                  


                    knownEncodings = []
                    knownNames = []
                    knownPoints = []
                    knownIdentificadorunico = []
                    knownEnfoque = []


                    printLog("para este nombre:"+ganador_name+", almacenamos esta puntuacion:"+str(puntuacion1)+", y este enfoque:"+str(enfoque))
                    knownEncodings.append(encoding1)
                    knownNames.append(ganador_name)
                    knownPoints.append(puntuacion1)
                    knownIdentificadorunico.append(fotos_identificadorunico)
                    knownEnfoque.append(enfoque)


                    if puntuacion2!=9999:
                        printLog("para este nombre2:"+ganador_name+", almacenamos esta puntuacion:"+str(puntuacion2))
                        # encoding2=losencodings[segundo_k]
                        knownEncodings.append(encoding2)
                        knownNames.append(ganador_name)
                        knownPoints.append(puntuacion2)
                        knownIdentificadorunico.append(fotos_identificadorunico)
                        knownEnfoque.append(enfoque)

                    if puntuacion3!=9999:
                        printLog("para este nombre3:"+ganador_name+", almacenamos esta puntuacion:"+str(puntuacion3))
                        # encoding3=losencodings[tercero_k]
                        knownEncodings.append(encoding3)
                        knownNames.append(ganador_name)
                        knownPoints.append(puntuacion3)
                        knownIdentificadorunico.append(fotos_identificadorunico)
                        knownEnfoque.append(enfoque)

                    anyade_datos(knownEncodings,knownNames,knownPoints,ganador_name,knownIdentificadorunico,knownEnfoque)
                    if not os.path.exists('motor/caras/'+LOCAL_ID+'/'+CAMARA_ID+'/'+ganador_name):
                        os.makedirs('motor/caras/'+LOCAL_ID+'/'+CAMARA_ID+'/'+ganador_name)



                    # copyfile(path_imgs+fichero_a_mover, './motor/caras/'+LOCAL_ID+'/'+CAMARA_ID+'/'+ganador_name+'/'+nombre_fichero_final+"_____"+str(count_global)+".jpg") 
                    copyfile(path_imgs+fichero_a_mover, './motor/caras/'+LOCAL_ID+'/'+CAMARA_ID+'/'+ganador_name+'/'+nombre_fichero_final+'_'+fotos_identificadorunico+".jpg") 
                    count_global=count_global+1
                    printLog("He copiado de aki: "+path_imgs+fichero_a_mover+ " a aki: "+'motor/caras/'+LOCAL_ID+'/'+CAMARA_ID+'/'+ganador_name+'/'+nombre_fichero_final+'_'+fotos_identificadorunico+".jpg")

                else:
                    printLog("Del grupo analizado no habia ni una puta cara")


                jj=0
                printLog("Voy a eliminar los ficheros procesados ya ")
                for b3 in grupos[i][j]: 
                    printLog("Borro:"+baterias_ficheros[i][grupos[i][j][jj]])
                    if os.path.isfile(path_imgs+baterias_ficheros[i][grupos[i][j][jj]]):
                        os.remove(path_imgs+baterias_ficheros[i][grupos[i][j][jj]])
                    jj=jj+1


                printLog("####################################################################")    
                printLog()    
                printLog()    
                printLog()    
                printLog()    
                printLog()    
                printLog()    
            j=j+1    
        i=i+1   

    # print()
    # print("//////////////////////////")
    # print()

    
    # sigue=False
    



printLog('-----------------------------------------------------------------------')

printLog("baterias")
printLog(baterias)
printLog()
printLog()
printLog()
printLog("baterias_ficheros")
printLog(baterias_ficheros)
printLog()
printLog()
printLog()
printLog("encoders")
printLog(encoders)
printLog()
printLog()
printLog()
printLog("comparaciones")
printLog(comparaciones)
printLog()
printLog()
printLog()

printLog("superan")
printLog(superan)
printLog()
printLog()
printLog()

printLog("grupos")
printLog(grupos)
printLog()
printLog()
printLog()

printLog("veces")
printLog(veces)
printLog()
printLog()
printLog()


# 1_2021-07-14_10:35:58.370305.avi_1.121212.jpg

