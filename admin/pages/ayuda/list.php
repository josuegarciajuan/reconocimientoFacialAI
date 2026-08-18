<?php

/* 
 * Ayuda — El Concilio (construido desde cero).
 * Guía práctica de cada sección del panel + preguntas frecuentes + contacto.
 * Estética coherente con el tema oscuro Mordor: usa box/report-box y las
 * variables --mordor-* de custom.css. Sin emails ni URLs inventadas.
 */

require_once __DIR__ . "/../../../libs/db.php";

$local_id = (int)($_SESSION["local_id"] ?? 0);
$usuario = (string)($_SESSION["user"] ?? "");
$fortaleza = "";
if ($local_id > 0) {
    $loc = DB::selectOne("SELECT nombre FROM locales WHERE id = ?", [$local_id]);
    if ($loc) {
        $fortaleza = (string)$loc["nombre"];
    }
}

$diagnostico = "Usuario: " . ($usuario !== "" ? $usuario : "—")
    . "\nFortaleza: " . ($fortaleza !== "" ? $fortaleza : "—")
    . "\nURL: " . ($_SERVER["REQUEST_URI"] ?? "—")
    . "\nFecha: " . date("Y-m-d H:i");
?>

<style>
    /* --- Tarjetas de guía (misma familia que .cam-card) --- */
    .ayuda-card {
        display: flex;
        flex-direction: column;
        gap: 0.6rem;
        height: 100%;
        border: 1px solid rgba(201, 162, 39, 0.16);
        transition: transform 0.22s ease, border-color 0.22s ease, box-shadow 0.22s ease;
    }
    .ayuda-card:hover,
    .ayuda-card:focus-visible {
        transform: translateY(-3px);
        border-color: rgba(201, 162, 39, 0.5);
        box-shadow: 0 16px 34px -16px rgba(0, 0, 0, 0.85), 0 0 0 1px rgba(201, 162, 39, 0.28);
    }
    .ayuda-card:focus-visible {
        outline: 2px solid rgba(255, 90, 31, 0.8);
        outline-offset: 2px;
    }
    .ayuda-card__head {
        display: flex;
        align-items: center;
        gap: 0.65rem;
    }
    .ayuda-card__emoji {
        font-size: 1.45rem;
        line-height: 1;
    }
    .ayuda-card__title {
        font-family: "Cinzel", serif;
        font-weight: 700;
        font-size: 0.98rem;
        color: var(--mordor-ceniza);
    }
    .ayuda-card__text {
        font-size: 0.84rem;
        line-height: 1.55;
        color: var(--mordor-humo);
    }
    .ayuda-card__go {
        margin-top: auto;
        display: inline-flex;
        align-items: center;
        gap: 0.3rem;
        font-size: 0.72rem;
        font-weight: 700;
        letter-spacing: 0.06em;
        text-transform: uppercase;
        color: var(--mordor-oro);
    }

    /* --- FAQ: acordeón nativo (accesible por teclado, sin JS) --- */
    .ayuda-faq details {
        border: 1px solid rgba(201, 162, 39, 0.16);
        border-radius: 0.6rem;
        background: rgba(0, 0, 0, 0.18);
        margin-bottom: 0.7rem;
        overflow: hidden;
        transition: border-color 0.2s ease;
    }
    .ayuda-faq details[open] {
        border-color: rgba(201, 162, 39, 0.4);
    }
    .ayuda-faq summary {
        display: flex;
        align-items: center;
        gap: 0.6rem;
        cursor: pointer;
        padding: 0.85rem 1rem;
        font-weight: 600;
        font-size: 0.92rem;
        color: var(--mordor-ceniza);
        list-style: none;
    }
    .ayuda-faq summary::-webkit-details-marker {
        display: none;
    }
    .ayuda-faq summary::after {
        content: "⌄";
        margin-left: auto;
        font-size: 1.15rem;
        line-height: 1;
        color: var(--mordor-oro);
        transition: transform 0.2s ease;
    }
    .ayuda-faq details[open] summary::after {
        transform: rotate(180deg);
    }
    .ayuda-faq summary:focus-visible {
        outline: 2px solid rgba(255, 90, 31, 0.8);
        outline-offset: -2px;
        border-radius: 0.6rem;
    }
    .ayuda-faq__answer {
        padding: 0 1rem 0.95rem;
        font-size: 0.86rem;
        line-height: 1.6;
        color: var(--mordor-humo);
    }
    .ayuda-faq__answer a {
        color: var(--mordor-oro);
        font-weight: 600;
        text-decoration: underline;
        text-decoration-color: rgba(201, 162, 39, 0.35);
        text-underline-offset: 3px;
    }
    .ayuda-faq__answer a:hover {
        color: var(--mordor-brasa);
    }

    /* --- Bloque de contacto / diagnóstico --- */
    .ayuda-contact__title {
        font-family: "Cinzel", serif;
        font-weight: 700;
        font-size: 1rem;
        color: var(--mordor-ceniza);
    }
    .ayuda-contact__text {
        font-size: 0.86rem;
        line-height: 1.6;
        color: var(--mordor-humo);
        margin-top: 0.35rem;
        max-width: 65ch;
    }
    #ayuda-diagnostico {
        width: 100%;
        min-height: 4.5rem;
        margin-top: 0.9rem;
        padding: 0.6rem 0.75rem;
        border-radius: 0.5rem;
        font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
        font-size: 0.78rem;
        line-height: 1.5;
        resize: vertical;
        background-color: rgba(0, 0, 0, 0.35);
        border: 1px solid rgba(201, 162, 39, 0.25);
        color: var(--mordor-ceniza);
    }
    #ayuda-diagnostico:focus {
        border-color: rgba(255, 90, 31, 0.55);
        outline: none;
        box-shadow: 0 0 0 3px rgba(255, 90, 31, 0.16);
    }

    @media (prefers-reduced-motion: reduce) {
        .ayuda-card,
        .ayuda-faq details,
        .ayuda-faq summary::after {
            transition: none;
        }
    }
