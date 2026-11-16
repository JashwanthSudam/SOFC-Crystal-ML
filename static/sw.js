/* Caches the app shell (pages, styles, scripts, icons). API calls always go to the network. */
const CACHE = "kstar-shell-v3";
const SHELL = ["/index.html", "/login.html", "/predict.html", "/history.html", "/style.css", "/theme.js", "/ui.js",
               "/config.js", "/pwa.js", "/research.js", "/dynamic.js", "/icon-192.png", "/manifest.json"];

self.addEventListener("install", e => {
  e.waitUntil(caches.open(CACHE).then(c => Promise.allSettled(SHELL.map(u => c.add(u)))).then(() => self.skipWaiting()));
});

self.addEventListener("activate", e => {
  e.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k))))
    .then(() => self.clients.claim()));
});

self.addEventListener("fetch", e => {
  const req = e.request, url = new URL(req.url);
  if (req.method !== "GET" || url.origin !== location.origin || url.pathname.startsWith("/api/")) return;
  // Pages: try the network first so updates show up, fall back to the saved copy when offline.
  if (req.mode === "navigate") {
    e.respondWith(fetch(req).then(r => { const c = r.clone(); caches.open(CACHE).then(ch => ch.put(req, c)); return r; })
      .catch(() => caches.match(req).then(r => r || caches.match("/index.html"))));
    return;
  }
  // Styles, scripts, icons: show the saved copy straight away and refresh it in the background.
  e.respondWith(caches.match(req).then(hit => {
    const net = fetch(req).then(r => { if (r.ok) { const c = r.clone(); caches.open(CACHE).then(ch => ch.put(req, c)); } return r; }).catch(() => hit);
    return hit || net;
  }));
});
