import cv2
import dlib
import numpy

import sys

# !/usr/bin/python
# -*- coding: utf-8 -*-

# sys.argv El primero es el nombre del programa, el segundo es la ruta de la imagen
# (la cara se trasplanta a esto y el tercero es la ruta de la imagen) para obtener la cara requerida.


#sys.argv = ["SwapFace.py", "E:/pycharm/Project/head.jpg", "E:/pycharm/Project/face.jpg"]

sys.argv = ["SwapFace.py", "./motor/caras/test2/1_2021-07-14_00:12:26.370305.avi_1.121212.jpg", "./motor/caras/test2/1_2021-07-14_00:12:3.370305.avi_1.121212.jpg"]


PREDICTOR_PATH = "./motor/models/shape_predictor_68_face_landmarks.dat"# Un modelo entrenado se puede llamar directamente aquí
SCALE_FACTOR = 1
FEATHER_AMOUNT = 11

FACE_POINTS = list(range(17, 68))
MOUTH_POINTS = list(range(48, 61))
RIGHT_BROW_POINTS = list(range(17, 22))
LEFT_BROW_POINTS = list(range(22, 27))
RIGHT_EYE_POINTS = list(range(36, 42))
LEFT_EYE_POINTS = list(range(42, 48))
NOSE_POINTS = list(range(27, 35))
JAW_POINTS = list(range(0, 17))

# Points used to line up the images.
ALIGN_POINTS = (LEFT_BROW_POINTS + RIGHT_EYE_POINTS + LEFT_EYE_POINTS +
                RIGHT_BROW_POINTS + NOSE_POINTS + MOUTH_POINTS)

# Points from the second image to overlay on the first. The convex hull of each
# element will be overlaid.
OVERLAY_POINTS = [
    LEFT_EYE_POINTS + RIGHT_EYE_POINTS + LEFT_BROW_POINTS + RIGHT_BROW_POINTS,
    NOSE_POINTS + MOUTH_POINTS,
]

# Amount of blur to use during colour correction, as a fraction of the
# pupillary distance.
COLOUR_CORRECT_BLUR_FRAC = 0.6

#Utilice dlib para extraer signos faciales
detector = dlib.get_frontal_face_detector()
predictor = dlib.shape_predictor(PREDICTOR_PATH)


class TooManyFaces(Exception):
    pass


class NoFaces(Exception):
    pass


def get_landmarks(im):
    rects = detector(im, 1) # Realizar detección de rostros

    if len(rects) > 1:
        raise TooManyFaces # Bajo la condición if, el aumento arroja una excepción, que indica que se detectaron varias caras.
    if len(rects) == 0:
        raise NoFaces

    return numpy.matrix([[p.x, p.y] for p in predictor(im, rects[0]).parts()]) # Realizar extracción de características faciales:


def annotate_landmarks(im, landmarks):
    im = im.copy()
    for idx, point in enumerate(landmarks):
        pos = (point[0, 0], point[0, 1])
        cv2.putText(im, str(idx), pos,
                    fontFace=cv2.FONT_HERSHEY_SCRIPT_SIMPLEX,
                    fontScale=0.4,
                    color=(0, 0, 255))
        cv2.circle(im, pos, 3, color=(0, 255, 255))
    return im

# Fusionar las características de la Figura 2 en la Figura 1
def draw_convex_hull(im, points, color):
    points = cv2.convexHull(points) # Buscando casco convexo
    cv2.fillConvexPoly(im, points, color=color) # Relleno del casco convexo


# La definición de función convencional get_face_mask () es: generar una máscara para una imagen y una matriz de logotipo. La máscara dibujará dos polígonos convexos blancos:
# Uno es el área alrededor de los ojos, y el otro es el área alrededor de la nariz y la boca. Después de eso, el área del borde de la máscara está emplumada 11 píxeles hacia afuera,
# Esto puede ayudar a eliminar las discontinuidades restantes.
def get_face_mask(im, landmarks):
    im = numpy.zeros(im.shape[:2], dtype=numpy.float64) # Tipo de datos personalizado

    for group in OVERLAY_POINTS:
        draw_convex_hull(im,
                         landmarks[group],
                         color=1)

    # array([[[0, 1, 2],
    #         [3, 4, 5]],
    #
    #        [[6, 7, 8],
    #         [9, 10, 11]]])
    #
    # En [61]: arr1.shape # ver forma
    # Out [61]: (2, 2, 3) # Explique que se trata de una matriz 2 * 2 * 3 (matriz), el resultado es una tupla, puede indexar la tupla, que es 0,1,2
    # In[62]: arr1.transpose((1, 0, 2))
    # Out[62]:
    # array([[[0, 1, 2],
    #         [6, 7, 8]],
    #
    #        [[3, 4, 5],
    #         [9, 10, 11]]])
    # Por ejemplo, el índice que comienza con el valor 6 es [1, 0, 0] y se convierte en [0, 1, 0] después de la transformación.

    im = numpy.array([im, im, im]).transpose((1, 2, 0))

    im = (cv2.GaussianBlur(im, (FEATHER_AMOUNT, FEATHER_AMOUNT), 0) > 0) * 1.0
    im = cv2.GaussianBlur(im, (FEATHER_AMOUNT, FEATHER_AMOUNT), 0)

    return im

