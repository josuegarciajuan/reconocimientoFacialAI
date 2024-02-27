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
#4_2024-01-30_15:50:57.284152.avi


def printLog(*args, **kwargs):
    print(*args, **kwargs)
    
    with open('motor/logs/guarda_movimientosV2_'+CAMARA_ID+'.out','a') as file:
        print(*args, **kwargs, file=file)


def hay_movimiento(the_motion_list):
    num=0
    for m in the_motion_list:
        if m==1:
            num=num+1
    retorno=False        
    printLog("dentro de hay_movimiento, numero de frames q ha habido mov:"+str(num)+"<- y para considerarse este es el limite(frames_con_movimiento):("+str(frames_con_movimiento)+")")
    # if num>=frames_con_movimiento and motion_list[-1]==1:
    if num>=frames_con_movimiento:
        retorno=True
        printLog("Si hay movimiento si")
    return retorno  


def subir_video(nombre):
    cmd='ftp-upload -h '+FTP_SERVER+' -u '+FTP_USER+' --password '+FTP_PASS+' -d motor/videos/'+LOCAL_ID+'/'+CAMARA_ID+' motor/videos/'+LOCAL_ID+'/'+nombre
    printLog(cmd)
    printLog("\n\n")
    os.system(cmd)
    os.remove('motor/videos/'+LOCAL_ID+'/'+nombre)
    printLog('Removido: motor/videos/'+LOCAL_ID+'/'+nombre)


def video_last_seconds(last_frames_param, tiempo_espera_fps_param, cv2_param, video_actual_param):
    printLog("dentro del hilo video_last_seconds voy a volcarl os ultimos frames")
    cfi=0
    aux=last_frames_param.obtenerPila()
    for f in aux:
        out.write(f)
        cv2_param.waitKey(tiempo_espera_fps_param)
        printLog("volcado de frame numero:"+str(cfi))
        cfi=cfi+1
    printLog("desde aqui dentro llamo a subir el video")    
    subir_video(video_actual)    


CAMARA_ID=99
printLog("REVISION DE argv")
printLog("argv[1]:"+str(sys.argv[1])+"<-")
printLog("argv[2]:"+str(sys.argv[2])+"<-")
printLog("argv[3]:"+str(sys.argv[3])+"<-")
printLog("argv[4]:"+str(sys.argv[4])+"<-")
printLog("argv[5]:"+str(sys.argv[5])+"<-")
printLog("argv[6]:"+str(sys.argv[6])+"<-")
printLog("argv[7]:"+str(sys.argv[7])+"<-")
printLog("argv[8]:"+str(sys.argv[8])+"<-")
printLog("argv[9]:"+str(sys.argv[9])+"<-")
printLog("argv[10]:"+str(sys.argv[10])+"<-")
printLog("argv[11]:"+str(sys.argv[11])+"<-")
printLog("argv[12]:"+str(sys.argv[12])+"<-")

exit(1)


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

SENSIBILIDAD=int(sys.argv[13]) #CUANTO MAS BAJO menos sensible

tiempo_espera_fps=int(1000/FPS)   # en 1000 ms / numero Fotogramas por segundo  =>  tiempo espera entre fotogramas









frames_a_analizar=int(segundos_analizar*FPS)  #cada X frames es 1 segundo
frames_con_movimiento=round(frames_a_analizar*porcentaje_mov/100)
frames_despues=FPS*3 #graba 2 segundo mas del movimiento recabado
prevFrame = None  #Initialize the first frame in the video stream


printLog("frames_a_analizar:"+str(frames_a_analizar))
printLog("frames_con_movimiento:"+str(frames_con_movimiento))

cap = cv2.VideoCapture(URL_CONEXION)
#cap.set(cv2.CAP_PROP_FPS, FPS)
#counter for the detection

i = 0

# Define the codec and create VideoWriter object
width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
size = (width, height)
fourcc = cv2.VideoWriter_fourcc(*'XVID')

motion_list = [ None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None   ]

grabando=False
parando=False
num_video=1
grabando_primera=False
video_actual=""
last_frames=fifo()
frames_i=0
count_para=0
siguegrabando=False
count_sensibilidad=0


