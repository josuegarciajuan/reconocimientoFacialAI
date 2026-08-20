import cv2, time
from datetime import datetime
import os
import sys

sys.path.append(".")
from fifo import fifo

# Nuevo algoritmo de captura/almacenaje (core/video.py): MP4 H.264 por streaming,
# sin AVI intermedio. El orquestador archiva_video.py lo mueve a videos_archivo/
# y genera la miniatura. FTP legacy ya no se usa (el vídeo se queda local).
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from motor.core.video import H264VideoWriter, VideoConfig  # noqa: E402
from motor.core.env import get_int  # noqa: E402
from motor.core.motion import MotionConfig, MotionDetector  # noqa: E402

#os.system('Xvfb :1 -screen 0 1600x1200x16  &')    # create virtual display with size 1600x1200 and 16 bit color. Color can be changed to 24 or 8
#os.environ['DISPLAY']=':1.0'    # tell X clients to use our virtual DISPLAY :1.0
#4_2024-01-30_15:50:57.284152.avi



#python3.7 motor/guarda_movimientosV3.py 1 1 2 60 220 22 60 0.6 1 45.148.29.34 testuser prueba123 'rtsp://admin:bakcAse4@172.16.51.223/cam/realmonitor?channel=1&subtype=0'
#python3.7 motor/guarda_movimientosV3.py 1 1 2 60 220 22 60 0.6 1 45.148.29.34 testuser prueba123 'rtsp://admin:bakcAse4@93.176.162.71:902/cam/realmonitor?channel=1&subtype=0'


# Log por frame (DEBUG): desactivado por defecto. Los prints por frame saturaban
# CPU y llenaban el .out sin límite (llegó a 1,4 GB). Activar con RF_DEBUG_FRAMES=1
# SOLO para depurar; en producción debe quedar a 0.
DEBUG_FRAMES = os.environ.get("RF_DEBUG_FRAMES", "0") == "1"


def printLog(*args, **kwargs):
    print(*args, **kwargs)
    
    with open('motor/logs/guarda_movimientosV2_'+CAMARA_ID+'.out','a') as file:
        print(*args, **kwargs, file=file)



LOCAL_ID=sys.argv[1]
CAMARA_ID=sys.argv[2]
# Truncar el log de esta cámara al arrancar: evita que el .out crezca sin límite
# entre reinicios del worker (capturador.php lo recicla cada N minutos).
try:
    with open('motor/logs/guarda_movimientosV2_'+CAMARA_ID+'.out','w') as _f:
        pass
except Exception:
    pass
# Mismo criterio para el stderr de ffmpeg (motor/logs/ffmpeg_<cam>.log):
# conserva solo la última ventana del worker, suficiente para diagnóstico.
try:
    with open('motor/logs/ffmpeg_'+CAMARA_ID+'.log','w') as _f:
        pass
except Exception:
    pass
segundos_analizar=int(sys.argv[3])  #cuanto mas segundos movs mas largos detecta los peqños los descarta por lo qe influira la sensibiliafda
porcentaje_mov=int(sys.argv[4]) #de este campo puede depender la sensibilidad
dontCare = int(sys.argv[5]) #Area of the detected contour, below this value it's not counted as detected   (tambien influye en la sensibilidad)
FPS = float(sys.argv[6])
maximo_videos=int(sys.argv[7]) #tiempo en segundos maximo de grabado
REDIMENSIONFRAME=float(sys.argv[8])
SENSIBILIDAD=int(sys.argv[9]) #analizar 1 de cada N frames. MAS ALTO = se analizan MENOS frames
                              #= MENOS sensible y MENOS CPU (la ventana efectiva pasa a
                              #segundos_analizar x N). Con 1 se analizan todos (default).

# Orden de argv (capturador.php): 1-9 como arriba, 10=seg_antes, 11=seg_despues,
# 12=FTP_SERVER, 13=FTP_USER, 14=FTP_PASS, 15=URL_CONEXION (Jos_Thread añade un
# identificador de 12 chars al final, se ignora). Fallback a la posición legacy 13
# para invocaciones antiguas con 13 args.
SEG_ANTES = float(sys.argv[10]) if len(sys.argv) > 10 else 2.0
SEG_DESPUES = float(sys.argv[11]) if len(sys.argv) > 11 else 2.0
FTP_SERVER = sys.argv[12] if len(sys.argv) > 12 else "localhost"  # legacy, sin uso
FTP_USER = sys.argv[13] if len(sys.argv) > 13 else "-"
FTP_PASS = sys.argv[14] if len(sys.argv) > 14 else "-"
URL_CONEXION = sys.argv[15] if len(sys.argv) > 15 else (sys.argv[13] if len(sys.argv) > 13 else "")

