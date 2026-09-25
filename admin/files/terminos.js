/* ============================================================
   terminos.js · Intercambio de terminología por tema
   ============================================================
   El panel tiene dos vocabularios:
     - "mordor" : jerga de El Señor de los Anillos
     - "pro"    : vocabulario profesional (por defecto)

   El servidor pinta el texto del tema activo dentro de cada
   `<span class="rf-term" data-mordor="…" data-pro="…">`.
   Este motor lo intercambia en caliente al cambiar de tema, sin
   recargar, escuchando el evento `rf:theme-change` (theme-switch.js).

   También expone window.rfTerm(clave) para textos dinámicos de JS
   (p. ej. los botones del hub), usando window.RF_TERMINOS.

   Vanilla JS, dependencia cero.
   ============================================================ */
(function (win, doc) {
  "use strict";

  var MAP = win.RF_TERMINOS || {};

  function temaActivo() {
    return doc.documentElement.classList.contains("theme-pro") ? "pro" : "mordor";
  }

  /* Texto para la clave en el tema actual (o en el indicado). */
  function rfTerm(clave, tema) {
    var e = MAP[clave];
    if (!e) { return clave; }
    var t = tema || temaActivo();
    var txt = (t === "mordor") ? (e.mordor || e.pro) : (e.pro || e.mordor);
    return (txt === undefined || txt === null) ? clave : txt;
  }

  /* Recorre los .rf-term y fija el texto del tema activo. */
  function aplicar(raiz) {
    var t = temaActivo();
    var attr = (t === "mordor") ? "data-mordor" : "data-pro";
    (raiz || doc).querySelectorAll(".rf-term").forEach(function (el) {
      var txt = el.getAttribute(attr);
      if (txt !== null) { el.textContent = txt; }
    });
  }

  win.rfTerm = rfTerm;
  win.rfTermAplicar = aplicar;

  doc.addEventListener("DOMContentLoaded", function () { aplicar(doc); });
  doc.documentElement.addEventListener("rf:theme-change", function () { aplicar(doc); });
})(window, document);
