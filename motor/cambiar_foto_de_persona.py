
from imutils import paths
import face_recognition
import pickle
import cv2
import os
from shutil import copyfile
import sys


LOCAL_ID=sys.argv[1]
foto_identificador_unico=sys.argv[2]
persona_cod_interno=sys.argv[3]


knownEncodings=[]
knownNames=[]
knownPoints=[]
knownIdentificadorunico=[]
knownEnfoques=[]


data = pickle.loads(open("/var/www/html/reconocimientoFacial/proyecto_definitivo/motor/bbdd_reconocimiento/"+LOCAL_ID+"/face_enc", "rb").read())


for ff in range(0,len(data["encodings"])):
    if foto_identificador_unico==data["identificadoresunicos"][ff]:
        name=persona_cod_interno
    else:
        name=data["names"][ff]

    knownEncodings.append(data["encodings"][ff])
    knownNames.append(name)
    knownPoints.append(data["points"][ff])
    knownIdentificadorunico.append(data["identificadoresunicos"][ff])
    knownEnfoques.append(data["enfoque"][ff])

"""
data = {"encodings": knownEncodings, "names": knownNames, "points": knownPoints, "identificadoresunicos": knownIdentificadorunico}
f = open("/var/www/html/reconocimientoFacial/proyecto_definitivo/motor/bbdd_reconocimiento/"+LOCAL_ID+"/face_enc", "wb")
f.write(pickle.dumps(data))
f.close()
"""

with FileLock('../motor/bbdd_reconocimiento/'+LOCAL_ID+'/face_enc'):    
	data = {"encodings": knownEncodings, "names": knownNames, "points": knownNames, "identificadoresunicos": knownIdentificadorunico, "enfoque": knownEnfoques}
	f = open('../motor/bbdd_reconocimiento/'+LOCAL_ID+'/face_enc', "wb")
	f.write(pickle.dumps(data))
	f.close()
	# printLog('anyadidos!')  


