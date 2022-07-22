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



"""
umbral_parecidosentresi=0.5555
umbral=0.5769
umbral_solounaodos=0.5259
umbral_delasmedias=0.6755
umbral_segurisimo=0.2155
veces_umbral_medias_augmenta=20
umbral_junto=0.6759
umbral_junto2=0.7559
porcentaje_veces_supera=29
DIFERENCIA_PROMERO_Y_SEGUNDO=0.0555
MAXIMAS_REPETICIONES_GUARDADO=100
"""

"""
umbral_parecidosentresi=0.5555
umbral=0.59
umbral_solounaodos=0.53
umbral_delasmedias=0.62
umbral_segurisimo=0.3
veces_umbral_medias_augmenta=20
umbral_junto=0.69
umbral_junto2=0.7559
porcentaje_veces_supera=20
DIFERENCIA_PROMERO_Y_SEGUNDO=0.0555
MAXIMAS_REPETICIONES_GUARDADO=100
"""



umbral_parecidosentresi=0.39        # cuando va a clasificar las fotos y los que son parecidos entre si para decir qe esla misma persona
umbral=0.59                         # umbral para comprara foto a foto y ver con cual supera y el qe se usa para recompara cuando ya se tiene la media
umbral_solounaodos=0.515            # para comparar con las medias pero solo hay 1 o 2 fotos
umbral_delasmedias=0.62             # umbral cuando se a exo las medias
# umbral_segurisimo=0.35              # si 1 foto supera esto es ese
umbral_segurisimo=0.40              # si 1 foto supera esto es ese
veces_umbral_medias_augmenta=15     # si se hay mas de X vces influya en los 2 umbrales de abajo
# umbral_junto=0.6355                 # la media de los qe superan y los qe no para esa persona qe se comparó
umbral_junto=0.69                 # la media de los qe superan y los qe no para esa persona qe se comparó
# umbral_junto2=0.6255                # la media de los qe superan y los qe no para esa persona qe se comparó
umbral_junto2=0.67                # la media de los qe superan y los qe no para esa persona qe se comparó
# porcentaje_veces_supera=21          # si de todas las veces no supera este porcentaje de veces supera 
# porcentaje_veces_supera=10          # si de todas las veces no supera este porcentaje de veces supera 
porcentaje_veces_supera=16          # si de todas las veces no supera este porcentaje de veces supera 
DIFERENCIA_PROMERO_Y_SEGUNDO=0.08   # en los ganadores la diferencia qe tienen qe tener para qe alomejor sea el 2º
MAXIMAS_REPETICIONES_GUARDADO=100   # 




cinco_segundos = timedelta(0, 10)

LOCAL_ID=sys.argv[1]
CAMARA_ID=sys.argv[2]


def printLog(*args, **kwargs):
    print(*args, **kwargs)
    # with open('motor/procesa_fotos_def_'+CAMARA_ID+'.out','a') as file:
    #     print(*args, **kwargs, file=file)


