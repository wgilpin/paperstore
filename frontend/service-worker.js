const CACHE_NAME = 'paperstore-v1';

self.addEventListener('install', (event) => {
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener('fetch', (event) => {
  // A fetch listener is required for the PWA to be recognized as installable.
  // Only intercept GET: re-issuing POST/PUT/PATCH requests here truncates their
  // bodies (e.g. multipart file uploads), surfacing as a 502 at the proxy.
  // Let the browser handle non-GET requests natively.
  if (event.request.method !== 'GET') return;
  event.respondWith(fetch(event.request));
});
