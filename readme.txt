NUEVO SERVER:


la cuenta de casasescortsmurcia@gmail.com
45.136.71.235 
eladmin
prueba123
ssh -i ~/.ssh/id_rsa eladmin@reconocimien.vps.webdock.cloud
mc . sftp://eladmin:prueba123@reconocimien.vps.webdock.cloud/var/www/
MYSQL: Prueba123!

scp eladmin@45.136.71.235:/home/testuser/motor/videos/1/1/pruebas.txt .
/home/testuser/motor/videos/1/1

camaras
prueba123
ssh -i ~/.ssh/id_rsa camaras@reconocimien.vps.webdock.cloud
MYSQL: Prueba123!




46.249.32.179
sshpass -p 'Prueba123!' ssh root@217.61.112.100


46.249.32.179
http://46.249.32.179/reconocimientoFacial/proyecto_definitivo/admin/


instalacion php
  sudo apt update
  sudo apt install apache2
  sudo apt install mysql-server
  sudo mysql_secure_installation
  sudo apt install php libapache2-mod-php php-mysql



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
cd /var/www/html/reconocimientoFacial/proyecto_definitivo/

cada uno de estos procesos dentro de 1 screen:

python3.7 motor/guarda_movimientos.py camaras.vps.webdock.io testuser prueba123 'rtsp://admin:bakcAse4@nouesmalt.duckdns.org:778/cam/realmonitor?channel=1&subtype=0' 1 3


python3.7 motor/guarda_movimientos.py camaras.vps.webdock.io testuser prueba123 'rtsp://admin:bakcAse4@172.16.51.52:554/cam/realmonitor?channel=1&subtype=0' 1 3



2007.pts-0.vps-ev632391
php capturador.php 2 1


1993.pts-0.vps-ev632391
php capturador.php 1 1


521.pts-0.camaras
php detector.php


509.pts-0.camaras
php clasificadorV2.php





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



