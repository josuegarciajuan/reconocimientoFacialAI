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

SENSIBILIDAD_ES_CARA=0.68

LOCAL_ID=sys.argv[1]
FICHERO=sys.argv[2]
CAMARA_ID="0"



time_ini = time.time()


def printLog(*args, **kwargs):
    print(*args, **kwargs)
    
    with open('/var/www/html/reconocimientoFacial/proyecto_definitivo/motor/procesa_videos_registro.out','a') as file:
       print(*args, **kwargs, file=file)







"""
----------------------------------------------------------------------------------------------------------------------------------------------------------------------
sacar imagenes con posibles caras de un video
----------------------------------------------------------------------------------------------------------------------------------------------------------------------
"""




modelFile = "/var/www/html/reconocimientoFacial/proyecto_definitivo/motor/models/res10_300x300_ssd_iter_140000.caffemodel"
configFile = "/var/www/html/reconocimientoFacial/proyecto_definitivo/motor/models/deploy.prototxt.txt"
net = cv2.dnn.readNetFromCaffe(configFile, modelFile)


name_file=os.path.join('/var/www/html/reconocimientoFacial/proyecto_definitivo/admin/files/videos_registro/', FICHERO)


printLog("tenemos este video:"+name_file)
cap = cv2.VideoCapture(name_file)

prev=0
segundos_ini=time.time()
num_frame=0




while(cap.isOpened()):
    # printLog('voy leyendo el video..')
    ret, img = cap.read()
    if ret == True:
        #printLog('tenemos frame k lo guardo ..')
        num_frame=num_frame+1


        #img = cv2.resize(img, None, fx=0.25, fy=0.25)
        height, width = img.shape[:2]
        height1, width1 = img.shape[:2]
        time_elapsed = time.time() - prev
        prev = time.time()

        img_original=img
        img_test=img



        blob = cv2.dnn.blobFromImage(cv2.resize(img_original, (300, 300)),1.0, (353, 353), (104.0, 117.0, 123.0))
        net.setInput(blob)
        faces3 = net.forward()
        
        for i in range(faces3.shape[2]):
            confidence = faces3[0, 0, i, 2]
            if confidence > SENSIBILIDAD_ES_CARA:

                printLog('cara encontrada en: '+name_file)

                box = faces3[0, 0, i, 3:7] * np.array([width1, height1, width1, height1])
                (x, y, x1, y1) = box.astype("int")
                #cv2.rectangle(img2, (x, y), (x1, y1), (0, 0, 255), 2)


                ydef=y-100
                if ydef<0:
                    ydef=0
                y1def=y1+100
                if y1def>height1:
                    y1def=height1-1

                xdef=x-100
                if xdef<0:
                    xdef=0
                x1def=x1+100
                if x1def>width1:
                    x1def=width1-1    


                rostro = img_original[ydef:y1def, xdef:x1def]


                sigue=True
                if(type(rostro) == type(None)):
                    sigue=False
                else:
                    
                    try:
                        # rostro = cv2.resize(rostro, (150, 150), interpolation=cv2.INTER_CUBIC)
                        rostro = cv2.resize(rostro, (250, 250), interpolation=cv2.INTER_CUBIC)
                    except Exception as e:
                        printLog(str(e))
                        sigue=False



                if sigue:
                    segs_elapsed = time.time() - segundos_ini
                    nombrefinal=FICHERO+'_'+str(segs_elapsed)
                    cv2.imwrite('/var/www/html/reconocimientoFacial/proyecto_definitivo/motor/caras/sinclasificar/'+nombrefinal+'.jpg', rostro)
                        

                    printLog("cara guardada en /"+nombrefinal+".jpg con esta confidence:"+str(confidence))

        
        # cv2.imshow("dnn", img)
        #printLog('----------------------------------------------------------');
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    else:
        break
cap.release()
cv2.destroyAllWindows()


# os.remove(name_file)

printLog("Llego al final y remuevo el video!")
    



"""
----------------------------------------------------------------------------------------------------------------------------------------------------------------------
Borrar las fotos no enfocadas ni centradas, y luego saca los encodings para guardarlos
----------------------------------------------------------------------------------------------------------------------------------------------------------------------
"""


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
        # copyfile(imagePath+"_tmp.jpg" , "/var/www/html/reconocimientoFacial/proyecto_definitivo/motor/removidas/tmp/"+name_file)
        os.remove(imagePath+"_tmp.jpg")
        if fm > UMBRAL_ENFOQUE_MAXIMO_CARA:    
            printLog("Ademas esta enfocada")
            devolver=fm
         
    else:
        fm = variance_of_laplacian(gray)
        #printLog("NO se puede recortar la face, por lo que aplico el umbral de la foto completa y su fm es:"+str(fm)+" y el umbral que considero:"+str(UMBRAL_ENFOQUE_MAXIMO))
        printLog("No se puede recortar la face")
        """
        if fm > UMBRAL_ENFOQUE_MAXIMO:
           devolver=fm
        """   

    printLog("Lo que estoy devolviendo al final:"+str(devolver))
    return devolver


