/**
 * Servidor de Lancelot en Cloudflare.
 *
 * Hace tres cosas:
 *   1. Sirve la app del celular (la carpeta publico/: HTML, JS, íconos…). Eso lo hace Cloudflare solo.
 *   2. Atiende la API /api/... : listar, agregar, completar, posponer, editar y borrar tareas.
 *   3. Cada minuto (Cron Trigger) revisa qué venció y manda la notificación al celular,
 *      aunque la laptop esté apagada. A los eventos, además, les avisa con días de anticipación.
 *
 *   celular ──/api──► este Worker ──► D1 (base de datos)
 *                         │
 *                    cada minuto ──► notificación push ──► celular
 */
import { DIAS_CORTOS, aTexto, ahoraEn, conHora, ddmm, desdeTexto, describirFaltan, diaSemana, hhmm, sumarMinutos }
  from "../publico/comun/fechas.js";
import { interpretar } from "../publico/comun/interprete.js";
import { aManana } from "../publico/comun/planificador.js";
import { Almacen, REPETICIONES_VALIDAS, TIPOS_VALIDOS, limpiarAnticipacion, limpiarDuracion } from "./almacen.js";
import { enviar } from "./push.js";
import { huecos, isoDia } from "../publico/comun/horario.js";
import { combinar, horasLibres, planDelDia } from "../publico/contexto.js";
import { accionValida, autorizado, firmarAccion } from "./seguridad.js";

const VERSION_SERVIDOR = "1.5";   // (el archivo principal de un Worker solo puede exportar "default")

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

const zonaDe = (env) => env.ZONA_HORARIA || "America/Lima";
const ahoraDe = (env) => ahoraEn(zonaDe(env));
/** "09:00" -> [9, 0]: la hora de los avisos anticipados. Opcional en "vars" de wrangler.jsonc; si no está, 9:00. */
const horaAvisoDe = (env) => {
  const m = /^(\d{1,2}):(\d{2})$/.exec(env.HORA_AVISO_PREVIO || "");
  return m && +m[1] < 24 && +m[2] < 60 ? [+m[1], +m[2]] : [9, 0];
};
// El celular espera unos minutos antes de mandar un aviso anticipado: si la laptop estaba prendida y ya lo
// mostró (y lo sincronizó), no se repite en el celular.
const MINUTOS_GRACIA_PREVIO = 5;

/** Servicios de notificaciones de los navegadores: solo a ellos se les envía (nada de direcciones inventadas). */
const SERVICIOS_PUSH = [/^fcm\.googleapis\.com$/, /\.push\.services\.mozilla\.com$/, /\.notify\.windows\.com$/,
  /\.push\.apple\.com$/, /^updates\.push\.services\.mozilla\.com$/];
const MAX_SUSCRIPCIONES = 10;
const MAX_ENVIOS_POR_MINUTO = 8;
const MAX_ACCIONES = 300;

