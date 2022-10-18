import cv2
import os
import sys

local_id=sys.argv[1]
posicion=sys.argv[2]


def printLog(*args, **kwargs):
    print(*args, **kwargs)
    
    with open('../motor/posicion_cara.out','a') as file:
        print(*args, **kwargs, file=file)


imagen="cosas_en_la_cara/pruebas/prueba02.jpg"


baseCascadePath = './cosas_en_la_cara/models/'


CascadeFilePath1 = baseCascadePath + 'haarcascade_frontalface_default.xml'
CascadeFilePath2 = baseCascadePath + 'haarcascade_mcs_eyepair_big.xml'
CascadeFilePath3 = baseCascadePath + 'haarcascade_mcs_eyepair_small.xml'
CascadeFilePath4 = baseCascadePath + 'haarcascade_mcs_leftear.xml'
CascadeFilePath5 = baseCascadePath + 'haarcascade_mcs_lefteye.xml'
CascadeFilePath6 = baseCascadePath + 'haarcascade_mcs_lefteye_alt.xml'
CascadeFilePath7 = baseCascadePath + 'haarcascade_mcs_mouth.xml'
CascadeFilePath8 = baseCascadePath + 'haarcascade_mcs_nose.xml'
CascadeFilePath9 = baseCascadePath + 'haarcascade_mcs_rightear.xml'
CascadeFilePath10 = baseCascadePath + 'haarcascade_mcs_righteye.xml'
CascadeFilePath11 = baseCascadePath + 'haarcascade_mcs_righteye_alt.xml'
CascadeFilePath12 = baseCascadePath + 'haarcascade_mcs_upperbody.xml'



Cascade1 = cv2.CascadeClassifier(CascadeFilePath1)
Cascade2 = cv2.CascadeClassifier(CascadeFilePath2)
Cascade3 = cv2.CascadeClassifier(CascadeFilePath3)
Cascade4 = cv2.CascadeClassifier(CascadeFilePath4)
Cascade5 = cv2.CascadeClassifier(CascadeFilePath5)
#Cascade6 = cv2.CascadeClassifier(CascadeFilePath6)
Cascade7 = cv2.CascadeClassifier(CascadeFilePath7)
Cascade8 = cv2.CascadeClassifier(CascadeFilePath8)
Cascade9 = cv2.CascadeClassifier(CascadeFilePath9)
Cascade10 = cv2.CascadeClassifier(CascadeFilePath10)
#Cascade11 = cv2.CascadeClassifier(CascadeFilePath11)
Cascade12 = cv2.CascadeClassifier(CascadeFilePath12)


frame = cv2.imread(imagen)
gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)


####################################################################################################################
objects = Cascade1.detectMultiScale(
    gray,
    scaleFactor=1.1,
    minNeighbors=5,
    minSize=(30, 30),
    flags=cv2.CASCADE_SCALE_IMAGE
)
print("Found {0} frontal face!".format(len(objects)))
pos=0
for (x, y, w, h) in objects:
    if pos==0:
        pos=pos+1
        container = cv2.rectangle(frame,(x,y),(x+w,y+h),(255,0,0),2)
####################################################################################################################


####################################################################################################################
objects = Cascade2.detectMultiScale(
    gray,
    scaleFactor=1.1,
    minNeighbors=5,
    minSize=(30, 30),
    flags=cv2.CASCADE_SCALE_IMAGE
)
print("Found {0} pares de ojos grandes!".format(len(objects)))
pos=0
for (x, y, w, h) in objects:
    if pos==0:
        pos=pos+1
        container = cv2.rectangle(frame,(x,y),(x+w,y+h),(255,0,0),2)
####################################################################################################################

####################################################################################################################
objects = Cascade3.detectMultiScale(
    gray,
    scaleFactor=1.1,
    minNeighbors=5,
    minSize=(30, 30),
    flags=cv2.CASCADE_SCALE_IMAGE
)
print("Found {0} pares de ojos pequños!".format(len(objects)))
pos=0
for (x, y, w, h) in objects:
    if pos==0:
        pos=pos+1
        container = cv2.rectangle(frame,(x,y),(x+w,y+h),(255,0,0),2)
####################################################################################################################

