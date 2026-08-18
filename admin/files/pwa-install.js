/**
 * pwa-install.js — Mordor Panel (Barad-dûr)
 * - Registra el Service Worker (solo HTTPS)
 * - Maneja el evento beforeinstallprompt
 * - Muestra modal central de instalación post-login (primera visita)
 * - Cooldown de 7 días en localStorage
 */
(function () {
  'use strict';

  // ── Service Worker registration (solo en HTTPS; sin SW la app sigue funcionando) ──
  if ('serviceWorker' in navigator && location.protocol === 'https:') {
    navigator.serviceWorker.register('./sw.js?v=1', { scope: './' }).catch(function () {
      // Fallo silencioso: la app funciona sin SW
    });
  }

  // ── PWA Install Prompt ──
  var deferredPrompt = null;
  var installPromptShown = false;

  window.addEventListener('beforeinstallprompt', function (e) {
    e.preventDefault();
    deferredPrompt = e;
  });

  // Detecta si ya está instalada como PWA
  function isStandalone() {
    return window.matchMedia('(display-mode: standalone)').matches ||
           window.matchMedia('(display-mode: minimal-ui)').matches ||
           navigator.standalone ||
           document.referrer.indexOf('android-app://') === 0;
  }

  // Comprueba si el aviso se mostró en los últimos 7 días
  function wasPromptedRecently() {
    try {
      var ts = localStorage.getItem('pwa_install_prompt_ts');
      if (ts) {
        var age = Date.now() - parseInt(ts, 10);
        return age < 7 * 24 * 60 * 60 * 1000; // 7 días
      }
    } catch (e) {}
    return false;
  }

  // Registra que el aviso ya se mostró
  function markPrompted() {
    try {
      localStorage.setItem('pwa_install_prompt_ts', String(Date.now()));
    } catch (e) {}
  }

  // Crea y muestra el modal central de instalación
  function showInstallModal() {
    if (installPromptShown) return;
    installPromptShown = true;

    var overlay = document.createElement('div');
    overlay.className = 'pwa-install-overlay';
    overlay.setAttribute('role', 'dialog');
    overlay.setAttribute('aria-modal', 'true');
    overlay.setAttribute('aria-labelledby', 'pwaTitle');

    overlay.innerHTML =
      '<div class="pwa-install-card">' +
        '<div class="pwa-icon">👁️</div>' +
        '<h2 id="pwaTitle">Instalar Mordor</h2>' +
        '<p class="pwa-sub">El Ojo que Todo lo Ve, como una app: sin barra del navegador, más rápido y siempre a mano en tu escritorio.</p>' +
        '<button class="pwa-btn-install" id="pwaInstallBtn">' +
          '<span class="pwa-btn-icon">⬇️</span> Instalar App' +
        '</button>' +
        '<button class="pwa-btn-continue" id="pwaContinueBtn">' +
          'Continuar en el navegador' +
        '</button>' +
        '<p class="pwa-manual-hint">' +
          'También puedes instalarla desde el menú <strong>⋮</strong> → <strong>Añadir a pantalla de inicio</strong>' +
        '</p>' +
      '</div>';

    // Estilos del modal (se inyectan aquí para no tocar app.css/custom.css)
    var style = document.createElement('style');
    style.textContent =
      '.pwa-install-overlay{position:fixed;inset:0;background:rgba(11,10,14,.92);backdrop-filter:blur(12px);' +
      '-webkit-backdrop-filter:blur(12px);z-index:20000;display:flex;align-items:center;justify-content:center;' +
      'padding:20px;animation:pwaFadeIn .3s ease}' +
      '@keyframes pwaFadeIn{from{opacity:0}to{opacity:1}}' +
      '.pwa-install-card{background:linear-gradient(160deg,#16121a,#1d1820);border:1px solid rgba(201,162,39,.25);' +
      'border-radius:24px;padding:36px 28px 28px;max-width:380px;width:100%;text-align:center;' +
      'box-shadow:0 20px 60px rgba(0,0,0,.6),0 0 0 1px rgba(255,255,255,.04);' +
      'animation:pwaSlideUp .4s cubic-bezier(.16,1,.3,1)}' +
      '@keyframes pwaSlideUp{from{opacity:0;transform:translateY(30px) scale(.96)}' +
      'to{opacity:1;transform:translateY(0) scale(1)}}' +
      '.pwa-install-card .pwa-icon{font-size:3rem;margin-bottom:8px}' +
      '.pwa-install-card h2{font-size:1.3rem;font-weight:700;color:#f6e6ae;margin:0 0 8px;' +
      'font-family:"Cinzel",serif;letter-spacing:.02em}' +
      '.pwa-install-card .pwa-sub{font-size:.85rem;color:#8a8078;line-height:1.5;margin:0 0 24px}' +
      '.pwa-btn-install{display:flex;align-items:center;justify-content:center;gap:8px;' +
      'width:100%;padding:14px;border:none;border-radius:999px;cursor:pointer;' +
      'font-size:.95rem;font-weight:700;font-family:inherit;' +
      'background:linear-gradient(135deg,#ff5a1f,#e03c00);color:#fff;' +
      'box-shadow:0 4px 20px rgba(255,90,31,.3);' +
      'transition:transform .2s,box-shadow .2s;margin-bottom:10px}' +
      '.pwa-btn-install:hover{transform:translateY(-2px);box-shadow:0 8px 28px rgba(255,90,31,.45)}' +
      '.pwa-btn-continue{display:block;width:100%;padding:10px;border:1px solid rgba(255,255,255,.1);' +
      'border-radius:999px;cursor:pointer;font-size:.82rem;font-weight:500;font-family:inherit;' +
      'background:transparent;color:#8a8078;transition:color .2s,background .2s;margin-bottom:14px}' +
      '.pwa-btn-continue:hover{color:#d8d0c4;background:rgba(255,255,255,.05)}' +
      '.pwa-manual-hint{font-size:.72rem;color:rgba(255,255,255,.3);line-height:1.5;margin:0}' +
      '.pwa-btn-icon{font-size:1rem}';

    document.head.appendChild(style);
    document.body.appendChild(overlay);

    // Botón Instalar → prompt nativo del navegador
    document.getElementById('pwaInstallBtn').addEventListener('click', function () {
      if (deferredPrompt) {
        deferredPrompt.prompt();
        deferredPrompt.userChoice.then(function (result) {
          if (result.outcome === 'accepted') {
            document.body.removeChild(overlay);
            style.parentNode.removeChild(style);
          }
          deferredPrompt = null;
        });
      } else {
        // Fallback: sin prompt nativo, resaltar la ayuda manual
        var hint = overlay.querySelector('.pwa-manual-hint');
        if (hint) hint.style.color = '#c9a227';
      }
    });

    // Botón Continuar → cierra y respeta el cooldown
    document.getElementById('pwaContinueBtn').addEventListener('click', function () {
      markPrompted();
      document.body.removeChild(overlay);
      style.parentNode.removeChild(style);
    });
  }

  // Comprobación post-login
  function checkInstallPrompt() {
    if (isStandalone()) return;       // Ya instalada
    if (!deferredPrompt) return;      // Navegador sin soporte de prompt
    if (wasPromptedRecently()) return; // Ya se mostró hace poco

    // Pequeña espera para que la página se pinte primero
    setTimeout(function () {
      showInstallModal();
    }, 1500);
  }

  // Al instalarse, limpiar estado
  window.addEventListener('appinstalled', function () {
    deferredPrompt = null;
    try {
      localStorage.setItem('pwa_install_prompt_ts', String(Date.now()));
    } catch (e) {}
    var overlay = document.querySelector('.pwa-install-overlay');
    if (overlay && overlay.parentNode) overlay.parentNode.removeChild(overlay);
  });

  // ── Ejecutar al cargar la página ──
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', checkInstallPrompt);
  } else {
    checkInstallPrompt();
  }
})();
