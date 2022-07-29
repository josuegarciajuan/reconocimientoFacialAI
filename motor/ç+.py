-capturador.php  > guarda_movimientos.py
    crea videos cuando detecta movimiento

-detector.php  > procesa_fotos_def_borrosaparteV2.py
    clasifica las fotos con caras


-detector.php  > procesa_videosV6.py
    saca fotos de un video con caras y cruces de lineas


-clasificadorV2.php





al principal devolvere:
si hay muchas desenfocadas da mas luz
si hay muchas que no se puede recortar, exate parta atras un poco
si hay pocas imagenes extraidas el video es muy corto
si hay pocas imagenes con cara no te as colocado bien





rm motor/bbdd_reconocimiento/1/*
rm motor/caras/sinclasificar/*
rm -R motor/caras/1/0/*
rm motor/removidas/nopasafiltros/*
cd motor
rm *.out
python3.7 crear_diccionario_inicial.py 
cd ..
php procesa_video_registro.php 1


//python3.7 procesa_video_registro.py 1 prueba2.avi


ls | wc -l


server
456 S
242 buenas
206 malas


local
251 S
227 buenas
62  malas







local
127 S
120 buenas
105 malas

server
214 S
120 buenas
105 malas



