from imutils import paths
import pickle
import os
import sys
from filelock import FileLock


def printLog(*args, **kwargs):
    print(*args, **kwargs)
    with open('motor/arreglar_diccionario.out','a') as file:
        print(*args, **kwargs, file=file)


LOCAL_ID=sys.argv[1]

knownEncodings = []
knownNames = []
knownPoints=[]
knownIdentificadorunico=[]


printLog('Abrir: /var/www/html/reconocimientoFacial/proyecto_definitivo/motor/bbdd_reconocimiento/'+LOCAL_ID+'/face_enc')

data = pickle.loads(open('/var/www/html/reconocimientoFacial/proyecto_definitivo/motor/bbdd_reconocimiento/'+LOCAL_ID+'/face_enc', "rb").read())
for i in range(0,len(data["encodings"])):
    knownEncodings.append(data["encodings"][i])
    knownPoints.append(data["points"][i])
    knownIdentificadorunico.append(data["identificadoresunicos"][i])
    
    name=data["names"][i]
    #if data["names"][i]==COPIA:
    #	name=ORIGINAL
    knownNames.append(name)





with FileLock('/var/www/html/reconocimientoFacial/proyecto_definitivo/motor/bbdd_reconocimiento/'+LOCAL_ID+'/face_enc'):    
	data = {"encodings": knownEncodings, "names": knownNames, "points": knownPoints, "identificadoresunicos": knownIdentificadorunico}
	f = open('/var/www/html/reconocimientoFacial/proyecto_definitivo/motor/bbdd_reconocimiento/'+LOCAL_ID+'/face_enc', "wb")
	f.write(pickle.dumps(data))
	f.close()
	printLog('anyadidos!')  
