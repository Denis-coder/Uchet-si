const CACHE = 'uchet-si-c-v2'
const ASSETS = ['./', './index.html', './manifest.webmanifest', './favicon.svg']
self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(ASSETS)).then(() => self.skipWaiting()))
})
self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))).then(() => self.clients.claim()))
})
self.addEventListener('fetch', e => {
  const u = new URL(e.request.url)
  if (u.hostname.includes('githubusercontent') || u.hostname.includes('api.github.com') || u.hostname.includes('jsdelivr')) return
  e.respondWith(caches.match(e.request).then(c => c || fetch(e.request).catch(() => c)))
})
