from imutils import paths
import pickle
import os
import sys
from filelock import FileLock

LOCAL_ID=sys.argv[1]
ORIGINAL=sys.argv[2]
COPIA=sys.argv[3]

def printLog(*args, **kwargs):
    print(*args, **kwargs)
    # with open('../motor/juntar_personas2.out','a') as file:
    #     print(*args, **kwargs, file=file)


knownEncodings = []
knownNames = []
knownPoints=[]
knownIdentificadorunico=[]
knownEnfoques=[]


# printLog("hola")

data = pickle.loads(open('../motor/bbdd_reconocimiento/'+LOCAL_ID+'/face_enc', "rb").read())
for i in range(0,len(data["encodings"])):
    knownEncodings.append(data["encodings"][i])
    knownPoints.append(data["points"][i])
    knownIdentificadorunico.append(data["identificadoresunicos"][i])
    knownEnfoques.append(data["enfoque"][i])
    
    name=data["names"][i]
    if data["names"][i]==COPIA:
    	name=ORIGINAL
    knownNames.append(name)

with FileLock('../motor/bbdd_reconocimiento/'+LOCAL_ID+'/face_enc'):    
	data = {"encodings": knownEncodings, "names": knownNames, "points": knownPoints, "identificadoresunicos": knownIdentificadorunico, "enfoque": knownEnfoques}
	f = open('../motor/bbdd_reconocimiento/'+LOCAL_ID+'/face_enc', "wb")
	f.write(pickle.dumps(data))
	f.close()
	# printLog('anyadidos!')  

