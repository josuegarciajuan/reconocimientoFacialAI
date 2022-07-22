# -ok-recorro las fotos sin clasificar del local_id, camara_id
# -ok-las qe estan juntas en el tiempo, osea qe entre una y la siguiente haya menos de 5segundos, las trata como una bateria a procesar juntas
# -ok-saca el encoder de cada foto de toda la bateria
# -ok-(cuidado pueden haber caras mezcladas en la misma bateria) las proximas entre si, las considera como la misma cara 
# --las qe se consideran la misma cara ya las comprao con el diccionario, a la qe mas se parezcan pos esa es ya la meto en su carpeta con su nombre random correpondiente si es nueva o existe..

# python3.7 motor/procesa_fotos_def_pruebas.py 3 3


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


# umbral_parecidosentresi=0.725
# umbral=0.61
# umbral_junto=0.65
# umbral_delasmedias=0.55
# DIFERENCIA_PROMERO_Y_SEGUNDO=0.05

umbral_parecidosentresi=0.6
umbral=0.5
umbral_junto=0.65
umbral_delasmedias=0.6
DIFERENCIA_PROMERO_Y_SEGUNDO=0.05
MAXIMAS_REPETICIONES_GUARDADO=100

cinco_segundos = timedelta(0, 5)

LOCAL_ID=sys.argv[1]
CAMARA_ID=sys.argv[2]


def printLog(*args, **kwargs):
    print(*args, **kwargs)
    # with open('motor/procesa_fotos_def.out','a') as file:
    #     print(*args, **kwargs, file=file)


def anyade_datos_def(maximo,count,knownEncoding,knownName,knownPoint,ganador_name):

    # printLog("anyade_datos_def, count:"+str(count))

    knownEncodings_def=[]
    knownNames_def=[]
    knownPoints_def=[]

    data = pickle.loads(open('motor/bbdd_reconocimiento/'+LOCAL_ID+'/face_enc', "rb").read())


    if count<MAXIMAS_REPETICIONES_GUARDADO:
        # printLog("cokmo count < MAXIMAS_REPETICIONES_GUARDADO("+str(MAXIMAS_REPETICIONES_GUARDADO)+")")
        knownEncodings_def.append(knownEncoding)
        knownNames_def.append(knownName)
        knownPoints_def.append(knownPoint)

        # printLog("anyado el encoding pasado")

        for ff in range(0,len(data["encodings"])):
            knownEncodings_def.append(data["encodings"][ff])
            knownNames_def.append(data["names"][ff])
            knownPoints_def.append(data["points"][ff])
            # printLog("anyado encoding q ya abia de este name"+data["names"][ff])

    else:
        if knownPoint >= maximo:      
            for ff in range(0,len(data["encodings"])):
                knownEncodings_def.append(data["encodings"][ff])
                knownNames_def.append(data["names"][ff])
                knownPoints_def.append(data["points"][ff])
        else:
            knownEncodings_def.append(knownEncoding)
            knownNames_def.append(knownName)
            knownPoints_def.append(knownPoint)

            for ff in range(0,len(data["encodings"])):
                if data["names"][ff]==ganador_name:
                    if data["points"][ff]<maximo:
                        knownEncodings_def.append(data["encodings"][ff])
                        knownNames_def.append(data["names"][ff])
                        knownPoints_def.append(data["points"][ff])
                else:
                    knownEncodings_def.append(data["encodings"][ff])
                    knownNames_def.append(data["names"][ff])
                    knownPoints_def.append(data["points"][ff])


    # printLog("anyado todo lo recabado")
    data = {"encodings": knownEncodings_def, "names": knownNames_def, "points": knownPoints_def}
    with FileLock('motor/bbdd_reconocimiento/'+LOCAL_ID+'/face_enc'):
        f = open('motor/bbdd_reconocimiento/'+LOCAL_ID+'/face_enc', "wb")
        f.write(pickle.dumps(data))
        f.close()

def anyade_datos(knownEncodings1,knownNames1,knownPoints1,ganador_name):

    # printLog("blokeado fichero y anyade_datos de "+ganador_name)

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
        anyade_datos_def(maximo,count,knownEncodings1[ff],knownNames1[ff],knownPoints1[ff],ganador_name)
    # printLog("Finalmente fichero desbloekado")







path_imgs='motor/caras/sinclasificar/'+LOCAL_ID+'/'+CAMARA_ID+'/'


