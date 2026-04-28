const CACHE_NAME = "md-piece-pwa-v9";
const APP_ASSETS = [
  "./",
  "./index.html",
  "./dashboard.html",
  "./styles.css",
  "./manifest.webmanifest",
  "./icon.svg",
  "./assets/app-icon-connect.png",
  "./assets/mdpiece-logo.jpg",
  "./scripts/feature-data.js",
  "./scripts/dashboard.js",
  "./scripts/feature-page.js",
  "./scripts/register-sw.js",
  "./pages/medications.html",
  "./pages/symptoms.html",
  "./pages/education.html",
  "./pages/condition-education.html",
  "./pages/symptom-analysis.html",
  "./pages/memo.html",
  "./pages/previsit.html",
  "./pages/labs.html",
  "./pages/ai-bot.html"
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(APP_ASSETS)).then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys
          .filter((key) => key !== CACHE_NAME && key.startsWith("md-piece-pwa-"))
          .map((key) => caches.delete(key))
      )
    ).then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  if (event.request.method !== "GET") {
    return;
  }

  const accept = event.request.headers.get("accept") || "";
  const isHtml = accept.includes("text/html");

  if (isHtml) {
    event.respondWith(
      fetch(event.request)
        .then((response) => {
          const clone = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
          return response;
        })
        .catch(() => caches.match(event.request).then((cached) => cached || caches.match("./index.html")))
    );
    return;
  }

  event.respondWith(
    caches.match(event.request).then((cached) => {
      if (cached) {
        return cached;
      }

      return fetch(event.request).then((response) => {
        const clone = response.clone();
        caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
        return response;
      });
    })
  );
});