# Uso de Procrustes Analysis para lograr la alineación de caras
def transformation_from_points(points1, points2): # La entrada es una matriz
    """
    Return an affine transformation [s * R | T] such that:
        sum ||s*R*p1,i + T - p2,i||^2
    is minimized.
    
    '' 'Ahora tenemos dos matrices de signos faciales, cada una de las cuales contiene las coordenadas de un rasgo facial (como las coordenadas de la punta de la nariz en la línea 30).
         Solo necesitamos descubrir cómo rotar, trasladar y escalar todos los puntos del primer vector para que coincidan con los puntos del segundo vector tanto como sea posible.
         Similar,
                 La misma transformación se puede utilizar para superponer la segunda imagen en la primera imagen. Para hacerlo más matemático, establecemos T, sy R, y encontramos el valor mínimo de la siguiente ecuación:  
         Entre ellos, R es una matriz ortogonal de 2x2, s es un escalar, T es un vector bidimensional y pi y qi son las etiquetas de fila y columna de la matriz de signos faciales calculada previamente.
                 Los hechos han demostrado que este tipo de problema puede resolverse mediante el análisis Procrustes convencional: ''
    """
    points1 = points1.astype(numpy.float64) # Convertir matriz de entrada a flotante
    points2 = points2.astype(numpy.float64)

    c1 = numpy.mean(points1, axis=0) # El centroide se calcula aquí
    c2 = numpy.mean(points2, axis=0)
    points1 -= c1
    points2 -= c2

    s1 = numpy.std(points1) # Calcular la desviación estándar
    s2 = numpy.std(points2)
    points1 /= s1 # Divide por desviación estándar, lo que elimina el sesgo de escala
    points2 /= s2

    U, S, Vt = numpy.linalg.svd(points1.T * points2) # Use la descomposición de valores singulares para calcular la parte giratoria.
    R = (U * Vt).T # .T debe ser transpuesto

    return numpy.vstack([numpy.hstack(((s2 / s1) * R,
                                       c2.T - (s2 / s1) * R * c1.T)),
                         numpy.matrix([0., 0., 1.])])


def read_im_and_landmarks(fname): # Leer foto
    # Use la función cv2.imread ()
    # Leer en la imagen. Esta imagen debe estar en la ruta de trabajo de este programa o proporcionar la ruta completa a la función.
    # El segundo parámetro es decirle a la función cómo leer esta imagen.
    # cv2.IMREAD_COLOR: leer en una imagen en color. La transparencia de la imagen será ignorada, este es el parámetro predeterminado.
    # cv2.IMREAD_GRAYSCALE: lee la imagen en modo gris
    #
    # import cv2
    # img = cv2.imread('lena.jpg', 0)
    #
    # PD: llame a opencv, incluso si la ruta de la imagen es incorrecta, OpenCV
    # No se lo recordará, pero cuando utiliza el comando printimg el resultado es Ninguno.
    im = cv2.imread(fname, cv2.IMREAD_COLOR)
    # import cv2
    # image = cv2.imread("D:/shape.bmp")
    # print(image.shape[0])
    # print(image.shape[1])
    # print(image.shape[2])
    # Resultado
    # 300
    # 200
    # 3
    # Entre ellos shape.bmp es una imagen en color con 200 píxeles horizontalmente y 300 píxeles verticalmente
    im = cv2.resize(im, (im.shape[1] * SCALE_FACTOR,
                         im.shape[0] * SCALE_FACTOR))
    s = get_landmarks(im)

    return im, s


def warp_im(im, M, dshape):
    output_im = numpy.zeros(dshape, dtype=im.dtype)
    cv2.warpAffine(im,
                   M[:2],
                   (dshape[1], dshape[0]),
                   dst=output_im,
                   borderMode=cv2.BORDER_TRANSPARENT,
                   flags=cv2.WARP_INVERSE_MAP)
    return output_im

# Los diferentes tonos de piel y la luz entre las dos imágenes provocan discontinuidades en los bordes del área de cobertura. Entonces tratamos de arreglarlo:
def correct_colours(im1, im2, landmarks1):
    # blur_amount se usa para calcular el núcleo gaussiano
    blur_amount = COLOUR_CORRECT_BLUR_FRAC * numpy.linalg.norm(
        numpy.mean(landmarks1[LEFT_EYE_POINTS], axis=0) -
        numpy.mean(landmarks1[RIGHT_EYE_POINTS], axis=0))
    blur_amount = int(blur_amount)
    if blur_amount % 2 == 0:
        blur_amount += 1
    im1_blur = cv2.GaussianBlur(im1, (blur_amount, blur_amount), 0)
    im2_blur = cv2.GaussianBlur(im2, (blur_amount, blur_amount), 0)

    # Para evitar la división por cero, no está claro por qué se multiplica por 128
    im2_blur += (128 * (im2_blur <= 1.0)).astype(im2_blur.dtype)

    return (im2.astype(numpy.float64) * im1_blur.astype(numpy.float64) /
            im2_blur.astype(numpy.float64))


im1, landmarks1 = read_im_and_landmarks(sys.argv[1])
im2, landmarks2 = read_im_and_landmarks(sys.argv[2])

M = transformation_from_points(landmarks1[ALIGN_POINTS],
                               landmarks2[ALIGN_POINTS])

mask = get_face_mask(im2, landmarks2)
warped_mask = warp_im(mask, M, im1.shape)
combined_mask = numpy.max([get_face_mask(im1, landmarks1), warped_mask],
                          axis=0)

warped_im2 = warp_im(im2, M, im1.shape)
warped_corrected_im2 = correct_colours(im1, warped_im2, landmarks1)

output_im = im1 * (1.0 - combined_mask) + warped_corrected_im2 * combined_mask

cv2.imwrite('./motor/output.jpg', output_im)