async function leerJson(request, limite = 20000) {
  if (Number(request.headers.get("Content-Length") || 0) > limite) throw new ErrorPedido("Pedido demasiado grande", 413);
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
    const t = datos.texto !== undefined
      ? desdeTextoLibre(datos.texto, ahora, (await almacen.preferencias()).vocabulario) : validar(datos, ahora);
    if (t.falta) return json(t, 422);                  // la app pregunta lo que falta y vuelve a enviar
    return json({ tarea: await almacen.agregar(t.titulo, t.fecha, t.repeticion, ahora, t.tipo, t.anticipacion, t.duracion) }, 201);
  }
  // La primera sincronización sube TODAS las tareas (también el historial de hechas): puede pesar bastante
  if (ruta === "/api/sync" && metodo === "POST") return sincronizar(await leerJson(request, 1_000_000), almacen, ahora);
  if (ruta === "/api/preferencias" && metodo === "GET") return json(await almacen.preferencias());
  // v3.19: lo que sabe la laptop (para que el celular calcule horas libres y sugerencias) y lo hecho aquí
  if (ruta === "/api/contexto" && metodo === "GET") {
    return json({ ahora: aTexto(ahora), contexto: await almacen.contexto(), acciones: await almacen.acciones() });
  }
  if (ruta === "/api/acciones" && metodo === "POST") {
    const { tipo, datos } = validarAccion(await leerJson(request));
    if ((await almacen.contarAcciones()) >= MAX_ACCIONES) {
      throw new ErrorPedido("Hay demasiadas acciones esperando a la laptop. Ábrela para que se sincronice.", 429);
    }
    return json({ accion: await almacen.agregarAccion(tipo, datos) }, 201);
  }
  if (ruta === "/api/vencidas/manana" && metodo === "POST") {
    const vencidas = (await almacen.pendientes()).filter((t) => t.fecha <= aTexto(ahora) && t.tipo !== "evento");
    for (const t of vencidas) await almacen.reprogramar(t.id, aTexto(aManana(desdeTexto(t.fecha), ahora)));
    return json({ movidas: vencidas.length });
  }

  const m = /^\/api\/tareas\/([\w-]{1,64})(?:\/(hecho|posponer|reprogramar))?$/.exec(ruta);
  if (m) {
    const [, id, accion] = m;
    let existia;
    if (!accion && metodo === "PATCH") {
      const t = validar(await leerJson(request), ahora, true);
      existia = await almacen.editar(id, t.titulo, t.fecha, t.repeticion, t.tipo, t.anticipacion, t.duracion);
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
/**
 * tipo y anticipacion son opcionales: al crear, si faltan, es una tarea sin avisos previos;
 * al editar (editando = true), si faltan, se deja lo que tenía (undefined).
 */
function validar(datos, ahora, editando = false) {
  const titulo = String(datos.titulo ?? "").trim().slice(0, 200);
  const f = desdeTexto(String(datos.fecha ?? ""));
  const repeticion = datos.repeticion || null;
  if (!titulo) throw new ErrorPedido("Falta el título");
  if (!f) throw new ErrorPedido("Fecha inválida (formato AAAA-MM-DD HH:MM)");
  const fecha = aTexto(f);                       // siempre igual de escrita: así se comparan bien como texto
  if (repeticion && !REPETICIONES_VALIDAS.has(repeticion)) throw new ErrorPedido("Repetición inválida");
  if (datos.tipo !== undefined && !TIPOS_VALIDOS.has(datos.tipo)) throw new ErrorPedido("Tipo inválido (tarea o evento)");
  if (!editando && fecha <= aTexto(ahora) && !repeticion) throw new ErrorPedido("Esa fecha ya pasó. Elige una hora futura.");
  const tipo = datos.tipo ?? (editando ? undefined : "tarea");
  const anticipacion = datos.anticipacion !== undefined ? limpiarAnticipacion(datos.anticipacion)
    : (editando ? undefined : null);
  const duracion = datos.duracion !== undefined ? limpiarDuracion(datos.duracion) : (editando ? undefined : null);
  return { titulo, fecha, repeticion, tipo, anticipacion, duracion };
}

/** "mañana 8pm pagar la luz" -> tarea, o { falta: "fecha" | "titulo" } para que la app pregunte. */
function desdeTextoLibre(texto, ahora, vocabulario = null) {
  const r = interpretar(String(texto).slice(0, 300), ahora, undefined, vocabulario);
  const extra = { repeticion: r.repeticion, tipo: r.tipo, anticipacion: r.avisos, duracion: r.duracion };
  if (!r.titulo) return { falta: "titulo", fecha: r.fecha && aTexto(r.fecha), ...extra };
  if (!r.fecha) return { falta: "fecha", titulo: r.titulo, ...extra };
  return validar({ titulo: r.titulo, fecha: aTexto(r.fecha), ...extra }, ahora);
}

// ------------------------------------------------------------ sincronización
/**
 * La laptop manda sus cambios y recibe los de aquí, en un solo pedido:
 *   → { desde: 1730000000000, cambios: [ {id, titulo, fecha, repeticion, estado, creada, completada, actualizada, borrada} ] }
 *   ← { aceptados: 3, rechazados: [], cambios: [...lo que cambió aquí desde 'desde'...], cursor: 1730000123456 }
 * 'cursor' es lo que la laptop manda como 'desde' la próxima vez.
 */
async function sincronizar(datos, almacen, ahora) {
  const desde = Number(datos.desde) || 0;
  const cambios = Array.isArray(datos.cambios) ? datos.cambios : [];
  if (cambios.length > 500) throw new ErrorPedido("Demasiados cambios en un pedido (máximo 500)");
  let aceptados = 0;
  const rechazados = [];          // un cambio inválido no frena a los demás (si no, la laptop quedaría trabada)
  for (const bruto of cambios) {
    try {
      if (await almacen.aplicarCambio(validarCambio(bruto), ahora)) aceptados++;
    } catch (e) {
      if (!(e instanceof ErrorPedido)) throw e;
      rechazados.push({ id: String(bruto?.id ?? ""), error: e.message });
    }
  }
  if (datos.preferencias && typeof datos.preferencias === "object") await guardarPreferencias(datos.preferencias, almacen);
  // v3.19: primero el contexto nuevo y después se borran las acciones ya aplicadas: así el celular nunca
  // ve un momento en que la acción desapareció pero el contexto todavía no la incluye.
  if (datos.contexto !== undefined) await almacen.guardarContexto(validarContexto(datos.contexto));
  if (Array.isArray(datos.acciones_ok)) {
    await almacen.borrarAcciones(datos.acciones_ok.filter((x) => Number.isInteger(x) && x > 0).slice(0, 500));
  }
  const filas = await almacen.cambiosDesde(desde);
  const cursor = filas.length ? filas[filas.length - 1].recibida : desde;
  return json({ aceptados, rechazados, cursor, completo: filas.length < 1000,
                cambios: filas.map(({ recibida, ...t }) => ({ ...t, borrada: Boolean(t.borrada) })),
                acciones: await almacen.acciones() });
}

/** Frases y vocabulario que comparte la laptop. Se limpian: solo textos, con tope de cantidad y largo. */
async function guardarPreferencias(p, almacen) {
  if (Array.isArray(p.frases)) {
    const frases = p.frases.filter((f) => typeof f === "string" && f.trim()).map((f) => f.trim().slice(0, 300)).slice(0, 300);
    await almacen.guardarPreferencia("frases", frases);
  }
  if (p.vocabulario && typeof p.vocabulario === "object") {
    const lista = (x) => (Array.isArray(x) ? x.filter((w) => typeof w === "string" && /^[a-z]{2,30}$/.test(w)).slice(0, 200) : []);
    await almacen.guardarPreferencia("vocabulario", {
      evento: lista(p.vocabulario.evento), no_evento: lista(p.vocabulario.no_evento), verbos: lista(p.vocabulario.verbos) });
  }
}

// ------------------------------------------------------------ contexto y acciones (v3.19)
const DIA = /^\d{4}-\d{2}-\d{2}$/;
const esDia = (x) => typeof x === "string" && DIA.test(x) && Boolean(desdeTexto(`${x} 00:00`));

/** El contexto de la laptop: se guarda tal cual, pero solo si tiene la forma esperada y un tamaño razonable. */
function validarContexto(c) {
  if (!c || typeof c !== "object" || Array.isArray(c) || c.version !== 1) throw new ErrorPedido("Contexto inválido");
  for (const k of ["horario", "excepciones", "actividades", "sugeridas"]) {
    if (!Array.isArray(c[k] ?? [])) throw new ErrorPedido(`Contexto inválido (${k})`);
  }
  if (JSON.stringify(c).length > 200_000) throw new ErrorPedido("Contexto demasiado grande", 413);
  return c;
}

/** Lo que el celular pide hacer a la laptop. Se valida todo: lo que entra aquí, la laptop lo aplica. */
function validarAccion(a) {
  const tipo = a?.tipo, d = a?.datos || {};
  if (tipo === "hecha") {
    if (!Number.isInteger(d.actividad_id) || d.actividad_id <= 0 || !esDia(d.dia)) throw new ErrorPedido("Acción inválida");
    return { tipo, datos: { actividad_id: d.actividad_id, dia: d.dia } };
  }
  if (tipo === "excepcion") {
    const titulo = String(d.titulo ?? "").trim().slice(0, 60);
    const filtro = String(d.filtro ?? "");
    if (!esDia(d.desde) || !esDia(d.hasta) || d.desde > d.hasta || !titulo || !/^[a-z]{0,5}$/.test(filtro) ||
        (desdeTexto(`${d.hasta} 00:00`) - desdeTexto(`${d.desde} 00:00`)) / 86400000 > 120) {
      throw new ErrorPedido("Excepción inválida");
    }
    return { tipo, datos: { desde: d.desde, hasta: d.hasta, filtro, titulo } };
  }
  if (tipo === "quitar_excepcion") {
    if (!esDia(d.desde) || !esDia(d.hasta) || !/^[a-z]{0,5}$/.test(String(d.filtro ?? ""))) throw new ErrorPedido("Acción inválida");
    return { tipo, datos: { desde: d.desde, hasta: d.hasta, filtro: String(d.filtro ?? "") } };
  }
  if (tipo === "actividad") {
    const nombre = String(d.nombre ?? "").trim().slice(0, 60);
    const veces = d.veces_semana ?? null, momento = d.momento ?? null;
    if (!nombre || !Number.isInteger(d.minutos) || d.minutos < 1 || d.minutos > 1440 ||
        (veces !== null && (!Number.isInteger(veces) || veces < 1 || veces > 7)) ||
        (momento !== null && !["manana", "tarde", "noche"].includes(momento))) {
      throw new ErrorPedido("Actividad inválida");
    }
    return { tipo, datos: { nombre, minutos: d.minutos, veces_semana: veces, momento } };
  }
  if (tipo === "quitar_actividad") {
    if (!Number.isInteger(d.id) || d.id <= 0) throw new ErrorPedido("Acción inválida");
    return { tipo, datos: { id: d.id } };
  }
  if (tipo === "sugerida") {
    const tarea = String(d.tarea ?? "");
    const actividad = d.actividad_id ?? null;
    if (!/^[\w-]{8,64}$/.test(tarea) || (actividad !== null && (!Number.isInteger(actividad) || actividad <= 0))) {
      throw new ErrorPedido("Acción inválida");
    }
    return { tipo, datos: { tarea, actividad_id: actividad } };
  }
  throw new ErrorPedido("Tipo de acción desconocido");
}

function validarCambio(c) {
  const id = String(c?.id ?? "");
  if (!/^[\w-]{8,64}$/.test(id)) throw new ErrorPedido("Cambio con id inválido");
  const t = validar({ titulo: c.titulo, fecha: c.fecha, repeticion: c.repeticion,
                     tipo: TIPOS_VALIDOS.has(c.tipo) ? c.tipo : undefined, anticipacion: c.anticipacion,
                     duracion: c.duracion }, null, true);
  const actualizada = Number(c.actualizada);
  if (!Number.isInteger(actualizada) || actualizada <= 0 || actualizada > Date.now() + 86400000) {
    throw new ErrorPedido("Cambio con fecha de modificación inválida");
  }
  const estado = c.estado === "hecha" ? "hecha" : "pendiente";
  const creada = desdeTexto(String(c.creada || "")) ? String(c.creada) : t.fecha;
  const completada = c.completada && desdeTexto(String(c.completada)) ? String(c.completada) : null;
  const avisoPrevio = c.aviso_previo && desdeTexto(String(c.aviso_previo)) ? String(c.aviso_previo) : null;
  return { id, ...t, estado, creada, completada, actualizada, borrada: c.borrada ? 1 : 0, aviso_previo: avisoPrevio };
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

/** "falta 1 semana · dom 15/11 09:00" */
const textoPrevio = (f, ahora) => {
  const faltan = describirFaltan(f, ahora);
  return `${faltan.charAt(0).toUpperCase()}${faltan.slice(1)} · ${DIAS_CORTOS[diaSemana(f)]} ${ddmm(f)} ${hhmm(f)}`;
};

/** Lo que corre cada minuto. */
async function avisarVencidas(env) {
  const almacen = new Almacen(env.DB);
  const ahora = ahoraDe(env);
  await almacen.adelantarRepetitivasOlvidadas(ahora);
  await almacen.cerrarEventosPasados(ahora);
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
      tipo: "tarea", evento: t.tipo === "evento", id: t.id, titulo: t.titulo, fecha: t.fecha, hora: hhmm(desdeTexto(t.fecha)),
      firmas: { hecho: await firmarAccion(env, t.id, t.fecha, "hecho"),
                posponer: await firmarAccion(env, t.id, t.fecha, "posponer") },
    }, firmas);
    intentos += r.intentos;
    // Una sola notificación por ocurrencia. Si no llegó a ningún celular (Google caído, sin internet),
    // se reintenta cada minuto durante 10 minutos.
    if (r.enviadas > 0 || t.fecha <= hace10min) await almacen.marcarAvisada(t.id, t.fecha);
  }
  // Avisos anticipados de eventos ("📅 Aniversario · falta 1 semana"). Un solo intento: si no llegó,
  // el próximo aviso (o el del mismo día) lo cubre.
  const conGracia = sumarMinutos(ahora, -MINUTOS_GRACIA_PREVIO);
  for (const { tarea: t } of await almacen.porAvisarAntes(conGracia, zonaDe(env), horaAvisoDe(env))) {
    if (puedeAvisar) {
      if (intentos >= MAX_ENVIOS_POR_MINUTO) break;
      const r = await enviarATodos(env, almacen, {
        tipo: "previo", id: t.id, titulo: `📅 ${t.titulo}`, cuerpo: textoPrevio(desdeTexto(t.fecha), ahora),
      }, firmas);
      intentos += r.intentos;
    }
    await almacen.marcarAvisoPrevio(t.id, ahora);
  }
  if (puedeAvisar && intentos < MAX_ENVIOS_POR_MINUTO) await avisarHueco(env, almacen, ahora, firmas);
}

