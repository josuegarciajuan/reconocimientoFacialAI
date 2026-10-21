<?php
/**
 * brand.php — identidad de la instancia (multi-instancia).
 *
 * Los valores viven en config/rutas.php (desde .env). Aquí solo se construyen
 * URLs y textos para no repetir rutas en index/login/manifest/PWA.
 */

if (!defined("RF_BASE_PATH")) {
    require_once __DIR__ . "/../../config/rutas.php";
}

function rf_brand_name(): string
{
    return defined("RF_BRAND_NAME") ? RF_BRAND_NAME : "Mordor · El Ojo que Todo lo Ve";
}

function rf_brand_short(): string
{
    return defined("RF_BRAND_SHORT") ? RF_BRAND_SHORT : "Barad-dûr";
}

function rf_brand_topbar(): string
{
    return defined("RF_BRAND_TOPBAR") ? RF_BRAND_TOPBAR : "Panel de Vigilancia";
}

function rf_brand_sub(): string
{
    return defined("RF_BRAND_SUB") ? RF_BRAND_SUB : "El Ojo que Todo lo Ve";
}

function rf_brand_sub_pro(): string
{
    return defined("RF_BRAND_SUB_PRO") ? RF_BRAND_SUB_PRO : "Reconocimiento facial · Control de accesos";
}

function rf_brand_desc(): string
{
    return defined("RF_BRAND_DESC") ? RF_BRAND_DESC : "Mordor · Vigilancia y Control de Accesos por Reconocimiento Facial.";
}

function rf_brand_icon_url(int $size = 192): string
{
    $dir = defined("RF_BRAND_ICON_DIR") ? RF_BRAND_ICON_DIR : "files";
    $file = "icon-192.png";
    if ($size >= 512) {
        $file = defined("RF_BRAND_ICON_512") ? RF_BRAND_ICON_512 : "icon-512.png";
    } elseif ($size >= 192) {
        $file = defined("RF_BRAND_ICON_192") ? RF_BRAND_ICON_192 : "icon-192.png";
    }
    return RF_BASE_PATH . "admin/" . trim($dir, "/") . "/" . ltrim($file, "/");
}

function rf_brand_maskable_icon_url(): string
{
    $dir = defined("RF_BRAND_ICON_DIR") ? RF_BRAND_ICON_DIR : "files";
    $file = defined("RF_BRAND_ICON_MASKABLE") ? RF_BRAND_ICON_MASKABLE : "icon-512.png";
    return RF_BASE_PATH . "admin/" . trim($dir, "/") . "/" . ltrim($file, "/");
}

function rf_brand_login_logo(): string
{
    return defined("RF_BRAND_LOGIN_LOGO") ? RF_BRAND_LOGIN_LOGO : "./files_login/logo-sauron.png";
}


/** Ruta RELATIVA al manifiesto (./files/...). Evita depender del prefijo
 *  público y funciona igual bajo /reconocimientoFacial, /rf y /ojos. */
function rf_brand_icon_rel(int $size = 192): string
{
    $dir = defined("RF_BRAND_ICON_DIR") ? RF_BRAND_ICON_DIR : "files";
    $file = "icon-192.png";
    if ($size >= 512) {
        $file = defined("RF_BRAND_ICON_512") ? RF_BRAND_ICON_512 : "icon-512.png";
    } elseif ($size >= 192) {
        $file = defined("RF_BRAND_ICON_192") ? RF_BRAND_ICON_192 : "icon-192.png";
    }
    return "./" . trim($dir, "/") . "/" . ltrim($file, "/");
}

function rf_brand_maskable_icon_rel(): string
{
    $dir = defined("RF_BRAND_ICON_DIR") ? RF_BRAND_ICON_DIR : "files";
    $file = defined("RF_BRAND_ICON_MASKABLE") ? RF_BRAND_ICON_MASKABLE : "icon-512.png";
    return "./" . trim($dir, "/") . "/" . ltrim($file, "/");
}

function rf_brand_manifest_start(): string
{
    return RF_BASE_PATH . "admin/";
}

/** JSON que consume admin/files/pwa-install.js. */
function rf_brand_js(): array
{
    return [
        "instance" => defined("RF_INSTANCE") ? RF_INSTANCE : "laboral",
        "name" => rf_brand_short(),
        "fullName" => rf_brand_name(),
        "emoji" => defined("RF_BRAND_PWA_EMOJI") ? RF_BRAND_PWA_EMOJI : "👁️",
        "installTitle" => defined("RF_BRAND_INSTALL_TITLE") ? RF_BRAND_INSTALL_TITLE : "Instalar Mordor",
        "installSub" => defined("RF_BRAND_INSTALL_SUB") ? RF_BRAND_INSTALL_SUB : "El Ojo que Todo lo Ve, como una app.",
    ];
}
