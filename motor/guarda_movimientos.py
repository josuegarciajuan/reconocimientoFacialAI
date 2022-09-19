import cv2, time, pandas
from datetime import datetime
import pysftp
import os
import _thread
import sys
import os

sys.path.append(".")
from fifo import fifo


# python3.7 motor/guarda_movimientos.py camaras.vps.webdock.io testuser prueba123 'rtsp://admin:bakcAse4@172.16.51.52:554/cam/realmonitor?channel=1&subtype=0' 1 1 KszrR2H1snGs
# python3.7 motor/guarda_movimientos.py camaras.vps.webdock.io testuser prueba123 'rtsp://admin:bakcAse4@nouesmalt.duckdns.org:779/cam/realmonitor?channel=1&subtype=0' 1 1 KszrR2H1snGs



FTP_SERVER=sys.argv[1]
FTP_USER=sys.argv[2]
FTP_PASS=sys.argv[3]
URL_CONEXION=sys.argv[4]
# URL_CONEXION='rtsp://admin:bakcAse4@nouesmalt.duckdns.org:778/cam/realmonitor?channel=1&subtype=0'
LOCAL_ID=sys.argv[5]
CAMARA_ID=sys.argv[6]


def printLog(*args, **kwargs):
    print(*args, **kwargs)
    
    with open('motor/guarda_movimientos_'+CAMARA_ID+'.out','a') as file:
        print(*args, **kwargs, file=file)
    


# Converting gray scale image to GaussianBlur
var1=21
var2=21

# If change in between static background and
# current frame is greater than 30 it will show white color(255)
#var3=42
var3=42
var4=255

# if cv2.contourArea(contour) < 10000:
#var5=1500
#->var5=1200
var5=800

maximo_videos=60


#CUANTOS FRAMES PARA QUE HAYA MOVIMIENTO
#->frames_a_analizar=20
frames_a_analizar=30
#->frames_con_movimiento=16
frames_con_movimiento=24


#CUANTOS FRAMES DESPUES SIGO GRAMABANDO
#->FRAMES_DESPUES=100
FRAMES_DESPUES=100

#CUANTOS FRAMES ANTES DEQUE HAYA MOVIMIENTO GRAMABANDO
#->frames_guardados=100
frames_guardados=120


def hay_movimiento(the_motion_list):
    num=0
    for m in the_motion_list:
        if m==1:
            num=num+1
    retorno=False        
    if num>=frames_con_movimiento and motion_list[-1]==1:
        retorno=True
    return retorno  

printLog("FTP_SERVER"+FTP_SERVER)
printLog("FTP_USER"+FTP_USER)
printLog("FTP_PASS"+FTP_PASS)
printLog("URL_CONEXION"+URL_CONEXION)
printLog("LOCAL_ID"+LOCAL_ID)
printLog("CAMARA_ID"+CAMARA_ID)

def subir_video(nombre):
    cnopts = pysftp.CnOpts()
    cnopts.hostkeys = None   
    #myHostname = "217.61.112.100"
    #myUsername = "testuser"
    #myPassword = "prueba123"
    myHostname = FTP_SERVER
    myUsername = FTP_USER
    myPassword = FTP_PASS

    with pysftp.Connection(host=myHostname, username=myUsername, password=myPassword, cnopts=cnopts) as sftp:
        print ("Connection succesfully stablished ... ")
        sftp.put('motor/videos/'+LOCAL_ID+'/'+nombre,'motor/videos/'+LOCAL_ID+'/'+CAMARA_ID+'/'+nombre)
        sftp.close()
    os.remove('motor/videos/'+LOCAL_ID+'/'+nombre)




# Assigning our static_back to None
static_back = None

# List when any moving object appear
# motion_list = [ None, None ]
motion_list = [ None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None  ]


# Time of movement
time_r = []

# Initializing DataFrame, one column is start
# time and other column is end time
df = pandas.DataFrame(columns = ["Start", "End"])

# Capturing video
#video = cv2.VideoCapture(0)
#video = cv2.VideoCapture('rtsp://admin:bakcAse4@172.16.51.52:554/cam/realmonitor?channel=1&subtype=0')
video = cv2.VideoCapture(URL_CONEXION)


