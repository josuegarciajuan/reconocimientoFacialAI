from imutils import paths


def printLog(*args, **kwargs):
    print(*args, **kwargs)
    
    with open('pruebas.out','a') as file:
      print(*args, **kwargs, file=file)


printLog("83")