</style>

<div class="intro-y flex flex-col sm:flex-row items-center mt-8">
    <h2 class="text-lg font-medium mr-auto">El Concilio · Ayuda</h2>
    <div class="w-full sm:w-auto flex mt-4 sm:mt-0">
        <a href="?page=dash" class="button text-white bg-theme-1 shadow-md mr-2">👁️ Ir a La Torre</a>
    </div>
</div>

<!-- Guía del Reino: qué se hace en cada sección y cómo -->
<div class="intro-y block sm:flex items-center h-10 mt-8">
    <h2 class="text-lg font-medium truncate mr-5">🗺️ Guía del Reino</h2>
</div>

<div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4 mt-5">

    <a href="?page=dash" class="ayuda-card box p-5 intro-y block">
        <div class="ayuda-card__head"><span class="ayuda-card__emoji" aria-hidden="true">👁️</span><span class="ayuda-card__title">La Torre · Dashboard</span></div>
        <p class="ayuda-card__text">Resumen del reino en una mirada: almas en la fortaleza, visitas de hoy, medias diarias y visitantes recurrentes. El Mapa de Asedio compara el periodo elegido con el anterior.</p>
        <span class="ayuda-card__go">Entrar →</span>
    </a>

    <a href="?page=locales" class="ayuda-card box p-5 intro-y block">
        <div class="ayuda-card__head"><span class="ayuda-card__emoji" aria-hidden="true">🏰</span><span class="ayuda-card__title">Fortalezas · Locales</span></div>
        <p class="ayuda-card__text">Cada fortaleza es un local con sus cámaras, su plano y su aforo. Solo los administradores pueden crearlas o editarlas; desde aquí se gestiona también el máximo de almas permitido.</p>
        <span class="ayuda-card__go">Entrar →</span>
    </a>

    <a href="?page=visitantes" class="ayuda-card box p-5 intro-y block">
        <div class="ayuda-card__head"><span class="ayuda-card__emoji" aria-hidden="true">🧙</span><span class="ayuda-card__title">Pueblos · Visitantes</span></div>
        <p class="ayuda-card__text">Registra visitantes con un vídeo corto para crear su identidad facial. El listado permite buscar por nombre o código y filtrar por cámara y fechas.</p>
        <span class="ayuda-card__go">Entrar →</span>
    </a>

    <a href="?page=accesos" class="ayuda-card box p-5 intro-y block">
        <div class="ayuda-card__head"><span class="ayuda-card__emoji" aria-hidden="true">⚔️</span><span class="ayuda-card__title">Movimientos · Accesos</span></div>
        <p class="ayuda-card__text">Todas las entradas y salidas registradas por las cámaras de puerta: persona, cámara y hora exacta. Filtra por periodo o por cámara para investigar un caso.</p>
        <span class="ayuda-card__go">Entrar →</span>
    </a>

    <a href="?page=lineas" class="ayuda-card box p-5 intro-y block">
        <div class="ayuda-card__head"><span class="ayuda-card__emoji" aria-hidden="true">📐</span><span class="ayuda-card__title">Líneas</span></div>
        <p class="ayuda-card__text">Dibuja sobre el plano las líneas que delimitan pasos y zonas. Cada línea se asocia a una cámara; aquí consultas los cruces registrados, filtrados por cámara.</p>
        <span class="ayuda-card__go">Entrar →</span>
    </a>

    <a href="?page=rutas" class="ayuda-card box p-5 intro-y block">
        <div class="ayuda-card__head"><span class="ayuda-card__emoji" aria-hidden="true">🗺️</span><span class="ayuda-card__title">Caminos · Rutas</span></div>
        <p class="ayuda-card__text">Coloca las cámaras sobre el plano y enlázalas entre sí para reconstruir recorridos: las rutas ordenan los pasos de cada persona por la fortaleza.</p>
        <span class="ayuda-card__go">Entrar →</span>
    </a>

    <a href="?page=config" class="ayuda-card box p-5 intro-y block">
        <div class="ayuda-card__head"><span class="ayuda-card__emoji" aria-hidden="true">⚒️</span><span class="ayuda-card__title">La Forja · Configuración</span></div>
        <p class="ayuda-card__text">Ajustes generales del panel y los planos: sensibilidad de detección, parámetros de vídeo y comportamiento de las cámaras. Cambia con cuidado: afecta a todo el reino.</p>
        <span class="ayuda-card__go">Entrar →</span>
    </a>

    <a href="?page=camaras" class="ayuda-card box p-5 intro-y block">
        <div class="ayuda-card__head"><span class="ayuda-card__emoji" aria-hidden="true">📡</span><span class="ayuda-card__title">El Ojo en Vivo · Cámaras</span></div>
        <p class="ayuda-card__text">Cada cámara con su snapshot en vivo, actualizado en segundo plano. Un clic abre el stream en tiempo real; si no hay stream, se muestra el último snapshot guardado.</p>
        <span class="ayuda-card__go">Entrar →</span>
    </a>

    <a href="?page=fichajes" class="ayuda-card box p-5 intro-y block">
        <div class="ayuda-card__head"><span class="ayuda-card__emoji" aria-hidden="true">⏳</span><span class="ayuda-card__title">Fichajes</span></div>
        <p class="ayuda-card__text">Entradas y salidas de los trabajadores agrupadas por persona y día: la entrada es el primer cruce por cámara de puerta y la salida el último por cámara de salida.</p>
        <span class="ayuda-card__go">Entrar →</span>
    </a>

