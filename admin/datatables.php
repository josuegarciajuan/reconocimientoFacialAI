<?php
declare(strict_types=1);

session_start();
require_once __DIR__ . '/../libs/db.php';
require_once __DIR__ . '/includes/datatables.php';
require_once __DIR__ . '/../libs/etiquetas.php';
require_once __DIR__ . '/../libs/fechas.php';
require_once __DIR__ . '/../libs/alarmas.php';
require_once __DIR__ . '/../libs/rutas.php';

header('Content-Type: application/json; charset=UTF-8');
$table = (string)($_GET['table'] ?? '');
$request = datatables_request($_GET);

function dt_json(array $request, int $total, int $filtered, array $data, ?string $error = null): never
{
    $response = datatables_response($request['draw'], $total, $filtered, $data);
    if ($error !== null) {
        $response['error'] = $error;
    }
    echo datatables_encode($response);
    exit;
}

if (empty($_SESSION['user']) || empty($_SESSION['local_id'])) {
    http_response_code(401);
    dt_json($request, 0, 0, [], 'No autorizado');
}

$local = (int)$_SESSION['local_id'];
$esc = static fn($v): string => datatables_html((string)$v);
$like = trim((string)($_GET['search']['value'] ?? ''));
$offset = $request['start']; $limit = $request['length'];

