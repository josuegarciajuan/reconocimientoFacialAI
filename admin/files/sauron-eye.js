/* ============================================================
   sauron-eye.js · El Ojo que Todo lo Ve
   Pupila que rastrea el cursor + parpadeo periódico.
   ============================================================ */
(function () {
  "use strict";

  var eyes = document.querySelectorAll(".sauron-eye");
  if (!eyes.length) return;

  var prefersReduced = window.matchMedia
    ? window.matchMedia("(prefers-reduced-motion: reduce)").matches
    : false;

  eyes.forEach(function (eye) {
    var pupil = eye.querySelector(".sauron-eye__pupil");
    var shine = eye.querySelector(".sauron-eye__shine");
    if (!pupil) return;

    var R = 3.6; // desplazamiento máximo de la pupila
    var current = { x: 0, y: 0 };
    var target = { x: 0, y: 0 };
    var raf = null;

    function setPupil(x, y) {
      var t = "translate(" + x.toFixed(2) + "," + y.toFixed(2) + ")";
      pupil.setAttribute("transform", t);
      if (shine) shine.setAttribute("transform", t);
    }

    function loop() {
      current.x += (target.x - current.x) * 0.12;
      current.y += (target.y - current.y) * 0.12;
      setPupil(current.x, current.y);
      if (Math.abs(target.x - current.x) > 0.05 || Math.abs(target.y - current.y) > 0.05) {
        raf = window.requestAnimationFrame(loop);
      } else {
        raf = null;
      }
    }

    function onMove(e) {
      var r = eye.getBoundingClientRect();
      var dx = e.clientX - (r.left + r.width / 2);
      var dy = e.clientY - (r.top + r.height / 2);
      var d = Math.sqrt(dx * dx + dy * dy) || 1;
      var f = Math.min(1, d / 320);
      target.x = (dx / d) * R * f;
      target.y = (dy / d) * R * f;
      if (!raf) raf = window.requestAnimationFrame(loop);
    }

    if (!prefersReduced) {
      document.addEventListener("mousemove", onMove);

      // Parpadeo: cada ~5s el ojo se entorna un instante
      setInterval(function () {
        eye.classList.add("sauron-eye--blink");
        setTimeout(function () {
          eye.classList.remove("sauron-eye--blink");
        }, 150);
      }, 5200);
    }
  });
})();
