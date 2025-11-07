self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open("static-v1").then((cache) => cache.addAll(["/", "/manifest.webmanifest"]))
  );
});

self.addEventListener("fetch", (event) => {
  event.respondWith(
    caches.match(event.request).then((response) => response || fetch(event.request))
  );
});