####################################################################################################################
objects = Cascade4.detectMultiScale(
    gray,
    scaleFactor=1.1,
    minNeighbors=5,
    minSize=(30, 30),
    flags=cv2.CASCADE_SCALE_IMAGE
)
print("Found {0} oreja izquierda!".format(len(objects)))
pos=0
for (x, y, w, h) in objects:
    if pos==0:
        pos=pos+1
        container = cv2.rectangle(frame,(x,y),(x+w,y+h),(255,0,0),2)
####################################################################################################################

####################################################################################################################
objects = Cascade5.detectMultiScale(
    gray,
    scaleFactor=1.1,
    minNeighbors=5,
    minSize=(30, 30),
    flags=cv2.CASCADE_SCALE_IMAGE
)
print("Found {0} ojo izq!".format(len(objects)))
pos=0
for (x, y, w, h) in objects:
    if pos==0:
        pos=pos+1
        container = cv2.rectangle(frame,(x,y),(x+w,y+h),(255,0,0),2)
####################################################################################################################
"""
####################################################################################################################
objects = Cascade6.detectMultiScale(
    gray,
    scaleFactor=1.1,
    minNeighbors=5,
    minSize=(30, 30),
    flags=cv2.CASCADE_SCALE_IMAGE
)
print("Found {0} ojo izq 2!".format(len(objects)))
#for (x, y, w, h) in objects:
#    container = cv2.rectangle(frame,(x,y),(x+w,y+h),(255,0,0),2)
####################################################################################################################
"""
####################################################################################################################
objects = Cascade7.detectMultiScale(
    gray,
    scaleFactor=1.1,
    minNeighbors=5,
    minSize=(30, 30),
    flags=cv2.CASCADE_SCALE_IMAGE
)
print("Found {0} boca!".format(len(objects)))
pos=0
for (x, y, w, h) in objects:
    if pos==0:
        pos=pos+1
        container = cv2.rectangle(frame,(x,y),(x+w,y+h),(255,0,0),2)
####################################################################################################################

####################################################################################################################
objects = Cascade8.detectMultiScale(
    gray,
    scaleFactor=1.1,
    minNeighbors=5,
    minSize=(30, 30),
    flags=cv2.CASCADE_SCALE_IMAGE
)
print("Found {0} nariz!".format(len(objects)))
pos=0
for (x, y, w, h) in objects:
    if pos==0:
        pos=pos+1
        container = cv2.rectangle(frame,(x,y),(x+w,y+h),(255,0,0),2)
####################################################################################################################

####################################################################################################################
objects = Cascade9.detectMultiScale(
    gray,
    scaleFactor=1.1,
    minNeighbors=5,
    minSize=(30, 30),
    flags=cv2.CASCADE_SCALE_IMAGE
)
print("Found {0} oreja derexa!".format(len(objects)))
pos=0
for (x, y, w, h) in objects:
    if pos==0:
        pos=pos+1
        container = cv2.rectangle(frame,(x,y),(x+w,y+h),(255,0,0),2)
####################################################################################################################

####################################################################################################################
objects = Cascade10.detectMultiScale(
    gray,
    scaleFactor=1.1,
    minNeighbors=5,
    minSize=(30, 30),
    flags=cv2.CASCADE_SCALE_IMAGE
)
print("Found {0} ojo derexo!".format(len(objects)))
pos=0
for (x, y, w, h) in objects:
    if pos==0:
        pos=pos+1
        container = cv2.rectangle(frame,(x,y),(x+w,y+h),(255,0,0),2)
####################################################################################################################
"""
####################################################################################################################
objects = Cascade11.detectMultiScale(
    gray,
    scaleFactor=1.1,
    minNeighbors=5,
    minSize=(30, 30),
    flags=cv2.CASCADE_SCALE_IMAGE
)
print("Found {0} ojo derexo 2!".format(len(objects)))
#for (x, y, w, h) in objects:
#    container = cv2.rectangle(frame,(x,y),(x+w,y+h),(255,0,0),2)
####################################################################################################################
"""
####################################################################################################################
objects = Cascade12.detectMultiScale(
    gray,
    scaleFactor=1.1,
    minNeighbors=5,
    minSize=(30, 30),
    flags=cv2.CASCADE_SCALE_IMAGE
)
print("Found {0} upperbody!".format(len(objects)))
pos=0
for (x, y, w, h) in objects:
    if pos==0:
        pos=pos+1
        container = cv2.rectangle(frame,(x,y),(x+w,y+h),(255,0,0),2)
####################################################################################################################



cv2.imshow('Video', frame)
cv2.waitKey()
cv2.destroyAllWindows()