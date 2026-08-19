/* ============================================================
   Barad-dûr · Motor de lore — bocadillos temáticos (tooltips)
   ============================================================
   Explica la terminología de Mordor / El Señor de los Anillos
   al pasar el ratón (hover) o al enfocar con teclado (focus).

   - Fuente de verdad: admin/includes/glosario.php -> window.RF_GLOSARIO
   - Resolución de términos:
       1) data-lore="<clave>" en el elemento (o ancestro) -> uso directo.
       2) Si no: comparación de texto del elemento contra el glosario
          (match "auto": igualdad exacta o contención con límite de palabra).
   - Términos con match:"explicito" SOLO aparecen con data-lore
     (evita falsos positivos en texto normal: Puerta, Salida, Encendida...).
   - Sin indicador visual en los elementos: todo tiene explicación por defecto.
   ============================================================ */

(function (win, doc) {
  "use strict";

  var GLOSARIO = win.RF_GLOSARIO || {};
  var EN_LOGIN = doc.body && doc.body.classList.contains("login");

  /* Normalización de texto: minúsculas, sin emojis/puntuación,
     espacios colapsados. Mantiene acentos (á é í ó ú ñ ü). */
  var EMOJI_RE = /[\u{1F000}-\u{1FAFF}\u{2600}-\u{27BF}\u{FE0F}\u{200D}\u{20E3}]/gu;
  function limpiar(t) {
    return (t || "")
      .replace(EMOJI_RE, " ")
      .replace(/[^\p{L}\p{N}\s]/gu, " ")
      .replace(/\s+/g, " ")
      .trim()
      .toLowerCase();
  }

  function escRe(s) {
    return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  }

  /* Índice de términos para búsqueda rápida (clave -> entrada) */
  var POR_CLAVE = {};
  var TERMINOS = []; // {clave, limpio, match}
  Object.keys(GLOSARIO).forEach(function (clave) {
    var e = GLOSARIO[clave];
    POR_CLAVE[clave] = e;
    if (e && e.termino) {
      TERMINOS.push({ clave: clave, limpio: limpiar(e.termino), match: e.match || "auto" });
    }
  });

  /* Elementos "titulares": donde buscar el texto significativo.
     Los títulos/labels del panel son los que llevan terminología. */
  var SEL_TITULO =
    'a, button, h1, h2, h3, h4, h5, th, label, summary, [class*="title"], [class*="label"], [class*="menu__title"], [class*="kpi-label"], [class*="ayuda-card__title"], [class*="notification-content__title"], [class*="breadcrumb"]';

  function textoDe(el) {
    if (!el) return "";
    var t = el.getAttribute && el.getAttribute("aria-label");
    if (!t) t = el.title || "";
    if (!t) t = el.textContent || "";
    return t;
  }

  /* Resuelve la entrada de glosario para un elemento: null si no hay. */
  function resolver(el) {
    if (!el || !el.closest) return null;

    // 1) data-lore explícito (elemento o ancestro)
    var marcado = el.closest("[data-lore]");
    if (marcado) {
      var clave = marcado.getAttribute("data-lore");
      if (POR_CLAVE[clave]) return POR_CLAVE[clave];
    }

    // 2) match automático por texto (solo match:"auto")
    var candidato = el.closest(SEL_TITULO) || el;
    var texto = limpiar(textoDe(candidato));
    if (!texto) return null;

    // 2a) igualdad exacta primero (gana sobre la contención)
    for (var i = 0; i < TERMINOS.length; i++) {
      var t = TERMINOS[i];
      if (t.match === "auto" && texto === t.limpio) {
        return GLOSARIO[t.clave];
      }
    }
    // 2b) contención con límite de palabra (solo textos cortos y temáticos)
    if (texto.length <= 90) {
      for (var j = 0; j < TERMINOS.length; j++) {
        var u = TERMINOS[j];
        if (u.match !== "auto" || u.limpio.length < 3) continue;
        var re = new RegExp("(^|\\s)" + escRe(u.limpio) + "(?=\\s|$)", "i");
        if (re.test(texto)) {
          return GLOSARIO[u.clave];
        }
      }
    }
    return null;
  }

  /* ---------- Tooltip ---------- */
  var tooltip = null;
  var timer = null;
  var ocultando = false;

  function construirTooltip() {
    var div = doc.createElement("div");
    div.className = "rf-lore";
    div.setAttribute("role", "tooltip");
    div.innerHTML =
      '<div class="rf-lore__term"></div>' +
      '<div class="rf-lore__mean"></div>' +
      '<div class="rf-lore__go"></div>';
    doc.body.appendChild(div);
    return div;
  }

  function mostrar(entrada, ancla) {
    if (!tooltip) tooltip = construirTooltip();
    tooltip.querySelector(".rf-lore__term").textContent = entrada.termino;
    tooltip.querySelector(".rf-lore__mean").textContent = entrada.significado;

    var go = tooltip.querySelector(".rf-lore__go");
    var destino = entrada.destino || "";
    var href = entrada.href;
    if (EN_LOGIN) href = null; // en login los enlaces del panel no existen
    if (destino) {
      if (href) {
        go.innerHTML = "";
        var a = doc.createElement("a");
        a.href = href;
        a.textContent = "Apunta a → " + destino;
        go.appendChild(a);
      } else {
        go.textContent = "Apunta a → " + destino;
      }
      go.style.display = "";
    } else {
      go.style.display = "none";
    }

    posicionar(ancla);
    tooltip.classList.add("rf-lore--show");
    tooltip.setAttribute("aria-hidden", "false");
  }

  function posicionar(ancla) {
    var r = ancla.getBoundingClientRect();
    var tw = tooltip.offsetWidth;
    var th = tooltip.offsetHeight;
    var left = r.left + r.width / 2 - tw / 2;
    left = Math.max(8, Math.min(left, win.innerWidth - tw - 8));
    var top = r.bottom + 10;
    if (top + th > win.innerHeight - 8) {
      top = r.top - th - 10;
      if (top < 8) top = 8;
    }
    tooltip.style.left = left + "px";
    tooltip.style.top = top + "px";
  }

  function ocultar() {
    if (!tooltip) return;
    tooltip.classList.remove("rf-lore--show");
    tooltip.setAttribute("aria-hidden", "true");
  }

  function programarOcultar() {
    ocultando = true;
    if (timer) clearTimeout(timer);
    timer = setTimeout(function () {
      ocultar();
      ocultando = false;
    }, 120);
  }

  /* ---------- Eventos (delegación global) ---------- */
  var ultimo = null;
  var rAF = win.requestAnimationFrame || function (fn) { setTimeout(fn, 16); };

  function onPointerOver(e) {
    var el = e.target && e.target.nodeType === 1 ? e.target : null;
    if (!el) return;
    if (el.closest && el.closest(".rf-lore")) return; // no dispara sobre el propio tooltip
    if (el.tagName === "INPUT" || el.tagName === "TEXTAREA" || el.tagName === "SELECT") return;

    if (ocultando) {
      clearTimeout(timer);
      ocultando = false;
    }

    rAF(function () {
      if (el === ultimo) return; // ya resuelto
      ultimo = el;
      var entrada = resolver(el);
      if (entrada) {
        mostrar(entrada, el);
      } else {
        ocultar();
      }
    });
  }

  function onPointerOut(e) {
    var el = e.target;
    if (!el || (el.closest && el.closest(".rf-lore"))) return;
    ultimo = null;
    programarOcultar();
  }

  function onFocusIn(e) {
    var el = e.target;
    if (!el || !el.closest) return;
    if (el.tagName === "INPUT" || el.tagName === "TEXTAREA" || el.tagName === "SELECT") return;
    var entrada = resolver(el);
    if (entrada) mostrar(entrada, el);
  }

  function onFocusOut(e) {
    var el = e.target;
    if (!el || (el.closest && el.closest(".rf-lore"))) return;
    ocultar();
  }

  function onKeyDown(e) {
    if (e.key === "Escape") ocultar();
  }

  function ocultarEnScroll() {
    ocultar();
  }

  if (doc.body) {
    doc.addEventListener("pointerover", onPointerOver, true);
    doc.addEventListener("pointerout", onPointerOut, true);
    doc.addEventListener("focusin", onFocusIn, true);
    doc.addEventListener("focusout", onFocusOut, true);
    doc.addEventListener("keydown", onKeyDown, true);
    win.addEventListener("scroll", ocultarEnScroll, true);
    win.addEventListener("resize", ocultarEnScroll, true);
  }
})(window, document);
