const CACHE='akhbar-blaharaa-v1';
self.addEventListener('install',event=>{event.waitUntil(caches.open(CACHE).then(c=>c.addAll(['/','/style.css','/news.js','/manifest.webmanifest','/icon.svg'])));self.skipWaiting();});
self.addEventListener('activate',event=>{event.waitUntil(self.clients.claim());});
self.addEventListener('fetch',event=>{const u=new URL(event.request.url);if(event.request.method!=='GET'||u.origin!==location.origin||u.pathname==='/news.json')return;event.respondWith(caches.match(event.request).then(c=>c||fetch(event.request).then(r=>{if(r.ok){const copy=r.clone();caches.open(CACHE).then(cache=>cache.put(event.request,copy));}return r;})));});
