#https://www.adrianbulat.com/face-alignment
#https://github.com/1adrianb/face-alignment

import face_alignment
from skimage import io
from imutils import paths
import os
import cv2



def printLog(*args, **kwargs):
    print(*args, **kwargs)
    
    with open('./out.out','a') as file:
    # with open('motor/procesa_fotos_def_XX.out','a') as file:
      print(*args, **kwargs, file=file)

fa = face_alignment.FaceAlignment(face_alignment.LandmarksType._2D, flip_input=False, device='cpu')



def analiza(path_imgs):

    printLog(path_imgs)

    imagePaths = list(paths.list_images(path_imgs))


    for (i, imagePath) in enumerate(imagePaths):
        name_file = imagePath.split(os.path.sep)[-1]
        printLog('analizando:'+name_file)

        input = io.imread(imagePath)
        preds = fa.get_landmarks(input)
        for (x) in preds:
            #print("paso"+str(x)+":"+str(y))
            #printLog(str(x))
            #printLog("----")
            printLog("x1,y1 izq: "+str(x[36][0])+","+str(x[36][1]))
            printLog("x2,y2 izq: "+str(x[39][0])+","+str(x[39][1]))
            printLog("x1,y1 der: "+str(x[42][0])+","+str(x[42][1]))
            printLog("x2,y2 der: "+str(x[45][0])+","+str(x[45][1]))
            largoizq=x[39][0]-x[36][0]
            largoder=x[45][0]-x[42][0]
            printLog("largoizq:"+str(largoizq))
            printLog("largoder:"+str(largoder))
            diff=abs(largoizq-largoder)
            printLog("diferencia ojos largo:"+str(diff))

            largoizq=x[39][1]-x[36][1]
            largoder=x[45][1]-x[42][1]
            printLog("altoizq:"+str(largoizq))
            printLog("altoder:"+str(largoder))
            diff=abs(largoizq-largoder)
            printLog("diferencia ojos alto:"+str(diff))


        printLog()
        printLog()    



#analiza('../removidas/seguro_frente/')
#printLog("----------------")
#analiza('../removidas/seguro_canto/')
#printLog("----------------")
#analiza('../removidas/seguro_perfil/')
#printLog("----------------")



def draw_points(imagePath):
    printLog(imagePath)

    frame = cv2.imread(imagePath)

    input = io.imread(imagePath)
    preds = fa.get_landmarks(input)


    for (x) in preds:

        i=0
        while i<=67:
            printLog("(x["+str(i)+"][0],x["+str(i)+"][1]):("+str(x[i][0])+","+str(x[i][1])+")")    
            container = cv2.rectangle(frame,(int(x[i][0]),int(x[i][1])),(int(x[i][0])+1,int(x[i][1])+1),(255,0,0),2)
            i=i+1

        printLog()
        printLog()    

    cv2.imshow('test', frame)
    cv2.waitKey()




def draw_eyes(imagePath):
    printLog(imagePath)

    frame = cv2.imread(imagePath)

    input = io.imread(imagePath)
    preds = fa.get_landmarks(input)


    for (x) in preds:


        printLog("x1,y1 izq: "+str(x[36][0])+","+str(x[36][1]))
        printLog("x2,y2 izq: "+str(x[39][0])+","+str(x[39][1]))
        printLog("x1,y1 der: "+str(x[42][0])+","+str(x[42][1]))
        printLog("x2,y2 der: "+str(x[45][0])+","+str(x[45][1]))
        largoizq=x[39][0]-x[36][0]
        largoder=x[45][0]-x[42][0]
        printLog("largoizq:"+str(largoizq))
        printLog("largoder:"+str(largoder))
        diff=abs(largoizq-largoder)
        printLog("diferencia ojos largo:"+str(diff))

        largoizq=x[39][1]-x[36][1]
        largoder=x[45][1]-x[42][1]
        printLog("altoizq:"+str(largoizq))
        printLog("altoder:"+str(largoder))
        diff=abs(largoizq-largoder)
        printLog("diferencia ojos alto:"+str(diff))

        container = cv2.rectangle(frame,(int(x[36][0]),int(x[36][1])),(int(x[36][0])+1,int(x[36][1])+1),(255,0,0),2)
        container = cv2.rectangle(frame,(int(x[39][0]),int(x[39][1])),(int(x[39][0])+1,int(x[39][1])+1),(255,0,0),2)
        container = cv2.rectangle(frame,(int(x[42][0]),int(x[42][1])),(int(x[42][0])+1,int(x[42][1])+1),(255,0,0),2)
        container = cv2.rectangle(frame,(int(x[45][0]),int(x[45][1])),(int(x[45][0])+1,int(x[45][1])+1),(255,0,0),2)

        printLog()
        printLog()    

    cv2.imshow('test', frame)
    cv2.waitKey()




