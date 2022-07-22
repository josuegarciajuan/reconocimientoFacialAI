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


image = cv2.imread('../removidas/seguro_canto/'+"1344.jpg")

detector = dlib.get_frontal_face_detector()
gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
rects = detector(gray, 2)


cv2.imshow("Original", image)


print("paso1")
for rect in rects:
    print("paso2")
    (x, y, w, h) = rect_to_bb(rect)
    recorte = imutils.resize(image[y:y + h, x:x + w], width=150)
    cv2.imshow("Recorte", recorte)

    


cv2.waitKey(0)