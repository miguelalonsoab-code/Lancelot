/**
 * Service worker: la parte de la app que sigue viva aunque la cierres.
 *
 *  - Recibe las notificaciones que manda el servidor y las muestra, con botones
 *    "✓ Hecho" y "+10 min" que funcionan sin abrir la app.
 *  - Guarda una copia de la app para que abra al instante (y sin internet muestre algo).
 *
 * La copia guardada se renueva sola cada vez que abres la app con internet.
 */
const VERSION = "lancelot-1.9";
const ARCHIVOS = [
  "/", "/index.html", "/estilos.css", "/app.js", "/cara.js", "/manifest.webmanifest",
  "/comun/fechas.js", "/comun/interprete.js", "/comun/comandos.js", "/comun/planificador.js", "/comun/frases.js",
  "/comun/horario.js", "/comun/recomendador.js", "/comun/perfil.js", "/contexto.js", "/calendario.js", "/iconos.js", "/comun/silabas.js",
  "/fuentes/manrope.woff2", "/fuentes/jetbrains-mono.woff2", "/iconos/icono-192.png", "/iconos/insignia-96.png",
];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(VERSION).then((c) => c.addAll(ARCHIVOS)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys()
    .then((claves) => Promise.all(claves.filter((k) => k !== VERSION).map((k) => caches.delete(k))))
    .then(() => self.clients.claim()));
});

// La app: primero internet (así siempre tienes la versión nueva y todos los archivos coinciden);
// si no hay conexión, la copia guardada. La API nunca pasa por aquí: siempre en vivo.
self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.origin !== location.origin || url.pathname.startsWith("/api/")) return;
  e.respondWith((async () => {
    const cache = await caches.open(VERSION);
    try {
      const r = await fetch(e.request);
      if (r.ok) e.waitUntil(cache.put(e.request, r.clone()));
      return r;
    } catch {
      return (await cache.match(e.request, { ignoreSearch: true })) || (await cache.match("/index.html")) || Response.error();
    }
  })());
});

// ------------------------------------------------------------ notificaciones
async function avisarALaApp(datos) {
  for (const cliente of await self.clients.matchAll({ type: "window" })) cliente.postMessage(datos);
}

self.addEventListener("push", (e) => {
  let datos = {};
  try { datos = e.data.json(); } catch { datos = { titulo: "Lancelot", cuerpo: e.data?.text() }; }
  const comun = { icon: "/iconos/icono-192.png", badge: "/iconos/insignia-96.png", lang: "es" };
  let aviso;
  if (datos.tipo === "tarea") {
    aviso = self.registration.showNotification(datos.evento ? `📅 ${datos.titulo}` : datos.titulo, {
      ...comun,
      body: datos.evento ? `Es hoy, a las ${datos.hora}` : `Era para las ${datos.hora}`,
      tag: datos.id,                       // si llega otra de la misma tarea, reemplaza a la anterior
      renotify: true,
      requireInteraction: true,            // se queda hasta que la atiendas
      vibrate: [200, 100, 200],
      data: datos,
      actions: [{ action: "hecho", title: "✓ Hecho" }, { action: "posponer", title: "+10 min" }],
    });
  } else if (datos.tipo === "hueco") {      // v3.21: sugerencia al quedar libre, con botones
    aviso = self.registration.showNotification(datos.titulo, {
      ...comun, body: datos.cuerpo || "", data: datos, tag: "hueco", renotify: true,
      actions: [{ action: "lo_hago", title: "✓ Lo hago" }, { action: "luego", title: "⏰ Más tarde" }],
    });
  } else {
    aviso = self.registration.showNotification(datos.titulo || "Lancelot", {
      ...comun, body: datos.cuerpo || "", data: datos,
      ...(datos.id ? { tag: `${datos.tipo}-${datos.id}` } : {}),     // un aviso anticipado por evento a la vez
    });
  }
  e.waitUntil(Promise.all([aviso, avisarALaApp({ tipo: "actualizar" })]));
});

self.addEventListener("notificationclick", (e) => {
  const datos = e.notification.data || {};
  e.notification.close();
  const deTarea = datos.tipo === "tarea" && (e.action === "hecho" || e.action === "posponer");
  const deHueco = datos.tipo === "hueco" && (e.action === "lo_hago" || e.action === "luego");
  if (deTarea || deHueco) {
    // El botón usa la firma que trajo la notificación: solo sirve para esto y esta acción
    e.waitUntil(fetch("/api/accion", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id: datos.id, fecha: deHueco ? datos.que : datos.fecha, accion: e.action,
                             firma: datos.firmas?.[e.action], nombre: datos.nombre }),
    }).then((r) => {
      if (!r.ok) throw new Error(`HTTP ${r.status}`);    // p. ej. cambiaste la clave: la firma vieja ya no vale
      return r.json();
    }).then(async (r) => {
      await avisarALaApp({ tipo: "actualizar", mensaje: r.mensaje });
      // Sin la app abierta, la respuesta se ve como una notificación cortita
      if (deHueco && !(await self.clients.matchAll({ type: "window" })).length && r.mensaje) {
        await self.registration.showNotification("Lancelot", { body: r.mensaje, tag: "hueco",
          icon: "/iconos/icono-192.png", badge: "/iconos/insignia-96.png" });
      }
    })
      .catch(() => self.registration.showNotification("No pude hacerlo desde aquí", {
        body: deHueco ? "Abre Lancelot y escríbelo ahí." : `Abre Lancelot para marcar «${datos.titulo}».`, icon: "/iconos/icono-192.png", badge: "/iconos/insignia-96.png",
      })));
    return;
  }
  // Tocar la notificación (no un botón): abrir la app, o traerla al frente si ya estaba abierta
  e.waitUntil(self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((ventanas) => {
    const abierta = ventanas.find((v) => new URL(v.url).origin === location.origin);
    return abierta ? abierta.focus() : self.clients.openWindow("/");
  }));
});
