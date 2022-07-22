#from imutils.face_utils import FaceAligner
import argparse
import imutils
import dlib
import cv2

import sys

sys.path.append(".")
from facealigner import FaceAligner


def rect_to_bb(rect):

	x = rect.left()
	y = rect.top()
	w = rect.right() - x
	h = rect.bottom() - y

	# return a tuple of (x, y, w, h)
	return (x, y, w, h)



detector = dlib.get_frontal_face_detector()
predictor = dlib.shape_predictor("../models/shape_predictor_68_face_landmarks.dat")
fa = FaceAligner(predictor, desiredFaceWidth=150)

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
image = cv2.imread('../removidas/cara/'+"1180.jpg")
image = imutils.resize(image, width=150)
gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
cv2.imshow("Input", image)
rects = detector(gray, 2)

print("paso0")

# loop over the face detections
for rect in rects:
	print("paso1")
	# extract the ROI of the *original* face, then align the face
	# using facial landmarks
	(x, y, w, h) = rect_to_bb(rect)
	faceOrig = imutils.resize(image[y:y + h, x:x + w], width=48)
	faceAligned = fa.align(image, gray, rect)
	# display the output images
	cv2.imshow("Original", faceOrig)
	cv2.imshow("Aligned", faceAligned)

	cv2.imwrite('/var/www/html/reconocimientoFacial/proyecto_definitivo/motor/removidas/nopasafiltros/alineada.jpg', faceAligned)


	cv2.waitKey(0)


print("paso2")


"""
python align_faces.py \
	--shape-predictor shape_predictor_68_face_landmarks.dat \
	--image images/example_01.jpg
"""