def draw_picoscontorno(imagePath):
    printLog(imagePath)

    frame = cv2.imread(imagePath)

    input = io.imread(imagePath)
    preds = fa.get_landmarks(input)


    for (x) in preds:


        printLog("x1,y1 izq: "+str(x[0][0])+","+str(x[0][1]))
        printLog("x1,y1 der: "+str(x[16][0])+","+str(x[16][1]))

        printLog("x1,y1 piconariz: "+str(x[30][0])+","+str(x[30][1]))
        printLog("x1,y1 barbilla: "+str(x[8][0])+","+str(x[8][1]))
        

        container = cv2.rectangle(frame,(int(x[0][0]),int(x[0][1])),(int(x[0][0])+1,int(x[0][1])+1),(255,0,0),2)
        container = cv2.rectangle(frame,(int(x[16][0]),int(x[16][1])),(int(x[16][0])+1,int(x[16][1])+1),(255,0,0),2)

        container = cv2.rectangle(frame,(int(x[30][0]),int(x[30][1])),(int(x[30][0])+1,int(x[30][1])+1),(255,255,0),2)

        container = cv2.rectangle(frame,(int(x[8][0]),int(x[8][1])),(int(x[8][0])+1,int(x[8][1])+1),(255,0,255),2)


        #container = cv2.rectangle(frame,(int(77),int(110)),(int(77)+1,int(110)+1),(255,255,255),2)
        #container = cv2.rectangle(frame,(int(67),int(110)),(int(67)+1,int(110)+1),(255,255,255),2)
        #container = cv2.rectangle(frame,(int(87),int(110)),(int(87)+1,int(110)+1),(255,255,255),2)

        printLog()
        printLog()    

    cv2.imshow('test', frame)
    cv2.waitKey()



#printLog("----------------")
#printLog("----------------")
#printLog("----------------")
#draw_eyes("../removidas/seguro_perfil/104.jpg")
#draw_points("../removidas/seguro_perfil/99.jpg")


#draw_picoscontorno("../removidas/cara/1_2021-09-01_13:16:45.569419.avi_0.394054651260376.jpg") #no pilla bien los punyos
#draw_picoscontorno("../removidas/cara/1_2021-09-01_13:16:45.569419.avi_0.34273266792297363.jpg")
#draw_picoscontorno("../removidas/cara/1_2021-09-01_13:16:45.569419.avi_0.41242361068725586.jpg")
#draw_picoscontorno("../removidas/cara/1_2021-09-01_13:16:45.569419.avi_1.499715805053711.jpg") #no pilla bien los punyos
#draw_picoscontorno("../removidas/cara/6.jpg") #no pilla bien los puntos
#draw_picoscontorno("../removidas/cara/89.jpg")


#draw_picoscontorno("../removidas/perfil/1_2021-09-01_13:16:28.763353.avi_0.30152273178100586.jpg")
#draw_picoscontorno("../removidas/perfil/1_2021-09-01_13:21:00.343304.avi_0.33136701583862305.jpg")
#draw_picoscontorno("../removidas/perfil/06.jpg") #no pilla bien los punyos
#draw_picoscontorno("../removidas/perfil/045.jpg")  #barbilla y nariz muy juntos por qe pilla desde arrinba acia abajo
#draw_picoscontorno("../removidas/perfil/00148.jpg") #2 caras en la foto, no pilla bien los untos
#draw_picoscontorno("../removidas/perfil/206.jpg")
#draw_picoscontorno("../removidas/perfil/691.jpg") #mirando acia abajo pero si es frontal pero muxa dif en la x entre barilla y toxa
#draw_picoscontorno("../removidas/perfil/853.jpg") #mirando acia abajo pero si es frontal pero muxa dif en la x entre barilla y toxa
#draw_picoscontorno("../removidas/perfil/886.jpg") #mirando acia abajo pero si es frontal pero muxa dif en la x entre barilla y toxa
#draw_picoscontorno("../removidas/perfil/1950.jpg")  #tiene la barbilla mu peqeña y le da muxa dif en las X
#draw_picoscontorno("../removidas/perfil/2023.jpg")  #mucxa dif en las x 

#def clasifica()
