<?php
/*
 * themeToggle.php — Conmutador de tema del panel (Mordor <-> Profesional).
 *
 * Se incluye en la topbar (admin/index.php) junto al buscador, las campanas
 * y el desplegable de local. Es un <button role="switch"> accesible:
 *   - aria-checked = "true"  -> tema profesional (Pro)
 *   - aria-checked = "false" -> tema Mordor (oscuro)
 *
 * El estado se persiste en localStorage ("rf-theme") + cookie ("rf_theme")
 * mediante admin/files/theme-switch.js. El servidor pinta el estado inicial
 * a partir de la cookie ($rf_tema, definido en index.php).
 *
 * El glifo es un diafragma/apertura de lente: la marca del modo profesional.
 */
$rf_pro = (($rf_tema ?? "pro") !== "mordor");
?>
<!-- BEGIN: Theme Toggle (Mordor / Profesional) -->
<button type="button" id="rf-theme-toggle" class="rf-theme-toggle intro-x"
        role="switch" aria-checked="<?= $rf_pro ? "true" : "false"; ?>"
        aria-label="<?= $rf_pro ? "Cambiar al tema Mordor" : "Cambiar al tema profesional"; ?>"
        title="<?= $rf_pro ? "Tema actual: Profesional. Cambiar a Mordor" : "Tema actual: Mordor. Cambiar a Profesional"; ?>">
    <svg class="rf-theme-toggle__aperture" viewBox="0 0 24 24" fill="none"
         stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"
         aria-hidden="true" focusable="false">
        <circle cx="12" cy="12" r="9"/>
        <path d="M15.5 12 L21 12"/>
        <path d="M13.75 15.03 L16.5 19.79"/>
        <path d="M10.25 15.03 L7.5 19.79"/>
        <path d="M8.5 12 L3 12"/>
        <path d="M10.25 8.97 L7.5 4.21"/>
        <path d="M13.75 8.97 L16.5 4.21"/>
        <circle cx="12" cy="12" r="1.6"/>
    </svg>
    <span class="rf-theme-toggle__label">Tema</span>
</button>
<!-- END: Theme Toggle -->