</div>

<!-- Preguntas frecuentes -->
<div class="intro-y block sm:flex items-center h-10 mt-8">
    <h2 class="text-lg font-medium truncate mr-5">🧙 Preguntas Frecuentes</h2>
</div>

<div class="intro-y box p-5 mt-5 ayuda-faq">

    <details>
        <summary>¿Cómo veo las cámaras en directo?</summary>
        <p class="ayuda-faq__answer">Entra en <a href="?page=camaras">El Ojo en Vivo</a> y haz clic en la cámara que quieras ver: se abre su stream en tiempo real. Si el stream no está disponible, se muestra automáticamente el último snapshot guardado. Las miniaturas se refrescan solas cada pocos segundos.</p>
    </details>

    <details>
        <summary>¿Cómo registro un visitante nuevo?</summary>
        <p class="ayuda-faq__answer">Ve a <a href="?page=visitantes">Pueblos</a>, pulsa el botón Registrar y graba un vídeo corto siguiendo las indicaciones: el sistema extrae la identidad facial. Si la cara ya existe en la fortaleza, te lo avisará para evitar duplicados.</p>
    </details>

    <details>
        <summary>¿Cómo interpreto los movimientos?</summary>
        <p class="ayuda-faq__answer"><a href="?page=accesos">Movimientos</a> lista cada entrada y salida registrada por las cámaras de puerta: quién fue, por qué cámara y a qué hora. Usa los filtros de fechas y de cámara para acotar la búsqueda, o el buscador para localizar a una persona concreta.</p>
    </details>

    <details>
        <summary>¿Cómo cambio el aforo de la fortaleza?</summary>
        <p class="ayuda-faq__answer">En <a href="?page=dash">La Torre</a>, la primera tarjeta (Almas en la Fortaleza) tiene un campo junto al indicador en vivo: escribe el nuevo máximo y pulsa Actualizar. El cambio se aplica de inmediato.</p>
    </details>

    <details>
        <summary>¿Cómo configuro el plano, las líneas y las rutas?</summary>
        <p class="ayuda-faq__answer">En <a href="?page=lineas">Líneas</a> dibujas sobre el plano los pasos o zonas que vigila cada cámara; en <a href="?page=rutas">Caminos</a> colocas y enlazas las cámaras para reconstruir recorridos. Los ajustes generales del panel (sensibilidad, vídeo…) están en <a href="?page=config">La Forja</a>.</p>
    </details>

    <details>
        <summary>¿Qué hago si una cámara no detecta bien?</summary>
        <p class="ayuda-faq__answer">Comprueba primero que la cámara está encendida en <a href="?page=camaras">El Ojo en Vivo</a> y que la imagen es nítida: limpia el objetivo y revisa la orientación. Si sigue fallando, revisa la sensibilidad de detección en <a href="?page=config">La Forja</a> o contacta con el administrador.</p>
    </details>