def anyade_datos_def(maximo,count,knownEncoding,knownName,knownPoint,ganador_name,knownIdentificadorunic):

    # printLog("anyade_datos_def, count:"+str(count))

    knownEncodings_def=[]
    knownNames_def=[]
    knownPoints_def=[]
    knownIdentificadorunico_def=[]

    data = pickle.loads(open('motor/bbdd_reconocimiento/'+LOCAL_ID+'/face_enc', "rb").read())


    if count<MAXIMAS_REPETICIONES_GUARDADO:
        # printLog("cokmo count < MAXIMAS_REPETICIONES_GUARDADO("+str(MAXIMAS_REPETICIONES_GUARDADO)+")")
        knownEncodings_def.append(knownEncoding)
        knownNames_def.append(knownName)
        knownPoints_def.append(knownPoint)
        knownIdentificadorunico_def.append(knownIdentificadorunic)

        # printLog("anyado el encoding pasado")

        for ff in range(0,len(data["encodings"])):
            knownEncodings_def.append(data["encodings"][ff])
            knownNames_def.append(data["names"][ff])
            knownPoints_def.append(data["points"][ff])
            knownIdentificadorunico_def.append(data["identificadoresunicos"][ff])
            # printLog("anyado encoding q ya abia de este name"+data["names"][ff])

    else:
        if knownPoint >= maximo:      
            for ff in range(0,len(data["encodings"])):
                knownEncodings_def.append(data["encodings"][ff])
                knownNames_def.append(data["names"][ff])
                knownPoints_def.append(data["points"][ff])
                knownIdentificadorunico_def.append(data["identificadoresunicos"][ff])
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
                else:
                    knownEncodings_def.append(data["encodings"][ff])
                    knownNames_def.append(data["names"][ff])
                    knownPoints_def.append(data["points"][ff])
                    knownIdentificadorunico_def.append(data["identificadoresunicos"][ff])


    # printLog("anyado todo lo recabado")
    data = {"encodings": knownEncodings_def, "names": knownNames_def, "points": knownPoints_def, "identificadoresunicos": knownIdentificadorunico_def}
    with FileLock('motor/bbdd_reconocimiento/'+LOCAL_ID+'/face_enc'):
        f = open('motor/bbdd_reconocimiento/'+LOCAL_ID+'/face_enc', "wb")
        f.write(pickle.dumps(data))
        f.close()

def anyade_datos(knownEncodings1,knownNames1,knownPoints1,ganador_name,knownIdentificadorunico1):

    printLog("blokeado fichero y anyade_datos de "+ganador_name)

    count=0
    maximo=0

    data = pickle.loads(open('motor/bbdd_reconocimiento/'+LOCAL_ID+'/face_enc', "rb").read())
    for ff in range(0,len(data["encodings"])):
        if data["names"][ff]==ganador_name:
            # printLog("ya tenia encoding")
            count=count+1
            if data["points"][ff]>maximo:
                maximo=data["points"][ff]
                # printLog("este es el maximo de momento:"+str(maximo))
        
    # printLog("maximo definitivo:"+str(maximo))

    for ff in range(0,len(knownEncodings1)):
        # printLog("nuevo encoding pasado qe se va a anyadir")
        anyade_datos_def(maximo,count,knownEncodings1[ff],knownNames1[ff],knownPoints1[ff],ganador_name,knownIdentificadorunico1[ff])
    # printLog("Finalmente fichero desbloekado")


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
    else:
        printLog("es frontal de mommento")     
        flipped = cv2.flip(gray, 1)
        faces6 = face_cascade6.detectMultiScale(flipped, 1.01,50)
        for (x,y,w,h) in faces6:
            eslateral=True
        if eslateral:
            printLog("es lateral 2")     
            #copyfile(imagePath, 'caras/pruebas_res/nocara/'+name_file)
        else:
            printLog("es frontal 1")     
            # copyfile(imagePath, 'caras/pruebas_res/escara/'+name_file)
            frontal=True
   
    ojos_detectado=False
    
    if eslateral:
        printLog("afirmo qe es lateral")  
        # ----------------------------------
        
        if not ojos_detectado:
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
    return frontal






path_imgs='motor/caras/sinclasificar/'+LOCAL_ID+'/'+CAMARA_ID+'/'


