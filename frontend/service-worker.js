const CACHE_NAME = 'sleep-invest-v1';

// 只快取不常變的靜態資源
const STATIC_ASSETS = [
  'apple-touch-icon.png',
  'icon-192.png',
  'icon-512.png',
  'https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600;700&family=IBM+Plex+Sans+TC:wght@300;400;500;700&display=swap',
  'https://cdn.jsdelivr.net/npm/chart.js'
];

// Install: 只快取 icon 和字型
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => cache.addAll(STATIC_ASSETS))
  );
  self.skipWaiting();
});

// Activate: 清掉舊快取
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
    )
  );
  self.clients.claim();
});

// Network first：所有請求都先打 server，失敗才用快取
self.addEventListener('fetch', event => {
  event.respondWith(
    fetch(event.request)
      .then(res => {
        // 順便更新快取（只存 STATIC_ASSETS 裡的東西）
        const url = event.request.url;
        if (STATIC_ASSETS.some(a => url.includes(a))) {
          const clone = res.clone();
          caches.open(CACHE_NAME).then(cache => cache.put(event.request, clone));
        }
        return res;
      })
      .catch(() => caches.match(event.request))
  );
});