while(True):
    cv2.waitKey(tiempo_espera_fps)

    try:
        ret, frame = cap.read()
        frame_original=frame
        frame = cv2.resize(frame, None, fx=REDIMENSIONFRAME, fy=REDIMENSIONFRAME)
    except Exception as e:
        printLog("excepcion conyo al redimnensionar frame")
        printLog(str(e))


    #Blur for better results
    output = cv2.GaussianBlur(frame, (21, 21), 0)


    #de cada cuantos frames cojo uno
    count_sensibilidad=count_sensibilidad+1
    if count_sensibilidad==SENSIBILIDAD:
        prevFrame = output
        count_sensibilidad=0


        #tratamiento del buffer de los últimos frames_a_analizar 
        last_frames.apilar(frame_original)
        frames_i=frames_i+1
        if frames_i==frames_a_analizar:
             last_frames.desapilar()
             frames_i=frames_i-1


        #If the prevFrame is None, initialize it
        if prevFrame is None:
            prevFrame = output
            continue


        #Compute the absolute difference between the current frame and prev frame
        frameDelta = cv2.absdiff(prevFrame, output) 


        #Convert to gray to detect contours
        frameDelta = cv2.cvtColor(frameDelta, cv2.COLOR_BGR2GRAY)
        thresh = cv2.threshold(frameDelta, 21, 255, cv2.THRESH_BINARY)[1]

        #Dilate the thresholded image to fill in holes, then find contours
        #on thresholded image
        thresh = cv2.dilate(thresh, None, iterations=2)
        cnts, hier = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
        cnts_sorted = sorted(cnts, key = cv2.contourArea, reverse = True)[:1]


        #comprobar si ha habido movimiento
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
            printLog ('Detected something' + str(i))
            #print ('Area: ' + str(cv2.contourArea(c)))
            # printLog ('-->' + str(cv2.contourArea(c)))

            motion = 1


        motion_list.append(motion)
        motion_list = motion_list[-frames_a_analizar:]
        printLog("Estado actual del movimiento:"+str(motion))


        if hay_movimiento(motion_list) and grabando==False:
            grabando=True
            grabando_primera=True
            printLog ("Detecto movimiento, empiezo a grabar...")

        if not hay_movimiento(motion_list) and grabando:
            parando=True
            printLog ("Ya no hay moviemiento, paro de grabar...")

        if parando:
            printLog ("estoy parando!")
            if hay_movimiento(motion_list):
                printLog ("Estaba parando pero, sigue habiendo movimiento, así que sigo grabando..!")
                count_para=0
                parando=False




        if grabando_primera:
            printLog ("Grabando primera...")

            #creo el video que se va a ir generando
            grabando_primera=False
            now = str(datetime.now())
            now=now.replace(" ","_");
            video_actual=CAMARA_ID+'_'+now+'.avi'
            out = cv2.VideoWriter('motor/videos/'+LOCAL_ID+'/'+video_actual, fourcc, FPS, size)
            time_inicio = time.time()
            printLog ("Se empieza a generar el siguiente video:"+video_actual)
            



            if not siguegrabando: 
                printLog ("finalmente, no sigo grabando, los frames que tenía en la pila, los anyado al final del video en un nuevo hilo")
                _thread.start_new_thread(video_last_seconds, (last_frames, tiempo_espera_fps, cv2, video_actual))


                printLog ("mientas se completa el video en otro hilo, vacio la pila")
                tamano=last_frames.tamano()
                while tamano>0:
                    tamano=last_frames.tamano()
                    if tamano>0:
                        last_frames.desapilar()
            else:
                printLog("viene de que se acaba de para un video, y acaba de reanudarse otro por que detectó mas movimiento")



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
            printLog ("se quiere parar de grabar "+str(count_para)+" frames despues y subiendo video:"+video_actual+" ...")
            count_para=0   
            parando=False    
            grabando=False
            out.release()
            #subir_video(video_actual)
            #_thread.start_new_thread(subir_video, (video_actual,))
            num_video=num_video+1
            #if motion_list[-1] == 1 and motion_list[-2] == 1 and motion_list[-3] == 1 and motion_list[-4] == 1 and motion_list[-5] == 1 and motion_list[-6] == 0:
            printLog("Se marca siguegrabando como false para que pase a volcar los ultimos frames del video")
            siguegrabando=False

            if hay_movimiento(motion_list):
                printLog ("Sigue habiendo movimiento, lo marco para que cree otro video y siga grabando..")
                grabando=True
                grabando_primera=True
                siguegrabando=True



    cv2.imshow('Webcam ',frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()