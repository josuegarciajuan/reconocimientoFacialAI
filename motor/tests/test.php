<?php

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

?>