# Umbrales globales del análisis (antes hardcodeados 21/21/2). Se leen de .env
# (RF_MOV_*); si faltan, se usan estos defaults = valores legacy (sin cambio de
# comportamiento). CRF: calidad prioritaria -> 20 (no 26: a 10 fps y caras
# pequeñas, 26 degrada el detalle que alimenta SR/GFPGAN). Sobreducible con
# RF_VIDEO_CRF en .env.
THRESHOLD = get_int(None, "RF_MOV_THRESHOLD", 21)
BLUR = get_int(None, "RF_MOV_BLUR", 21)
DILATE = get_int(None, "RF_MOV_DILATE", 2)
CRF = get_int(None, "RF_VIDEO_CRF", 20)

printLog("seg_antes=" + str(SEG_ANTES) + " seg_despues=" + str(SEG_DESPUES))
printLog("url=" + URL_CONEXION)

tiempo_espera_fps=int(1000/FPS)   # en 1000 ms / numero Fotogramas por segundo  =>  tiempo espera entre fotogramas
cfg_mov = MotionConfig(segundos_analizar=segundos_analizar,
                       porcentaje_mov=porcentaje_mov,
                       dontCare=dontCare,
                       fps=int(FPS),
                       sensibilidad=SENSIBILIDAD,
                       threshold=THRESHOLD, blur=BLUR, dilate=DILATE)
frames_a_analizar = cfg_mov.frames_a_analizar      # tamaño del buffer de decisión
frames_con_movimiento = cfg_mov.frames_con_movimiento  # nº de frames con mov para disparar
detector = MotionDetector(cfg_mov)
frames_antes=int(SEG_ANTES*FPS)    # pre-roll: frames previos al movimiento que se vuelcan al inicio
frames_despues=int(SEG_DESPUES*FPS) # post-roll: frames posteriores al movimiento


printLog("frames_a_analizar:"+str(frames_a_analizar))
printLog("frames_con_movimiento:"+str(frames_con_movimiento))

cap = cv2.VideoCapture(URL_CONEXION)
#cap.set(cv2.CAP_PROP_FPS, FPS)
#counter for the detection

i = 0

# Tamaño de captura (resolución original, sin el resize de análisis).
# Lectura defensiva: en RTSP, CAP_PROP_FRAME_WIDTH/HEIGHT pueden devolver 0
# antes del primer frame; se completa con el primer frame leído (así la
# grabación usa SIEMPRE la resolución real máxima del stream).
width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
size = (width, height) if width > 0 and height > 0 else None


grabando=False
parando=False
haymovimiento=False
num_video=1
grabando_primera=False
video_actual=""
last_frames=fifo()
frames_i=0
count_para=0
siguegrabando=False
count_sensibilidad=0
writer=None   # H264VideoWriter activo (MP4 H.264 directo)


