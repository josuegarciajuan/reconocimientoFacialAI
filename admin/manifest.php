<?php
/**
 * Manifiesto PWA por instancia.
 *
 * Se sirve como `application/manifest+json` y usa la identidad de
 * admin/includes/brand.php (RF_BRAND_*). La ruta pública termina en
 * `manifest.php`; el panel-gate la deja pasar sin cookie para que Chrome pueda
 * instalar la app.
 */
require_once __DIR__ . '/includes/brand.php';

header('Content-Type: application/manifest+json; charset=utf-8');
header('Cache-Control: public, max-age=300');

$start = rf_brand_manifest_start();
$icons = [
    [
        'src' => rf_brand_icon_url(192),
        'sizes' => '192x192',
        'type' => 'image/png',
        'purpose' => 'any',
    ],
    [
        'src' => rf_brand_icon_url(512),
        'sizes' => '512x512',
        'type' => 'image/png',
        'purpose' => 'any',
    ],
    [
        'src' => rf_brand_maskable_icon_url(),
        'sizes' => '512x512',
        'type' => 'image/png',
        'purpose' => 'maskable',
    ],
];

echo json_encode([
    'id' => $start,
    'name' => rf_brand_name(),
    'short_name' => rf_brand_short(),
    'description' => rf_brand_desc(),
    'start_url' => $start,
    'scope' => $start,
    'display' => 'standalone',
    'display_override' => ['standalone', 'minimal-ui'],
    'background_color' => defined('RF_BRAND_BG_COLOR') ? RF_BRAND_BG_COLOR : '#0b0a0e',
    'theme_color' => defined('RF_BRAND_THEME_COLOR') ? RF_BRAND_THEME_COLOR : '#16121a',
    'orientation' => 'portrait',
    'lang' => 'es-ES',
    'icons' => $icons,
], JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES | JSON_PRETTY_PRINT);
