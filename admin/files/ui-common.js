/* ============================================================
   Barad-dûr · UI común (secciones) — helper responsivo global
   Requiere jQuery (cargado en el layout) y el plugin de modales
   de Midone (app.js). Patrones:
   - rfToast(msg, tipo)            feedback visual no invasivo
   - rfLightbox(url, titulo)       visor de imagen (lightbox)
   - rfCamModal(id, urlStream, urlSnapshot, titulo)  modal de stream MJPEG
   - rfRefrescarSnapshots()        refresco periódico de snapshots
   ============================================================ */

(function (win, doc, $) {
  "use strict";

  /* ------------------------------------------------------------------ */
  /* Apertura de modales Midone                                          */
  /* El plugin de modales vive en el jQuery interno del bundle app.js y   */
  /* se engancha por delegación en body (a[data-toggle="modal"]).        */
  /* El panel carga además un jQuery 1.4.4 global SIN el plugin, así que  */
  /* en lugar de $().modal('show') reutilizamos el mecanismo de la app:   */
  /* un disparador <a data-toggle="modal" data-target="#id"> clicado.     */
  /* ------------------------------------------------------------------ */
  function rfAbrirModal(id) {
    var modal = doc.getElementById(id);
    if (!modal) {
      return;
    }
    var trigger = doc.getElementById(id + "-trigger");
    if (!trigger) {
      trigger = doc.createElement("a");
      trigger.id = id + "-trigger";
      trigger.href = "javascript:;";
      trigger.setAttribute("data-toggle", "modal");
      trigger.setAttribute("data-target", "#" + id);
      trigger.style.display = "none";
      doc.body.appendChild(trigger);
    }
    try {
      trigger.click();
    } catch (e) {
      /* nada que hacer si el mecanismo de la app no está disponible */
    }
  }

  /* ------------------------------------------------------------------ */
  /* Toast minimalista (top-right, auto-dismiss)                         */
  /* ------------------------------------------------------------------ */
  var toastTimer = null;

  function rfToast(mensaje, tipo) {
    tipo = tipo || "ok";
    var toast = doc.getElementById("rf-toast");
    if (!toast) {
      toast = doc.createElement("div");
      toast.id = "rf-toast";
      toast.className = "rf-toast";
      toast.innerHTML =
        '<span class="rf-toast__icon">' +
        '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">' +
        '<polyline points="20 6 9 17 4 12"></polyline></svg></span>' +
        '<span class="rf-toast__msg"></span>';
      doc.body.appendChild(toast);
    }
    toast.className = "rf-toast rf-toast--" + tipo;
    toast.querySelector(".rf-toast__msg").textContent = mensaje;
    // forzar reflow para reiniciar la transición
    void toast.offsetWidth;
    toast.classList.add("rf-toast--show");
    if (toastTimer) {
      clearTimeout(toastTimer);
    }
    toastTimer = setTimeout(function () {
      toast.classList.remove("rf-toast--show");
    }, 2600);
  }

  /* ------------------------------------------------------------------ */
  /* Lightbox: modal Midone con imagen a pantalla (max 72vh)             */
  /* ------------------------------------------------------------------ */
  function rfLightbox(url, titulo) {
    titulo = titulo || "Imagen";
    var modal = doc.getElementById("rf-lightbox-modal");
    if (!modal) {
      modal = doc.createElement("div");
      modal.id = "rf-lightbox-modal";
      modal.className = "modal";
      modal.setAttribute("role", "dialog");
      modal.setAttribute("aria-modal", "true");
      modal.innerHTML =
        '<div class="modal__content box p-5">' +
        '<div class="flex items-center mb-4">' +
        '<h3 class="media-modal__title mr-auto truncate"></h3>' +
        '<a href="javascript:;" data-dismiss="modal" class="button button--sm text-white bg-theme-6 ml-3">Cerrar</a>' +
        "</div>" +
        '<img class="media-modal__img" alt="" src="">' +
        "</div>";
      doc.body.appendChild(modal);
    }
    modal.querySelector(".media-modal__title").textContent = titulo;
    var img = modal.querySelector(".media-modal__img");
    img.setAttribute("alt", titulo);
    img.src = url;
    // Auto-zoom hacia la cara: las fotos de caras_procesadas llevan la cara
    // centrada (recorte simétrico + SR), así que el modo cover las amplía.
    if (url.indexOf("caras_procesadas/") !== -1) {
      img.classList.add("media-modal__img--zoom");
    } else {
      img.classList.remove("media-modal__img--zoom");
    }
    rfAbrirModal(modal.id);
  }

  /* ------------------------------------------------------------------ */
  /* Modal de cámara: stream MJPEG con fallback a snapshot               */
  /* ------------------------------------------------------------------ */

  /* 1x1 transparente: al cerrar el modal se apunta aquí para abortar la
     conexión multipart/x-mixed-replace del stream. */
  var RF_IMG_VACIO =
    "data:image/gif;base64,R0lGODlhAQABAAAAACH5BAEKAAEALAAAAAABAAEAAAICTAEAOw==";

  /* Corta el stream del modal (sin tocar los handlers del siguiente open). */
  function rfPararStreamCamara(modal) {
    if (!modal) {
      return;
    }
    var im = modal.querySelector(".live-modal__img");
    if (!im) {
      return;
    }
    im.onload = null;
    im.onerror = null;
    im.src = RF_IMG_VACIO;
  }

  function rfCamModal(id, streamUrl, snapshotUrl, titulo) {
    titulo = titulo || "Cámara";
    var modal = doc.getElementById("rf-cam-modal");
    if (!modal) {
      modal = doc.createElement("div");
      modal.id = "rf-cam-modal";
      modal.className = "modal";
      modal.setAttribute("role", "dialog");
      modal.setAttribute("aria-modal", "true");
      modal.innerHTML =
        '<div class="modal__content box p-4 sm:p-5">' +
        '<div class="flex items-center mb-4">' +
        '<span class="live-dot" aria-hidden="true"></span>' +
        '<h3 class="media-modal__title mr-auto truncate"></h3>' +
        '<a href="javascript:;" data-dismiss="modal" class="button button--sm text-white bg-theme-6 ml-3">Cerrar</a>' +
        "</div>" +
        '<img class="live-modal__img" alt="">' +
        '<div class="stream-detail__meta">' +
        '<span class="text-xs text-gray-500 dark:text-gray-600">Stream en directo (MJPEG)</span>' +
        '<span class="ml-auto text-xs" id="rf-cam-hint"></span>' +
        "</div>" +
        "</div>";
      doc.body.appendChild(modal);

      /* Al cerrar (botón, clic fuera o Escape) se corta el MJPEG: si no, el
         <img> oculto seguía suscrito al ffmpeg de rf-live y podía pintar
         frames de la cámara anterior al abrir otra. Además libera el ffmpeg. */
      if (win.MutationObserver) {
        var obs = new win.MutationObserver(function () {
          if (!modal.classList.contains("show")) {
            rfPararStreamCamara(modal);
          }
        });
        obs.observe(modal, { attributes: true, attributeFilter: ["class"] });
      }
    }

    modal.querySelector(".media-modal__title").textContent = titulo;
    var hint = doc.getElementById("rf-cam-hint");
    if (hint) {
      hint.textContent = "";
    }

    /* <img> NUEVO por apertura: reasignar src sobre el mismo nodo dejaba viva
       la conexión multipart anterior en varios navegadores (se veía otra
       cámara, distinta en cada clic). Reemplazarlo garantiza el aborto. */
    var viejo = modal.querySelector(".live-modal__img");
    var img = doc.createElement("img");
    img.className = "live-modal__img";
    img.setAttribute("alt", titulo);
    if (viejo && viejo.parentNode) {
      rfPararStreamCamara(modal);
      viejo.parentNode.replaceChild(img, viejo);
    } else {
      (modal.querySelector(".modal__content") || modal).appendChild(img);
    }

    img.onerror = function () {
      // El stream no está disponible: caer al último snapshot
      img.onerror = null;
      img.src = snapshotUrl;
      if (hint) {
        hint.textContent = "Sin stream: mostrando último snapshot";
      }
    };
    // Cache-buster: evita reutilizar una respuesta multipart anterior.
    img.src = streamUrl + (streamUrl.indexOf("?") === -1 ? "?" : "&") + "_=" + Date.now();

    rfAbrirModal(modal.id);
  }

  /* ------------------------------------------------------------------ */
  /* Modal de vídeo: reproducción de un vídeo de movimiento (MP4 H.264)  */
  /* rfVideoModal(id, url, poster, titulo, personaId, personaNombre)     */
  /*   - url:    video.php?id=<id> (stream con Range)                    */
  /*   - poster: video.php?id=<id>&poster=1 (miniatura, opcional)        */
  /*   - personaId/personaNombre: si el vídeo está vinculado a una       */
  /*     persona, se muestra su enlace en el pie del modal (vínculo      */
  /*     automático vídeos ↔ personas).                                  */
  /* ------------------------------------------------------------------ */
  function rfVideoModal(id, url, poster, titulo, personaId, personaNombre) {
    titulo = titulo || "Vídeo";
    var modal = doc.getElementById("rf-video-modal");
    if (!modal) {
      modal = doc.createElement("div");
      modal.id = "rf-video-modal";
      modal.className = "modal";
      modal.setAttribute("role", "dialog");
      modal.setAttribute("aria-modal", "true");
      modal.innerHTML =
        '<div class="modal__content box p-4 sm:p-5">' +
        '<div class="flex items-center mb-4">' +
        '<h3 class="media-modal__title mr-auto truncate"></h3>' +
        '<a href="javascript:;" data-dismiss="modal" class="button button--sm text-white bg-theme-6 ml-3">Cerrar</a>' +
        "</div>" +
        '<video class="rf-video-modal__player" controls autoplay playsinline preload="metadata"></video>' +
        '<div class="rf-video-modal__personas mt-3 text-sm"></div>' +
        "</div>";
      doc.body.appendChild(modal);
    }
    modal.querySelector(".media-modal__title").textContent = titulo;
    var video = modal.querySelector(".rf-video-modal__player");
    video.poster = poster || "";
    video.innerHTML =
      '<source src="' + url + '" type="video/mp4">' +
      "Tu navegador no soporta la etiqueta de video.";
    video.load();
    var pie = modal.querySelector(".rf-video-modal__personas");
    if (pie) {
      if (personaId) {
        var nombre = personaNombre || "persona " + personaId;
        pie.innerHTML =
          '<a href="?page=visitantes&mode=editar&id=' + personaId +
          '" class="inline-flex items-center gap-1 text-theme-1 font-medium hover:underline">' +
          "👤 Ver persona: " + nombre + "</a>";
      } else {
        pie.innerHTML = "";
      }
    }
    rfAbrirModal(modal.id);
  }

  /* ------------------------------------------------------------------ */
  /* Refresco de snapshots por mtime (sin re-descargar lo que no cambia)  */
  /* Sondea estado_ajax.php y solo re-apunta el src de la tarjeta cuyo    */
  /* snapshot cambió, con ?v=<mtime> (URL cacheable). Si nada cambió, no  */
  /* se transfiere ninguna imagen.                                        */
  /* ------------------------------------------------------------------ */
  function rfRefrescarSnapshots(intervaloMs) {
    intervaloMs = intervaloMs || 5000;
    var endpoint = "pages/camaras/estado_ajax.php";

    function ids() {
      var out = [];
      doc.querySelectorAll(".cam-card[data-camara-id]").forEach(function (card) {
        var id = card.getAttribute("data-camara-id");
        if (id) { out.push(id); }
      });
      return out;
    }

    function aplicar(mapa) {
      doc.querySelectorAll(".cam-card__img[data-snapshot]").forEach(function (img) {
        var card = img.closest(".cam-card");
        var id = card ? card.getAttribute("data-camara-id") : null;
        if (!id || !mapa || mapa[id] === undefined) { return; }
        var mtime = String(mapa[id]);
        if (mtime === (img.getAttribute("data-v") || "")) { return; }
        var media = img.closest(".cam-card__media");
        if (media) { media.classList.add("cam-card__media--loading"); }
        img.onload = function () {
          if (media) { media.classList.remove("cam-card__media--loading"); }
        };
        img.src = img.getAttribute("data-snapshot") + "?v=" + mtime;
        img.setAttribute("data-v", mtime);
      });
    }

    function refrescar() {
      var lista = ids();
      if (lista.length === 0) { return; }
      $.getJSON(endpoint, { ids: lista.join(",") }).done(function (r) {
        if (r && r.ok && r.mtime) { aplicar(r.mtime); }
      });
    }

    if (doc.querySelectorAll(".cam-card__img[data-snapshot]").length > 0) {
      refrescar();
      setInterval(refrescar, intervaloMs);
    }
  }

  /* ------------------------------------------------------------------ */
  /* Fotos HQ progresivas: cuando la versión x4plus de una foto esté     */
  /* lista, se recarga SOLO esa imagen (cache-buster) sin refrescar la   */
  /* página. La imagen se "autonitida" ~35-40 s después de aparecer.     */
  /* ------------------------------------------------------------------ */
  function rfRefrescarFotosHQ(intervaloMs) {
    intervaloMs = intervaloMs || 4000;
    var re = /caras_procesadas\/(\d+)\.jpg/;

    function tick() {
      var imgs = doc.querySelectorAll('img[src*="caras_procesadas/"]');
      var pendientes = {};
      var i, m, fid;
      for (i = 0; i < imgs.length; i++) {
        var img = imgs[i];
        if (img.getAttribute("data-hq") === "1") { continue; }
        m = re.exec(img.getAttribute("src") || "");
        if (!m) { continue; }
        fid = m[1];
        pendientes[fid] = pendientes[fid] || [];
        pendientes[fid].push(img);
      }
      var fids = Object.keys(pendientes);
      if (fids.length === 0) { return; }

      $.get("./accionesAjax.php?a=8", { ids: fids.join(",") }, function (resp) {
        var hq = (resp && resp.hq) ? resp.hq : [];
        var j, k;
        for (j = 0; j < hq.length; j++) {
          var list = pendientes[String(hq[j])] || [];
          for (k = 0; k < list.length; k++) {
            var im = list[k];
            var base = (im.getAttribute("src") || "").split("?")[0];
            im.setAttribute("data-hq", "1");
            im.src = base + "?v=" + Date.now();
          }
        }
      }, "json");
    }

    tick();
    setInterval(tick, intervaloMs);
  }

  /* ------------------------------------------------------------------ */
  /* Drawer lateral del panel (móvil <768px)                             */
  /* Hamburguesa (#panel-drawer-toggler) -> abre; cierra con el botón ✕, */
  /* el backdrop o la tecla Esc. Bloquea el scroll de fondo.             */
  /* ------------------------------------------------------------------ */
  function rfPanelDrawer() {
    var drawer = doc.getElementById("panel-drawer");
    if (!drawer) {
      return;
    }
    var backdrop = doc.getElementById("panel-drawer-backdrop");
    var toggler = doc.getElementById("panel-drawer-toggler");
    var closer = doc.getElementById("panel-drawer-close");

    function abrir() {
      drawer.classList.add("panel-drawer--open");
      drawer.setAttribute("aria-hidden", "false");
      if (backdrop) {
        backdrop.classList.add("panel-drawer-backdrop--open");
        backdrop.setAttribute("aria-hidden", "false");
      }
      doc.body.classList.add("panel-drawer-lock");
    }

    function cerrar() {
      drawer.classList.remove("panel-drawer--open");
      drawer.setAttribute("aria-hidden", "true");
      if (backdrop) {
        backdrop.classList.remove("panel-drawer-backdrop--open");
        backdrop.setAttribute("aria-hidden", "true");
      }
      doc.body.classList.remove("panel-drawer-lock");
    }

    if (toggler) {
      toggler.addEventListener("click", function (e) {
        e.preventDefault();
        abrir();
      });
    }
    if (closer) {
      closer.addEventListener("click", function (e) {
        e.preventDefault();
        cerrar();
      });
    }
    if (backdrop) {
      backdrop.addEventListener("click", cerrar);
    }
    // cerrar al pulsar cualquier item del menú
    drawer.querySelectorAll(".menu").forEach(function (item) {
      item.addEventListener("click", cerrar);
    });
    // tecla Escape
    doc.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && drawer.classList.contains("panel-drawer--open")) {
        cerrar();
      }
    });
  }

  /* ------------------------------------------------------------------ */
  /* Tooltip universal auto-posicionado (rf-tip)                        */
  /* Cualquier elemento con data-tip="texto" muestra un globo estilo    */
  /* Mordor que elige dirección entre los 4 puntos cardinales según el  */
  /* espacio disponible en el viewport. Se puede reutilizar en cualquier */
  /* sección sin más que añadir el atributo data-tip al elemento.       */
  /* ------------------------------------------------------------------ */
  var rfTipEl = null;

  function rfTipObtener() {
    if (!rfTipEl) {
      rfTipEl = doc.createElement("div");
      rfTipEl.className = "rf-tip";
      rfTipEl.setAttribute("role", "tooltip");
      rfTipEl.style.display = "none";
      doc.body.appendChild(rfTipEl);
    }
    return rfTipEl;
  }

  function rfTipMostrar(objetivo, texto) {
    var tip = rfTipObtener();
    var margen = 8;
    tip.textContent = texto;
    tip.className = "rf-tip";
    tip.style.display = "block";
    tip.style.left = "0px";
    tip.style.top = "0px";

    var rect = objetivo.getBoundingClientRect();
    var tipW = tip.offsetWidth;
    var tipH = tip.offsetHeight;

    var abajo = win.innerHeight - rect.bottom; // espacio libre bajo el elemento
    var arriba = rect.top;                     // espacio libre sobre el elemento
    var derecha = win.innerWidth - rect.right; // espacio libre a la derecha
    var izquierda = rect.left;                 // espacio libre a la izquierda

    var cabe = {
      down: abajo >= tipH + margen,
      up: arriba >= tipH + margen,
      right: derecha >= tipW + margen,
      left: izquierda >= tipW + margen
    };
    // Primera dirección que cabe; en caso de empate/nada cabe, cae en down
    var orden = ["down", "up", "right", "left"];
    var dir = "down";
    for (var i = 0; i < orden.length; i++) {
      if (cabe[orden[i]]) {
        dir = orden[i];
        break;
      }
    }

    var x = 0;
    var y = 0;
    if (dir === "down" || dir === "up") {
      x = rect.left + rect.width / 2 - tipW / 2;
      y = (dir === "down") ? rect.bottom + margen : rect.top - tipH - margen;
      x = Math.max(margen, Math.min(x, win.innerWidth - tipW - margen));
    } else {
      x = (dir === "right") ? rect.right + margen : rect.left - tipW - margen;
      y = rect.top + rect.height / 2 - tipH / 2;
      y = Math.max(margen, Math.min(y, win.innerHeight - tipH - margen));
    }

    tip.style.left = x + "px";
    tip.style.top = y + "px";
    tip.classList.add("rf-tip--" + dir);
  }

  function rfTipOcultar() {
    if (rfTipEl) {
      rfTipEl.style.display = "none";
    }
  }

  function rfTipInit() {
    // Mostrar al pasar el ratón o al enfocar con teclado
    function obtenerObjetivo(e) {
      var t = e.target;
      return (t && t.closest) ? t.closest("[data-tip]") : null;
    }
    doc.addEventListener("mouseover", function (e) {
      var t = obtenerObjetivo(e);
      if (t && t.getAttribute("data-tip")) {
        rfTipMostrar(t, t.getAttribute("data-tip"));
      }
    });
    doc.addEventListener("mouseout", function (e) {
      if (obtenerObjetivo(e)) {
        rfTipOcultar();
      }
    });
    doc.addEventListener("focusin", function (e) {
      var t = obtenerObjetivo(e);
      if (t && t.getAttribute("data-tip")) {
        rfTipMostrar(t, t.getAttribute("data-tip"));
      }
    });
    doc.addEventListener("focusout", function (e) {
      if (obtenerObjetivo(e)) {
        rfTipOcultar();
      }
    });
    // Ocultar al hacer scroll o redimensionar (el tooltip es position:fixed)
    doc.addEventListener("scroll", rfTipOcultar, true);
    win.addEventListener("resize", rfTipOcultar);
  }

  /* Exposición global */
  win.rfToast = rfToast;
  win.rfLightbox = rfLightbox;
  win.rfCamModal = rfCamModal;
  win.rfVideoModal = rfVideoModal;
  win.rfRefrescarSnapshots = rfRefrescarSnapshots;
  win.rfRefrescarFotosHQ = rfRefrescarFotosHQ;
  win.verFoto = rfLightbox; // alias legacy de los javascript.php de secciones
  win.rfTipInit = rfTipInit; // inicialización delegada (ver $(function) abajo)

  // Inicialización automática de refresco cuando hay rejilla de cámaras
  $(function () {
    rfPanelDrawer();
    rfTipInit();
    if (doc.querySelectorAll(".cam-card__img[data-snapshot]").length > 0) {
      rfRefrescarSnapshots(5000);
    }
    // Fotos de caras: cuando su versión HQ (x4plus) esté lista, se "autonitidan"
    // en el panel sin recargar la página (consulta cada ~4 s).
    if (doc.querySelectorAll('img[src*="caras_procesadas/"]').length > 0) {
      rfRefrescarFotosHQ(4000);
    }
  });
})(window, document, jQuery);
