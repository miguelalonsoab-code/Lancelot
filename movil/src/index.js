/**
 * Servidor de Lancelot en Cloudflare.
 *
 * Hace tres cosas:
 *   1. Sirve la app del celular (la carpeta publico/: HTML, JS, íconos…). Eso lo hace Cloudflare solo.
 *   2. Atiende la API /api/... : listar, agregar, completar, posponer, editar y borrar tareas.
 *   3. Cada minuto (Cron Trigger) revisa qué venció y manda la notificación al celular,
 *      aunque la laptop esté apagada.
 *
 *   celular ──/api──► este Worker ──► D1 (base de datos)
 *                         │
 *                    cada minuto ──► notificación push ──► celular
 */
import { aTexto, ahoraEn, desdeTexto, hhmm, sumarMinutos } from "../publico/comun/fechas.js";
import { interpretar } from "../publico/comun/interprete.js";
import { aManana } from "../publico/comun/planificador.js";
import { Almacen, REPETICIONES_VALIDAS } from "./almacen.js";
import { enviar } from "./push.js";
import { accionValida, autorizado, firmarAccion } from "./seguridad.js";

const VERSION_SERVIDOR = "1.0";   // (el archivo principal de un Worker solo puede exportar "default")

export default {
  async fetch(request, env) {
    try {
      return await atender(request, env);
    } catch (e) {
      if (e instanceof ErrorPedido) return json({ error: e.message }, e.estado);
      console.error(e);
      return json({ error: "Error interno del servidor" }, 500);
    }
  },

  async scheduled(_evento, env, ctx) {
    ctx.waitUntil(avisarVencidas(env));
  },
};

class ErrorPedido extends Error {
  constructor(mensaje, estado = 400) { super(mensaje); this.estado = estado; }
}

