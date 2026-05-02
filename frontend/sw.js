const CACHE_VERSION = "mdpiece-v28";
const STATIC_CACHE = `${CACHE_VERSION}-static`;
const API_CACHE = `${CACHE_VERSION}-api`;

const STATIC_ASSETS = [
  "/",
  "/index.html",
  "/css/style.css",
  "/js/app.js",
  "/manifest.json",
  "/icons/icon-192.png",
  "/icons/icon-512.png",
];

// Install: cache static assets
self.addEventListener("install", (e) => {
  e.waitUntil(
    caches.open(STATIC_CACHE).then((cache) => cache.addAll(STATIC_ASSETS))
  );
  self.skipWaiting();
});

// Activate: clean old caches
self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys
          .filter((k) => k !== STATIC_CACHE && k !== API_CACHE)
          .map((k) => caches.delete(k))
      )
    )
  );
  self.clients.claim();
});

// Listen for skip waiting message from client
self.addEventListener("message", (e) => {
  if (e.data && e.data.type === "SKIP_WAITING") {
    self.skipWaiting();
  }
});

// Fetch: network-first for API, cache-first for static
self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);

  // API requests: network first, fallback to cache
  if (url.pathname.startsWith("/api") || url.origin.includes("localhost:8000")) {
    e.respondWith(
      fetch(e.request)
        .then((res) => {
          if (res.ok && e.request.method === "GET") {
            const clone = res.clone();
            caches.open(API_CACHE).then((cache) => cache.put(e.request, clone));
          }
          return res;
        })
        .catch(() => caches.match(e.request))
    );
    return;
  }

  // Static assets: network first, fallback to cache
  e.respondWith(
    fetch(e.request).then((res) => {
      if (res.ok) {
        const clone = res.clone();
        caches.open(STATIC_CACHE).then((cache) => cache.put(e.request, clone));
      }
      return res;
    }).catch(() => {
      return caches.match(e.request).then((cached) => {
        if (cached) return cached;
        if (e.request.destination === "document") {
          return caches.match("/index.html");
        }
      });
    })
  );
});

// Background sync for offline form submissions
self.addEventListener("sync", (e) => {
  if (e.tag === "sync-records") {
    e.waitUntil(syncPendingRecords());
  }
});

async function syncPendingRecords() {
  const db = await openPendingDB();
  const pending = await db.getAll("pending");
  for (const record of pending) {
    try {
      await fetch(record.url, {
        method: record.method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(record.body),
      });
      await db.delete("pending", record.id);
    } catch {
      break; // still offline
    }
  }
}

function openPendingDB() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open("mdpiece-pending", 1);
    req.onupgradeneeded = () => req.result.createObjectStore("pending", { keyPath: "id", autoIncrement: true });
    req.onsuccess = () => {
      const db = req.result;
      resolve({
        getAll: (store) => new Promise((res) => {
          const tx = db.transaction(store, "readonly");
          const r = tx.objectStore(store).getAll();
          r.onsuccess = () => res(r.result);
        }),
        delete: (store, key) => new Promise((res) => {
          const tx = db.transaction(store, "readwrite");
          tx.objectStore(store).delete(key);
          tx.oncomplete = () => res();
        }),
      });
    };
    req.onerror = () => reject(req.error);
  });
}

// Push notifications
self.addEventListener("push", (e) => {
  const data = e.data?.json() ?? { title: "MD.Piece", body: "新通知" };
  e.waitUntil(
    self.registration.showNotification(data.title, {
      body: data.body,
      icon: "/icons/icon-192.png",
      badge: "/icons/icon-72.png",
      vibrate: [200, 100, 200],
    })
  );
});

self.addEventListener("notificationclick", (e) => {
  e.notification.close();
  e.waitUntil(clients.openWindow("/"));
});
