/* ============================================================
   theme-switch.js · Conmutador de tema del panel
   ============================================================
   Alterna entre el tema "Mordor" (oscuro, jerga LdA) y el tema
   "Profesional" / Iris (claro). Estado en <html>:
     - class="dark" / class="theme-pro"  (mutuamente excluyentes)
     - data-theme="mordor" | "pro"
     - color-scheme + <meta name="theme-color">

   Persistencia:
     - localStorage["rf-theme"]  (fuente rápida por dispositivo)
     - cookie "rf_theme"         (permite al servidor pintar el tema
                                  correcto en el primer byte, sobre todo
                                  en el login)
   Por defecto: "pro" (profesional).

   El script inline de <head> (index.php / login.php) hace la misma
   resolución ANTES del primer pintado para evitar el flash. Aquí se
   reconcilia, se atiende el clic y se sincronizan las pestañas.

   Vanilla JS, sin dependencias. No escribe fuera de rf-theme/rf_theme.
   ============================================================ */
(function (win, doc) {
  "use strict";

  var root = doc.documentElement;
  var KEY = "rf-theme";
  var COLOR_PRO = "#F5F3EC";
  var COLOR_MORDOR = "#16121a";

  function leerLS() {
    try { return win.localStorage.getItem(KEY); } catch (e) { return null; }
  }

  function leerCookie() {
    var m = doc.cookie.match(/(?:^|;\s*)rf_theme=(mordor|pro)/);
    return m ? m[1] : null;
  }

  function actual() {
    var k = leerLS();
    var c = leerCookie();
    return (k === "mordor" || k === "pro") ? k : (c || "pro");
  }

  /* Aplica el tema en el documento. persistir=true guarda la elección. */
  function aplicar(tema, persistir) {
    var pro = (tema !== "mordor");
    root.classList.toggle("theme-pro", pro);
    root.classList.toggle("dark", !pro);
    root.setAttribute("data-theme", pro ? "pro" : "mordor");
    root.style.colorScheme = pro ? "light" : "dark";

    var meta = doc.getElementById("rf-theme-color");
    if (meta) { meta.setAttribute("content", pro ? COLOR_PRO : COLOR_MORDOR); }

    var btn = doc.getElementById("rf-theme-toggle");
    if (btn) {
      btn.setAttribute("aria-checked", pro ? "true" : "false");
      btn.setAttribute("aria-label", pro ? "Cambiar al tema Mordor" : "Cambiar al tema profesional");
      btn.setAttribute("title", pro
        ? "Tema actual: Profesional. Cambiar a Mordor"
        : "Tema actual: Mordor. Cambiar a Profesional");
    }

    if (persistir) {
      try { win.localStorage.setItem(KEY, tema); } catch (e) { /* modo privado */ }
      doc.cookie = "rf_theme=" + tema + "; path=/; max-age=31536000; SameSite=Lax";
    }

    root.dispatchEvent(new CustomEvent("rf:theme-change", {
      detail: { theme: tema, pro: pro }
    }));
  }

  /* API pública mínima (por si otra parte del panel la necesita). */
  win.rfSetTheme = aplicar;
  win.rfGetTheme = function () {
    return root.classList.contains("theme-pro") ? "pro" : "mordor";
  };

  doc.addEventListener("DOMContentLoaded", function () {
    var btn = doc.getElementById("rf-theme-toggle");
    if (btn) {
      btn.addEventListener("click", function () {
        aplicar(root.classList.contains("theme-pro") ? "mordor" : "pro", true);
      });
    }
    // Reconciliar con lo persistido (el inline script ya lo dejó listo).
    aplicar(actual(), false);
  });

  // Sincronía entre pestañas del mismo navegador.
  win.addEventListener("storage", function (e) {
    if (e.key === KEY) { aplicar(e.newValue || "pro", false); }
  });
})(window, document);
