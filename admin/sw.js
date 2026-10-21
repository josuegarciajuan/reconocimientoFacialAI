/* RF Panel — Service Worker multi-instancia
 * Estrategia network-first con cache como fallback.
 * El scope se deriva del registro (`/reconocimientoFacial/admin/` o
 * `/ojos/admin/`), de modo que cada instancia tiene su propia cache y nunca
 * intercepta la otra. Solo cachea estáticos de files/ (nunca HTML con sesión
 * ni APIs ajax).
 */
var SCOPE = new URL(self.registration.scope).pathname; // termina en "/"
var CACHE = 'rf-panel-' + SCOPE.replace(/[^a-z0-9]+/gi, '-').replace(/^-+|-+$/g, '') + '-v2';

var PRECACHE = [
  './manifest.php',
  './files/custom.css'
];

self.addEventListener('install', function (e) {
  e.waitUntil(
    caches.open(CACHE).then(function (c) {
      return c.addAll(PRECACHE).catch(function () { /* silencioso */ });
    })
  );
  self.skipWaiting();
});

self.addEventListener('activate', function (e) {
  e.waitUntil(
    caches.keys().then(function (keys) {
      return Promise.all(keys.filter(function (k) { return k !== CACHE; }).map(function (k) { return caches.delete(k); }));
    })
  );
  self.clients.claim();
});

self.addEventListener('fetch', function (e) {
  var url = new URL(e.request.url);
  // Solo requests del scope de ESTA instancia (p. ej. /ojos/admin/).
  if (url.pathname.indexOf(SCOPE) !== 0) return;
  // No interceptar POST ni acciones ajax
  if (e.request.method !== 'GET') return;
  if (url.pathname.indexOf('index.php') !== -1 && url.search.indexOf('action=') !== -1) return;
  // No interceptar el streaming en vivo
  if (url.pathname.indexOf('/live') !== -1) return;

  // Solo persistimos en cache estáticos de files/ (nunca HTML con sesión)
  var esEstatico = url.pathname.indexOf(SCOPE + 'files/') === 0;

  // Network-first: intenta red, fallback a cache
  e.respondWith(
    fetch(e.request, { cache: 'no-cache' }).then(function (res) {
      if (esEstatico && res && res.status === 200 && res.type === 'basic') {
        var clone = res.clone();
        caches.open(CACHE).then(function (c) { c.put(e.request, clone); });
      }
      return res;
    }).catch(function () {
      return caches.match(e.request);
    })
  );
});

// Forzar skipWaiting cuando la página lo solicita
self.addEventListener('message', function (e) {
  if (e.data && e.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }
});