</div>

<!-- Contacto -->
<div class="intro-y block sm:flex items-center h-10 mt-8">
    <h2 class="text-lg font-medium truncate mr-5">🛡️ Último Recurso</h2>
</div>

<div class="intro-y box p-5 mt-5">
    <div class="flex flex-col sm:flex-row sm:items-center sm:gap-4">
        <div class="flex-1">
            <h3 class="ayuda-contact__title">¿Aún no lo resuelves?</h3>
            <p class="ayuda-contact__text">Si el problema persiste, contacta con el administrador. Incluye los datos de sesión de abajo: permiten localizar tu fortaleza y el origen del fallo con rapidez.</p>
        </div>
        <div class="flex-none mt-4 sm:mt-0">
            <button type="button" class="button text-white bg-theme-1 shadow-md" onclick="rfCopiarDiagnostico()">📋 Copiar datos de sesión</button>
        </div>
    </div>
    <textarea id="ayuda-diagnostico" readonly aria-label="Datos de sesión para enviar al administrador"><?= htmlspecialchars($diagnostico, ENT_QUOTES); ?></textarea>
</div>

<script>
    // Copia los datos de diagnóstico al portapapeles (usa rfToast de ui-common.js).
    function rfCopiarDiagnostico() {
        var area = document.getElementById("ayuda-diagnostico");
        if (!area) { return; }
        area.focus();
        area.select();
        area.setSelectionRange(0, area.value.length);
        var copiadoLegacy = false;
        try {
            copiadoLegacy = document.execCommand("copy");
        } catch (e) {
            copiadoLegacy = false;
        }
        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(area.value).then(
                function () { rfToast("Datos de sesión copiados", "ok"); },
                function () { rfToast(copiadoLegacy ? "Datos de sesión copiados" : "Selecciona y copia el texto a mano", copiadoLegacy ? "ok" : "err"); }
            );
            return;
        }
        rfToast(copiadoLegacy ? "Datos de sesión copiados" : "Selecciona y copia el texto a mano", copiadoLegacy ? "ok" : "err");
    }
</script>
