from imutils import face_utils
import numpy as np
import imutils
import dlib
import cv2

import os
import matplotlib.pyplot as plt








#si no detecta cara ta,mbioen la considero lateral
#si la encuientra pero el anxo de sus ojos es la diferencia de los 2 es > 10 p.e. es lateral


def prueba3():

    PREDICTOR_PATH = "models/shape_predictor_68_face_landmarks.dat"
    detector = dlib.get_frontal_face_detector()
    predictor = dlib.shape_predictor(PREDICTOR_PATH)

    # load the input image, resize it, and convert it to grayscale
    image = plt.imread('caras/frontal/1_2021-07-14_00:19:3.370305.avi_1.121212.jpg')
    orig = image
    image = imutils.resize(image, width=500)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # detect faces in the grayscale image
    rects = detector(gray, 1)

    # loop over the face detections
    for (i, rect) in enumerate(rects):
      # determine the facial landmarks for the face region, then
      # convert the facial landmark (x, y)-coordinates to a NumPy
      # array
      shape = predictor(gray, rect)
      shape = face_utils.shape_to_np(shape)

      # convert dlib's rectangle to a OpenCV-style bounding box
      # [i.e., (x, y, w, h)], then draw the face bounding box
      (x, y, w, h) = face_utils.rect_to_bb(rect)
      cv2.rectangle(image, (x, y), (x + w, y + h), (0, 255, 0), 2)

      # show the face number
      cv2.putText(image, "Face #{}".format(i + 1), (x - 10, y - 10),
        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

      # loop over the (x, y)-coordinates for the facial landmarks
      # and draw them on the image
      pos=0
      x1=0
      x2=0
      x3=0
      x4=0
      for (x, y) in shape:
        
        # print("pos:"+str(pos))
        esojo=False
        if pos==36:
          print("x,y (37)"+str(x)+","+str(y))
          esojo=True
          x1=x
        if pos==39:
          print("x,y (40)"+str(x)+","+str(y))
          esojo=True
          x2=x
        if pos==42:
          print("x,y (43)"+str(x)+","+str(y))
          esojo=True
          x3=x
        if pos==45:
          print("x,y (46)"+str(x)+","+str(y))
          esojo=True
          x4=x

        if not esojo:
          cv2.circle(image, (x, y), 1, (0, 0, 255), -1)
        else:
          cv2.circle(image, (x, y), 1, (255, 0, 0), -1)  

        pos=pos+1

      ancho=x2-x1
      print("ancho ojo 1:"+str(ancho))
      ancho=x4-x3
      print("ancho ojo 2:"+str(ancho))


    # show the output image with the face detections + facial landmarks
    plt.subplot(121)
    plt.imshow(orig)
    plt.xticks([])
    plt.yticks([])
    plt.title("Intput")

    plt.subplot(122)
    plt.imshow(image)
    plt.xticks([])
    plt.yticks([])
    plt.title("Output")

    #fname = "results/"+"result_" + args["image"][1]

    #plt.savefig(fname)
    plt.show()


prueba3()

exit()


















PREDICTOR_PATH = "models/shape_predictor_68_face_landmarks.dat"
 
 
# Inicializa el detector de cara de dlib (HOG-based) y luego crea
# El factor predictivo de la marca facial
detector = dlib.get_frontal_face_detector()
predictor = dlib.shape_predictor(PREDICTOR_PATH)
 
# Cargar la imagen de entrada, redimensiona y la convierte a escala de grises
image = cv2.imread('caras/frontal/1_2021-07-14_02:10:49.370305.avi_1.121212.jpg')
image = imutils.resize(image, width=500)
gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
 
# Detectar caras en la imagen en escala de grises
rects = detector(gray, 1)
 
# ciclo sobre las detecciones de la cara
for (i, rect) in enumerate(rects):
# Determinar las marcas faciales para la región de la cara, luego
# Convertir el punto de referencia (x, y) - coordina a un array NumPy
  shape = predictor(gray, rect)
  shape = face_utils.shape_to_np(shape)
 
  ojos=0
  # ciclo sobre las partes de la cara individualmente
  for (name, (i, j)) in face_utils.FACIAL_LANDMARKS_IDXS.items():
  # Clonar la imagen original para que podamos dibujar en ella, entonces
  # Mostrar el nombre de la parte de la cara en la imagen
    clone = image.copy()
    cv2.putText(clone, name, (10, 90), cv2.FONT_HERSHEY_SIMPLEX,0.9, (0, 0, 255), 2)
    if name=="right_eye":
      ojos=ojos+1
    if name=="left_eye":
      ojos=ojos+1


  if ojos==2:
    print("es cara")




# Sobre el subconjunto de marcas faciales, dibuja la
# Parte de la cara específica
    for (x, y) in shape[i:j]:
      cv2.circle(clone, (x, y), 2, (53, 104, 45), -1)
      print("paso i,j:"+str(i)+",,"+str(j))
      print("paso x,y"+str(x)+",,"+str(y))
      print()

      
    

 
# Extraer el ROI de la región de la cara como una imagen separada
    (x, y, w, h) = cv2.boundingRect(np.array([shape[i:j]]))
    roi = image[y:y + h, x:x + w]
    roi = imutils.resize(roi, width=250, inter=cv2.INTER_CUBIC)


 
    # muestra la parte particular de la cara
    cv2.imshow("ROI", roi)
    cv2.imshow("Image", clone)
    cv2.waitKey(0)
 
  # Visualizar todas las marcas faciales con una superposición transparente
  output = face_utils.visualize_facial_landmarks(image, shape)
  cv2.imshow("Image", output)
  cv2.waitKey(0)
  





