while(True):
    # headless (opencv-python-headless): cv2.waitKey no está disponible -> time.sleep
    time.sleep(tiempo_espera_fps/1000.0)

    try:
        ret, frame = cap.read()
        if not ret or frame is None:
            continue
        frame_original = frame
        # primera lectura: si CAP_PROP devolvió 0, fijar el tamaño real del stream
        if size is None:
            h, w = frame_original.shape[:2]
            size = (w, h)
        frame = cv2.resize(frame, None, fx=REDIMENSIONFRAME, fy=REDIMENSIONFRAME)
    except Exception as e:
        printLog("excepcion conyo al redimnensionar frame")
        printLog(str(e))


    #de cada cuantos frames cojo uno
    count_sensibilidad=count_sensibilidad+1
    if count_sensibilidad==SENSIBILIDAD:
        count_sensibilidad=0

        #tratamiento del buffer de los últimos frames_antes (pre-roll)
        last_frames.apilar(frame_original)
        frames_i=frames_i+1
        if frames_i==frames_antes:
             last_frames.desapilar()
             frames_i=frames_i-1

        # Análisis de movimiento (motor/core/motion.py): absdiff + umbral +
        # contorno máximo. Devuelve (motion, hay); motion es None si este frame
        # no se analizó (primer frame o gate de sensibilidad). El blur se aplica
        # SOLO cuando se analiza (saturar CPU en todos los frames no aportaba).
        motion, haymovimiento_nuevo = detector.process(frame)
        if motion is not None:
            haymovimiento = haymovimiento_nuevo
        if DEBUG_FRAMES:
            printLog("Estado actual del movimiento:"+str(motion)+" haymovimiento:"+str(haymovimiento))

        if haymovimiento and grabando==False:
            grabando=True
            grabando_primera=True
            printLog ("Detecto movimiento, empiezo a grabar...")

        if not haymovimiento and grabando:
            parando=True
            printLog ("Ya no hay moviemiento, paro de grabar...")

        if parando:
            printLog ("estoy parando!")
            if detector.hay_ahora():
                printLog ("Estaba parando pero, sigue habiendo movimiento, así que sigo grabando..!")
                count_para=0
                parando=False


        if grabando_primera:
            printLog ("Grabando primera...")

            #creo el video MP4 H.264 que se va a ir generando
            grabando_primera=False
            now = str(datetime.now())
            now=now.replace(" ","_");
            video_actual=CAMARA_ID+'_'+now+'.mp4'
            # Publicación atómica (fix moov-race): se escribe a `video_actual.tmp`
            # y SOLO se renombra a .mp4 cuando ffmpeg cierra correctamente (moov
            # escrito). Así detector.php nunca lanza archiva/procesa sobre un MP4
            # a medio escribir (que lee 0 frames y falla el archivado).
            video_tmp = video_actual + '.tmp'
            # Fase 4c: layout con subdirectorio de cámara (motor/videos/<local>/<cam>/)
            os.makedirs('motor/videos/'+LOCAL_ID+'/'+CAMARA_ID, exist_ok=True)
            writer = H264VideoWriter('motor/videos/'+LOCAL_ID+'/'+CAMARA_ID+'/'+video_tmp,
                                     size, int(FPS), VideoConfig(crf=CRF),
                                     stderr_path='motor/logs/ffmpeg_'+CAMARA_ID+'.log')
            time_inicio = time.time()
            printLog ("Se empieza a generar el siguiente video:"+video_actual)

            if not siguegrabando:
                printLog ("pre-roll: vuelco del buffer de los ultimos frames al inicio del video")
                # pre-roll: los frames previos al movimiento se escriben al INICIO del vídeo,
                # en orden y en este mismo hilo (antes se hacía en un hilo concurrente sobre
                # el mismo VideoWriter -> condición de carrera / frames corruptos).
                for f in last_frames.obtenerPila():
                    writer.write(f)
                last_frames.vaciar()
                frames_i=0
            else:
                printLog("viene de que se acaba de parar un video, y acaba de reanudarse otro por que detectó mas movimiento")



        if grabando:
            if DEBUG_FRAMES:
                printLog ("Grabando...")

            if writer is not None:
                writer.write(frame_original)
            time_elapsed = time.time() - time_inicio
            # key = cv2.waitKey(500)
            if time_elapsed>maximo_videos:
                parando=True            
                printLog ("han pasdo mas de "+str(maximo_videos)+" segs, marco pa qe se pare..")



        if parando and grabando:
            count_para=count_para+1
            if DEBUG_FRAMES:
                printLog("Proceso de frenado:"+str(count_para))


        if count_para==frames_despues:
            printLog ("se quiere parar de grabar "+str(count_para)+" frames despues y cerrando video:"+video_actual+" ...")
            count_para=0   
            parando=False    
            grabando=False
            if writer is not None:
                peso = writer.close()
                writer = None
                tmp_path = 'motor/videos/'+LOCAL_ID+'/'+CAMARA_ID+'/'+video_tmp
                final_path = 'motor/videos/'+LOCAL_ID+'/'+CAMARA_ID+'/'+video_actual
                if peso is not None:
                    # cierre correcto: publicar (rename atómico; el detector solo
                    # ve .mp4 completos)
                    try:
                        if os.path.exists(tmp_path):
                            os.rename(tmp_path, final_path)
                    except OSError as e:
                        printLog("no se pudo renombrar video: "+str(e))
                else:
                    # cierre fallido (ffmpeg muerto/timeout): descartar el tmp
                    try:
                        if os.path.exists(tmp_path):
                            os.remove(tmp_path)
                    except OSError as e:
                        printLog("no se pudo borrar tmp corrupto: "+str(e))
                printLog("Video cerrado: "+video_actual+" peso="+str(peso)+" bytes")
            num_video=num_video+1
            printLog("Se marca siguegrabando como false")
            siguegrabando=False

            if detector.hay_ahora():
                printLog ("Sigue habiendo movimiento, lo marco para que cree otro video y siga grabando..")
                grabando=True
                grabando_primera=True
                siguegrabando=True


        if DEBUG_FRAMES:
            printLog("Y muestro webcam")
        # headless: sin imshow
        # if cv2.waitKey(1) & 0xFF == ord('q'):
        #     break

cap.release()
