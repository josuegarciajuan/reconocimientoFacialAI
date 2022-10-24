
from imutils import paths
import face_recognition
import pickle
import cv2
import os
from shutil import copyfile


#get paths of each file in folder named Images
#Images here contains my data(folders of various persons)
imagePaths = list(paths.list_images('./inicial'))
knownEncodings = []
knownNames = []
knownPoints = []
knownIdentificadorunico=[]
knownEnfoques=[]

i=1
# loop over the image paths
for (i, imagePath) in enumerate(imagePaths):
    # extract the person name from the image path
    name = imagePath.split(os.path.sep)[-1]
    print("nombre imagen:" + name)
    image = cv2.imread(imagePath)
    rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    #Use Face_recognition to locate faces
    boxes = face_recognition.face_locations(rgb,model='hog')
    # compute the facial embedding for the face
    encodings = face_recognition.face_encodings(rgb, boxes)
    # loop over the encodings
    for encoding in encodings:
        if not os.path.exists('caras/inicial'):
            os.makedirs('caras/inicial')
        k = str(i)    
        copyfile(imagePath, './caras/inicial/'+name)
        i=i+1
        knownEncodings.append(encoding)
        knownNames.append(name)
        knownPoints.append(0.5)
        knownIdentificadorunico.append(1)
        knownEnfoques.append(100)

#save emcodings along with their names in dictionary data
data = {"encodings": knownEncodings, "names": knownNames, "points": knownPoints, "identificadoresunicos": knownIdentificadorunico, "enfoque": knownEnfoques }
#use pickle to save data into a file for later use
f = open("bbdd_reconocimiento/1/face_enc", "wb")
#f = open("face_enc", "wb")
f.write(pickle.dumps(data))
f.close()

