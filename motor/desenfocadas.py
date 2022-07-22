
# import the necessary packages
from imutils import paths
import argparse
import cv2
import os
from shutil import copyfile

UMBRAL_BRILLO=1000


def printLog(*args, **kwargs):
    print(*args, **kwargs)
    # with open('motor/desenfocadas.out','a') as file:
    #     print(*args, **kwargs, file=file)


def variance_of_laplacian(image):
    # compute the Laplacian of the image and then return the focus
    # measure, which is simply the variance of the Laplacian
    return cv2.Laplacian(image, cv2.CV_64F).var()
 


def comprueba_desenfocada1(): 
    # construct the argument parse and parse the arguments
    ap = argparse.ArgumentParser()
    ap.add_argument("-i", "--images", required=True,
    help="path to input directory of images")
    # ap.add_argument("-t", "--threshold", type=float, default=600.0,
    ap.add_argument("-t", "--threshold", type=float, default=1000.0,
    help="focus measures that fall below this value will be considered 'blurry'")
    args = vars(ap.parse_args())

    i=0
    # loop over the input images
    for imagePath in paths.list_images(args["images"]):
        # load the image, convert it to grayscale, and compute the
        # focus measure of the image using the Variance of Laplacian
        # method
        image = cv2.imread(imagePath)
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        fm = variance_of_laplacian(gray)
        text = "Not Blurry"
     
        # if the focus measure is less than the supplied threshold,
        # then the image should be considered "blurry"
        if fm < args["threshold"]:
            text = "Blurry"
            print("la imnagen "+imagePath+" es "+text+" - "+("{}: {:.2f}".format(text, fm)))


        

        # show the image
        # cv2.putText(image, "{}: {:.2f}".format(text, fm), (10, 30),
        # cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 3)
        # cv2.imshow("Image", image)
        # key = cv2.waitKey(0)



def comprueba_enfocada2(imagePath):

    enfocada=False

    image = cv2.imread(imagePath)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    fm = variance_of_laplacian(gray)

    printLog("el fm: "+str(fm))

    if fm < UMBRAL_BRILLO:
        enfocada=True

    return enfocada
        

path_imgs="motor/caras/test2"
imagePaths = list(paths.list_images(path_imgs))

for (i, imagePath) in enumerate(imagePaths):
    name_file = imagePath.split(os.path.sep)[-1]

    printLog("Analizar fichero:"+imagePath)
    if comprueba_enfocada2(imagePath):
        printLog('ENFOCADA')
        copyfile(imagePath, 'motor/caras/enfocadas/'+name_file)
    else:
        printLog('DESENFOCADA')
        copyfile(imagePath, 'motor/caras/desenfocadas2/'+name_file)

    printLog()