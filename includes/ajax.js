function nuevoAjax()
{ 
	/* Crea el objeto AJAX. Esta funcion es generica para cualquier utilidad de este tipo, por
	lo que se puede copiar tal como esta aqui */
	var xmlhttp=false; 
	try 
	{ 
		// Creacion del objeto AJAX para navegadores no IE
		xmlhttp=new ActiveXObject("Msxml2.XMLHTTP"); 
	}
	catch(e)
	{ 
		try
		{ 
			// Creacion del objet AJAX para IE 
			xmlhttp=new ActiveXObject("Microsoft.XMLHTTP"); 
		} 
		catch(E) { xmlhttp=false; }
	}
	if (!xmlhttp && typeof XMLHttpRequest!='undefined') { xmlhttp=new XMLHttpRequest(); } 
	return xmlhttp; 
}

function select_ajax(ruta,id_origen,id_destino,capa) {
		var valor=document.getElementById(id_origen).options[document.getElementById(id_origen).selectedIndex].value;
		
		if(valor==0)
		{
			// Si el usuario eligio la opcion "Elige", no voy al servidor y pongo todo por defecto
			combo=document.getElementById(id_destino);
			combo.length=0;
			var nuevaOpcion=document.createElement("option"); nuevaOpcion.value=0; 
			nuevaOpcion.innerHTML="elige valor...";
			combo.appendChild(nuevaOpcion);	combo.disabled=true;
		}
		else
		{			
			ajax=nuevoAjax();
			ajax.open("GET", ruta+valor, true);
			ajax.onreadystatechange=function() 
			{ 
				if (ajax.readyState==1)
				{
					// Mientras carga elimino la opcion "Elige localidad" y pongo una que dice "Cargando"
					combo=document.getElementById(id_destino);
					combo.length=0;
					var nuevaOpcion=document.createElement("option"); nuevaOpcion.value=0; 
					nuevaOpcion.innerHTML="Cargando...";
					combo.appendChild(nuevaOpcion); combo.disabled=true;	
				}
				if (ajax.readyState==4)	document.getElementById(capa).innerHTML=ajax.responseText;
			}
			ajax.send(null);
		}
}
function EnviarFormulario(formid,obj){ 
		var Formulario;
		
		if (obj) Formulario = formid; 
		else Formulario = document.getElementById(formid); 

         var longitudFormulario = Formulario.elements.length; 
         var cadenaFormulario = "";
         var sepCampos = ""; 
         for (var i=0; i <= Formulario.elements.length-1;i++) {
		 	if ( Formulario.elements[i].type == 'checkbox') {
		 		if  ( Formulario.elements[i].checked ) {
         			cadenaFormulario += sepCampos+Formulario.elements[i].name+'='+escape(Formulario.elements[i].value); 
        			sepCampos="&"; 
				}
			} else {
				cadenaFormulario += sepCampos+Formulario.elements[i].name+'='+escape(Formulario.elements[i].value); 
        		sepCampos="&";
			}
		 }
		 
		 return cadenaFormulario;
	} 