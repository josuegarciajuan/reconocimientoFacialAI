/* ============================================================
   ring-hub.js · El Ojo del Anillo — centro de mando flotante
   ============================================================
   El widget "💍 Un Anillo" (abajo a la derecha) abre un hub
   compacto con: búsqueda global, navegación rápida y el estado
   de los Seis Centinelas en vivo. En reposo actúa como semáforo:
   "El Anillo arde" cuando hay anomalías (centinelas caídos,
   cámaras apagadas, aforo al límite).

   Estado servido por admin/accionesAjax.php?a=7 (resumen JSON)
   y a=5 (HTML de los centinelas, reutilizado del dashboard).

   Vanilla JS, sin jQuery (mismo patrón que dashboard.js).
   ============================================================ */
(function (win, doc) {
  "use strict";

  var btn = doc.getElementById("ring-widget");
  var hub = doc.getElementById("ring-hub");
  if (!btn || !hub) { return; }

  var campo   = doc.getElementById("ring-hub-buscar");
  var form    = doc.getElementById("ring-hub-form");
  var badge   = doc.getElementById("ring-hub-badge");
  var resumen = doc.getElementById("ring-hub-estado");
  var daemons  = doc.getElementById("ring-hub-daemons");
  var btnCerrar = doc.getElementById("ring-hub-cerrar");

  var abierto = false;
  var timerEstado  = null;  // semáforo: siempre, ~15 s
  var timerDaemons = null;  // centinelas: solo con el hub abierto, ~10 s

  /* GET JSON silencioso y tolerante (sin jQuery). */
  function ajaxGet(url, cb) {
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
   * Semáforo: estado del anillo en reposo
   * -------------------------------------------------------- */
  function aplicarSemafaro(r) {
    if (!r || !r.ok) { return; }

    var anomalias = parseInt(r.anomalias || 0, 10) || 0;

    if (badge) {
      badge.textContent = anomalias > 0 ? anomalias : "";
      badge.classList.toggle("ring-widget__badge--show", anomalias > 0);
    }
    btn.classList.toggle("ring-widget--arde", anomalias > 0);
    btn.setAttribute("aria-label",
      anomalias > 0
        ? "El Anillo arde: " + (r.detalle || []).join(" · ") + ". Abre el centro de mando."
        : "Un Anillo para gobernarlos a todos — abre el centro de mando");

    if (resumen) {
      var partes = [];
      if (r.daemons) {
        partes.push((r.daemons.en_pie || 0) + "/" + r.daemons.total + " centinelas");
      }
      if (r.camaras && r.camaras.total > 0) {
        partes.push((r.camaras.total - r.camaras.apagadas) + "/" + r.camaras.total + " cámaras");
      }
      if (r.aforo && r.aforo.max > 0) {
        partes.push("aforo " + r.aforo.pct + "%");
      }
      resumen.textContent = partes.length > 0 ? partes.join(" · ") : "El Ojo vigila";
    }
  }

  function refrescaEstado() {
    ajaxGet("accionesAjax.php?a=7", aplicarSemafaro);
  }

  /* ----------------------------------------------------------
   * Centinelas (solo refresco con el hub abierto)
   * -------------------------------------------------------- */
  function refrescaDaemons() {
    ajaxGet("accionesAjax.php?a=5", function (r) {
      if (r && r.ok && daemons && r.html) {
        daemons.innerHTML = r.html;
      }
    });
  }

  /* ----------------------------------------------------------
   * Apertura / cierre
   * -------------------------------------------------------- */
  function abrir() {
    if (abierto) { return; }
    abierto = true;
    hub.classList.add("ring-hub--open");
    hub.setAttribute("aria-hidden", "false");
    btn.setAttribute("aria-expanded", "true");
    refrescaEstado();
    refrescaDaemons();
    timerDaemons = win.setInterval(refrescaDaemons, 10000);
    if (campo) {
      win.setTimeout(function () { campo.focus(); }, 60);
    }
  }

  function cerrar() {
    if (!abierto) { return; }
    abierto = false;
    hub.classList.remove("ring-hub--open");
    hub.setAttribute("aria-hidden", "true");
    btn.setAttribute("aria-expanded", "false");
    if (timerDaemons) { win.clearInterval(timerDaemons); timerDaemons = null; }
    btn.focus();
  }

  function toggle() {
    if (abierto) { cerrar(); } else { abrir(); }
  }

  /* ----------------------------------------------------------
   * Búsqueda global (mismo destino que search.php)
   * -------------------------------------------------------- */
  function buscar() {
    if (!campo) { return; }
    var term = campo.value.trim();
    if (term === "") { campo.focus(); return; }
    win.location.href = "?page=visitantes&buscador=" + encodeURIComponent(term);
  }

  /* ----------------------------------------------------------
   * Eventos
   * -------------------------------------------------------- */
  btn.addEventListener("click", toggle);

  if (btnCerrar) {
    btnCerrar.addEventListener("click", function () { cerrar(); });
  }

  if (form) {
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      buscar();
    });
  }
  if (campo) {
    campo.addEventListener("keydown", function (e) {
      if (e.key === "Escape") { e.preventDefault(); cerrar(); }
    });
  }

  doc.addEventListener("keydown", function (e) {
    if ((e.ctrlKey || e.metaKey) && (e.key === "k" || e.key === "K")) {
      e.preventDefault();
      toggle();
    } else if (e.key === "Escape" && abierto) {
      cerrar();
    }
  });

  // Clic fuera del hub y del botón -> cerrar
  doc.addEventListener("pointerdown", function (e) {
    if (!abierto) { return; }
    if (!hub.contains(e.target) && !btn.contains(e.target)) {
      cerrar();
    }
  });

  /* ----------------------------------------------------------
   * Apagar / Encender el Ojo (motor de visión completo)
   * -------------------------------------------------------- */
  function powerSetState(estado) {
    var b = doc.getElementById("ring-hub-power");
    if (!b) { return; }
    b.setAttribute("data-estado", estado);
    b.classList.remove("power-btn--on", "power-btn--off");
    b.classList.add("power-btn--" + estado);
    var lbl = doc.getElementById("ring-hub-power-label");
    if (lbl) { lbl.textContent = (estado === "on") ? "Apagar el Ojo" : "Encender el Ojo"; }
  }

  function powerToggle() {
    var b = doc.getElementById("ring-hub-power");
    if (!b) { return; }
    var estado = b.getAttribute("data-estado");
    var target = (estado === "on") ? "off" : "on";
    var verb = (target === "off") ? "apagar" : "encender";
    if (!win.confirm("¿Seguro que quieres " + verb + " todo el motor de visión? (captura, detector, clasificador, live…)")) {
      return;
    }
    b.disabled = true;
    ajaxGet("accionesAjax.php?a=11&accion_power=" + target, function (r) {
      b.disabled = false;
      if (!r || r.ok !== true) {
        if (win.rfToast) { win.rfToast("⚠️ No se ha podido " + verb + " el sistema", "err"); }
        return;
      }
      powerSetState(r.estado);
      if (win.rfToast) {
        var msg = (target === "off") ? "🔴 Motor apagado · " : "🟢 Motor encendido · ";
        win.rfToast(msg + (r.salida || ""), "ok");
      }
      refrescaDaemons();
    });
  }

  var powerBtn = doc.getElementById("ring-hub-power");
  if (powerBtn) { powerBtn.addEventListener("click", powerToggle); }

  /* ----------------------------------------------------------
   * Arranque: estado inicial del semáforo + polling
   * -------------------------------------------------------- */
  refrescaEstado();
  timerEstado = win.setInterval(refrescaEstado, 15000);
})(window, document);