# printLog("paso2")
count_global=0
sigue=True
while sigue:
    # printLog("INI procesando......")


    # printLog("recojo ficheros disponibles..")

    imagePaths = list(paths.list_images(path_imgs))

    ficheros = []
    ficheros_path = []
    for (i, imagePath) in enumerate(imagePaths):
        name_file = imagePath.split(os.path.sep)[-1]
        

        
        if esfrontal(imagePath):
            ficheros.append(name_file)
            ficheros_path.append(imagePath)

            printLog('en ficheros anyado:'+name_file)
            printLog('en ficheros_path anyado:'+imagePath)
        else:
            os.remove(imagePath)
        


    # printLog()
    # printLog()
    # printLog()
    # printLog()
    # printLog("-----------------")
    # printLog()
    # printLog()
    # printLog()
    # printLog()

    ficheros=sorted(ficheros)
    ficheros_path=sorted(ficheros_path)

    baterias = []
    baterias_ficheros = []
    encoders = []
    count = 0

    iniciado=False


    # printLog("ordenando ficheros por proximidad")
    for (i, fichero) in enumerate(ficheros):
        printLog("->i:"+str(i))
        printLog('ordenando ficheros por proximidad,   Nombre fichero:'+fichero) 
        printLog('Pero este Path?:'+ficheros_path[i]) 

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

       
        printLog("camara_id:"+camara_id)
        printLog("fecha:"+fecha)
        printLog("hora:"+hora)
        printLog("segundos:"+segundos)

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
                else:
                    printLog("El grupo es nuevo por que la diferencia es >5segs con el anterior")

                    new_bateria=[fecha_datetime_definitiva]
                    baterias.append(new_bateria)

                    new_bateria_ficheros=[fichero]
                    baterias_ficheros.append(new_bateria_ficheros)

                    new_bateria_encoders=[encodings[0]]
                    encoders.append(new_bateria_encoders)

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

                count=count+1


            anterior=fecha_datetime_definitiva
        else:
            printLog("Esta imagen no tiene caras1")
            os.remove(ficheros_path[i])
            printLog("imagen removida:"+ficheros_path[i])

        printLog()    
        # printLog()    


    # printLog("Ficheros ordenados por proximidad:")
    # printLog(baterias_ficheros)
    # printLog()
    # printLog()
    # printLog()

    # printLog('----')

    # printLog("creo array de comparacion ")
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

    # printLog("Array bateria fechas")
    # printLog(baterias)

    # printLog()
    # printLog()
    # printLog()

    # printLog("Array comparaciones")
    # printLog(comparaciones)

    # printLog()
    # printLog()
    # printLog()


    # printLog("veo cuales superan")    
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
        
    # printLog("Array superan")
    # printLog(superan)


    # printLog()
    # printLog()
    # printLog()


    # printLog("Ara ya creo grupos de la misma hora y de mismas personas")

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
                # printLog("estoy en el j=0,preparo qe tenemos 1 grupo")
                num_grupos=1
            else:    
                # printLog("estamos en j="+str(j)+", por lo qe preparo a ver si este o alguno de sus compañeros los meto donde")
                esta_alguno=False
                encual=0



            for b3 in superan[i][j]: 
                if j==0:
                    # printLog("para superan de i,j:"+str(i)+","+str(j)+"anyado elemento a grupo inicial")
                    grupos[i][num_grupos-1].append(superan[i][j][k])
                    veces[i][num_grupos-1].append(1)
                else:
                    # printLog("Ya no estoy en el j inicial de este grupo de imgs:"+str(i)+", por lo qe voy a ver donde los meto, tenemos:"+str(superan[i][j][k]))

                    
                    h=0
                    for b4 in grupos[i]: 
                        w=0
                        for b5 in grupos[i][h]: 
                            # printLog("recorriendo los grupos, tenemos ("+str(i)+","+str(h)+","+str(w)+") :"+str(grupos[i][h][w]))

                            if superan[i][j][k]==grupos[i][h][w]:
                                # printLog("como ya estaba metido, marco como qe esta y ara metere a todos sus compañeros meto todos sus compañeros:")
                                esta_alguno=True
                                encual=h
                                veces[i][h][w]=veces[i][h][w]+1

                            w=w+1
                        h=h+1
                k=k+1    

            if j>0:
                if not esta_alguno:
                    #creo nuevo grupo
                    # printLog("no habia ninguno metido, por lo qe creo nuevo grupo con estos")

                    l=0
                    num_grupos=num_grupos+1
                    for b3 in superan[i][j]: 
                        # printLog("Voy a anyadir:"+str(superan[i][j][l]))
                        grupos[i][num_grupos-1].append(superan[i][j][l])
                        veces[i][num_grupos-1].append(1)
                        l=l+1
                    
                else:
                    # printLog("ya habia alguno metido por lo qe los demas los meto en el grupo en el cual habia alguno")

                    l=0
                    for b6 in superan[i][j]: 
                        # printLog("trato de meter "+str(superan[i][j][l]))
                        if not superan[i][j][l] in grupos[i][encual]:
                            grupos[i][encual].append(superan[i][j][l])
                            veces[i][encual].append(1)
                            # printLog("como no estaba, lo meto")
                        else:
                            # printLog("ya estaba")    
                            josue=True # sentencia auxiliar para no dejar el else vacio qe sino peta
                        l=l+1
                
            j=j+1 
            # printLog("traceando2:")
            # printLog(grupos)   
        i=i+1  

    # printLog("grupos") 
    # printLog(grupos) 
    # printLog("veces") 
    # printLog(veces) 
    # printLog('-----------------------------------------------------------------------')    
    

    i=0
    for b in grupos:
        j=0
        for b2 in grupos[i]: 
            if len(grupos[i][j])>0:
                k=0
                # printLog()
                # printLog()
                # printLog()
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




                nombre_fichero_final=""
                nombre_inicializado=False
                nombre_puesto=False
                for b3 in grupos[i][j]: 
                    printLog("--------------------->"+baterias_ficheros[i][grupos[i][j][k]])

                    if k==(len(grupos[i][j])-1):
                        if k==0:
                            nombre_fichero_final=baterias_ficheros[i][grupos[i][j][k]]
                        else:
                            nombre_fichero_final=nombre_fichero_final+"----"+baterias_ficheros[i][grupos[i][j][k]]
                        nombre_puesto=True



                    name_file=baterias_ficheros[i][grupos[i][j][k]]


                    
                    if cv2.haveImageReader (path_imgs+name_file):


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
                                # printLog("ganador_idx:"+str(ganador_idx))

                            hay_cara=True 


                            for encoding in encodings:
                                data = pickle.loads(open('motor/bbdd_reconocimiento/'+LOCAL_ID+'/face_enc', "rb").read())

                                # printLog("numero encodings")
                                # printLog(len(encodings))
                                # printLog()
                                # printLog()
                                # printLog("encodings guardados")
                                # printLog(data["encodings"])
                                # printLog()
                                # printLog()
                                # printLog("encoding actual")
                                # printLog(encoding)
                                # printLog()
                                # printLog()

                                face_distances = face_recognition.face_distance(data["encodings"],encoding)

                                losencodings.append(encoding)

                                printLog("Voy a analizar las facedistances")



                                for fa, face_distance in enumerate(face_distances):

                                    printLog("para este name:"+data["names"][fa]+", es "+str(face_distance))


                                    if data["names"][fa] in puntuaciones:
                                        printLog("paso1:"+str(face_distance))
                                        veces2[data["names"][fa]]=veces2[data["names"][fa]]+1
                                        puntuaciones[data["names"][fa]]=puntuaciones[data["names"][fa]]+face_distance

                                    else:
                                        printLog("paso2:"+str(face_distance))
                                        puntuaciones[data["names"][fa]] = face_distance
                                        veces2[data["names"][fa]] = 1


                                    if not data["names"][fa] in listado_puntuaciones:
                                        listado_puntuaciones[data["names"][fa]] = []
                                    listado_puntuaciones[data["names"][fa]].append(face_distance)
                                    



                                    if face_distance<umbral_segurisimo or face_distance<umbral:

                                        if face_distance<umbral_segurisimo:                                    
                                            veces_segurisimo=veces_segurisimo+1
                                            elnombresegurisimo=data["names"][fa]
                                            puntuacion_segurisimo=face_distance
                                            printLog("supera el umbral de segurisimo")

                                    

                                        if data["names"][fa] in puntuaciones_supera:
                                            printLog("paso3:"+str(face_distance))
                                            veces_supera[data["names"][fa]]=veces_supera[data["names"][fa]]+1
                                            puntuaciones_supera[data["names"][fa]]=puntuaciones_supera[data["names"][fa]]+face_distance

                                        else:
                                            printLog("paso4:"+str(face_distance))
                                            puntuaciones_supera[data["names"][fa]] = face_distance
                                            veces_supera[data["names"][fa]] = 1



                                        if not data["names"][fa] in ganadores:
                                            printLog("Como no estaba en ganadores, lo anyado")    
                                            ganadores.append(data["names"][fa])


                                        printLog("supera el umbral con este nombre:"+data["names"][fa])
                                        printLog("puntuacion:"+str(face_distance))
                                    # printLog("veces superado:"+str(veces_supera[data["names"][fa]]))

                                    printLog()

                        else:   
                            printLog("No tiene caras esta imagen joder!")  
                            losencodings.append('') 

                        k=k+1    


                printLog()    
                printLog("Voy a analizar de los qe ha superado, sus medias y historias a ver con cual me qedo:")
                
                for g in ganadores: 

                    # si no supera un % de veces incremental ni se calcula
                    printLog("el nombre:"+g+", si no supera un % de veces incremental ni se calcula. Tenemos estas veces:"+str(veces2[g])+", y estas veces_supera:"+str(veces_supera[g]))
                    sigue_analizando=False
                    if veces2[g]<=2:
                        sigue_analizando=True
                        printLog("Como es < qe 2 veces lo supero")
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
                        # printLog("ademas la puntuacion definitiva es (media/veces):"+str(definitivo))

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
                        media_supera1=m2/count_supera

                        rango_min=media1-(mediana/2)
                        rango_max=media1+(mediana/2)
                        rango_min_supera=media_supera1-(mediana_supera/2)
                        rango_max_supera=media_supera1+(mediana_supera/2)


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


                        if v_media_supera>0:

                            media=media/v_media
                            media_supera=media_supera/v_media_supera

                            printLog("")
                            printLog("La media definitiva limpia:"+str(media))
                            printLog("La media supera definitiva limpia:"+str(media_supera))



                            if veces_segurisimo>0:
                                printLog("estoy segurisimo qe es este")

                                ganador=elnombresegurisimo
                                puntuacion=puntuacion_segurisimo
                                veces_ganador=veces_segurisimo
                                veces_supera_ganador=veces_segurisimo

                            else: 
                                activate=False

                                if veces2[g]>veces_umbral_medias_augmenta:
                                    if media_supera<umbral and media<umbral_junto2:
                                        activate=True
                                else:
                                    if media_supera<umbral and media<umbral_junto:
                                        activate=True


                                if activate:
                                    printLog("la media supera el umbral")
                                    if media<puntuacion:
                                        # printLog("voy a actualizar el segundo con estos datos:"+ganador+" - "+str(puntuacion)+" - "+str(veces_ganador)+" - "+str(veces_supera_ganador))

                                        tercero_def=segundo
                                        tercero_k=segundo_k
                                        tercero_punt=segundo_punt

                                        segundo=ganador
                                        puntuacion_segundo=puntuacion
                                        veces_segundo=veces_ganador
                                        veces_supera_segundo=veces_supera_ganador
                                        segundo_k=primero_k
                                        segundo_punt=primero_punt

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
                        else:
                            printLog("no supera ni una vez el umbral!")



                printLog("ya analizadas las medias, voy a qedarme con el gnaador")

                if puntuacion==999:
                    # name=str(random.randint(1000,9999))
                    name="NUEVO"
                    printLog("No hay ganador es cara nueva, le asigno este nombre:"+name)
                else:

                    # en base al numero de veces qe se ha encontrado, la media, la diferencia con el segundo


                    printLog("ganador:"+ganador+" - puntuacion:"+str(puntuacion)+", veces:"+str(veces_ganador)+", veces_supera:"+str(veces_supera_ganador))    
                    printLog("segundo:"+segundo+" - puntuacion:"+str(puntuacion_segundo)+", veces:"+str(veces_segundo)+", veces_supera:"+str(veces_supera_segundo))        
                    name=ganador
                    if abs(puntuacion-puntuacion_segundo)<DIFERENCIA_PROMERO_Y_SEGUNDO:

                        printLog("se diferencian de muy poco")




                        if veces_supera_ganador *2 < veces_supera_segundo:
                            printLog("el segundo aparece el doble de veces qe el primero de superado")    
                            name=segundo
                            puntuacion=puntuacion_segundo
                        else:
                            aux_ganador=veces_supera_ganador*100/veces_ganador
                            aux_segundo=veces_supera_segundo*100/veces_segundo
                            printLog("tasa de supero ganador"+str(aux_ganador))
                            printLog("tasa de supero segundo"+str(aux_segundo))

                            if aux_segundo>aux_ganador:
                                printLog("como el segundo la tasa de superacion es mas veces")
                                name=segundo
                                puntuacion=puntuacion_segundo
                    printLog("ganador definitivo:"+name)





                if not name in kien_puntuaciones:
                    kien_veces[name]=1
                    kien_puntuaciones[name]=puntuacion
                    kien_k[name]=k

                    kien_lista_puntuaciones[name]=[]
                    kien_lista_puntuaciones[name].append(puntuacion)


                    kien_encodings[name]=[]
                    kien_encodings[name].append(encoding)

                    printLog("Todavia no tenemos este name: "+name+" asi qe lo guardo con esta puntuacion:"+str(puntuacion))
                else:
                    kien_veces[name]=kien_veces[name]+1
                    kien_puntuaciones[name]=kien_puntuaciones[name]+puntuacion
                    printLog("Este name: "+name+" ya se tenia asi qe incremento su puntuacion y sus veces. Puntuacion:"+kien_puntuaciones[name]+", veces: "+kien_veces[name])
                    


                        


                # printLog("img analizada!!!!!!!!!!!!!!!!!!!!!!!!!")
                printLog()

                #k=k+1



                printLog("la imagen representativa de estas sera:"+baterias_ficheros[i][grupos[i][j][ganador_idx]])
                fichero_a_mover=baterias_ficheros[i][grupos[i][j][ganador_idx]]


                if hay_cara:

                    printLog("Una vez analizadas todas las imagenes del grupo, voy a tomar decisiones: de a kien de los nombres almacenados pertenece la cara")


                    for name in kien_puntuaciones:
                        media=kien_puntuaciones[name]/kien_veces[name]
                        printLog("para este nombre:"+name+" tenemos esta puntuacion:"+str(kien_puntuaciones[name])+", y estas veces:"+str(kien_veces[name])+", la media al final es:"+str(media))
                        kien_puntuaciones[name]=media


                    printLog("Voy a ver el ganador")
                    ganador_name=""
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
                        if kien_puntuaciones[name]<ganador_pts:
                            ganador_pts=kien_puntuaciones[name]
                            ganador_name=name
                            hay_ganador=True
                            printLog("De momento el ganador es:"+ganador_name+", con estos puntos"+str(ganador_pts))


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



                    if hay_ganador:
                        printLog("Hay ganador")
                        if ganador_pts>umbral_delasmedias:
                            printLog("No se cumple el umbral de las medias, por lo qe lo considero nuevo,"+str(ganador_pts)+"--"+str(umbral_delasmedias))
                            ganador_name="NUEVO"


                    if ganador_name=="NUEVO":
                        # ganador_name=str(random.randint(10000,99999))

                        proc = subprocess.Popen("php ws.php nombreunico", shell=True, stdout=subprocess.PIPE)
                        ganador_name = str(proc.stdout.read())
                        ganador_name = ganador_name.replace("'", "")



                        printLog("Como es nuevo, le voy a asignar un random: "+ganador_name)


                    printLog("el nombre definitivo asignado es:"+ganador_name)




                    # encoding=losencodings[ganador_idx]
                    
                    
                    # printLog("el encoding qe voy a guardar al final para esta imagen es:")
                    # printLog(encoding)
                    # printLog("qe sale de es este ganador_idx:"+str(ganador_idx))
                    # printLog()


                    proc = subprocess.Popen("php ws.php fotos_identificadorunico", shell=True, stdout=subprocess.PIPE)
                    fotos_identificadorunico = str(proc.stdout.read())
                    fotos_identificadorunico = fotos_identificadorunico.replace("'", "")
                    #fotos_identificadorunico= str(random.randint(10000,99999))                  


                    knownEncodings = []
                    knownNames = []
                    knownPoints = []
                    knownIdentificadorunico = []

                    knownEncodings.append(encoding1)
                    knownNames.append(ganador_name)
                    knownPoints.append(puntuacion1)
                    knownIdentificadorunico.append(fotos_identificadorunico)


                    if puntuacion2!=9999:
                        # encoding2=losencodings[segundo_k]
                        knownEncodings.append(encoding2)
                        knownNames.append(ganador_name)
                        knownPoints.append(puntuacion2)
                        knownIdentificadorunico.append(fotos_identificadorunico)

                    if puntuacion3!=9999:
                        # encoding3=losencodings[tercero_k]
                        knownEncodings.append(encoding3)
                        knownNames.append(ganador_name)
                        knownPoints.append(puntuacion3)
                        knownIdentificadorunico.append(fotos_identificadorunico)

                    anyade_datos(knownEncodings,knownNames,knownPoints,ganador_name,knownIdentificadorunico)
                    if not os.path.exists('motor/caras/'+LOCAL_ID+'/'+CAMARA_ID+'/'+ganador_name):
                        os.makedirs('motor/caras/'+LOCAL_ID+'/'+CAMARA_ID+'/'+ganador_name)



                    # copyfile(path_imgs+fichero_a_mover, './motor/caras/'+LOCAL_ID+'/'+CAMARA_ID+'/'+ganador_name+'/'+nombre_fichero_final+"_____"+str(count_global)+".jpg") 
                    copyfile(path_imgs+fichero_a_mover, './motor/caras/'+LOCAL_ID+'/'+CAMARA_ID+'/'+ganador_name+'/'+nombre_fichero_final+'_'+fotos_identificadorunico+".jpg") 
                    count_global=count_global+1
                    # printLog("He copiado de aki: "+path_imgs+fichero_a_mover+ " a aki: "+'motor/caras/'+LOCAL_ID+'/'+CAMARA_ID+'/'+ganador_name+'/'+nombre_fichero_final+".jpg")

                else:
                    printLog("Del grupo analizado no habia ni una puta cara")


                jj=0
                printLog("Voy a eliminar los ficheros procesados ya ")
                for b3 in grupos[i][j]: 
                    printLog("Borro:"+baterias_ficheros[i][grupos[i][j][jj]])
                    if os.path.isfile(path_imgs+baterias_ficheros[i][grupos[i][j][jj]]):
                        os.remove(path_imgs+baterias_ficheros[i][grupos[i][j][jj]])
                    jj=jj+1


                printLog("#################")    
                printLog()    
                printLog()    
                # printLog()    
                # printLog()    
            j=j+1    
        i=i+1   

    # print()
    # print("//////////////////////////")
    # print()

    
    # sigue=False
    # exit()



printLog('-----------------------------------------------------------------------')

# printLog("baterias")
# printLog(baterias)
# printLog()
# printLog()
# printLog()
printLog("baterias_ficheros")
printLog(baterias_ficheros)
printLog()
printLog()
printLog()
# printLog("encoders")
# printLog(encoders)
# printLog()
# printLog()
# printLog()
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




