/* Service worker de SIMPAC (lo registra src/pwa.js solo en producción y fuera de Capacitor).
   Guarda la cáscara de la app para que abra rápido y vuelva a abrir sin red:
     - /assets/ (JS y CSS con hash en el nombre): primero la caché; si no está, la red y se guarda;
     - index.html y el manifest: primero la red (así un despliegue nuevo se ve en la siguiente
       visita); sin red, lo guardado.
   NUNCA guarda datos: las consultas a Supabase, los tiles del mapa y las imágenes de otros
   servidores van siempre a la red. Un dato viejo presentado como actual sería engañar: sin red, la
   app misma lo dice ("sin conexión"). */
const VERSION = "simpac-v1";
const CASCARA = ["/", "/index.html", "/manifest.webmanifest"];

self.addEventListener("install", (e) => {
  e.waitUntil(
    caches
      .open(VERSION)
      .then((c) => c.addAll(CASCARA))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches
      .keys()
      .then((claves) => Promise.all(claves.filter((k) => k !== VERSION).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (e) => {
  const { request } = e;
  if (request.method !== "GET") return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return; // Supabase, tiles, fuentes: solo red

  if (url.pathname.startsWith("/assets/")) {
    // con hash en el nombre: lo que está en caché es lo correcto para siempre
    e.respondWith(
      caches.match(request).then(
        (hit) =>
          hit ||
          fetch(request).then((r) => {
            if (r.ok) caches.open(VERSION).then((c) => c.put(request, r.clone()));
            return r;
          })
      )
    );
    return;
  }

  if (request.mode === "navigate" || CASCARA.includes(url.pathname)) {
    // primero la red; sin red, la última cáscara guardada
    e.respondWith(
      fetch(request)
        .then((r) => {
          if (r.ok) caches.open(VERSION).then((c) => c.put("/index.html", r.clone()));
          return r;
        })
        .catch(() => caches.match("/index.html"))
    );
  }
  // lo demás (íconos del manifest, etc.): red, como siempre
});
