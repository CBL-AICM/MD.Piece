// MD. Piece PWA service worker — cache-first for app shell, network-first for data.

const APP_VERSION = 'mdp-v2.2-onnx';
const APP_SHELL = [
  './', './index.html', './manifest.json',
  './css/style.css',
  './js/main.js', './js/data.js', './js/inference.js', './js/dashboard.js',
  './js/patient-browser.js', './js/whatif.js', './js/training.js',
  './js/experiment.js', './js/n-of-1.js',
  './icons/icon-192.svg', './icons/icon-512.svg',
  './model/model.onnx', './model/scaler.json',
];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(APP_VERSION).then(cache => cache.addAll(APP_SHELL)));
  self.skipWaiting();
});

self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(keys =>
    Promise.all(keys.filter(k => k !== APP_VERSION).map(k => caches.delete(k)))
  ));
  self.clients.claim();
});

self.addEventListener('fetch', e => {
  const url = new URL(e.request.url);
  // skip cross-origin (onnxruntime-web CDN + WASM blobs)
  if (url.origin !== location.origin) return;
  if (url.pathname.endsWith('/cohort.json') || url.pathname.includes('/data/')) {
    // network-first for cohort data
    e.respondWith(
      fetch(e.request)
        .then(r => {
          const copy = r.clone();
          caches.open(APP_VERSION).then(c => c.put(e.request, copy));
          return r;
        })
        .catch(() => caches.match(e.request))
    );
    return;
  }
  // cache-first for shell (incl. model.onnx)
  e.respondWith(
    caches.match(e.request).then(c => c || fetch(e.request))
  );
});
