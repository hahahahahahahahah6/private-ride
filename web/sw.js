// 私人专车 PWA service worker
// 页面和静态文件：先走网络（保证拿到最新版），断网时用缓存兜底。
// API 请求（/rides、/me、/auth 等）一律不缓存，直接走网络。
const CACHE = "private-ride-v1";
const SHELL = [
  "/web/",
  "/web/index.html",
  "/web/passenger.html",
  "/web/driver.html",
  "/web/account.html",
  "/web/track.html",
  "/web/app.js",
  "/web/i18n.js",
  "/web/styles.css",
  "/web/offline.html",
  "/web/icons/icon-192.png",
];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (e) => {
  const req = e.request;
  const url = new URL(req.url);
  // 只管本站 /web/ 下的 GET；API 和第三方（地图、Stripe）都不碰
  if (req.method !== "GET" || url.origin !== self.location.origin || !url.pathname.startsWith("/web/")) return;
  e.respondWith(
    fetch(req)
      .then((res) => {
        if (res.ok) {
          const copy = res.clone();
          caches.open(CACHE).then((c) => c.put(req, copy));
        }
        return res;
      })
      .catch(async () => {
        const hit = await caches.match(req, { ignoreSearch: true });
        if (hit) return hit;
        if (req.mode === "navigate") return caches.match("/web/offline.html");
        return Response.error();
      })
  );
});
