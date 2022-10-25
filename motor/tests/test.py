import cv2
import numpy as np
import time
import os
import pickle
import _thread
from imutils import paths
import sys
import subprocess

from filelock import FileLock


import imutils

from datetime import datetime, timedelta


sys.path.append(".")

fecha=sys.argv[1]



def printLog(*args, **kwargs):
    print(*args, **kwargs)
    
    with open('log.out','a') as file:
       print(*args, **kwargs, file=file)




aux = str(datetime.now())
lastsix=aux[-6:]
now=fecha+"."+lastsix

printLog("->"+now+"<-")