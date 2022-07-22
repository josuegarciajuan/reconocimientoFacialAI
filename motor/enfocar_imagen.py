import cv2 as cv
import numpy as np

#def unsharp_mask(image, kernel_size=(7, 7), sigma=4.0, amount=1.5, threshold=0):
def enfocar_imagen(image, kernel_size=(7, 7), sigma=2.0, amount=1.5, threshold=0):
    """Return a sharpened version of the image, using an unsharp mask."""
    blurred = cv.GaussianBlur(image, kernel_size, sigma)
    sharpened = float(amount + 1) * image - float(amount) * blurred
    sharpened = np.maximum(sharpened, np.zeros(sharpened.shape))
    sharpened = np.minimum(sharpened, 255 * np.ones(sharpened.shape))
    sharpened = sharpened.round().astype(np.uint8)
    if threshold > 0:
        low_contrast_mask = np.absolute(image - blurred) < threshold
        np.copyto(sharpened, image, where=low_contrast_mask)
    return sharpened


image = cv.imread('/var/www/html/reconocimientoFacial/proyecto_definitivo/admin/caras_procesadas/1.jpg')
sharpened_image = enfocar_imagen(image)
cv.imwrite('/var/www/html/reconocimientoFacial/proyecto_definitivo/admin/caras_procesadas/1.jpg', sharpened_image)