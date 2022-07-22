from imutils import paths
import face_recognition
import pickle
import cv2
import os
from shutil import copyfile
import random

def printLog(*args, **kwargs):
    print(*args, **kwargs)
    # with open('output.out','a') as file:
    #     print(*args, **kwargs, file=file)

imagePaths = list(paths.list_images('./tests3'))
knownEncodings = []
knownNames = []
j=1
for (i, imagePath) in enumerate(imagePaths):
    name_file = imagePath.split(os.path.sep)[-1]
    #name_file = name[0:3]
    name=str(random.randint(1000,9999))

    printLog('Nombre fichero:'+name_file)
    printLog('Nombre random k le asignaria:'+name)

    image = cv2.imread(imagePath)


    # rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    # boxes = face_recognition.face_locations(rgb,model='hog')
    # encodings = face_recognition.face_encodings(rgb, boxes)

    
    boxes = face_recognition.face_locations(image,model='hog')
    encodings = face_recognition.face_encodings(image, boxes)

    if(len(encodings)>0):

        printLog('len encodings:'+str(len(encodings)))

        for encoding in encodings:
            data = pickle.loads(open('face_enc', "rb").read())
            printLog('hay caras en la imagen')

            matches = face_recognition.compare_faces(data["encodings"],encoding,0.55)
            # printLog('Esta cara tiene este numero en el diccionario:'+str(len(matches)))




            face_distances = face_recognition.face_distance(data["encodings"],encoding)

            for fa, face_distance in enumerate(face_distances):
                print("The test image has a distance of {:.2} from known image #{}".format(face_distance, fa)+"-----"+data["names"][fa])
                print("- With a normal cutoff of 0.6, would the test image match the known image? {}".format(face_distance < 0.6))
                print("- With a very strict cutoff of 0.5, would the test image match the known image? {}".format(face_distance < 0.5))
                print()


        

    else:
        printLog('La foto no tiene caras!')

    printLog('-----------------------------------------')    