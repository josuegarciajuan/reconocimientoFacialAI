import cv2, time, pandas
from datetime import datetime
import pysftp
import os
import _thread
import sys

sys.path.append(".")
from fifo import fifo


#os.system('Xvfb :1 -screen 0 1600x1200x16  &')    # create virtual display with size 1600x1200 and 16 bit color. Color can be changed to 24 or 8
#os.environ['DISPLAY']=':1.0'    # tell X clients to use our virtual DISPLAY :1.0



FTP_SERVER=sys.argv[1]
FTP_USER=sys.argv[2]
FTP_PASS=sys.argv[3]
URL_CONEXION=sys.argv[4]
# URL_CONEXION="rtsp://admin:bakcAse4@172.16.51.223:554/cam/realmonitor?channel=1&subtype=0"
LOCAL_ID=sys.argv[5]
CAMARA_ID=sys.argv[6]

segundos_analizar=int(sys.argv[7])  #cuanto mas segundos movs mas largos detecta los peqños los descarta por lo qe influira la sensibiliafda
porcentaje_mov=int(sys.argv[8]) #de este campo puede depender la sensibilidad
#dontCare = 500
dontCare = int(sys.argv[9]) #Area of the detected contour, below this value it's not counted as detected   (tambien influye en la sensibilidad)
#Limit the FPS to 10 (For this task the lower the better)   
#cap.set(cv2.cv.CV_CAP_PROP_FPS, 15)
#FPS = 15
FPS = float(sys.argv[10])
maximo_videos=int(sys.argv[11]) #tiempo en segundos maximo de grabado
#REDIMENSIONFRAME=0.60  #reduce un poco el fram original para no guardar videos tan grandes
REDIMENSIONFRAME=float(sys.argv[12])




def printLog(*args, **kwargs):
    # print(*args, **kwargs)
    
    with open('motor/logs/guarda_movimientosV2_'+CAMARA_ID+'.out','a') as file:
        print(*args, **kwargs, file=file)


def hay_movimiento(the_motion_list):
    num=0
    for m in the_motion_list:
        if m==1:
            num=num+1
    retorno=False        
    if num>=frames_con_movimiento and motion_list[-1]==1:
        retorno=True
    return retorno  


def subir_video(nombre):
    cmd='ftp-upload -h '+FTP_SERVER+' -u '+FTP_USER+' --password '+FTP_PASS+' -d motor/videos/'+LOCAL_ID+'/'+CAMARA_ID+' motor/videos/'+LOCAL_ID+'/'+nombre
    printLog(cmd)
    printLog("\n\n")
    os.system(cmd)
    os.remove('motor/videos/'+LOCAL_ID+'/'+nombre)




frames_a_analizar=int(segundos_analizar*FPS)  #cada X frames es 1 segundo
frames_con_movimiento=round(frames_a_analizar*porcentaje_mov/100)
frames_despues=10 #esto es fijo, graba 1 segundo mas del movimiento recabado
prevFrame = None  #Initialize the first frame in the video stream

cap = cv2.VideoCapture(URL_CONEXION)

cap.set(cv2.CAP_PROP_FPS, FPS)
#counter for the detection
i = 0


# Define the codec and create VideoWriter object
width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
size = (width, height)
fourcc = cv2.VideoWriter_fourcc(*'XVID')



motion_list = [ None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None  ]



grabando=False
parando=False
num_video=1
grabando_primera=False
video_actual=""
last_frames=fifo()
frames_i=0
count_para=0
siguegrabando=False


