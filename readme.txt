NUEVO SERVER:


la cuenta de casasescortsmurcia@gmail.com
45.136.71.235 
eladmin
prueba123
ssh -i ~/.ssh/id_rsa eladmin@reconocimien.vps.webdock.cloud
mc . sftp://eladmin:prueba123@reconocimien.vps.webdock.cloud/var/www/
MYSQL: Prueba123!

scp eladmin@45.136.71.235:/var/www/html/reconocimientofacialV2/motor/caras/sinclasificar/1/1/* .
/home/testuser/motor/videos/1/1

camaras
prueba123
ssh -i ~/.ssh/id_rsa camaras@reconocimien.vps.webdock.cloud
MYSQL: Prueba123!



scp /home/testuser/motor/videos/1/6/* eladmin@45.136.71.235:/home/testuser/motor/videos/1/6/





45.136.71.235
sshpass -p 'Prueba123!' ssh root@217.61.112.100


46.249.32.179
http://45.136.71.235/reconocimientofacialV2/admin/

https://scrapscrap.xyz/admin


instalacion php
  sudo apt update
  sudo apt install apache2
  sudo apt install mysql-server
  sudo mysql_secure_installation
  sudo apt install php libapache2-mod-php php-mysql
  apt-get install php-gd
  service apache2 restart


instalacion FTP
  sudo apt install vsftpd
  sudo systemctl start vsftpd
  sudo systemctl enable vsftpd
  sudo cp /etc/vsftpd.conf  /etc/vsftpd.conf_default
  sudo useradd -m testuser
  sudo passwd testuser
  sudo nano /etc/vsftpd.conf
  añadir esto para que le de permisos de lectura desde una web por ejemplo:   anon_umask=022    y   local_umask=022
  edit /etc/vsftpd.chroot_list, and add one user per line
  Find the entry labeled write_enable=NO, and change the value to “YES.”   and chroot_local_user=YES    and  chroot_list_file=/etc/vsftpd.chroot_list
  añador esto allow_writeable_chroot=YES
  sudo systemctl restart vsftpd.service
  



NO
/*
  sudo openssl req -x509 -nodes -days 365 -newkey rsa:2048 -keyout /etc/ssl/private/vsftpd.pem -out /etc/ssl/private/vsftpd.pem
  sudo nano /etc/vsftpd.conf
  change the line ssl_enable=NO to ssl_enable=YES:
  Then, add the following lines:

  rsa_cert_file=/etc/ssl/private/vsftpd.pem
  rsa_private_key_file=/etc/ssl/private/vsftpd.pem
  allow_anon_ssl=NO
  force_local_data_ssl=YES
  force_local_logins_ssl=YES
  ssl_tlsv1=YES
  ssl_sslv2=NO
  ssl_sslv3=NO
  require_ssl_reuse=NO
  ssl_ciphers=HIGH
  pasv_min_port=40000
  pasv_max_port=50000

  sudo systemctl restart vsftpd.service  
*/

añador esto allow_writeable_chroot=YES y reiniciar


apt-get install ftp-upload



/******************************************************
NO se usa pero esto sive para crear mas usuarios

nano /etc/vsftpd.conf

And add the following lines:
# Disable anonymous login
anonymous_enable=NO
 
# Enable the userlist 
userlist_enable=YES
 
# Configure the userlist to act as a whitelist (only allow users who are listed there)
userlist_deny=NO
 
# Allow the local users to login to the FTP (if they're in the userlist)
local_enable=YES
 
# Allow virtual users to use the same privileges as local users
virtual_use_local_privs=YES
 
# Setup the virtual users config folder
user_config_dir=/etc/vsftpd/user_config_dir/


useradd ftp1
passwd ftp1

nano  /etc/vsftpd.user_list
josue

> nano /etc/vsftpd/user_config_dir/josue

local_root=/var/www/ftp1
write_enable=YES


nano /etc/passwd  
poner la ruta correspondiente


sudo systemctl restart vsftpd.service

******************************************************/









instalacion python
  sudo apt-get install software-properties-common
  sudo add-apt-repository ppa:deadsnakes/ppa
  sudo apt-get update
  sudo apt-get install python3.7