const json = (datos, estado = 200) => new Response(JSON.stringify(datos), {
  status: estado,
  headers: { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store" },
});

const ahoraDe = (env) => ahoraEn(env.ZONA_HORARIA || "America/Lima");

/** Servicios de notificaciones de los navegadores: solo a ellos se les envía (nada de direcciones inventadas). */
const SERVICIOS_PUSH = [/^fcm\.googleapis\.com$/, /\.push\.services\.mozilla\.com$/, /\.notify\.windows\.com$/,
  /\.push\.apple\.com$/, /^updates\.push\.services\.mozilla\.com$/];
const MAX_SUSCRIPCIONES = 10;
const MAX_ENVIOS_POR_MINUTO = 8;

async function leerJson(request) {
  if (Number(request.headers.get("Content-Length") || 0) > 20000) throw new ErrorPedido("Pedido demasiado grande", 413);
  try {
    return await request.json();
  } catch {
    throw new ErrorPedido("El cuerpo no es JSON válido");
  }
}

// ------------------------------------------------------------------- rutas
async function atender(request, env) {
  const url = new URL(request.url);
  const ruta = url.pathname;
  const metodo = request.method;
  if (!ruta.startsWith("/api/")) return env.ASSETS.fetch(request);

  // Sin clave: estado (para saber si la dirección es correcta) y botones de notificaciones (con firma)
  if (ruta === "/api/estado") {
    return json({ ok: true, version: VERSION_SERVIDOR, configurado: Boolean(env.CLAVE && env.VAPID_PUBLICA) });
  }
  if (ruta === "/api/accion" && metodo === "POST") return accionDeNotificacion(await leerJson(request), env);

  if (!(await autorizado(request, env))) return json({ error: "Clave incorrecta" }, 401);
  const almacen = new Almacen(env.DB);
  const ahora = ahoraDe(env);

  if (ruta === "/api/tareas" && metodo === "GET") {
    return json({ ahora: aTexto(ahora), tareas: await almacen.pendientes() });
  }
  if (ruta === "/api/tareas" && metodo === "POST") {
    const datos = await leerJson(request);
    const t = datos.texto !== undefined ? desdeTextoLibre(datos.texto, ahora) : validar(datos, ahora);
    if (t.falta) return json(t, 422);                  // la app pregunta lo que falta y vuelve a enviar
    return json({ tarea: await almacen.agregar(t.titulo, t.fecha, t.repeticion, ahora) }, 201);
  }
  if (ruta === "/api/vencidas/manana" && metodo === "POST") {
    const vencidas = (await almacen.pendientes()).filter((t) => t.fecha <= aTexto(ahora));
    for (const t of vencidas) await almacen.reprogramar(t.id, aTexto(aManana(desdeTexto(t.fecha), ahora)));
    return json({ movidas: vencidas.length });
  }

  const m = /^\/api\/tareas\/([\w-]{1,64})(?:\/(hecho|posponer|reprogramar))?$/.exec(ruta);
  if (m) {
    const [, id, accion] = m;
    let existia;
    if (!accion && metodo === "PATCH") {
      const t = validar(await leerJson(request), ahora, true);
      existia = await almacen.editar(id, t.titulo, t.fecha, t.repeticion);
    } else if (!accion && metodo === "DELETE") {
      existia = await almacen.eliminar(id);
    } else if (accion === "hecho" && metodo === "POST") {
      const cuerpo = await request.text();               // opcional: { fecha } = la ocurrencia que viste
      let esperada = null;
      try { esperada = cuerpo ? JSON.parse(cuerpo).fecha : null; } catch { throw new ErrorPedido("El cuerpo no es JSON válido"); }
      const t = await almacen.completar(id, ahora, esperada || null);
      if (!t) return json({ error: "No existe esa tarea" }, 404);
      return t.yaResuelta ? json({ error: "Esa tarea ya estaba resuelta.", tarea: t.tarea }, 409) : json({ tarea: t });
    } else if (accion === "posponer" && metodo === "POST") {
      const minutos = Number((await leerJson(request)).minutos);
      if (!Number.isInteger(minutos) || minutos < 1 || minutos > 7 * 1440) throw new ErrorPedido("Minutos inválidos");
      existia = await almacen.posponer(id, minutos, ahora);
    } else if (accion === "reprogramar" && metodo === "POST") {
      const f = desdeTexto((await leerJson(request)).fecha);
      if (!f || aTexto(f) <= aTexto(ahora)) throw new ErrorPedido("Elige una fecha futura");
      existia = await almacen.reprogramar(id, aTexto(f));
    } else {
      return json({ error: "Método no permitido" }, 405);
    }
    return existia ? json({ tarea: await almacen.obtener(id) }) : json({ error: "No existe esa tarea" }, 404);
  }

  // Notificaciones
  if (ruta === "/api/push/clave" && metodo === "GET") return json({ clave: env.VAPID_PUBLICA || null });
  if (ruta === "/api/push/suscribir" && metodo === "POST") {
    const { suscripcion: s, dispositivo } = await leerJson(request);
    const local = env.PERMITIR_PUSH_LOCAL === "1" && s?.endpoint?.startsWith("http://127.0.0.1");   // solo en pruebas
    let servicio = "";
    try { const u = new URL(s.endpoint); servicio = u.protocol === "https:" ? u.hostname : ""; } catch { /* inválida */ }
    if (!(local || SERVICIOS_PUSH.some((r) => r.test(servicio))) || s.endpoint.length > 1000 ||
        !s.keys?.p256dh || !s.keys?.auth) {
      throw new ErrorPedido("Suscripción inválida");
    }
    if ((await almacen.contarSuscripciones()) >= MAX_SUSCRIPCIONES) {
      throw new ErrorPedido("Hay demasiados dispositivos suscritos. Desactiva las notificaciones en alguno.");
    }
    await almacen.guardarSuscripcion(s, String(dispositivo || "").slice(0, 80), ahora);
    return json({ ok: true });
  }
  if (ruta === "/api/push/desuscribir" && metodo === "POST") {
    await almacen.borrarSuscripcion(String((await leerJson(request)).endpoint || ""));
    return json({ ok: true });
  }
  if (ruta === "/api/push/prueba" && metodo === "POST") {
    const { enviadas } = await enviarATodos(env, almacen, {
      tipo: "prueba", titulo: "🔔 Notificaciones listas",
      cuerpo: "Así te avisaré de tus tareas, aunque la laptop esté apagada.",
    });
    return json({ enviadas });
  }

  return json({ error: "No existe esa ruta" }, 404);
}

// ------------------------------------------------------------ validaciones
function validar(datos, ahora, editando = false) {
  const titulo = String(datos.titulo ?? "").trim().slice(0, 200);
  const f = desdeTexto(String(datos.fecha ?? ""));
  const repeticion = datos.repeticion || null;
  if (!titulo) throw new ErrorPedido("Falta el título");
  if (!f) throw new ErrorPedido("Fecha inválida (formato AAAA-MM-DD HH:MM)");
  const fecha = aTexto(f);                       // siempre igual de escrita: así se comparan bien como texto
  if (repeticion && !REPETICIONES_VALIDAS.has(repeticion)) throw new ErrorPedido("Repetición inválida");
  if (fecha <= aTexto(ahora) && !repeticion && !editando) throw new ErrorPedido("Esa fecha ya pasó. Elige una hora futura.");
  return { titulo, fecha, repeticion };
}

/** "mañana 8pm pagar la luz" -> tarea, o { falta: "fecha" | "titulo" } para que la app pregunte. */
function desdeTextoLibre(texto, ahora) {
  const r = interpretar(String(texto).slice(0, 300), ahora);
  if (!r.titulo) return { falta: "titulo", fecha: r.fecha && aTexto(r.fecha), repeticion: r.repeticion };
  if (!r.fecha) return { falta: "fecha", titulo: r.titulo, repeticion: r.repeticion };
  return validar({ titulo: r.titulo, fecha: aTexto(r.fecha), repeticion: r.repeticion }, ahora);
}

// ------------------------------------------------------------ notificaciones
async function accionDeNotificacion({ id, fecha, accion, firma }, env) {
  if (!["hecho", "posponer"].includes(accion) || !(await accionValida(env, id, fecha, accion, firma))) {
    return json({ error: "Firma inválida" }, 403);
  }
  const almacen = new Almacen(env.DB);
  const tarea = await almacen.obtener(id);
  if (!tarea || tarea.estado !== "pendiente" || tarea.fecha !== fecha) {
    return json({ ok: true, mensaje: "Esa tarea ya estaba resuelta." });      // botón de una notificación vieja
  }
  const ahora = ahoraDe(env);
  if (accion === "hecho") {
    const r = await almacen.completar(id, ahora, fecha);
    return json({ ok: true, mensaje: r?.yaResuelta ? "Esa tarea ya estaba resuelta." : `✓ ${tarea.titulo}` });
  }
  await almacen.posponer(id, 10, ahora);
  return json({ ok: true, mensaje: `+10 min: ${tarea.titulo}` });
}

const vapidDe = (env) => ({ publica: env.VAPID_PUBLICA, privada: env.VAPID_PRIVADA,
  contacto: env.CONTACTO_PUSH || "https://github.com/miguelalonsoab-code/Lancelot" });

/**
 * Envía a todos los celulares suscritos. Devuelve { enviadas, intentos }.
 * Borra las suscripciones muertas: 404/410 (el celular ya no existe) y 401/403 (fue creada con otras
 * claves de notificación, así que nunca más va a funcionar: la app se vuelve a suscribir sola al abrirse).
 */
async function enviarATodos(env, almacen, datos, firmas = new Map()) {
  if (!env.VAPID_PUBLICA || !env.VAPID_PRIVADA) return { enviadas: 0, intentos: 0 };
  const suscripciones = await almacen.suscripciones();
  const estados = await Promise.all(suscripciones.map((s) => enviar(s, datos, vapidDe(env), firmas).catch(() => 0)));
  let enviadas = 0;
  for (const [i, estado] of estados.entries()) {
    if ([401, 403, 404, 410].includes(estado)) await almacen.borrarSuscripcion(suscripciones[i].endpoint);
    else if (estado >= 200 && estado < 300) enviadas++;
    else console.warn("push no entregado", estado);
  }
  return { enviadas, intentos: suscripciones.length };
}

/** Lo que corre cada minuto. */
async function avisarVencidas(env) {
  const almacen = new Almacen(env.DB);
  const ahora = ahoraDe(env);
  await almacen.adelantarRepetitivasOlvidadas(ahora);
  const puedeAvisar = Boolean(env.VAPID_PUBLICA && env.VAPID_PRIVADA) && (await almacen.contarSuscripciones()) > 0;
  const hace10min = aTexto(sumarMinutos(ahora, -10));
  const firmas = new Map();
  let intentos = 0;
  // Plan gratuito: 10 ms de CPU por ejecución y cifrar una notificación cuesta ~1,5 ms.
  // Por eso hay un tope de envíos por minuto; lo que no alcance, sale al minuto siguiente.
  for (const t of await almacen.porAvisar(ahora, 5)) {
    if (!puedeAvisar) { await almacen.marcarAvisada(t.id, t.fecha); continue; }   // nadie a quien avisar
    if (intentos >= MAX_ENVIOS_POR_MINUTO) break;
    const r = await enviarATodos(env, almacen, {
      tipo: "tarea", id: t.id, titulo: t.titulo, fecha: t.fecha, hora: hhmm(desdeTexto(t.fecha)),
      firmas: { hecho: await firmarAccion(env, t.id, t.fecha, "hecho"),
                posponer: await firmarAccion(env, t.id, t.fecha, "posponer") },
    }, firmas);
    intentos += r.intentos;
    // Una sola notificación por ocurrencia. Si no llegó a ningún celular (Google caído, sin internet),
    // se reintenta cada minuto durante 10 minutos.
    if (r.enviadas > 0 || t.fecha <= hace10min) await almacen.marcarAvisada(t.id, t.fecha);
  }
}
