/* ============================================================
   Barad-dûr · Dashboard "La Torre" (2026-08-19)
   JavaScript VANILLA (el proyecto usa jQuery 1.4.4: sin .on(),
   sin .fail(); por eso este módulo NO depende de jQuery).
   Refresco en vivo del feed, count-up, secciones expandibles,
   caldero de aforo y centinelas.
   ============================================================ */
(function () {
  "use strict";

  var reduceMotion = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* GET JSON silencioso y tolerante (sin jQuery). */
  function dashAjaxGet(url, cb) {
    var xhr = new XMLHttpRequest();
    xhr.open("GET", url, true);
    xhr.onreadystatechange = function () {
      if (xhr.readyState !== 4) { return; }
      if (xhr.status !== 200) { cb(null); return; }
      try { cb(JSON.parse(xhr.responseText)); }
      catch (e) { cb(null); }
    };
    xhr.onerror = function () { cb(null); };
    xhr.send();
  }

  /* ----------------------------------------------------------
   * Reloj del hero
   * -------------------------------------------------------- */
  function dashReloj() {
    var el = document.getElementById("dash-clock");
    if (!el) { return; }
    var d = new Date();
    var p = function (n) { return (n < 10 ? "0" : "") + n; };
    el.textContent = p(d.getHours()) + ":" + p(d.getMinutes()) + ":" + p(d.getSeconds());
  }
  dashReloj();
  setInterval(dashReloj, 1000);

  /* ----------------------------------------------------------
   * Count-up (números que suben al cargar)
   * -------------------------------------------------------- */
  function dashCountUp() {
    var els = document.querySelectorAll(".count-up");
    for (var i = 0; i < els.length; i++) {
      (function (el) {
        var target = parseInt(el.getAttribute("data-count"), 10);
        if (isNaN(target)) { return; }
        if (reduceMotion) { el.textContent = target; return; }
        var dur = 900, t0 = null;
        function paso(ts) {
          if (t0 === null) { t0 = ts; }
          var p = Math.min(1, (ts - t0) / dur);
          el.textContent = Math.round(target * (1 - Math.pow(1 - p, 3)));
          if (p < 1) { requestAnimationFrame(paso); }
        }
        requestAnimationFrame(paso);
      })(els[i]);
    }
  }
  dashCountUp();

  /* ----------------------------------------------------------
   * Secciones expandibles (pergaminos) — delegación de eventos
   * -------------------------------------------------------- */
  document.addEventListener("click", function (e) {
    var t = e.target && e.target.closest ? e.target.closest(".scroll-section__toggle") : null;
    if (!t) { return; }
    var section = t.closest(".scroll-section");
    var bodyId = t.getAttribute("aria-controls");
    var body = bodyId ? document.getElementById(bodyId) : section.querySelector(".scroll-section__body");
    if (!section || !body) { return; }
    var abierto = section.classList.contains("scroll-section--open");
    if (abierto) {
      section.classList.remove("scroll-section--open");
      body.setAttribute("hidden", "hidden");
      t.setAttribute("aria-expanded", "false");
    } else {
      section.classList.add("scroll-section--open");
      body.removeAttribute("hidden");
      t.setAttribute("aria-expanded", "true");
    }
  });

  /* ----------------------------------------------------------
   * Caldero de aforo: animar la lava al cargar
   * -------------------------------------------------------- */
  var lava = document.getElementById("aforo-lava");
  if (lava) {
    var nivelObjetivo = lava.style.getPropertyValue("--nivel") || "0%";
    if (reduceMotion) {
      lava.style.setProperty("--nivel", nivelObjetivo);
    } else {
      lava.style.setProperty("--nivel", "0%");
      requestAnimationFrame(function () {
        requestAnimationFrame(function () {
          lava.style.setProperty("--nivel", nivelObjetivo);
        });
      });
    }
  }

  /* ----------------------------------------------------------
   * Cambiar aforo (AJAX, sin recargar)
   * -------------------------------------------------------- */
  window.dashCambiarAforo = function () {
    var input = document.getElementById("aforo_input");
    var valor = input ? parseInt(input.value, 10) : NaN;
    if (isNaN(valor) || valor < 0) {
      if (window.rfToast) { rfToast("⚒️ El número de almas debe ser válido", "err"); }
      return;
    }
    dashAjaxGet("accionesAjax.php?a=6&nuevo_aforo=" + encodeURIComponent(valor), function (r) {
      if (!r || r.ok !== true) {
        if (window.rfToast) { rfToast("⚠️ La forja no ha podido fijar el aforo", "err"); }
        return;
      }
      var gauge = document.getElementById("aforo-gauge");
      var lavaEl = document.getElementById("aforo-lava");
      var actualEl = document.getElementById("aforo-actual");
      var maxEl = document.getElementById("aforo-max");
      var semEl = document.getElementById("aforo-sem");
      if (actualEl) { actualEl.textContent = r.actual; }
      if (maxEl) { maxEl.textContent = r.max; }
      if (semEl) { semEl.textContent = r.sem_txt; }
      if (lavaEl) { lavaEl.style.setProperty("--nivel", r.pct + "%"); }
      if (gauge) {
        gauge.classList.remove("aforo-gauge--ok", "aforo-gauge--warn", "aforo-gauge--full");
        gauge.classList.add("aforo-gauge--" + r.estado);
      }
      if (input) { input.value = ""; }
      if (window.rfToast) { rfToast("⚒️ Aforo fijado: " + r.actual + " almas", "ok"); }
    });
  };

  /* ----------------------------------------------------------
   * Refresco en vivo: feed + quién está dentro + falta fichar
   * -------------------------------------------------------- */
  function dashRefrescaVivo() {
    if (!document.getElementById("live-feed-list")) { return; }
    dashAjaxGet("accionesAjax.php?a=4", function (r) {
      if (!r || !r.feed) { return; }
      var feed = document.getElementById("live-feed-list");
      if (feed) { feed.innerHTML = r.feed; }
      var dentro = document.getElementById("inside-now-list");
      if (dentro && r.dentro !== undefined) { dentro.innerHTML = r.dentro; }
      var falta = document.getElementById("missing-list");
      if (falta && r.falta !== undefined) { falta.innerHTML = r.falta; }
      if (r.dentro_count !== undefined) {
        var dc = document.getElementById("dentro-count");
        var hd = document.getElementById("hero-dentro");
        if (dc) { dc.textContent = r.dentro_count; }
        if (hd) { hd.textContent = r.dentro_count; }
      }
      if (r.falta_count !== undefined) {
        var fc = document.getElementById("falta-count");
        if (fc) { fc.textContent = r.falta_count; }
      }
      var upd = document.getElementById("feed-actualizado");
      if (upd && r.updated) { upd.textContent = r.updated; }
      dashCountUp();
    });
  }
  setInterval(dashRefrescaVivo, 15000);

  /* ----------------------------------------------------------
   * Los Seis Centinelas (daemons) cada 60s
   * -------------------------------------------------------- */
  function dashRefrescaDaemons() {
    if (!document.getElementById("daemons-grid")) { return; }
    dashAjaxGet("accionesAjax.php?a=5", function (r) {
      if (!r || !r.html) { return; }
      var grid = document.getElementById("daemons-grid");
      if (grid) { grid.innerHTML = r.html; }
      var upd = document.getElementById("daemons-updated");
      if (upd) {
        var d = new Date();
        var mm = d.getMinutes();
        upd.textContent = "actualizado a las " + d.getHours() + ":" + (mm < 10 ? "0" : "") + mm;
      }
    });
  }
  setTimeout(dashRefrescaDaemons, 10000);
  setInterval(dashRefrescaDaemons, 60000);
})();