# printLog("paso2")
count_global=0
sigue=True
while sigue:
    # printLog("procesando..")


    # printLog("recojo ficheros disponibles..")

    imagePaths = list(paths.list_images(path_imgs))

    ficheros = []
    ficheros_path = []
    for (i, imagePath) in enumerate(imagePaths):
        name_file = imagePath.split(os.path.sep)[-1]
        # printLog('Nombre fichero:'+name_file)
        ficheros.append(name_file)
        ficheros_path.append(imagePath)

    # printLog()
    # printLog("------")
    # printLog()

    ficheros=sorted(ficheros)

    baterias = []
    baterias_ficheros = []
    encoders = []
    count = 0

    iniciado=False


    # printLog("ordenando ficheros por proximidad")
    for (i, fichero) in enumerate(ficheros):
        # printLog('ordenando ficheros por proximidad,   Nombre fichero:'+fichero) 
        # printLog('Path:'+ficheros_path[i]) 

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
        fecha_completa=fecha+' '+hora

       
        # printLog("camara_id:"+camara_id)
        # printLog("fecha:"+fecha)
        # printLog("hora:"+hora)
        # printLog("segundos:"+segundos)
        

        fecha_datetime = datetime.strptime(fecha_completa, '%Y-%m-%d %H:%M:%S')
        segundos_datetime = timedelta(0, int(segundos))
        fecha_datetime_definitiva = fecha_datetime+segundos_datetime

        # printLog("fecha_datetime_definitiva:")
        # printLog(fecha_datetime_definitiva)
        


        image = cv2.imread(ficheros_path[i])
        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        boxes = face_recognition.face_locations(rgb,model='cnn')
        encodings = face_recognition.face_encodings(rgb, boxes)


        if len(encodings)>0:
            # printLog("tiene encodings")
            if iniciado:
                # printLog("Ya no es el 1º en analizar")

                diferencia=fecha_datetime_definitiva-anterior
                if diferencia<=cinco_segundos:
                    # printLog("pertenece al mismo grupo pues la diferencia es < 5 segs con el anterior")
                    baterias[count-1].append(fecha_datetime_definitiva)
                    baterias_ficheros[count-1].append(fichero)
                    encoders[count-1].append(encodings[0])
                else:
                    # printLog("El grupo es nuevo por que la diferencia es >5segs con el anterior")

                    new_bateria=[fecha_datetime_definitiva]
                    baterias.append(new_bateria)

                    new_bateria_ficheros=[fichero]
                    baterias_ficheros.append(new_bateria_ficheros)

                    new_bateria_encoders=[encodings[0]]
                    encoders.append(new_bateria_encoders)

                    count=count+1

            else:
                # printLog("Es el 1º en analizar")
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

        # printLog()    
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


    # printLog('-----------------------------------------------------------------------')    
    

    i=0
    for b in grupos:
        j=0
        for b2 in grupos[i]: 
            if len(grupos[i][j]):
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

                ganador_idx=0
                ganador_vec=0

                hay_cara=False


                nombre_fichero_final=""
                nombre_inicializado=False
                nombre_puesto=False
                for b3 in grupos[i][j]: 
                    # printLog("--------------------->"+baterias_ficheros[i][grupos[i][j][k]])

                    if k==(len(grupos[i][j])-1):
                        nombre_fichero_final=nombre_fichero_final+"----"+baterias_ficheros[i][grupos[i][j][k]]
                        nombre_puesto=True


                    veces2={}
                    veces_supera={}
                    puntuaciones={}
                    puntuaciones_supera={}
                    ganadores=[]
                    ganador = ""
                    puntuacion = 999
                    segundo = ""
                    puntuacion_segundo = 999
                    veces_ganador=0
                    veces_segundo=0
                    veces_supera_ganador=0
                    veces_supera_segundo=0

                    segundo_def=""
                    tercero_def=""
                    segundo_k=0
                    tercero_k=0
                    primero_k=0

                    primero_punt=0
                    segundo_punt=0
                    tercero_punt=0



                    name_file=baterias_ficheros[i][grupos[i][j][k]]
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
                                    # printLog("paso1")
                                    veces2[data["names"][fa]]=veces2[data["names"][fa]]+1
                                    puntuaciones[data["names"][fa]]=puntuaciones[data["names"][fa]]+face_distance

                                else:
                                    # printLog("paso2:"+str(face_distance))
                                    puntuaciones[data["names"][fa]] = face_distance
                                    veces2[data["names"][fa]] = 1

                                if face_distance<umbral:

                                    if data["names"][fa] in puntuaciones_supera:
                                        # printLog("paso1")
                                        veces_supera[data["names"][fa]]=veces_supera[data["names"][fa]]+1
                                        puntuaciones_supera[data["names"][fa]]=puntuaciones_supera[data["names"][fa]]+face_distance

                                    else:
                                        # printLog("paso2:"+str(face_distance))
                                        puntuaciones_supera[data["names"][fa]] = face_distance
                                        veces_supera[data["names"][fa]] = 1



                                    if not data["names"][fa] in ganadores:
                                        # printLog("Como no estaba en ganadores, lo anyado")    
                                        ganadores.append(data["names"][fa])


                                    printLog("supera el umbral con este nombre:"+data["names"][fa])
                                    printLog("puntuacion:"+str(face_distance))
                                # printLog("veces superado:"+str(veces_supera[data["names"][fa]]))

                                # printLog()



                            printLog("Voy a analizar de los qe ha superado, sus medias y historias a ver con cual me qedo:")
                            for g in ganadores:
                                media=puntuaciones[g]/veces2[g]
                                media_supera=puntuaciones_supera[g]/veces_supera[g]
                                definitivo=media/veces2[g]
                                printLog("el nombre:"+g+", tienes esta media:"+str(media)+" y aparece estas veces:"+str(veces2[g]))
                                printLog("el nombre:"+g+", tienes esta media_supera:"+str(media_supera)+" y supera estas veces:"+str(veces_supera[g]))
                                printLog("ademas la puntuacion definitiva es (media/veces):"+str(definitivo))

                                if media_supera<umbral and media<umbral_junto:
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
                                        ganador = g
                                        puntuacion = media
                                        veces_ganador=veces2[g]
                                        veces_supera_ganador=veces_supera[g]
                                        primero_k=k
                                        primero_punt=media




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
                                        aux_ganador=veces_ganador/veces_supera_ganador
                                        aux_segundo=veces_segundo/veces_supera_segundo
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
                                kien_encodings[name]=[]
                                kien_encodings[name].append(encoding)

                                printLog("Todavia no tenemos este name: "+name+" asi qe lo guardo con esta puntuacion:"+str(puntuacion))
                            else:
                                kien_veces[name]=kien_veces[name]+1
                                kien_puntuaciones[name]=kien_puntuaciones[name]+puntuacion
                                printLog("Este name: "+name+" ya se tenia asi qe incremento su puntuacion y sus veces")
                    else:
                        printLog("No tiene caras esta imagen joder!")  
                        losencodings.append('') 
                        


                    # printLog("img analizada!!!!!!!!!!!!!!!!!!!!!!!!!")
                    printLog()

                    k=k+1



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
                    for name in kien_puntuaciones:
                        printLog("para este nombre:"+name+", la puntuacion es:"+str(kien_puntuaciones[name]))
                        if kien_puntuaciones[name]<ganador_pts:
                            ganador_pts=kien_puntuaciones[name]
                            ganador_name=name
                            hay_ganador=True
                            printLog("De momento el ganador es:"+ganador_name+", con estos puntos"+str(ganador_pts))

                    



                    if hay_ganador:
                        printLog("Hay ganador")
                        if ganador_pts>umbral_delasmedias:
                            printLog("No se cumple el umbral de las medias, por lo qe lo considero nmuevo")
                            ganador_name="NUEVO"


                    if ganador_name=="NUEVO":
                        ganador_name=str(random.randint(10000,99999))

                        proc = subprocess.Popen("php ws.php nombreunico", shell=True, stdout=subprocess.PIPE)
                        ganador_name = str(proc.stdout.read())
                        ganador_name = ganador_name.replace("'", "")


                        printLog("Como es nuevo, le voy a asignar un random: "+ganador_name)
                        


                    printLog("el nombre definitivo asignado es:"+ganador_name)


                    encoding=losencodings[ganador_idx]
                    
                    
                    # printLog("el encoding qe voy a guardar al final para esta imagen es:")
                    # printLog(encoding)
                    # printLog("qe sale de es este ganador_idx:"+str(ganador_idx))
                    # printLog()


                    knownEncodings = []
                    knownNames = []
                    knownPoints = []

                    knownEncodings.append(encoding)
                    knownNames.append(ganador_name)
                    knownPoints.append(primero_punt)

                    if segundo_punt>0:
                        encoding2=losencodings[segundo_k]
                        knownEncodings.append(encoding2)
                        knownNames.append(ganador_name)
                        knownPoints.append(segundo_punt)

                    if tercero_punt>0:
                        encoding3=losencodings[tercero_k]
                        knownEncodings.append(encoding3)
                        knownNames.append(ganador_name)
                        knownPoints.append(tercero_punt)

                    anyade_datos(knownEncodings,knownNames,knownPoints,ganador_name)
                    if not os.path.exists('motor/caras/'+LOCAL_ID+'/'+CAMARA_ID+'/'+ganador_name):
                        os.makedirs('motor/caras/'+LOCAL_ID+'/'+CAMARA_ID+'/'+ganador_name)


                    copyfile(path_imgs+fichero_a_mover, './motor/caras/'+LOCAL_ID+'/'+CAMARA_ID+'/'+ganador_name+'/'+nombre_fichero_final+"_____"+str(count_global)+".jpg") 
                    count_global=count_global+1
                    # printLog("He copiado de aki: "+path_imgs+fichero_a_mover+ " a aki: "+'motor/caras/'+LOCAL_ID+'/'+CAMARA_ID+'/'+ganador_name+'/'+nombre_fichero_final+".jpg")

                else:
                    printLog("Del grupo analizado no habia ni una puta cara")



                jj=0
                # printLog("Voy a eliminar los ficheros procesados ya ")
                for b3 in grupos[i][j]: 
                    # printLog("Borro:"+baterias_ficheros[i][grupos[i][j][jj]])
                    if os.path.isfile(path_imgs+baterias_ficheros[i][grupos[i][j][jj]]):
                        os.remove(path_imgs+baterias_ficheros[i][grupos[i][j][jj]])
                    jj=jj+1


                printLog("#################")    
                printLog()    
                # printLog()    
                # printLog()    
                # printLog()    
            j=j+1    
        i=i+1   


    
    # sigue=False




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

