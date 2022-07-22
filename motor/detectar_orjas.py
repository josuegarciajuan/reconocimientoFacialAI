import cv2
import numpy as np

left_ear_cascade = cv2.CascadeClassifier('./models/haarcascade_mcs_leftear.xml')
right_ear_cascade = cv2.CascadeClassifier('./models/haarcascade_mcs_rightear.xml')

if left_ear_cascade.empty():
  raise IOError('Unable to load the left ear cascade classifier xml file')

if right_ear_cascade.empty():
  raise IOError('Unable to load the right ear cascade classifier xml file')

img = cv2.imread('./removidas/nopasafiltros/'+"7_2021-11-22_17:33:50.087530.avi_23.47844099998474.jpg")

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

gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

left_ear = left_ear_cascade.detectMultiScale(gray, 1.3, 5)
right_ear = right_ear_cascade.detectMultiScale(gray, 1.3, 5)

print("A ver")

for (x,y,w,h) in left_ear:
    cv2.rectangle(img, (x,y), (x+w,y+h), (0,255,0), 3)
    print("Inquierda")

for (x,y,w,h) in right_ear:
    cv2.rectangle(img, (x,y), (x+w,y+h), (255,0,0), 3)
    print("Derecha")

cv2.imshow('Ear Detector', img)
cv2.waitKey()
cv2.destroyAllWindows()