librerias python
  apt-get install --reinstall python3-apt
  sudo apt-get install python3-pip
  python3.7 -m pip install imutils
  python3.7 -m pip install numpy
  python3.7 -m pip install opencv-python
  python3.7 -m pip install --upgrade pip
  sudo apt-get -y install cmake
  python3.7 -m pip install opencv-python
  apt-get update && apt-get install -y python3-opencv
  apt install -y libgl1-mesa-glx
  apt update && apt install -y libsm6 libxext6 ffmpeg libfontconfig1 libxrender1 libgl1-mesa-glx
  sudo cp /usr/lib/python3.7/lib-dynload/_bz2.cpython-37m-x86_64-linux-gnu.so /usr/local/lib/python3.7/
  sudo update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.7 2
  python3.7 -m pip install cmake
  sudo apt-get update
  sudo apt-get install build-essential cmake
  sudo apt-get install libopenblas-dev liblapack-dev 
  sudo apt-get install libx11-dev libgtk-3-dev
  sudo apt-get install python python-dev python-pip
  sudo apt-get install python3 python3-dev python3-pip
  pip3 cache dir  el directorio qe de entrar en el y rm -R *
  pip cache purge
  python3.7 -m pip uninstall cmake
  python3.7 -m pip install cmake
  sudo apt-get install libboost-all-dev
  python3.7 -m pip install scipy
  python3.7 -m pip install scikit-image
  pip cache purge
  cd /tmp
  apt-get install --reinstall python3-apt
  update-alternatives  --set python3  /usr/bin/python3.7
  cd /usr/lib/python3/dist-packages
  ln -s apt_pkg.cpython-{35m,34m}-x86_64-linux-gnu.so
  cd  /usr/lib/python3/dist-packages
  ls -la /usr/lib/python3/dist-packages
  sudo cp apt_pkg.cpython-36m-x86_64-linux-gnu.so apt_pkg.so
  sudo unlink apt_pkg.so
  sudo cp apt_pkg.cpython-36m-x86_64-linux-gnu.so apt_pkg.so
  sudo cp apt_pkg.cpython-36m-x86_64-linux-gnu.so apt_pkg.so
  cd /tmp
  apt install git
  git clone https://github.com/davisking/dlib.git
  cd dlib
  mkdir build; cd build; cmake ..; cmake --build .
  cd ..
  sudo apt-get install python3.7-gdbm
  python3.7 -m pip install --upgrade setuptools
  sudo apt-get remove cmake
  sudo apt-get purge cmake
  python3.7 -m pip uninstall cmake
  sudo apt-get install build-essential cmake
  sudo apt-get install python3.7-dev
  python3.7 setup.py install
  python3.7 -m pip install face_recognition
  python3.7 -m pip install filelock
  python3.7 -m pip install wheel
  python3.7 -m pip install pandas
  python3.7 -m pip install pysftp
  pip install opencv-contrib-python
  sudo apt-get install python3-tk 
  sudo apt-get install python3.7-tk 
  python3.7 -m pip install keyboard

  pip uninstall PyNaCl
  apt remove python3-nacl
  python3.7 -m pip install PyNaCl

  python3.7 -m pip install face-alignment
  python3.7 -m pip install matplotlib
  python3.7 -m pip uninstall colorama
  python3.7 -m pip install colorama
  python3.7 -m pip install requests
  python3.7 -m pip install pyOpenSSL --upgrade
  NO//apt-get install -y xvfb
  NO//apt-get install x11vnc xvfb fluxbox

extras
  apt-get install htop
  apt-get install screen
  apt-get install ffmpeg

  apt install composer



