const CACHE_VERSION = "mdpiece-v147-tabbar-fullbleed";
const STATIC_CACHE = `${CACHE_VERSION}-static`;
const API_CACHE = `${CACHE_VERSION}-api`;

const STATIC_ASSETS = [
  "/",
  "/index.html",
  "/css/style.css?v=v116-dark-no-grad",
  "/css/medical-warm.css?v=v6-dark-no-grad",
  "/css/v11-modern.css?v=v19-tabbar-fullbleed",
  "/css/elder-mode.css?v=v4-fix-clobber",
  "/css/ghibli-theme.css?v=v3",
  "/css/edu-codex.css?v=v3",
  "/js/i18n.js?v=v83-predict-nav",
  "/js/bell.js?v=v81-bell",
  "/js/app.js?v=v153-fontpage",
  "/js/edu-codex.js?v=v3",
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

  // 非 http(s) 請求（blob:、data:、chrome-extension: 等）讓瀏覽器自己處理 —
  // 有些行動瀏覽器把 blob: 也送進 SW，再丟 fetch() 會出怪事（Samsung Internet PWA
  // 預覽圖載入失敗就是這個 trap）。
  if (url.protocol !== "http:" && url.protocol !== "https:") {
    return;
  }

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

// 限制：notificationclick 只能跳到本站相對路徑，避免 open redirect。
function _safeNotificationUrl(raw) {
  if (typeof raw !== "string" || !raw) return "/";
  // 只接受 "/path" 形式的相對路徑（不允許 protocol-relative "//evil.com"）
  if (raw.length > 1 && raw[0] === "/" && raw[1] !== "/") return raw;
  return "/";
}

// Push notifications
const VIBRATE_BY_PRIORITY = {
  low:     [120],
  normal:  [200, 100, 200],
  high:    [300, 100, 300, 100, 300],
  urgent:  [400, 80, 400, 80, 400, 80, 400],
};

self.addEventListener("push", (e) => {
  let data = { title: "MD.Piece", body: "新通知" };
  try {
    if (e.data) data = { ...data, ...e.data.json() };
  } catch {
    if (e.data) data.body = e.data.text();
  }
  const url = _safeNotificationUrl(data.url);
  const tag = data.tag || `mdpiece-${Date.now()}`;
  const priority = data.priority || "normal";
  const vibrate = VIBRATE_BY_PRIORITY[priority] || VIBRATE_BY_PRIORITY.normal;

  e.waitUntil(
    (async () => {
      // 若有任何同源視窗活著，請前景頁面播自訂鈴聲（瀏覽器不允許 SW 直接放音）
      const wins = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
      let anyFocused = false;
      for (const w of wins) {
        try {
          w.postMessage({
            type: "mdpiece-play-bell",
            reminder_type: data.reminder_type,
            bell_sound: data.bell_sound,
            bell_volume: data.bell_volume,
            priority,
          });
          if (w.focused) anyFocused = true;
        } catch {}
      }

      // 即使前景在播鈴聲，仍顯示通知，方便使用者點進對應頁
      await self.registration.showNotification(data.title, {
        body: data.body,
        icon: "/icons/icon-192.png",
        badge: "/icons/icon-72.png",
        vibrate,
        tag,
        renotify: true,
        requireInteraction: priority === "urgent",
        silent: anyFocused && !!data.bell_sound,  // 前景自播鈴聲時，避免 OS 再響一次
        data: {
          url,
          reminder_id: data.reminder_id,
          reminder_type: data.reminder_type,
          priority,
        },
      });
    })()
  );
});

self.addEventListener("notificationclick", (e) => {
  e.notification.close();
  const targetUrl = _safeNotificationUrl(e.notification.data && e.notification.data.url);
  const sameOriginUrl = new URL(targetUrl, self.location.origin).href;
  e.waitUntil(
    clients.matchAll({ type: "window", includeUncontrolled: true }).then((wins) => {
      for (const w of wins) {
        if ("focus" in w && w.url && new URL(w.url).origin === self.location.origin) {
          w.postMessage({ type: "mdpiece-notification-click", url: targetUrl });
          return w.focus();
        }
      }
      return clients.openWindow(sameOriginUrl);
    })
  );
});