def escara(imagePath):

    frontal=False


    
    face1 = "/var/www/html/reconocimientoFacial/proyecto_definitivo/motor/models/haarcascade_frontalface2.xml"
    face2 = "/var/www/html/reconocimientoFacial/proyecto_definitivo/motor/models/haarcascade_frontalface_alt.xml"
    face3 = "/var/www/html/reconocimientoFacial/proyecto_definitivo/motor/models/haarcascade_frontalface_alt2.xml"
    face4 = "/var/www/html/reconocimientoFacial/proyecto_definitivo/motor/models/haarcascade_frontalface_alt_tree.xml"
    face5 = "/var/www/html/reconocimientoFacial/proyecto_definitivo/motor/models/haarcascade_frontalface_default.xml"
    face6 = "/var/www/html/reconocimientoFacial/proyecto_definitivo/motor/models/haarcascade_profileface.xml"
    face7 = "/var/www/html/reconocimientoFacial/proyecto_definitivo/motor/cosas_en_la_cara/models/haarcascade_frontalface_default.xml"

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

    data = pickle.loads(open('/var/www/html/reconocimientoFacial/proyecto_definitivo/motor/bbdd_reconocimiento/'+LOCAL_ID+'/face_enc', "rb").read())

    for ff in range(0,len(data["encodings"])):
        knownEncodings_def.append(data["encodings"][ff])
        knownNames_def.append(data["names"][ff])
        knownPoints_def.append(data["points"][ff])
        knownIdentificadorunico_def.append(data["identificadoresunicos"][ff])
        knownEnfoque_def.append(data["enfoque"][ff])
        #printLog("anyado encoding q ya abia de este name"+data["names"][ff]+", y el enfoque:"+data["enfoque"][ff])


    #printLog("anyado todo lo recabado")
    data = {"encodings": knownEncodings_def, "names": knownNames_def, "points": knownPoints_def, "identificadoresunicos": knownIdentificadorunico_def, "enfoque": knownEnfoque_def}
    with FileLock('/var/www/html/reconocimientoFacial/proyecto_definitivo/motor/bbdd_reconocimiento/'+LOCAL_ID+'/face_enc'):
        f = open('/var/www/html/reconocimientoFacial/proyecto_definitivo/motor/bbdd_reconocimiento/'+LOCAL_ID+'/face_enc', "wb")
        f.write(pickle.dumps(data))
        f.close()










# UMBRAL_ENFOQUE_MAXIMO=120 # menos de este desenfoque , se descartan
# UMBRAL_ENFOQUE_MAXIMO_CARA=90 #menos de este enfoque se descartan ,pero solo actuando sobre la cara

# UMBRAL_ENFOQUE_MAXIMO=300 # menos de este desenfoque , se descartan
UMBRAL_ENFOQUE_MAXIMO_CARA=120 #menos de este enfoque se descartan ,pero solo actuando sobre la cara

path_imgs='/var/www/html/reconocimientoFacial/proyecto_definitivo/motor/caras/sinclasificar/'



imagePaths = list(paths.list_images(path_imgs))


knownEncodings = []
knownNames = []
knownPoints = []
knownIdentificadorunico = []
knownEnfoque = []


proc = subprocess.Popen("php /var/www/html/reconocimientoFacial/proyecto_definitivo/ws.php nombreunico", shell=True, stdout=subprocess.PIPE)
ganador_name = str(proc.stdout.read())
ganador_name = ganador_name.replace("'", "")
printLog("Como es nuevo, le voy a asignar un random: "+ganador_name)


for (i, imagePath) in enumerate(imagePaths):
    name_file = imagePath.split(os.path.sep)[-1]
    printLog('analizando:'+name_file)


    insertada=False
    enfoque=comprueba_enfocada(imagePath,name_file)
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

                if(len(encodings)>1):
                    printLog("Esto no puede pasar, hay mas de 1 cara en la imagen")
                else:
                    printLog("Perfecto, supera todos los filtros")
                    insertada=True

                    for encoding in encodings:    
                        knownEncodings.append(encoding)  

                        
                    proc = subprocess.Popen("php /var/www/html/reconocimientoFacial/proyecto_definitivo/ws.php fotos_identificadorunico", shell=True, stdout=subprocess.PIPE)
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
        copyfile(imagePath , "/var/www/html/reconocimientoFacial/proyecto_definitivo/motor/removidas/nopasafiltros/"+name_file)
    else:
        printLog('La imagen es buena, voy a ponerla en su correspondiente carpeta, para conservarla: '+imagePath)

        if not os.path.exists('/var/www/html/reconocimientoFacial/proyecto_definitivo/motor/caras/'+LOCAL_ID+'/'+CAMARA_ID+'/'+ganador_name):
            os.makedirs('/var/www/html/reconocimientoFacial/proyecto_definitivo/motor/caras/'+LOCAL_ID+'/'+CAMARA_ID+'/'+ganador_name)

        copyfile(imagePath, '/var/www/html/reconocimientoFacial/proyecto_definitivo/motor/caras/'+LOCAL_ID+'/'+CAMARA_ID+'/'+ganador_name+'/'+name_file+'_'+fotos_identificadorunico+".jpg") 
        printLog("He copiado de aki: "+imagePath+ " a aki: "+ganador_name+'/'+name_file+'_'+fotos_identificadorunico+".jpg")
    os.remove(imagePath)



anyade_datos(knownEncodings,knownNames,knownPoints,ganador_name,knownIdentificadorunico,knownEnfoque)



time_elapsed = time.time() - time_ini
printLog("Tiempo de analizar el video:" + str(time_elapsed))



