<?php


//2022-10-25 12:57:32.302218
$fecha=date("Y-m-d H:i:s");
$fecha=str_replace(" ", "_", $fecha);
echo "->".$fecha."<-\n\n";
exec("python3.7 test.py ".$fecha);

/*
test("/home/videos","var/www/html/videos");

function test($path,$destino){
	$dir = opendir($path);

	while ($elemento = readdir($dir)){
	    if( $elemento != "." && $elemento != ".." &&){

	    	if(is_dir($path."/".$elemento)){
	    		test($path."/".$elemento,$destino."/".$elemento);
	    	}else{
	    		$fichero=$path.$elemento;
	    		exec("ffmpeg -i ".$fichero." -c:v libx264 -crf ".$destino."/".basename($elemento, ".avi").".mp4". " > /dev/null 2>/dev/null &");
	    	}
	    }
	}	
	unset($dir);
}

*/
?>