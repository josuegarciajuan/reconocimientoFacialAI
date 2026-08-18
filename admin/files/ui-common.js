/* ============================================================
   Barad-dûr · UI común (secciones) — helper responsivo global
   Requiere jQuery (cargado en el layout) y el plugin de modales
   de Midone (app.js). Patrones:
   - rfToast(msg, tipo)            feedback visual no invasivo
   - rfLightbox(url, titulo)       visor de imagen (lightbox)
   - rfCamModal(id, url, titulo)   modal de stream MJPEG
   - rfRefrescarSnapshots()        refresco periódico de snapshots
   ============================================================ */

(function (win, doc, $) {
  "use strict";

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
    try {
      $("#" + modal.id).modal("show");
    } catch (e) {
      /* el plugin de modal no está disponible: nada que hacer */
    }
  }

  /* ------------------------------------------------------------------ */
  /* Modal de cámara: stream MJPEG con fallback a snapshot               */
  /* ------------------------------------------------------------------ */
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
        '<img class="live-modal__img" alt="" src="">' +
        '<div class="stream-detail__meta">' +
        '<span class="text-xs text-gray-500 dark:text-gray-600">Stream en directo (MJPEG)</span>' +
        '<span class="ml-auto text-xs" id="rf-cam-hint"></span>' +
        "</div>" +
        "</div>";
      doc.body.appendChild(modal);
    }
    modal.querySelector(".media-modal__title").textContent = titulo;
    var img = modal.querySelector(".live-modal__img");
    img.setAttribute("alt", titulo);
    img.src = streamUrl;
    img.onerror = function () {
      // El stream no está disponible: caer al último snapshot
      img.onerror = null;
      img.src = snapshotUrl;
      var hint = doc.getElementById("rf-cam-hint");
      if (hint) {
        hint.textContent = "Sin stream: mostrando último snapshot";
      }
    };
    var hint = doc.getElementById("rf-cam-hint");
    if (hint) {
      hint.textContent = "";
    }
    try {
      $("#" + modal.id).modal("show");
    } catch (e) {
      /* plugin de modal no disponible */
    }
  }

  /* ------------------------------------------------------------------ */
  /* Refresco periódico de snapshots (cache-buster ligero)               */
  /* Marca las imágenes .cam-card__img[data-snapshot] y re-apunta el src  */
  /* cada intervalo respetando la caché de dofoto (15s).                  */
  /* ------------------------------------------------------------------ */
  function rfRefrescarSnapshots(intervaloMs) {
    intervaloMs = intervaloMs || 15000;
    function refrescar() {
      doc.querySelectorAll(".cam-card__img[data-snapshot]").forEach(function (img) {
        var base = img.getAttribute("data-snapshot");
        var card = img.closest(".cam-card__media");
        if (card) {
          card.classList.add("cam-card__media--loading");
        }
        img.src = base + "?t=" + Math.floor(Date.now() / 1000);
        img.onload = function () {
          if (card) {
            card.classList.remove("cam-card__media--loading");
          }
        };
      });
    }
    if (doc.querySelectorAll(".cam-card__img[data-snapshot]").length > 0) {
      refrescar();
      setInterval(refrescar, intervaloMs);
    }
  }

  /* Exposición global */
  win.rfToast = rfToast;
  win.rfLightbox = rfLightbox;
  win.rfCamModal = rfCamModal;
  win.rfRefrescarSnapshots = rfRefrescarSnapshots;
  win.verFoto = rfLightbox; // alias legacy de los javascript.php de secciones

  // Inicialización automática de refresco cuando hay rejilla de cámaras
  $(function () {
    if (doc.querySelectorAll(".cam-card__img[data-snapshot]").length > 0) {
      rfRefrescarSnapshots(15000);
    }
  });
})(window, document, jQuery);