try {
if ($table === 'visitantes') {
    $where = ['e.camara_id IN (SELECT id FROM camaras WHERE local_id = ?)']; $params = [$local];
    $from = 'estancias e JOIN personas p ON p.id=e.persona_id';
    if (!empty($_GET['camara']) && $_GET['camara'] !== '-') { $where[]='e.camara_id=?'; $params[]=(int)$_GET['camara']; }
    if ((string)($_GET['trabajador'] ?? '') === '1') $where[]='p.trabajador=1';
    if (($v=trim((string)($_GET['desde'] ?? ''))) !== '') { $where[]='e.fecha_ini>=?'; $params[]=rango_a_sql($v, date('Y-m-d 00:00:00')); }
    if (($v=trim((string)($_GET['hasta'] ?? ''))) !== '') { $where[]='e.fecha_ini<=?'; $params[]=rango_a_sql($v, date('Y-m-d 23:59:59')); }
    if ($like !== '') { $where[]='(p.nombre LIKE ? OR p.cod_interno LIKE ?)'; $params[]="%$like%"; $params[]="%$like%"; }
    $w=implode(' AND ',$where);
    $total=(int)(DB::selectOne('SELECT COUNT(DISTINCT e.persona_id) n FROM '.$from.' WHERE e.camara_id IN (SELECT id FROM camaras WHERE local_id=?)',[$local])['n']??0);
    $filtered=(int)(DB::selectOne('SELECT COUNT(DISTINCT e.persona_id) n FROM '.$from.' WHERE '.$w,$params)['n']??0);
    $order=datatables_order($request['column'], ['0'=>'MAX(e.fecha_ini)','1'=>'p.nombre','2'=>'MAX(e.fecha_ini)','3'=>'COUNT(e.id)']);
    $rows=DB::select('SELECT e.persona_id,p.cod_interno,p.nombre,p.trabajador,MAX(e.fecha_ini) ultima,COUNT(e.id) estancias,(SELECT MIN(f.id) FROM fotos f JOIN estancias ef ON ef.id=f.estancia_id WHERE ef.persona_id=e.persona_id) foto_id FROM '.$from.' WHERE '.$w.' GROUP BY e.persona_id,p.cod_interno,p.nombre,p.trabajador ORDER BY '.$order.' '.$request['direction'].' LIMIT '.$limit.' OFFSET '.$offset,$params);
    $data=[]; foreach($rows as $r){ $id=(int)$r['persona_id']; $name=$r['nombre']!==''?$r['nombre']:$r['cod_interno']; $acciones='<a href="?page=visitantes&mode=editar&id='.$id.'">Ver</a> · <a href="?page=accesos&persona_id='.$id.'">Movimientos</a> · <a href="?page=visitantes&mode=editar&id='.$id.'#videos">Vídeos</a> · <a href="?page=lineas&persona_id='.$id.'">Cruces</a> · <a href="?page=rutas&persona_id='.$id.'">Rutas</a>';if((int)$r['trabajador']===1)$acciones.=' · <a href="?page=fichajes&persona_id='.$id.'">Fichajes</a>'; $data[]=[
        '<img alt="Foto de '.$esc($name).'" class="img-thumb" loading="lazy" src="./caras_procesadas/'.(int)$r['foto_id'].'.jpg">',
        '<a class="text-theme-1 font-medium hover:underline" href="?page=visitantes&mode=editar&id='.$id.'">'.$esc(persona_label($name,$r['cod_interno'])).'</a>',
        $esc($r['ultima']), (int)$r['estancias'], $acciones]; }
    dt_json($request,$total,$filtered,$data);
}

if ($table === 'accesos') {
    $where=['e.fecha_ini>=?','e.fecha_ini<=?']; $params=[rango_a_sql((string)($_GET['desde']??''),date('Y-m-d H:i:s',time()-86400)),rango_a_sql((string)($_GET['hasta']??''),date('Y-m-d H:i:s'))];
    if (!empty($_GET['camara'])&&$_GET['camara']!=='-'){ $where[]='e.camara_id=?';$params[]=(int)$_GET['camara']; } else {$where[]='c.local_id=?';$params[]=$local;}
    if (!empty($_GET['persona_id'])&&$_GET['persona_id']!=='-'){ $where[]='e.persona_id=?';$params[]=(int)$_GET['persona_id']; }
    if($like!==''){ $where[]='(p.nombre LIKE ? OR p.cod_interno LIKE ?)';$params[]="%$like%";$params[]="%$like%"; }
    $w=implode(' AND ',$where); $base='estancias e JOIN personas p ON p.id=e.persona_id JOIN camaras c ON c.id=e.camara_id';
    $total=(int)(DB::selectOne('SELECT COUNT(*) n FROM '.$base.' WHERE e.fecha_ini>=? AND e.fecha_ini<=? AND c.local_id=?',[$params[0],$params[1],$local])['n']??0);
    $filtered=(int)(DB::selectOne('SELECT COUNT(*) n FROM '.$base.' WHERE '.$w,$params)['n']??0);
    $rows=DB::select('SELECT e.id,e.persona_id,e.fecha_ini,e.fecha_fin,p.nombre,p.cod_interno,c.id camara_id,c.descripcion camara,(SELECT MIN(v.id) FROM videos v WHERE v.local_id=c.local_id AND v.camara_id=e.camara_id AND v.fecha_ini<=e.fecha_fin AND COALESCE(v.fecha_fin,v.fecha_ini)>=e.fecha_ini) video_id FROM '.$base.' WHERE '.$w.' ORDER BY e.fecha_ini '.$request['direction'].' LIMIT '.$limit.' OFFSET '.$offset,$params);
    $ids=array_map(static fn($r)=>(int)$r['id'],$rows);$fotos=[];if($ids){$in=implode(',',array_fill(0,count($ids),'?'));foreach(DB::select('SELECT estancia_id,GROUP_CONCAT(id ORDER BY id) ids FROM fotos WHERE estancia_id IN ('.$in.') GROUP BY estancia_id',$ids) as $f){$fotos[(int)$f['estancia_id']]=array_map('intval',array_filter(explode(',',(string)$f['ids'])));}}
    $data=[];foreach($rows as $r){$id=(int)$r['persona_id'];$n=$r['nombre']?:$r['cod_interno'];$fh='—';foreach(array_slice($fotos[(int)$r['id']]??[],0,2) as $fid){$fh.='<img alt="Foto de '.$esc($n).'" class="img-thumb ml-1" loading="lazy" src="./caras_procesadas/'.$fid.'.jpg">';}$video=$r['video_id']?'<a href="../video.php?id='.(int)$r['video_id'].'" target="_blank">▶ Ver</a>':'—';$data[]=[ $esc($r['fecha_ini']),'<a href="?page=visitantes&mode=editar&id='.$id.'">'.$esc($n).'</a>',camara_link((int)$r['camara_id'],$r['camara']),$fh,$video,$esc(formato_duracion(max(1,strtotime($r['fecha_fin'])-strtotime($r['fecha_ini']))))];} dt_json($request,$total,$filtered,$data);
}

if ($table === 'fichajes') {
    $where=['f.local_id=?','f.fecha>=?','f.fecha<=?'];$params=[$local,(string)($_GET['desde']??date('Y-m-d')),(string)($_GET['hasta']??date('Y-m-d'))];if(!empty($_GET['persona_id'])&&$_GET['persona_id']!=='-'){$where[]='f.persona_id=?';$params[]=(int)$_GET['persona_id'];}$w=implode(' AND ',$where);$total=(int)(DB::selectOne('SELECT COUNT(*) n FROM fichajes f WHERE f.local_id=?',[$local])['n']??0);$filtered=(int)(DB::selectOne('SELECT COUNT(*) n FROM fichajes f JOIN personas p ON p.id=f.persona_id WHERE '.$w,$params)['n']??0);$rows=DB::select('SELECT f.*,p.nombre,p.cod_interno,ce.descripcion cam_entrada,cs.descripcion cam_salida FROM fichajes f JOIN personas p ON p.id=f.persona_id LEFT JOIN camaras ce ON ce.id=f.entrada_camara_id LEFT JOIN camaras cs ON cs.id=f.salida_camara_id WHERE '.$w.' ORDER BY f.fecha DESC,p.nombre,f.bloque LIMIT '.$limit.' OFFSET '.$offset,$params);$data=[];foreach($rows as $r){$data[]=[persona_link((int)$r['persona_id'],persona_label($r['nombre'],$r['cod_interno'])),$esc($r['fecha']),(int)$r['bloque'],$esc($r['entrada_hora']??'—'),$r['entrada_camara_id']?camara_link((int)$r['entrada_camara_id'],$r['cam_entrada']):'—','—',$esc($r['salida_hora']??'—'),$r['salida_camara_id']?camara_link((int)$r['salida_camara_id'],$r['cam_salida']):'—','—','—',$esc($r['estado'])];}dt_json($request,$total,$filtered,$data);
}

if ($table === 'lineas') {
    $where=['c.local_id=?','cl.fecha>=?','cl.fecha<=?'];$params=[$local,(string)($_GET['desde']??date('Y-m-d 00:00:00')),(string)($_GET['hasta']??date('Y-m-d 23:59:59'))];foreach([['camara','c.id'],['linea','cl.linea_id'],['trayectoria','cl.direccion'],['persona_id','cl.persona_id']] as $f){if(!empty($_GET[$f[0]])&&$_GET[$f[0]]!=='-'){$where[]=$f[1].'=?';$params[]=(int)$_GET[$f[0]];}}$w=implode(' AND ',$where);$base='cruces_lineas cl LEFT JOIN lineas l ON l.id=cl.linea_id LEFT JOIN camaras c ON c.id=l.camara_id LEFT JOIN personas p ON p.id=cl.persona_id';$total=(int)(DB::selectOne('SELECT COUNT(*) n FROM '.$base.' WHERE c.local_id=?',[$local])['n']??0);$filtered=(int)(DB::selectOne('SELECT COUNT(*) n FROM '.$base.' WHERE '.$w,$params)['n']??0);$rows=DB::select('SELECT cl.*,l.nombre linea_nombre,c.id camara_id,c.descripcion camara,p.nombre persona_nombre,p.cod_interno FROM '.$base.' WHERE '.$w.' ORDER BY cl.created DESC LIMIT '.$limit.' OFFSET '.$offset,$params);$data=[];foreach($rows as $r){$data[]=[ $esc($r['fecha']),camara_link((int)$r['camara_id'],$r['camara']),$esc($r['linea_nombre']),((int)$r['direccion']===1?'← ':'→ ').((int)$r['direccion']===1?'Derecha a Izquierda':'Izquierda a Derecha'),$r['persona_id']?persona_link((int)$r['persona_id'],persona_label($r['persona_nombre'],$r['cod_interno'])):'—',$r['video_id']?'▶ Ver':'—','—'];}dt_json($request,$total,$filtered,$data);
}

if ($table === 'locales') {
    $where='1=1';$params=[];if($like!==''){$where='(nombre LIKE ? OR url_logo LIKE ?)';$params=["%$like%","%$like%"];} $total=(int)(DB::selectOne('SELECT COUNT(*) n FROM locales')['n']??0);$filtered=(int)(DB::selectOne('SELECT COUNT(*) n FROM locales WHERE '.$where,$params)['n']??0);$rows=DB::select('SELECT l.*, (SELECT COUNT(*) FROM camaras c WHERE c.local_id=l.id) camaras,(SELECT COUNT(*) FROM personas p WHERE p.local_id=l.id) personas FROM locales l WHERE '.$where.' ORDER BY l.id '.$request['direction'].' LIMIT '.$limit.' OFFSET '.$offset,$params);$data=[];foreach($rows as $r){$data[]=['<img alt="" class="rounded-full" loading="lazy" src="'.$esc($r['url_logo']).'">',$esc($r['nombre']),(int)$r['aforo_max'],(int)$r['aforo_actual'],(int)$r['camaras'],(int)$r['personas'],'<a href="?page=locales&mode=editar&id='.(int)$r['id'].'">Editar</a>'];}dt_json($request,$total,$filtered,$data);
}

if ($table === 'alarmas' || $table === 'alarmas_telefonos' || $table === 'config_locales') {
    if ($table === 'alarmas_telefonos') {
        $total=(int)(DB::selectOne('SELECT COUNT(*) n FROM alarmas_telefonos WHERE local_id=?',[$local])['n']??0);
        $rows=DB::select('SELECT id,nombre,telefono,activo FROM alarmas_telefonos WHERE local_id=? ORDER BY id '.$request['direction'].' LIMIT '.$limit.' OFFSET '.$offset,[$local]);$data=[];foreach($rows as $r){$data[]=[$esc($r['nombre']),$esc($r['telefono']),((int)$r['activo']===1?'Activo':'Inactivo'),'<a href="acciones_ajax.php?a=2&id='.(int)$r['id'].'">Quitar</a>'];}dt_json($request,$total,$total,$data);
    }
    if ($table === 'config_locales') {
        $total=(int)(DB::selectOne('SELECT COUNT(*) n FROM locales')['n']??0);$rows=DB::select('SELECT l.*, (SELECT COUNT(*) FROM camaras c WHERE c.local_id=l.id) camaras,(SELECT COUNT(*) FROM personas p WHERE p.local_id=l.id) personas FROM locales l ORDER BY l.id '.$request['direction'].' LIMIT '.$limit.' OFFSET '.$offset);$data=[];foreach($rows as $r){$data[]=[$esc($r['nombre']),(int)$r['aforo_max'],(int)$r['aforo_actual'],(int)$r['camaras'],(int)$r['personas'],'<a href="?page=config&tab=locales&editar='.(int)$r['id'].'">Editar</a>'];}dt_json($request,$total,$total,$data);
    }
    $total=(int)(DB::selectOne('SELECT COUNT(*) n FROM alarmas WHERE local_id=?',[$local])['n']??0);$rows=DB::select('SELECT a.fecha,a.severidad,a.video_id,a.notificacion_vista,c.id camara_id,c.descripcion camara FROM alarmas a LEFT JOIN camaras c ON c.id=a.camara_id WHERE a.local_id=? ORDER BY a.fecha '.$request['direction'].' LIMIT '.$limit.' OFFSET '.$offset,[$local]);$data=[];foreach($rows as $r){$data[]=[$esc($r['fecha']),$r['camara_id']?camara_link((int)$r['camara_id'],$r['camara']):'Local (cualquier cámara)',$esc(strtoupper($r['severidad'])),$r['video_id']?'▶ Ver':'—',((int)$r['notificacion_vista']===0?'NUEVA':'Vista')];}dt_json($request,$total,$total,$data);
}

if ($table === 'rutas') {
    // Evita generar IN () cuando el local aún no tiene puerta configurada.
    [$puertas_disponibles, $salidas_disponibles] = camaras_puerta_salida($local);
    if (!$puertas_disponibles) { dt_json($request, 0, 0, []); }
    [$puertas,$salidas]=camaras_puerta_salida($local);$where=['e.camara_id IN ('.implode(',',array_map('intval',$puertas)).')','e.fecha_ini>=?','e.fecha_ini<=?'];$params=[(string)($_GET['desde']??date('Y-m-d 00:00:00')),(string)($_GET['hasta']??date('Y-m-d 23:59:59'))];if(!empty($_GET['persona_id'])&&$_GET['persona_id']!=='-'){$where[]='e.persona_id=?';$params[]=(int)$_GET['persona_id'];}$w=implode(' AND ',$where);$total=(int)(DB::selectOne('SELECT COUNT(*) n FROM estancias e WHERE '.$w,$params)['n']??0);$rows=DB::select('SELECT e.* FROM estancias e WHERE '.$w.' ORDER BY e.fecha_ini ASC LIMIT '.$limit.' OFFSET '.$offset,$params);$data=[];foreach($rows as $e){$r=construye_ruta($e,$salidas);$data[]=[$esc($r['inicio']),$esc($r['fin']),persona_link((int)$r['persona_id'],$r['nombre']),(int)$r['num_camaras'],$esc($r['tiempo']),'<a href="javascript:;" onclick="abrirCamino('.(int)$r['inicio_id'].')">▶ Ver camino</a>'];}dt_json($request,$total,$total,$data);
}

dt_json($request, 0, 0, [], 'Listado no soportado');
} catch (Throwable $exception) {
    error_log('DataTables endpoint failed for table ' . $table . ': ' . $exception->getMessage());
    http_response_code(500);
    dt_json($request, 0, 0, [], 'No se pudo cargar el listado');
}
