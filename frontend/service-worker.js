const CACHE_NAME = 'paperstore-v1';

self.addEventListener('install', (event) => {
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener('fetch', (event) => {
  // Pass-through to network.
  // A fetch listener is required for the PWA to be recognized as installable.
  event.respondWith(fetch(event.request));
});