while(True):
    # Capture frame-by-frame
    ret, frame = cap.read()
    frame_original=frame

    frame = cv2.resize(frame, None, fx=REDIMENSIONFRAME, fy=REDIMENSIONFRAME)


    last_frames.apilar(frame_original)
    frames_i=frames_i+1
    if frames_i==frames_a_analizar:
         last_frames.desapilar()
         frames_i=frames_i-1


    #Blur for better results
    output = cv2.GaussianBlur(frame, (21, 21), 0)

    #If the prevFrame is None, initialize it
    if prevFrame is None:
        prevFrame = output
        continue

    
    #Compute the absolute difference between the current frame and prev frame
    frameDelta = cv2.absdiff(prevFrame, output) 

    prevFrame = output

    #Convert to gray to detect contours
    frameDelta = cv2.cvtColor(frameDelta, cv2.COLOR_BGR2GRAY)
    thresh = cv2.threshold(frameDelta, 21, 255, cv2.THRESH_BINARY)[1]

    #Dilate the thresholded image to fill in holes, then find contours
    #on thresholded image
    thresh = cv2.dilate(thresh, None, iterations=2)

    cnts, hier = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE)

    cnts_sorted = sorted(cnts, key = cv2.contourArea, reverse = True)[:1]

    motion = 0
    #Loop over the contours
    for c in cnts_sorted:
        #If the contour is too small, ignore it
        if cv2.contourArea(c) < dontCare:
            continue

        # compute the bounding box for the contour, draw it on the frame,
        # and update the text
        (x, y, w, h) = cv2.boundingRect(c)
        cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
        i+=1
        #print ('Detected something' + str(i))
        #print ('Area: ' + str(cv2.contourArea(c)))
        # printLog ('-->' + str(cv2.contourArea(c)))

        motion = 1

    
    motion_list.append(motion)
    motion_list = motion_list[-frames_a_analizar:]
    #printLog("Estado actual del movimiento:"+str(motion))




    if hay_movimiento(motion_list) and grabando==False:
        grabando=True
        grabando_primera=True
        printLog ("Detecto movimiento, empiezo a grabar...")

    if not hay_movimiento(motion_list) and grabando:
        parando=True
        printLog ("Ya no hay moviemiento, paro de grabar...")

    if parando:
        if hay_movimiento(motion_list):
            printLog ("Estaba parando pero, sigue habiendo movimiento, así que sigo grabando..!")
            count_para=0
            parando=False




    if grabando_primera:
        grabando_primera=False
        now = str(datetime.now())
        now=now.replace(" ","_");
        video_actual=CAMARA_ID+'_'+now+'.avi'
        out = cv2.VideoWriter('motor/videos/'+LOCAL_ID+'/'+video_actual, fourcc, FPS, size)

        time_inicio = time.time()
        printLog ("Grabando primera...")


        if not siguegrabando: 
            aux=last_frames.obtenerPila()
            for f in aux:
                out.write(f)
            tamano=last_frames.tamano()
            while tamano>0:
                tamano=last_frames.tamano()
                if tamano>0:
                    last_frames.desapilar()



    if grabando:
        printLog ("Grabando...")

        out.write(frame_original)
        time_elapsed = time.time() - time_inicio
        # key = cv2.waitKey(500)
        if time_elapsed>maximo_videos:
            parando=True            
            printLog ("han pasdo mas de "+str(maximo_videos)+" segs, marco pa qe se pare..")
    if parando and grabando:
        count_para=count_para+1
        printLog("Proceso de frenado:"+str(count_para))


    if count_para==frames_despues:
        printLog ("parado de grabar "+str(count_para)+" frames despues y subiendo video:"+video_actual+" ...")
        count_para=0   
        parando=False    
        grabando=False
        out.release()
        #subir_video(video_actual)
        _thread.start_new_thread(subir_video, (video_actual,))
        num_video=num_video+1
        #if motion_list[-1] == 1 and motion_list[-2] == 1 and motion_list[-3] == 1 and motion_list[-4] == 1 and motion_list[-5] == 1 and motion_list[-6] == 0:
        siguegrabando=False

        if hay_movimiento(motion_list):
            grabando=True
            grabando_primera=True
            printLog ("Sigue habiendo movimiento despues de subir el video..")
            siguegrabando=True
        


    # cv2.imshow('Webcam ',frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()