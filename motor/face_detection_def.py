from imutils import paths
import face_recognition
import pickle
import cv2
import os
from shutil import copyfile
import random


def anyade_datos(knownEncodings1,knownNames1):
    
    # print('voy a anaydir datos al fichero')

    data = pickle.loads(open('face_enc', "rb").read())
    for ff in range(0,len(data["encodings"])):
        knownEncodings1.append(data["encodings"][ff])
        knownNames1.append(data["names"][ff])
        # printLog('Este ya estaba:'+data["names"][i])

    data = {"encodings": knownEncodings1, "names": knownNames1}
    f = open('face_enc', "wb")
    f.write(pickle.dumps(data))
    f.close()
    # print('anyadidos!')   



imagePaths = list(paths.list_images('./caras_procesadas'))
knownEncodings = []
knownNames = []

# umbral=0.63
umbral=0.61
umbral_junto=0.65

j=1
for (i, imagePath) in enumerate(imagePaths):
    name_file = imagePath.split(os.path.sep)[-1]
    #name_file = name[0:3]
    name=str(random.randint(10000,99999))

    print('Nombre fichero:'+name_file)
    

    image = cv2.imread(imagePath)


    rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    #boxes = face_recognition.face_locations(rgb,model='hog')
    boxes = face_recognition.face_locations(rgb,model='cnn')
    encodings = face_recognition.face_encodings(rgb, boxes)

    
    # boxes = face_recognition.face_locations(image,model='hog')
    # encodings = face_recognition.face_encodings(image, boxes)

    veces={}
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


    if(len(encodings)>0):

        print('len encodings:'+str(len(encodings)))

        for encoding in encodings:
            data = pickle.loads(open('face_enc', "rb").read())
            # print('hay caras en la imagen')

            # matches = face_recognition.compare_faces(data["encodings"],encoding,0.55)
            # print('Esta cara tiene este numero en el diccionario:'+str(len(matches)))

            # print("aki anyadiria el encoding al fichero encoding")


            face_distances = face_recognition.face_distance(data["encodings"],encoding)
         
            for fa, face_distance in enumerate(face_distances):
                # print("The test image has a distance of {:.2} from known image #{}".format(face_distance, fa)+"-----"+data["names"][fa])
                # print("- With a normal cutoff of 0.6, would the test image match the known image? {}".format(face_distance < 0.6))
                # print("- With a very strict cutoff of 0.5, would the test image match the known image? {}".format(face_distance < 0.5))


                if data["names"][fa] in puntuaciones:
                    # print("paso1")
                    veces[data["names"][fa]]=veces[data["names"][fa]]+1
                    puntuaciones[data["names"][fa]]=puntuaciones[data["names"][fa]]+face_distance

                else:
                    # print("paso2:"+str(face_distance))
                    puntuaciones[data["names"][fa]] = face_distance
                    veces[data["names"][fa]] = 1

                if face_distance<umbral:
                    print("supera el umbral con este nombre:"+data["names"][fa])
                    print("puntuacion:"+str(face_distance))



                    if data["names"][fa] in puntuaciones_supera:
                        # print("paso1")
                        veces_supera[data["names"][fa]]=veces_supera[data["names"][fa]]+1
                        puntuaciones_supera[data["names"][fa]]=puntuaciones_supera[data["names"][fa]]+face_distance

                    else:
                        # print("paso2:"+str(face_distance))
                        puntuaciones_supera[data["names"][fa]] = face_distance
                        veces_supera[data["names"][fa]] = 1



                    if not data["names"][fa] in ganadores:
                        print("Como no estaba en ganadores, lo anyado")    
                        ganadores.append(data["names"][fa])
                print()

            



            print("Voy a ver el ganador")
            for g in ganadores:
                media=puntuaciones[g]/veces[g]
                media_supera=puntuaciones_supera[g]/veces_supera[g]
                definitivo=media/veces[g]
                print("el nombre:"+g+", tienes esta media:"+str(media)+" y aparece estas veces:"+str(veces[g]))
                print("el nombre:"+g+", tienes esta media_supera:"+str(media_supera)+" y supera estas veces:"+str(veces_supera[g]))
                print("ademas la puntuacion definitiva es (media/veces):"+str(definitivo))

                if media_supera<umbral and media<umbral_junto:
                    print("la media supera el umbral")
                    if media<puntuacion:
                        print("voy a actualizar el segundo con estos datos:"+ganador+" - "+str(puntuacion)+" - "+str(veces_ganador)+" - "+str(veces_supera_ganador))

                        segundo=ganador
                        puntuacion_segundo=puntuacion
                        veces_segundo=veces_ganador
                        veces_supera_segundo=veces_supera_ganador
                        

                        print("Es menor qe la puntuacion actual y lo guardo como ganador")
                        ganador = g
                        puntuacion = media
                        veces_ganador=veces[g]
                        veces_supera_ganador=veces_supera[g]




        
            
            if puntuacion==999:
                name=str(random.randint(1000,9999))
                print("No hay ganador es cara nueva, le asigno este nombre:"+name)
            else:
                print("ganador:"+ganador+" - puntuacion:"+str(puntuacion)+", veces:"+str(veces_ganador)+", veces_supera:"+str(veces_supera_ganador))    
                print("segundo:"+segundo+" - puntuacion:"+str(puntuacion_segundo)+", veces:"+str(veces_segundo)+", veces_supera:"+str(veces_supera_segundo))        
                name=ganador
                if abs(puntuacion-puntuacion_segundo)<0.05:
                    print("de diferenciuan de muy poco")
                    aux_ganador=veces_ganador/veces_supera_ganador
                    aux_segundo=veces_segundo/veces_supera_segundo
                    print("tasa de supero ganador"+str(aux_ganador))
                    print("tasa de supero segundo"+str(aux_segundo))

                    if aux_segundo>aux_ganador:
                        print("como el segundo tiene mas veces")
                        name=segundo
                print("ganador definitivo:"+name)

                
                

            knownEncodings = []
            knownNames = []
            knownEncodings.append(encoding)
            knownNames.append(name)
            anyade_datos(knownEncodings,knownNames)

            if not os.path.exists('tests2/'+name):
                os.makedirs('tests2/'+name)
                # printLog('creo el directorio:'+name)


            copyfile(imagePath, './tests2/'+name+'/'+name_file) 



    else:
        print('La foto no tiene caras!')

    

    print('-----------------------------------------')    




    