// ------------------------------------------------------------ hueco libre (v3.20)
const MINUTOS_GRACIA_HUECO = 5;      // si la laptop te lo ofreció (estabas frente a ella), aquí no se repite
const MINUTOS_PARA_SUGERIR = 20;     // si el hueco empezó hace más, ya no se avisa

/**
 * Al empezar un hueco libre (saliste del trabajo, terminó una clase) te propone qué hacer, con la misma
 * lógica que la laptop y el celular (comun/horario.js, comun/recomendador.js). Una vez por hueco.
 * Espera unos minutos: si la laptop ya te lo dijo en la burbuja, sube 'hueco_avisado' y aquí se calla.
 * Se apaga desde la laptop: SUGERENCIAS_EN_CELULAR = False en config.py.
 */
async function avisarHueco(env, almacen, ahora, firmas) {
  const base = await almacen.contexto();
  if (!base || base.perfil?.avisar_huecos === false || !base.horario?.length) return;
  const ctx = combinar(base, await almacen.acciones());
  const dia = conHora(ahora, 0, 0);
  const tareas = await almacen.pendientes();
  const despertar = conHora(dia, ...ctx.perfil.despertar.split(":").map(Number));
  const inicio = huecos(dia, ctx.horario, ctx.perfil.despertar, ctx.perfil.dormir, null, 30, ctx.excepciones,
    tareas.filter((t) => t.duracion && t.fecha.startsWith(isoDia(dia)))
      .map((t) => [desdeTexto(t.fecha), sumarMinutos(desdeTexto(t.fecha), t.duracion), t.titulo]))
    .map(([a]) => a)
    .find((a) => a > despertar && sumarMinutos(a, MINUTOS_GRACIA_HUECO) <= ahora && ahora < sumarMinutos(a, MINUTOS_PARA_SUGERIR));
  if (!inicio) return;
  const clave = aTexto(inicio);
  if (base.hueco_avisado === clave || (await almacen.leerAjuste("hueco_avisado")) === clave) return;
  await almacen.guardarAjuste("hueco_avisado", clave);       // se intenta una sola vez, llegue o no
  const plan = planDelDia(ctx, tareas, dia, ahora);
  const s = plan.sugerencias[0];
  if (!s || s.inicio > sumarMinutos(ahora, 30)) return;
  const hasta = horasLibres(ctx, tareas, dia, ahora, 1).find(([a, b]) => a <= s.inicio && s.inicio < b)?.[1] || s.fin;
  const que = s.clase === "estudio" ? "estudiar" : s.nombre;
  await enviarATodos(env, almacen, {
    tipo: "hueco", id: clave, titulo: "💡 Tienes un hueco libre",
    cuerpo: `Hasta las ${hhmm(hasta)}. ¿Qué tal ${que}? (${s.motivo})`,
  }, firmas);
}
