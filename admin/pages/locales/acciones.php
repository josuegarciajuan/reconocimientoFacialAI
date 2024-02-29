<?php

/*
 * * * * * * * * * * * * * * * * * * 
  29 feb. 2024 11:35:18
  Josué García Juan
 * * * * * * * * * * * * * * * * * *
*/


if(isset($_GET["submit"]) and $_GET["submit"]!=""){
    $campos=["nombre","url_logo","usuario","aforo_max"];
    $valores=[$_POST["nombre"],$_POST["url_logo"],$_POST["usuario"],$_POST["aforo_max"]];
    
    if(isset($_GET["id"]) and $_GET["id"]!=""){
        $sql->Actualizar("locales",$campos,$valores,"id=".$_GET["id"]);
        $id=$_GET["id"];
    }else{
        $sql->Insertar("locales",$campos,$valores);
        $id=$sql->id;
        
        $cmds=[
            "mkdir ".URL_FTP_BASE."motor/videos/".$id,
            "mkdir ".URL_FTP_BASE."motor/videos_lineas/".$id,
            "mkdir ".RUTA_PROYECTO."motor/caras/".$id,
            "chmod -R 777 ".URL_FTP_BASE."motor/videos/".$id,
            "chmod -R 777 ".URL_FTP_BASE."motor/videos_lineas/".$id,
            "chmod -R 777 ".RUTA_PROYECTO."motor/caras/".$id,
            
            "mkdir ".RUTA_PROYECTO."motor/caras/".$id."/C0",
            "mkdir ".RUTA_PROYECTO."motor/caras/sinclasificar/".$id,
            "mkdir ".RUTA_PROYECTO."motor/bbdd_reconocimiento/".$id,
            "chmod -R 777 ".RUTA_PROYECTO."motor/caras/".$id."/C0",
            "chmod -R 777 ".RUTA_PROYECTO."motor/caras/sinclasificar/".$id,
            "chmod -R 777 ".RUTA_PROYECTO."motor/bbdd_reconocimiento/".$id,
            
            "mkdir ".RUTA_PROYECTO."motor/videos/".$id,
            "mkdir ".RUTA_PROYECTO."motor/fotos_lineas/".$id,
            "chmod -R 777 ".RUTA_PROYECTO."motor/videos/".$id,
            "chmod -R 777 ".RUTA_PROYECTO."motor/fotos_lineas/".$id,
         
            //RUTA_PYTHON." ".RUTA_PROYECTO."motor/crear_diccionario_inicial_parametrizado.py ".$id,
            "cp ".RUTA_PROYECTO."motor/inicial/face_enc ".RUTA_PROYECTO."motor/bbdd_reconocimiento/".$id."/face_enc",
            "chmod -R 777 ".RUTA_PROYECTO."motor/bbdd_reconocimiento/".$id."/face_enc",
        ];
        
        echo "<br />-----EJECUTAR---<br /><br />";
        for($i=0;$i<count($cmds);$i++){
            echo $cmds[$i]."<br />";
            //$return=shell_exec($cmds[$i]);
            exec($cmds[$i]." 2>&1", $output, $return_var);
            echo "output:<br />";
            var_dump($output);
            echo "--<br />";
            echo "return_var:".$return_var."<br />";
            echo "-------------<br />";
            sleep(1);
        }
        echo "<br />----------------<br />";
        
        
    }
    if($_POST["passw"]!=""){
        $sql->Actualizar("locales",["passw"],$_POST["passw"],"id=".$id);
    }
    
}