# Define the codec and create VideoWriter object
width = int(video.get(cv2.CAP_PROP_FRAME_WIDTH) + 0.5)
height = int(video.get(cv2.CAP_PROP_FRAME_HEIGHT) + 0.5)
size = (width, height)
fourcc = cv2.VideoWriter_fourcc(*'XVID')



grabando=False
parando=False
num_video=1
grabando_primera=False
video_actual=""

last_frames=fifo()

frames_i=0

count_para=0
# Infinite while loop to treat stack of image as video
while True:
    # Reading frame(image) from video
    check, frame = video.read()
    frame_original=frame


    last_frames.apilar(frame_original)
    frames_i=frames_i+1
    if frames_i==frames_guardados:
         last_frames.desapilar()
         frames_i=frames_i-1



    #frame = cv2.resize(frame, None, fx=0.25, fy=0.25)
    frame = cv2.resize(frame, None, fx=0.60, fy=0.60)

    # Initializing motion = 0(no motion)
    motion = 0

    # Converting color image to gray_scale image
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    # Converting gray scale image to GaussianBlur
    # so that change can be find easily
    #gray = cv2.GaussianBlur(gray, (21, 21), 0)
    gray = cv2.GaussianBlur(gray, (var1, var2), 0)

    # In first iteration we assign the value
    # of static_back to our first frame
    if static_back is None:
        static_back = gray
        continue

    # Difference between static background
    # and current frame(which is GaussianBlur)
    diff_frame = cv2.absdiff(static_back, gray)

    # If change in between static background and
    # current frame is greater than 30 it will show white color(255)
    # cambio
    # thresh_frame = cv2.threshold(diff_frame, 30, 255, cv2.THRESH_BINARY)[1]
    thresh_frame = cv2.threshold(diff_frame, var3, var4, cv2.THRESH_BINARY)[1]
    # thresh_frame = cv2.dilate(thresh_frame, None, iterations = 2)
    thresh_frame = cv2.dilate(thresh_frame, None, iterations = 1)  # esto por lo qe e visto en el ejemplo de la xica, es para poner mas intenso el blanco despues 
    # de kitarle el fondo, osea ella pone iterations 5 para qe el blanco salga muxo mas intenso
    


    # Finding contour of moving object
    cnts,_ = cv2.findContours(thresh_frame.copy(),cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    for contour in cnts:
        # cambio 
        # if cv2.contourArea(contour) < 10000:
        if cv2.contourArea(contour) < var5:
            continue
        motion = 1

        (x, y, w, h) = cv2.boundingRect(contour)
        # making green rectangle arround the moving object
        cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 3)

    # Appending status of motion
    motion_list.append(motion)

    # motion_list = motion_list[-2:]
    motion_list = motion_list[-frames_a_analizar:]


    printLog("Estado actual del movimiento:"+str(motion))


    #Para saber si hay movimiento, de los ultimos 10, 8 han de tener movimiento

    #Para saber si ya no hay movimiento, delos ultimos 10, 8 no han de tener movimiento



    # Appending Start time of motion
    #if motion_list[-1] == 1 and motion_list[-2] == 1 and motion_list[-3] == 1 and motion_list[-4] == 1 and motion_list[-5] == 1 and motion_list[-6] == 0 and grabando==False:
    if hay_movimiento(motion_list) and grabando==False:
        time_r.append(datetime.now())
        grabando=True
        grabando_primera=True
        printLog ("Detecto movimiento, empiezo a grabar...")

    # Appending End time of motion
    # if motion_list[-1] == 0 and motion_list[-2] == 1:
    #if motion_list[-1] == 0 and motion_list[-2] == 0 and motion_list[-3] == 0 and motion_list[-4] == 0 and motion_list[-5] == 0 and motion_list[-6] == 0 and motion_list[-7] == 0 and motion_list[-8] == 0 and motion_list[-9] == 0 and motion_list[-10] == 0 and motion_list[-11] == 0 and motion_list[-12] == 0 and motion_list[-13] == 0 and motion_list[-14] == 0 and motion_list[-15] == 0 and motion_list[-16] == 0 and motion_list[-17] == 0 and motion_list[-18] == 0 and motion_list[-19] == 0 and motion_list[-20] == 0 and motion_list[-21] == 0 and motion_list[-22] == 0 and motion_list[-23] == 0 and motion_list[-24] == 0 and motion_list[-25] == 0 and motion_list[-26] == 0 and motion_list[-27] == 0 and motion_list[-28] == 0 and motion_list[-29] == 0 and motion_list[-30] == 0 and motion_list[-31] == 0 and motion_list[-32] == 0 and motion_list[-33] == 0 and motion_list[-34] == 0 and motion_list[-35] == 0 and motion_list[-36] == 0 and motion_list[-37] == 0 and motion_list[-38] == 0 and motion_list[-39] == 0 and motion_list[-40] == 0 and motion_list[-41] == 0 and motion_list[-42] == 0 and motion_list[-43] == 0 and motion_list[-44] == 0 and motion_list[-45] == 0 and motion_list[-46] == 0 and motion_list[-47] == 0 and motion_list[-48] == 0 and motion_list[-49] == 0 and motion_list[-50] == 1:
    if not hay_movimiento(motion_list) and grabando:
        time_r.append(datetime.now())
        parando=True
        # printLog ("Ya no hay moviemiento, paro de grabar...")

    if grabando_primera:
        grabando_primera=False
        now = str(datetime.now())
        now=now.replace(" ","_");
        video_actual=CAMARA_ID+'_'+now+'.avi'
        #out = cv2.VideoWriter('videos/'+video_actual, fourcc, 20.0, size)
        out = cv2.VideoWriter('motor/videos/'+LOCAL_ID+'/'+video_actual, fourcc, 10.0, size)
        # out = cv2.VideoWriter('/home/testuser/motor/videos/'+LOCAL_ID+'/'+CAMARA_ID+'/'+video_actual, fourcc, 15.0, size)
        #out = cv2.VideoWriter('/home/testuser/motor/videos/'+LOCAL_ID+'/'+CAMARA_ID+'/'+video_actual, fourcc, 10.0, size)

        time_inicio = time.time()
        printLog ("Grabando primera...")


        aux=last_frames.obtenerPila()
        for f in aux:
            out.write(f)
        tamano=last_frames.tamano()
        while tamano>0:
            tamano=last_frames.tamano()
            if tamano>0:
                last_frames.desapilar()






    if grabando:
        out.write(frame_original)
        time_elapsed = time.time() - time_inicio
        # key = cv2.waitKey(500)
        if time_elapsed>maximo_videos:
            parando=True            
            #printLog ("han pasdo mas de "+str(maximo_videos)+" segs, marco pa qe se pare..")
    if parando and grabando:
        count_para=count_para+1


    if count_para==FRAMES_DESPUES:
        printLog ("parado de grabar "+str(count_para)+" frames despues y subiendo video:"+video_actual+" ...")
        count_para=0   
        parando=False    
        grabando=False
        out.release()
        # #subir_video(video_actual)
        _thread.start_new_thread(subir_video, (video_actual,))
        num_video=num_video+1
        #if motion_list[-1] == 1 and motion_list[-2] == 1 and motion_list[-3] == 1 and motion_list[-4] == 1 and motion_list[-5] == 1 and motion_list[-6] == 0:
        
        if hay_movimiento(motion_list):
            time_r.append(datetime.now())
            grabando=True
            grabando_primera=True
            printLog ("Sigue habiendo movimiento despues de subir el video..")
        

    # Displaying image in gray_scale
    # cv2.imshow("Gray Frame", gray)

    # Displaying the difference in currentframe to
    # the staticframe(very first_frame)
    # cv2.imshow("Difference Frame", diff_frame)

    # Displaying the black and white image in which if
    # intensity difference greater than 30 it will appear white
    # cv2.imshow("Threshold Frame", thresh_frame)

    # Displaying color frame with contour of motion of object
    # cv2.imshow("Color Frame", frame)

    #->key = cv2.waitKey(10)

    key = cv2.waitKey(80)
    # if q entered whole process will stop
    if key == ord('q'):
        # if something is movingthen it append the end time of movement
        if motion == 1:
            time_r.append(datetime.now())



# Appending time of motion in DataFrame
for i in range(0, len(time_r), 2):
    df = df.append({"Start":time_r[i], "End":time_r[i + 1]}, ignore_index = True)

# Creating a CSV file in which time of movements will be saved
#df.to_csv("Time_of_movements.csv")


video.release()

# Destroying all the windows
cv2.destroyAllWindows()
