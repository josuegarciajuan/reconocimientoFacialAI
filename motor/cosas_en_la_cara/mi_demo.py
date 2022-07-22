import cv2  # OpenCV Library

# -----------------------------------------------------------------------------
#       Load and configure Haar Cascade Classifiers
# -----------------------------------------------------------------------------

# location of OpenCV Haar Cascade Classifiers:
baseCascadePath = './models/'


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





"""
"7_2021-11-22_17:33:50.087530.avi_23.47844099998474.jpg"
"7_2021-11-22_17:33:50.087530.avi_9.232777118682861.jpg"
"7_2021-11-22_17:33:50.087530.avi_22.84834885597229.jpg"
"7_2021-11-22_17:33:50.087530.avi_34.568800926208496.jpg"
"7_2021-11-22_17:44:18.479447.avi_2.1983284950256348.jpg"
"7_2021-11-22_17:45:01.267029.avi_1.583559513092041.jpg"
"7_2021-11-22_17:46:56.306935.avi_2.5312178134918213.jpg"
"7_2021-11-22_17:46:56.306935.avi_5.202584981918335.jpg"
"7_2021-11-22_17:47:06.260205.avi_12.270466804504395.jpg"
"7_2021-11-22_18:10:50.919440.avi_53.41225337982178.jpg"
"7_2021-11-22_18:10:50.919440.avi_70.28371667861938.jpg"
"7_2021-11-22_18:14:34.095118.avi_0.3046281337738037.jpg"
"7_2021-11-22_18:34:39.653961.avi_5.521178722381592.jpg"
"""
frame = cv2.imread('../removidas/nopasafiltros/'+"7_2021-11-22_18:34:39.653961.avi_5.521178722381592.jpg")





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
#for (x, y, w, h) in objects:
#    container = cv2.rectangle(frame,(x,y),(x+w,y+h),(255,0,0),2)
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
#for (x, y, w, h) in objects:
#    container = cv2.rectangle(frame,(x,y),(x+w,y+h),(255,0,0),2)
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
#for (x, y, w, h) in objects:
#    container = cv2.rectangle(frame,(x,y),(x+w,y+h),(255,0,0),2)
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
#for (x, y, w, h) in objects:
#    container = cv2.rectangle(frame,(x,y),(x+w,y+h),(255,0,0),2)
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
#for (x, y, w, h) in objects:
#    container = cv2.rectangle(frame,(x,y),(x+w,y+h),(255,0,0),2)
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
#for (x, y, w, h) in objects:
#    container = cv2.rectangle(frame,(x,y),(x+w,y+h),(255,0,0),2)
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
#for (x, y, w, h) in objects:
#    container = cv2.rectangle(frame,(x,y),(x+w,y+h),(255,0,0),2)
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
#for (x, y, w, h) in objects:
#    container = cv2.rectangle(frame,(x,y),(x+w,y+h),(255,0,0),2)
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
#for (x, y, w, h) in objects:
#    container = cv2.rectangle(frame,(x,y),(x+w,y+h),(255,0,0),2)
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
#for (x, y, w, h) in objects:
#    container = cv2.rectangle(frame,(x,y),(x+w,y+h),(255,0,0),2)
####################################################################################################################







cv2.imshow('Video', frame)
cv2.waitKey()
cv2.destroyAllWindows()