subir proyecto a /var/www/html/
mkdir /home/testuser/motor
chmod -R 777 /home/testuser/motor
mkdir /home/testuser/motor/videos
chmod -R 777 /home/testuser/motor/videos
mkdir /home/testuser/motor/videos_lineas
chmod -R 777 /home/testuser/motor/videos_lineas
rm -R /var/www/html/reconocimientoFacial/proyecto_definitivo/motor/caras/*
mkdir /var/www/html/reconocimientoFacial/proyecto_definitivo/motor/caras/sinclasificar/
chmod -R 777 /var/www/html/reconocimientoFacial/proyecto_definitivo/motor/caras/sinclasificar/
rm -R /var/www/html/reconocimientoFacial/proyecto_definitivo/motor/bbdd_reconocimiento/*
rm -R /var/www/html/reconocimientoFacial/proyecto_definitivo/motor/fotos_lineas/*
rm -R /var/www/html/reconocimientoFacial/proyecto_definitivo/admin/caras_procesadas/*

conectar a mysql
CREATE USER 'newuser'@'localhost' IDENTIFIED BY 'prueba123@4522gwrQWWERw';
GRANT ALL PRIVILEGES ON *.* TO 'newuser'@'localhost';
luego desconectar, conectar con este usuario y 
create database reconocimientofacial2;
use reconocimientofacial2


cd /var/www/html/reconocimientoFacial/
chmod -R 777 *



http://camaras.vps.webdock.io/reconocimientoFacial/proyecto_definitivo/admin/index.php?page=visitantes&buscar=1&camara=-&desde=9/01%2012:01%20AM&hasta=10/22%2012:59%20PM&trabajador=0




------------------------------------------------

FUNCIONAMIENTO MOTOR:
screen -XS <session-id> quit
screen -S <session_name>
cd /var/www/html/reconocimientoFacial/proyecto_definitivo/

cada uno de estos procesos dentro de 1 screen:


python3.7 motor/guarda_movimientos.py camaras.vps.webdock.io testuser prueba123 'rtsp://admin:bakcAse4@nouesmalt.duckdns.org:778/cam/realmonitor?channel=1&subtype=0' 1 3
python3.7 motor/guarda_movimientos.py camaras.vps.webdock.io testuser prueba123 'rtsp://admin:bakcAse4@172.16.51.52:554/cam/realmonitor?channel=1&subtype=0' 1 3



p1-php procesos_panel_control.php {DEBUG(0=>NO,1=>si)}  
llama a motor/devuelve_posicion_cara.py y lo mantiene en marcha con threads.
Se encarga de recorrer esta ruta: RUTA_PROYECTO + "admin/files/videos_registro" y devolver si es la posicion de cara que se espera con una puntuacion
##El video de registro se sube a: admin/files/videos_registro_videos/{local_id}_{nombre_persona}.avi
(si me lo quiero saltar:
cp /home/testuser/pruebas/p1/1_josue.avi admin/files/videos_registro_videos/1_josue.avi
)

p2-php procesa_video_registro.php
esperando que haya un video de registro. Si lo hay, lo divide en minivideos de 4 segundos y llama a:
motor/procesa_video_registro_1.py y motor/procesa_video_registro_2.py
el 1º se encarga de sacar caras de los minivideos
el 2º se encarga de recorrer estas fotos, descartas las no enfocadas y las enfocadas sacar los encodings y guardarlos
##lo separa en minivideos que se guardan en admin/files/videos_registro_videos_partidos
##por cada video saca caras que las guarda en: 'motor/caras/sinclasificar_videos/'+'0_'+now+'.avi_'+str(segs_elapsed)+'.jpg'
##finalmente las mete en: 'motor/caras/'+LOCAL_ID+'/C0/'+ganador_name+'/'+name_file+'_'+fotos_identificadorunico+".jpg"
(si me lo quiero saltar:
cp -R /home/testuser/pruebas/p2/5w7AF4sNu7X6OJYtVU38I3fun motor/caras/1/C0/
cp /home/testuser/pruebas/p2/face_enc motor/bbdd_reconocimiento/1/
)



p3-php clasificadorV2.php
con las fotos que ya han guardado los encodings, recorre su lugar de donde se han giuardado, y ya crea las estancias y mueve las fotos a su lugar difinitivo y crea tambien si es persona nueva
##las clasifica dependiendo de la carpeta donde estan alojadas y las mete en:admin/caras_procesadas/".$sql->id.".jpg
(no se puede saltar para hacer prueba pues hace varios inserts, por lo que: php clasificadorV2.php)
(si me lo quiero saltar:
cp /home/testuser/pruebas/p3/ 
)

p4-capturador.php {local_id} {desde(si se pasa un valor es que se usa desde el server si no se pasa es que es desde local)}
habrá que encender uno de estos procesos por cada local
llama y mantiene a motor/guarda_movimientos.py que es llamado por cada camara en el local
graba videos cuando detecta movimiento
(este proceso se puede poner en un ordenador a parte, por que luego sube los videos por ftp al server bueno, así libera memoria)
##crea una copia en motor/videos/'+LOCAL_ID+'/'+nombre  que se autoelimina y sube a: FTP_RUTA/motor/videos/'+LOCAL_ID+'/'+CAM_ID+'/'+nombre
(si me lo quiero saltar:
cp /home/testuser/pruebas/p2/face_enc motor/bbdd_reconocimiento/1/
cp /home/testuser/pruebas/p4/* /home/testuser/motor/videos/1/1 
)




p5-detector.php
llama y mantiene comprobando que no se desborde la ram de estos procesos
procesa_videosV6.py  y  procesa_fotos_def_borrosaparteV2.py
el 1º: procesa los cruces de lineas y saca caras del video
el 2º: busca a quien pertence la cara de las fotos sacadas del 1º
##p5.1.- guarda las lineas en:motor/fotos_lineas/"+lineas_ids[ii]+"/"+numrandom+".jpg
##p5.1.- guarda las caras en motor/caras/sinclasificar/'+LOCAL_ID+'/'+CAMARA_ID+'/'+FICHERO+'_'+str(segs_elapsed)+'.jpg
##p5.2.- finalmente las mete en: 'motor/caras/'+LOCAL_ID+'/'+CAMARA_ID+'/'+ganador_name+'/'+name_file+'_'+fotos_identificadorunico+".jpg"
(
si me quiero saltar la 1º parte:
cp /home/testuser/pruebas/p5/1/* /var/www/html/reconocimientofacialV2/motor/caras/sinclasificar/1/1/
cp /home/testuser/pruebas/p2/face_enc motor/bbdd_reconocimiento/1/
scp motor/caras/sinclasificar/1/1/* eladmin@45.136.71.235:/var/www/html/reconocimientofacialV2/motor/caras/sinclasificar/1/1/


si me quiero saltar la 2º parte:
cp -R /home/testuser/pruebas/p5/2/5w7AF4sNu7X6OJYtVU38I3fun motor/caras/1/1/
cp /home/testuser/pruebas/p2/face_enc motor/bbdd_reconocimiento/1/
)



python3.7 motor/procesa_fotos_def_borrosaparteV2.py 1 3 0.38 0 0 0 0 0 0 0 0 0.551 0.535 0.551 0.37 12 0.61 0.63 2 0.511 0.491 0.511 0.35 20 0.58 0.61 4 0.531 0.515 0.521 0.36 15 0.58 0.611 4 0.04 500 9 300 1000 120 90 450 1200 mJNXRkq9ebqE



python3.7 /var/www/html/reconocimientofacialV2/motor/procesa_videosV6.py 1 1 '1_2022-11-02_11:01:20.318914.avi' '/var/www/html/reconocimientofacialV2/' 0.68 '/home/testuser/' 150 5 10 750 562 750 562 3 5 1500 3 0.15 300 300 1.0 353 353 104.0 117.0 123.0 100 150

python3.7 motor/procesa_fotos_def_borrosaparteV2.py 1 1 0.38 0 0 0 0 0 0 0 0 0.551 0.535 0.551 0.37 12 0.61 0.63 2 0.511 0.491 0.511 0.35 20 0.58 0.61 4 0.531 0.515 0.521 0.36 15 0.58 0.611 4 0.04 500 9 300 1000 120 90 450 1200



anyadir sensibilidad de movimiento por camara
anyadir que en el procesamiento del video inicial solo se guarde ciertas de cada posicion





rm -R motor/caras/1/C0/*
rm -R motor/caras/1/1/*
rm motor/caras/sinclasificar/1/1/*
rm -R motor/caras/1/1/*
rm motor/bbdd_reconocimiento/1/face_enc
rm motor/videos/1/*
rm motor/fotos_lineas/1/*

rm -R motor/logs/*
rm motor/removidas/nopasafiltros/*
rm motor/caras/sinclasificar_videos/*
rm motor/*.out
rm motor/removidas/tmp/*
rm motor/removidas/nopasafiltros/*
rm motor/removidas/notienecaras/*

rm /home/testuser/motor/videos/1/1/*

rm admin/files/videos_registro/*
rm admin/files/videos_registro_posiciones/*
rm admin/files/videos_registro_pruebas/*
rm admin/files/videos_registro_resultados/*
rm admin/files/videos_registro_videos/*
rm admin/files/videos_registro_videos_partidos/*
rm admin/caras_procesadas/*
rm libs/threads_files_aux/*_vr_*
rm aux/*
cd motor
python3.7 crear_diccionario_inicial_parametrizado.py 1
cd ..


https://tempmail.ninja/
haciendopruebas@xuge.life
268198

mysql -u root -pcamaras reconocimientofacial3
mysql -u newuser -p reconocimientofacial2
prueba123@4522gwrQWWERw

delete from cruces_lineas;
delete from estancias;
delete from fotos;
delete from personas;
exit;


https://correotemporal.org/enviar-correo-anonimo/


clasificadorV2
procesos_panel_control
procesa_video_registro
scp eladmin@45.136.71.235:/home/testuser/pruebas/p1/* /home/testuser/pruebas/p1/
scp eladmin@45.136.71.235:/home/testuser/pruebas/p2/5w7AF4sNu7X6OJYtVU38I3fun/* /home/testuser/pruebas/p2/5w7AF4sNu7X6OJYtVU38I3fun
scp eladmin@45.136.71.235:/home/testuser/pruebas/p2/face_enc /home/testuser/pruebas/p2/
scp eladmin@45.136.71.235:/home/testuser/pruebas/p4/* /home/testuser/pruebas/p4/
scp eladmin@45.136.71.235:/home/testuser/pruebas/p5/1/* /home/testuser/pruebas/p5/1/
scp eladmin@45.136.71.235:/home/testuser/pruebas/p5/2/5w7AF4sNu7X6OJYtVU38I3fun/* /home/testuser/pruebas/p5/2/5w7AF4sNu7X6OJYtVU38I3fun







------------------------------------------------
-resetear y empezar de 0:
rm -R /var/www/html/reconocimientoFacial/proyecto_definitivo/admin/caras_procesadas/*
rm -R /var/www/html/reconocimientoFacial/proyecto_definitivo/motor/bbdd_reconocimiento/*
rm -R /var/www/html/reconocimientoFacial/proyecto_definitivo/motor/caras/*
mkdir /var/www/html/reconocimientoFacial/proyecto_definitivo/motor/caras/sinclasificar/
chmod -R 777 /var/www/html/reconocimientoFacial/proyecto_definitivo/motor/caras/sinclasificar/
rm -R /var/www/html/reconocimientoFacial/proyecto_definitivo/motor/fotos_lineas/*
rm -R /home/testuser/motor/videos/*
rm -R /home/testuser/motor/videos_lineas/*
ejecutar el reset de la bbdd (select primero para ver las lineas anteriores donde estan)


-comprobar todo creado bien:
    -crear local:
        -creado /home/testuser/motor/videos/1
        -creado /home/testuser/motor/videos_lineas/1
        -creado /var/www/html/reconocimientoFacial/proyecto_definitivo/motor/caras/1
        -creado /var/www/html/reconocimientoFacial/proyecto_definitivo/motor/caras/sinclasificar/1
        -creado /var/www/html/reconocimientoFacial/proyecto_definitivo/motor/bbdd_reconocimiento/1
        -creado /var/www/html/reconocimientoFacial/proyecto_definitivo/motor/bbdd_reconocimiento/1/face_enc


    -cargar plano
        -fichero nuevo en: /var/www/html/reconocimientoFacial/proyecto_definitivo/admin/pages/config/planos/plano_1.extension

    -crear camara
        -creado /home/testuser/motor/videos/1/1  
        -creado /home/testuser/motor/videos_lineas/1/1   
        -creado /var/www/html/reconocimientoFacial/proyecto_definitivo/motor/caras/1/1
        -creado /var/www/html/reconocimientoFacial/proyecto_definitivo/motor/caras/sinclasificar/1/1




INSERT INTO `camaras` VALUES (1,1,'Camara fichador',NULL,'rtsp://admin:bakcAse4@172.16.51.51:554/cam/realmonitor?channel=1&subtype=0',0,0,0,0,0,0,'-','2021-09-30 14:40:44','rtsp://admin:bakcAse4@nouesmalt.duckdns.org:778/cam/realmonitor?channel=1&subtype=0'),

(2,1,'Camara pasillo',NULL,'rtsp://admin:bakcAse4@172.16.51.50:554/cam/realmonitor?channel=1&subtype=0',0,0,0,0,0,0,'-','2021-09-30 14:41:33','rtsp://admin:bakcAse4@nouesmalt.duckdns.org:777/cam/realmonitor?channel=1&subtype=0'),

(3,1,'Camara josue',NULL,'rtsp://admin:bakcAse4@172.16.51.52:554/cam/realmonitor?channel=1&subtype=0',0,0,0,0,0,0,'-','2021-09-30 14:42:02','rtsp://admin:bakcAse4@nouesmalt.duckdns.org:779/cam/realmonitor?channel=1&subtype=0'),

(4,1,'Camara salida',NULL,'rtsp://admin:bakcAse4@172.16.51.53:554/cam/realmonitor?channel=1&subtype=0',0,0,0,0,1,0,'-','2021-09-30 14:42:19','rtsp://admin:bakcAse4@nouesmalt.duckdns.org:780/cam/realmonitor?channel=1&subtype=0'),

(5,1,'Camara entrada',NULL,'rtsp://admin:bakcAse4@172.16.51.54:554/cam/realmonitor?channel=1&subtype=0',0,0,0,1,0,0,'-','2021-09-30 14:43:06','rtsp://admin:bakcAse4@nouesmalt.duckdns.org:781/cam/realmonitor?channel=1&subtype=0'),

(6,2,'Habitaciones',NULL,'rtsp://admin:bakcAse4@192.168.31.210:554/cam/realmonitor?channel=1&subtype=0',0,0,0,0,0,1,'-','2021-10-04 09:40:07','rtsp://admin:bakcAse4@lunaxilxes.duckdns.org:777/cam/realmonitor?channel=1&subtype=0'),

(7,2,'Recepcion',NULL,'rtsp://admin:bakcAse4@192.168.31.211:554/cam/realmonitor?channel=1&subtype=0',0,0,0,0,0,1,'-','2021-10-04 09:40:28','rtsp://admin:bakcAse4@lunaxilxes.duckdns.org:778/cam/realmonitor?channel=1&subtype=0'),

(8,2,'Arriba',NULL,'rtsp://admin:bakcAse4@192.168.31.212:554/cam/realmonitor?channel=1&subtype=0',0,0,0,0,0,1,'-','2021-10-04 09:40:41','rtsp://admin:bakcAse4@lunaxilxes.duckdns.org:779/cam/realmonitor?channel=1&subtype=0'),

(9,2,'Pasillo',NULL,'rtsp://admin:bakcAse4@192.168.31.213:554/cam/realmonitor?channel=1&subtype=0',0,0,0,0,0,1,'-','2021-10-04 09:40:58','rtsp://admin:bakcAse4@lunaxilxes.duckdns.org:780/cam/realmonitor?channel=1&subtype=0');



    -crear linea
        -creado /home/testuser/motor/videos_lineas/1/1/1
        -creado /var/www/html/reconocimientoFacial/proyecto_definitivo/motor/fotos_lineas/1













********************************************



Config camaras
---------------------------------------------
(inicial)

Conditions

-Picture:
Bri  50
con  55
sat  55
sha  50
Gam  48

-Exposure
outdoor
auto
on
50

-backlight
off

-wb
auto

-day and night
auto middle  6s


Video
-Substream activado
-Encode H264H  
-smart  off 
-resol  1920x1080 
-FPS    10
-bit t  CBR
-bit r  768
-fram   20


---------------------------------------------

(nueva1)

Conditions

-Picture:
Bri  56
con  50
sat  60
sha  70
Gam  45



-Exposure  (recepcion y cocina)
60Kz
manual
1/12  
10-90
on
68


-Exposure  (arrinba y habitaciones)
DAY
60Kz
manual
1/60  
10-90
on
68


-Exposure  (arrinba y habitaciones)
NIGHT
60Kz
manual
1/12  
10-90
on
68




-backlight
off

-wb
auto

-day and night
COlor


Video
-Substream activado
-Encode H264H  
-smart  off 
-resol  1280x960 
-FPS    18
-bit t  CBR
-bit r  2048
-fram   40


---------------------------------------------






********************************************




[hevc @ 0x3073980] The cu_qp_delta 30 is outside the valid range [-26, 25].
Traceback (most recent call last):
  File "motor/guarda_movimientosV2.py", line 127, in <module>
    output = cv2.GaussianBlur(frame, (21, 21), 0)
cv2.error: OpenCV(4.6.0) /io/opencv/modules/imgproc/src/smooth.dispatch.cpp:617: error: (-215:Assertion failed) !_src.empty() in function 'GaussianBlur'