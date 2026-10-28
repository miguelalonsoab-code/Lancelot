/**
 * Lancelot en el celular.
 *
 *   - Escribes como en la laptop: "mañana 8pm pagar la luz". Si falta algo, pregunta.
 *   - La lista se agrupa en: vencidas, hoy, mañana y los días siguientes.
 *   - Tocar el círculo = hecho. Tocar la tarea = más opciones (posponer, reprogramar, editar, borrar).
 *   - Los EVENTOS (aniversario, examen, viaje…) llevan 📅 y "faltan N días"; avisan con anticipación.
 *   - Orden de la lista: Tareas vencidas (siempre a la vista) · 📅 Próximos eventos · tareas por día.
 *   - Tocar la cara: una frase (las de fábrica y las tuyas de la laptop), en voz alta si la voz está activada.
 *   - Las notificaciones las manda el servidor cada minuto, aunque la app esté cerrada (ver sw.js).
 *
 * Todo lo que el usuario escribe se muestra con textContent (nunca como HTML).
 */
import { Cara } from "./cara.js";
import { ACCIONES_CELULAR, interpretarComando } from "./comun/comandos.js";
import {
  aTexto, ahoraEn, conHora, DIAS, describirAtraso, describirFaltan, describirFecha, desdeTexto, diasEntre, diaSemana,
  hhmm, MESES, soloFecha, sumarDias, sumarMinutos,
} from "./comun/fechas.js";
import { avisosPrevios, describirAvisos, describirRango, interpretar as interpretarBase, REPETICIONES, TIPOS }
  from "./comun/interprete.js";
import { BolsaFrases, REFLEXIONES } from "./comun/frases.js";
import { coincide, describirBloque, describirExcepcion, describirLibre, duracionMinutos, hablarDuracion, interpretarBloque,
  interpretarExcepcion, isoDia, leerDuracion, lunesDe, minutos } from "./comun/horario.js";
import { opcionesReprogramar } from "./comun/planificador.js";
import { describirActividad, interpretarActividad, leerHora } from "./comun/perfil.js";
import { describirPlan } from "./comun/recomendador.js";
import { pintarCalendario } from "./calendario.js";
import { actividadesQueNombra, combinar, esSugerida, hechasEntre, horasLibres, planDelDia } from "./contexto.js";

const ZONA = "America/Lima";
const NOMBRE = "Miguel";
const VERSION_APP = "1.6";

const $ = (id) => document.getElementById(id);
const ahora = () => ahoraEn(ZONA);
const cara = new Cara($("cara"));

const estado = {
  clave: leer("clave"),
  tareas: [],
  espera: null,          // { falta: "titulo" | "fecha", titulo, fecha, repeticion, tipo, anticipacion, duracion }
  saludado: false,
  instalar: null,        // aviso de "instalar app" que ofrece Chrome
  vocabulario: null,     // lo que la laptop aprendió de tus correcciones Tarea/Evento
  // v3.19: lo que sabe la laptop (horario, perfil…) y lo hecho aquí que todavía no llegó allá
  contexto: null,
  acciones: [],
  vista: leer("vista") === "calendario" ? "calendario" : "lista",
  calMes: null,          // primer día del mes que se ve en el calendario
  calModo: leer("calModo") === "semana" ? "semana" : "mes",
  calDia: null,          // día elegido
  ultimoPlan: null,      // { plan, dia } de la última sugerencia mostrada (para «agéndalo»)
};
/** El contexto de la laptop + lo pendiente de aquí (ver contexto.js). */
const ctx = () => combinar(estado.contexto, estado.acciones);
const frases = new BolsaFrases(REFLEXIONES);

/** Igual que el intérprete común, pero con lo aprendido en la laptop. */
const interpretar = (texto, ahora) => interpretarBase(texto, ahora, undefined, estado.vocabulario);

// ------------------------------------------------------------ utilidades
function leer(clave) { try { return localStorage.getItem(clave); } catch { return null; } }
function guardar(clave, valor) {
  try { valor === null ? localStorage.removeItem(clave) : localStorage.setItem(clave, valor); } catch { /* sin almacenamiento */ }
}

/** Crea un elemento: el("button", { class: "x", onclick }, "texto", hijo…) */
function el(tag, attrs = {}, ...hijos) {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === undefined || v === null || v === false) continue;
    if (k.startsWith("on")) n.addEventListener(k.slice(2), v);
    else if (k === "class") n.className = v;
    else n.setAttribute(k, v === true ? "" : v);
  }
  for (const h of hijos.flat()) if (h !== null && h !== undefined && h !== false) n.append(h);
  return n;
}

const plural = (n, uno, varios) => `${n} ${n === 1 ? uno : varios}`;
const esEvento = (t) => t.tipo === "evento";
const conIcono = (t) => (esEvento(t) ? `📅 ${t.titulo}` : t.titulo);
const capital = (s) => s.charAt(0).toUpperCase() + s.slice(1);
const aInput = (texto) => texto.replace(" ", "T");                 // '2026-10-11 20:00' -> datetime-local
const deInput = (valor) => (valor ? valor.replace("T", " ").slice(0, 16) : "");

function decir(texto) {
  $("dice").textContent = texto;
}

// ------------------------------------------------------------ voz (frases)
const vozActiva = () => leer("voz") !== "0";

/** Lee en voz alta con la voz del celular (Chrome), si hay una en español. */
function hablar(texto) {
  if (!vozActiva() || !("speechSynthesis" in window)) return;
  const v = speechSynthesis.getVoices();
  const voz = v.find((x) => /^es[-_](PE|419|US|MX)/i.test(x.lang)) || v.find((x) => /^es/i.test(x.lang));
  try {                                              // la voz es un extra: si falla, la frase igual se ve
    const u = new SpeechSynthesisUtterance(texto);
    u.lang = voz?.lang || "es-419";
    if (voz) u.voice = voz;
    speechSynthesis.cancel();
    speechSynthesis.speak(u);
  } catch { /* sin voz */ }
}

function decirFrase() {
  const frase = frases.sacar();
  if (!frase) return;
  decir(`💬 ${frase}`);
  hablar(frase);
  cara.celebrar(1.5);
}

$("cara").addEventListener("click", () => { if (estado.clave) decirFrase(); });
$("cara").addEventListener("keydown", (e) => { if ((e.key === "Enter" || e.key === " ") && estado.clave) decirFrase(); });

/** Tus frases y lo aprendido, que sube la laptop. Si falla, quedan las de fábrica. */
async function cargarPreferencias() {
  const r = await api("/api/preferencias").catch(() => null);
  if (!r) return;
  frases.cambiar([...REFLEXIONES, ...(r.frases || [])]);
  estado.vocabulario = r.vocabulario || null;
}

// ------------------------------------------------------------ servidor
class SinConexion extends Error {}

async function api(ruta, { metodo = "GET", cuerpo } = {}) {
  let r;
  try {
    r = await fetch(ruta, {
      method: metodo,
      headers: { Authorization: `Bearer ${estado.clave}`, "Content-Type": "application/json" },
      body: cuerpo === undefined ? undefined : JSON.stringify(cuerpo),
    });
  } catch {
    throw new SinConexion("Sin conexión. Revisa tu internet e inténtalo de nuevo.");
  }
  const datos = await r.json().catch(() => ({}));
  if (r.status === 401) {
    const eraConocida = Boolean(leer("clave"));
    guardar("clave", null);
    estado.clave = null;
    mostrarConectar(eraConocida ? "La clave cambió. Escribe la nueva para seguir."
      : "Esa clave no es correcta. Son 4 grupos de 5 letras y números, separados por guiones.");
    throw new Error("Clave incorrecta");
  }
  if (!r.ok && r.status !== 422) throw new Error(datos.error || `El servidor respondió ${r.status}.`);
  return { codigo: r.status, ...datos };
}

/** Ejecuta una acción con el servidor; si falla, Lancelot lo dice en la burbuja. */
async function intentar(accion) {
  try {
    return await accion();
  } catch (e) {
    if (e.message !== "Clave incorrecta") decir(e.message);
    return null;
  }
}

let numeroDeCarga = 0;

async function recargar() {
  if (!estado.clave) return;
  const mia = ++numeroDeCarga;                       // si llega una respuesta vieja después de una nueva, se ignora
  const r = await intentar(() => api("/api/tareas"));
  if (!r || mia !== numeroDeCarga) return;
  estado.tareas = r.tareas;
  pintar();
  cargarContexto();
}

/** Horario, perfil y actividades que subió la laptop, y lo hecho aquí que ella todavía no aplicó. */
async function cargarContexto() {
  const r = await api("/api/contexto").catch(() => null);
  if (!r) return;
  estado.contexto = r.contexto || null;
  estado.acciones = r.acciones || [];
  pintar();
}

/** Pide algo a la laptop (se aplica cuando sincronice) y lo suma al instante aquí. */
async function accion(tipo, datos) {
  const r = await intentar(() => api("/api/acciones", { metodo: "POST", cuerpo: { tipo, datos } }));
  if (r?.accion) estado.acciones.push(r.accion);
  return r?.accion || null;
}

// ------------------------------------------------------------ pantallas
function mostrarConectar(mensaje) {
  $("conectar").hidden = false;
  $("principal").hidden = $("redactar").hidden = $("b-ajustes").hidden = true;
  cara.poner("dormido");
  document.body.dataset.estado = "dormido";
  decir(mensaje || "Hola, soy Lancelot. Conecta este celular con tu clave.");
}

function mostrarPrincipal() {
  $("conectar").hidden = true;
  $("principal").hidden = $("redactar").hidden = $("b-ajustes").hidden = false;
}

$("f-conectar").addEventListener("submit", async (e) => {
  e.preventDefault();
  await conectar($("clave").value.trim());
});

async function conectar(clave) {
  if (!clave) return;
  estado.clave = clave;
  decir("Comprobando…");
  try {
    const r = await api("/api/tareas");
    guardar("clave", clave);
    estado.tareas = r.tareas;
    mostrarPrincipal();
    pintar();
    cargarPreferencias();
    cargarContexto();
    decir(`¡Listo, ${NOMBRE}! Ya estamos conectados. Activa las notificaciones en ⚙.`);
    cara.celebrar();
  } catch (e) {
    if (e instanceof SinConexion) decir(e.message);
  }
}

// ------------------------------------------------------------ lista
/**
 * Tareas vencidas (siempre, aunque no haya) · 📅 Próximos eventos · las tareas agrupadas por día.
 * Un evento nunca "vence": el de hoy sigue entre los eventos hasta que termina el día.
 */
function agrupar(tareas, now) {
  const limite = aTexto(now);
  const c = ctx();
  const grupos = new Map([["vencidas", { tipo: "vencidas", titulo: "", tareas: [] }]]);
  const eventos = tareas.filter(esEvento);
  if (eventos.length) grupos.set("eventos", { tipo: "eventos", titulo: `📅 Próximos eventos · ${eventos.length}`, tareas: eventos });
  for (const t of tareas.filter((x) => !esEvento(x))) {
    const f = desdeTexto(t.fecha);
    let clave, titulo, tipo;
    if (t.fecha <= limite && !esSugerida(c, t)) {
      clave = "vencidas"; tipo = "vencidas";
    } else if (t.fecha <= limite) {                // 💡 agendada desde una sugerencia: no "vence"
      clave = soloFecha(now).toISOString(); tipo = "hoy"; titulo = "Hoy";
    } else {
      const dias = diasEntre(now, f);
      clave = soloFecha(f).toISOString();
      tipo = dias === 0 ? "hoy" : "futuro";
      titulo = dias === 0 ? "Hoy" : dias === 1 ? "Mañana"
        : `${capital(DIAS[diaSemana(f)])} ${f.getUTCDate()} de ${MESES[f.getUTCMonth()]}`;
    }
    if (!grupos.has(clave)) grupos.set(clave, { tipo, titulo, tareas: [] });
    grupos.get(clave).tareas.push(t);
  }
  const vencidas = grupos.get("vencidas");
  vencidas.titulo = `Tareas vencidas · ${vencidas.tareas.length}`;
  return [...grupos.values()];                       // el Map conserva el orden: vencidas, eventos, días
}

function pintar() {
  const now = ahora();
  $("lista").hidden = estado.vista !== "lista";
  $("calendario").hidden = estado.vista !== "calendario";
  $("p-lista").setAttribute("aria-selected", estado.vista === "lista");
  $("p-calendario").setAttribute("aria-selected", estado.vista === "calendario");
  if (estado.vista === "calendario") pintarVistaCalendario(now);
  const lista = $("lista");
  lista.replaceChildren();
  const grupos = agrupar(estado.tareas, now);
  for (const g of grupos) {
    const vacia = g.tipo === "vencidas" && !g.tareas.length;
    const cabeza = el("div", { class: "grupo-cabeza" }, el("h3", {}, g.titulo),
      g.tipo === "vencidas" && !vacia && el("button", { class: "enlace", onclick: todasAManana }, "Pasar todas a mañana"));
    lista.append(el("section", { class: "grupo", "data-tipo": g.tipo, "data-vacio": vacia }, cabeza,
      vacia ? el("p", { class: "nada" }, "Ninguna. Vas al día 👌") : g.tareas.map((t) => fila(t, g.tipo, now))));
  }
  if (estado.tareas.length === 0) {
    lista.append(el("p", { class: "vacio" }, "No tienes nada pendiente. Escribe abajo, por ejemplo: «el viernes a las 3 llamar al banco»."));
  }
  actualizarCara(now);
}

function fila(t, tipo, now) {
  const f = desdeTexto(t.fecha);
  const faltan = esEvento(t) ? describirFaltan(f, now) : null;
  const dia = tipo === "eventos" ? `${capital(DIAS[diaSemana(f)])} ${f.getUTCDate()} de ${MESES[f.getUTCMonth()]}` : null;
  const sugerida = esSugerida(ctx(), t);
  const pasada = t.fecha <= aTexto(now);
  const detalle = [dia, tipo === "vencidas" ? describirAtraso(f, now) : null,
    sugerida && pasada ? `💡 Era a las ${hhmm(f)}: si no la haces, mañana se quita sola` : null,
    t.duracion && tipo !== "vencidas" ? `De ${describirRango(f, t.duracion).replace("–", " a ")}` : null,
    faltan && capital(faltan),
    t.repeticion ? `Se repite: ${REPETICIONES[t.repeticion].toLowerCase()}` : null].filter(Boolean).join(". ");
  const nodo = el("div", { class: "tarea", "data-id": t.id, "data-evento": esEvento(t) },
    el("span", { class: "hora" }, hhmm(f)),
    el("button", { class: "que", onclick: () => opcionesDeTarea(t) },
      el("span", { class: "titulo" }, (sugerida ? "💡 " : "") + conIcono(t)), detalle && el("span", { class: "detalle" }, detalle)),
    el("button", { class: "hecho", "aria-label": `Marcar «${t.titulo}» como hecha`, onclick: () => completar(t, nodo) }));
  return nodo;
}

/** Tareas vencidas de verdad (las 💡 agendadas desde una sugerencia no cuentan). */
const vencidasDe = (now) => { const c = ctx(); return estado.tareas.filter((t) => t.fecha <= aTexto(now) && !esEvento(t) && !esSugerida(c, t)); };

function actualizarCara(now) {
  const limite = aTexto(now);
  const vencidas = vencidasDe(now);
  const hoy = estado.tareas.filter((t) => t.fecha > limite && diasEntre(now, desdeTexto(t.fecha)) === 0);
  const h = now.getUTCHours();
  const animo = vencidas.length ? "alerta" : hoy.length ? "pendiente" : (h >= 23 || h < 6) ? "dormido" : "tranquilo";
  cara.poner(animo, hoy.length);
  document.body.dataset.estado = animo;
  if (!estado.saludado && !estado.espera) {
    estado.saludado = true;
    decir(resumen(now, true));
  }
}

/** Lo que Lancelot te dice al abrir la app (o si preguntas "¿qué tengo para hoy?"). */
function resumen(now, conSaludo = false) {
  const limite = aTexto(now);
  const vencidas = vencidasDe(now);
  const hoy = estado.tareas.filter((t) => t.fecha > limite && diasEntre(now, desdeTexto(t.fecha)) === 0);
  const h = now.getUTCHours();
  const saludo = h >= 5 && h < 12 ? "Buenos días" : h < 19 && h >= 12 ? "Buenas tardes" : "Buenas noches";
  const partes = conSaludo ? [`${saludo}, ${NOMBRE}.`] : [];
  if (hoy.length) {
    const p = hoy[0];
    partes.push(`Hoy te ${hoy.length === 1 ? "queda" : "quedan"} ${plural(hoy.length, "tarea", "tareas")}. ` +
      `La próxima: ${p.titulo}, a las ${hhmm(desdeTexto(p.fecha))}.`);
  } else {
    partes.push("No tienes nada más para hoy.");
  }
  if (vencidas.length) partes.push(`Y ${plural(vencidas.length, "vencida", "vencidas")}: tócala para reprogramar.`);
  // Eventos de los próximos 7 días (los de hoy ya salieron arriba)
  const pronto = estado.tareas.filter((t) => esEvento(t) && t.fecha > limite &&
    diasEntre(now, desdeTexto(t.fecha)) >= 1 && diasEntre(now, desdeTexto(t.fecha)) <= 7);
  if (pronto.length) {
    partes.push(`Se acerca: ${pronto.slice(0, 2).map((t) => `${t.titulo} (${describirFaltan(desdeTexto(t.fecha), now)})`).join(" y ")}.`);
  }
  return partes.join(" ");
}

// ------------------------------------------------------------ acciones
async function completar(t, nodo) {
  if (nodo?.classList.contains("lista-hecha")) return;      // doble toque: ya va en camino
  nodo?.classList.add("lista-hecha");
  const r = await intentar(() => api(`/api/tareas/${t.id}/hecho`, { metodo: "POST", cuerpo: { fecha: t.fecha } }));
  if (!r) { nodo?.classList.remove("lista-hecha"); recargar(); return; }
  cara.celebrar();
  decir(r.tarea.estado === "pendiente"
    ? `✓ ${t.titulo}. La próxima vez: ${describirFecha(desdeTexto(r.tarea.fecha), ahora())}.`
    : `✓ ${t.titulo}. ¡Bien hecho!`);
  nodo?.classList.add("saliendo");
  setTimeout(recargar, 330);
}

async function cambiarFecha(t, fecha, mensaje) {
  const r = await intentar(() => api(`/api/tareas/${t.id}/reprogramar`, { metodo: "POST", cuerpo: { fecha } }));
  if (!r) return;
  cerrarHoja();
  decir(mensaje || `Movida a ${describirFecha(desdeTexto(fecha), ahora())}: ${t.titulo}.`);
  cara.celebrar();
  recargar();
}

async function posponer(t, minutos) {
  const r = await intentar(() => api(`/api/tareas/${t.id}/posponer`, { metodo: "POST", cuerpo: { minutos } }));
  if (!r) return;
  cerrarHoja();
  decir(`Te la recuerdo en ${minutos < 60 ? `${minutos} minutos` : plural(minutos / 60, "hora", "horas")}: ${t.titulo}.`);
  recargar();
}

async function todasAManana() {
  const r = await intentar(() => api("/api/vencidas/manana", { metodo: "POST" }));
  if (!r) return;
  decir(r.movidas ? `Pasé ${plural(r.movidas, "tarea", "tareas")} a mañana, a la misma hora.` : "No tienes tareas vencidas.");
  if (r.movidas) cara.celebrar();
  recargar();
}

const PISTA = "mañana 8pm pagar la luz";
const normalizarSimple = (t) => t.toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "").trim();

function terminarEspera() {
  estado.espera = null;
  entrada.placeholder = PISTA;
}

async function crear(titulo, fecha, repeticion, tipo = "tarea", anticipacion = null, duracion = null) {
  const r = await intentar(() => api("/api/tareas", { metodo: "POST",
    cuerpo: { titulo, fecha, repeticion, tipo, anticipacion, duracion } }));
  if (!r) return false;
  terminarEspera();                                  // antes de cerrar la hoja: así no dice "no la anoté"
  cerrarHoja();
  cara.celebrar();
  const cuando = describirFecha(desdeTexto(r.tarea.fecha), ahora());
  const avisos = anticipacion ? ` Te aviso ${describirAvisos(anticipacion).replace("avisa ", "")} y ese día.` : "";
  decir(`Anotado${tipo === "evento" ? " el evento" : ""}: ${r.tarea.titulo}, ${cuando}` +
    `${repeticion ? ` (${REPETICIONES[repeticion].toLowerCase()})` : ""}.${avisos}`);
  await recargar();
  return true;
}

// ------------------------------------------------------------ escribir
const entrada = $("entrada");

entrada.addEventListener("input", () => vistaPrevia(entrada.value));

function vistaPrevia(texto) {
  const vista = $("vista");
  vista.dataset.tipo = "";
  if (!texto.trim()) {
    vista.textContent = estado.espera?.falta === "titulo" ? "Escribe qué te recuerdo." : "";
    return;
  }
  if (estado.espera?.falta === "titulo") { vista.textContent = `Título: «${texto.trim()}»`; return; }
  const c = interpretarComando(texto);
  if (c && !estado.espera) {
    vista.dataset.tipo = "comando";
    vista.textContent = ACCIONES_CELULAR.has(c.accion) ? "Pregunta para Lancelot (Enter)" : "Eso es un comando de la laptop";
    if (c.accion === "horario_agregar") {
      const b = interpretarBloque(c.texto || "");
      vista.textContent = typeof b === "string" ? b : `🗓 Horario: ${describirBloque(b)}`;
    }
    if (c.accion === "excepcion") {                  // se ve antes de enviar qué día y qué se libera
      const e = interpretarExcepcion(c.texto || "", soloFecha(ahora()));
      vista.textContent = typeof e === "string" ? e : `🏖 Día libre: ${describirExcepcion(e)}` +
        (e.filtro ? " (solo ese bloque)" : " (todo el horario)");
    }
    return;
  }
  const r = interpretar(texto, ahora());
  if (estado.espera?.falta === "fecha") {
    vista.textContent = r.fecha ? `Para: ${describirFecha(r.fecha, ahora())}` : "Dime cuándo: «mañana a las 5», «en 2 horas»…";
    return;
  }
  const partes = [`${r.tipo === "evento" ? "📅 " : ""}«${r.titulo || "…"}»`,
    r.fecha ? describirFecha(r.fecha, ahora()) : "te preguntaré cuándo"];
  if (r.repeticion) partes.push(REPETICIONES[r.repeticion].toLowerCase());
  if (r.fecha && r.duracion) partes[1] = `${describirFecha(r.fecha, ahora())}–${describirRango(r.fecha, r.duracion).split("–")[1]}`;
  if (r.avisos) partes.push(describirAvisos(r.avisos));
  vista.textContent = "Entendí: " + partes.join(", ");
}

$("f-tarea").addEventListener("submit", async (e) => {
  e.preventDefault();
  const texto = entrada.value.trim();
  if (!texto) return;
  $("b-enviar").disabled = true;
  try {
    if (await procesar(texto)) entrada.value = "";
  } finally {
    $("b-enviar").disabled = false;
    vistaPrevia(entrada.value);
  }
});

/** Lo escrito: respuesta a una pregunta, comando o tarea nueva. Devuelve true si se usó. */
async function procesar(texto) {
  const now = ahora();
  const espera = estado.espera;
  if (espera && /^(?:olvidalo|olvida|cancela|cancelar|nada|no|dejalo)[.!]*$/.test(normalizarSimple(texto))) {
    terminarEspera();
    cerrarHoja();
    decir("Listo, no anoto nada.");
    return true;
  }
  if (espera?.falta === "titulo") {
    // El título recién llega ahora: recién ahora se sabe si es un evento ("aniversario")
    const r = interpretar(texto, now);
    const titulo = r.titulo || capital(texto);
    const tipo = r.tipo === "evento" ? "evento" : espera.tipo;
    const repeticion = espera.repeticion || (r.tipo === "evento" ? r.repeticion : null);
    return crear(titulo, espera.fecha, repeticion, tipo, espera.anticipacion || avisosPrevios(tipo, repeticion, null),
      espera.duracion || r.duracion);
  }
  if (espera?.falta === "fecha") {
    const r = interpretar(texto, now);
    if (!r.fecha) { decir("No entendí la fecha. Prueba con «mañana a las 5» o «en 2 horas»."); return false; }
    const repeticion = r.repeticion || espera.repeticion;
    return crear(espera.titulo, aTexto(r.fecha), repeticion, espera.tipo,
      espera.anticipacion || avisosPrevios(espera.tipo, repeticion, null), r.duracion || espera.duracion);
  }
  const c = interpretarComando(texto);
  if (c) { await comando(c); return true; }

  const r = interpretar(texto, now);
  if (!r.titulo && r.fecha) {
    estado.espera = { falta: "titulo", fecha: aTexto(r.fecha), repeticion: r.repeticion, tipo: r.tipo,
                      anticipacion: r.anticipacion, duracion: r.duracion };
    decir(`¿Qué te recuerdo ${describirFecha(r.fecha, now)}? (Escribe «olvídalo» para cancelar.)`);
    entrada.placeholder = "Por ejemplo: pagar la luz";
    return true;
  }
  if (!r.fecha) { pedirFecha(r.titulo, r.repeticion, r.tipo, r.anticipacion, r.duracion); return true; }
  if (aTexto(r.fecha) <= aTexto(now) && !r.repeticion) { decir("Esa hora ya pasó. Dime una hora futura."); return false; }
  return crear(r.titulo, aTexto(r.fecha), r.repeticion, r.tipo, r.avisos, r.duracion);
}

async function comando(c) {
  const now = ahora();
  const limite = aTexto(now);
  if (c.accion === "hora") return decir(`Son las ${hhmm(now)}.`);
  if (c.accion === "saludo") return decir(resumen(now, true));
  if (c.accion === "agenda") {
    const hoy = estado.tareas.filter((t) => t.fecha > limite && diasEntre(now, desdeTexto(t.fecha)) === 0);
    return decir(hoy.length ? `Hoy:\n${hoy.map((t) => `${hhmm(desdeTexto(t.fecha))}  ${conIcono(t)}`).join("\n")}` : resumen(now));
  }
  if (c.accion === "frase") return decirFrase();
  if (c.accion === "vencidas") {
    const v = vencidasDe(now);
    return decir(v.length ? `${capital(plural(v.length, "vencida", "vencidas"))}:\n${v.map((t) => t.titulo).join("\n")}`
      : "No tienes tareas vencidas.");
  }
  if (c.accion === "vencidas_manana") return todasAManana();
  if (["sugerir", "agendar_plan", "actividad_hecha", "excepcion", "excepciones", "libre", "horario_ver",
       "actividad", "actividades", "borrar_actividad", "horario_agregar", "horario_borrar", "despertar", "dormir",
       "meta_estudio", "perfil"].includes(c.accion)) {
    return comandoDelHorario(c, now);
  }
  decir("Eso lo hago en la laptop. Aquí anoto tareas, te digo tu agenda, tus horas libres y qué hacer, " +
    "y anoto días libres o actividades hechas.");
}

// ------------------------------------------------------------ horario y sugerencias (v3.19)
const SIN_CONTEXTO = "Todavía no recibí tu horario ni tu perfil: abre Lancelot en la laptop con internet y se sincroniza solo.";

async function comandoDelHorario(c, now) {
  const x = ctx();
  if (!x.conocido) return decir(SIN_CONTEXTO);
  const hoy = soloFecha(now);
  if (c.accion === "horario_ver") {
    return decir(x.horario.length ? `Tu horario:\n${x.horario.map(describirBloque).join("\n")}`
      : "No tienes horario anotado. Se anota en la laptop: «horario: de lunes a viernes de 9 a 6 trabajo».");
  }
  if (c.accion === "libre") {
    const manana = c.texto === "manana";
    const libres = horasLibres(x, estado.tareas, manana ? sumarDias(hoy, 1) : hoy, now);
    const cuando = manana ? "Mañana" : "Hoy";
    return decir(libres.length ? `${cuando} tienes ${hablarDuracion(minutos(libres))} libre: ${describirLibre(libres)}.`
      : `${cuando} no te queda tiempo libre en tu horario.`);
  }
  if (c.accion === "excepciones" || c.accion === "actividades" || c.accion === "perfil") return mostrarMisCosas();
  if (c.accion === "horario_agregar") return agregarBloque(c.texto || "");
  if (c.accion === "horario_borrar") {
    const buscado = normalizarSimple(c.texto || "");
    const b = x.horario.find((y) => buscado && normalizarSimple(y.titulo).includes(buscado));
    return b ? quitarBloque(b) : decir(`No encontré «${c.texto}» en tu horario.`);
  }
  if (c.accion === "despertar" || c.accion === "dormir") {
    const h = leerHora(c.texto || "", c.accion);
    if (!h) return decir("No entendí la hora. Por ejemplo: «me despierto a las 6:30».");
    return guardarPerfil({ [c.accion]: h });
  }
  if (c.accion === "meta_estudio") {
    const d = leerDuracion(normalizarSimple(c.texto || ""));
    const meta = d ? d[0] : Number((/\d+/.exec(c.texto || "") || [])[0]);
    if (!meta) return decir("No entendí. Por ejemplo: «meta de estudio 120 minutos».");
    return guardarPerfil({ meta_estudio: meta });
  }
  if (c.accion === "actividad") return agregarActividad(c.texto || "");
  if (c.accion === "borrar_actividad") {
    const buscado = normalizarSimple(c.texto || "");
    const a = x.actividades.find((y) => buscado && normalizarSimple(y.nombre).includes(buscado));
    return a ? quitarActividad(a) : decir(`No encontré «${c.texto}» en tus actividades.`);
  }
  if (c.accion === "excepcion") {
    const e = interpretarExcepcion(c.texto || "", hoy);
    if (typeof e === "string") return decir(e);
    if (e.filtro && x.horario.length && !x.horario.some((b) => coincide(e.filtro, b.titulo))) {
      return decir(`No encontré nada parecido a «${e.titulo.split(" ").at(-1)}» en tu horario. ` +
        "Di «el … tengo libre» para liberar todo el día.");
    }
    if (!(await accion("excepcion", e))) return null;
    cara.celebrar();
    decir(`🏖 Anotado: ${describirExcepcion(e)}. Ya lo cuento en tus horas libres (la laptop lo guarda al sincronizar).`);
    return pintar();
  }
  if (c.accion === "actividad_hecha") {
    const acts = actividadesQueNombra(x, c.texto || "");
    if (!acts.length) return decir(`«${c.texto}» no está en tus actividades. Se agregan en la laptop (pestaña 🙂 Perfil).`);
    for (const a of acts) await marcarHecha(a);
    return null;
  }
  if (c.accion === "sugerir") {
    const manana = c.texto === "manana";
    return mostrarPlan(manana ? sumarDias(hoy, 1) : hoy, now);
  }
  if (c.accion === "agendar_plan") {
    const u = estado.ultimoPlan || { plan: planDelDia(x, estado.tareas, hoy, now), dia: hoy };
    return agendar(u.plan, u.dia);
  }
  return null;
}

async function agregarActividad(texto) {
  const a = interpretarActividad(texto);
  if (typeof a === "string") return decir(a);
  if (ctx().actividades.some((y) => normalizarSimple(y.nombre) === normalizarSimple(a.nombre))) {
    return decir(`«${a.nombre}» ya está en tus actividades.`);
  }
  if (!(await accion("actividad", a))) return null;
  cara.celebrar();
  decir(`🙂 Anotado: ${describirActividad(a)}. Ya te lo sugiero (la laptop lo guarda al sincronizar).`);
  return pintar();
}

async function quitarActividad(a) {
  if (a.id === null) return decir("Esa actividad todavía no llegó a la laptop: espera a que sincronice y quítala.");
  if (!(await accion("quitar_actividad", { id: a.id }))) return null;
  decir(`Quité ${a.nombre} de tus actividades.`);
  pintar();
  if (hojaAbierta) mostrarMisCosas();
  return null;
}

async function agregarBloque(texto) {
  const b = interpretarBloque(texto);
  if (typeof b === "string") { decir(b); return false; }
  if (!(await accion("bloque", b))) return false;
  cara.celebrar();
  decir(`🗓 Anotado en tu horario: ${describirBloque(b)}. Ya lo cuento (la laptop lo guarda al sincronizar).`);
  pintar();
  return true;
}

async function quitarBloque(b) {
  if (b.id == null) return decir("Ese bloque todavía no llegó a la laptop: espera a que sincronice y quítalo.");
  if (!(await accion("quitar_bloque", { id: b.id }))) return null;
  decir(`Quité ${b.titulo} de tu horario.`);
  pintar();
  if (hojaAbierta) mostrarMisCosas();
  return null;
}

async function guardarPerfil(datos) {
  if (!(await accion("perfil", datos))) return;
  const p = ctx().perfil;
  decir(`🙂 Guardado: despiertas ${p.despertar}, duermes ${p.dormir}, meta de estudio ${duracionMinutos(p.meta_estudio)}.`);
  pintar();
}

async function quitarExcepcion(e) {
  if (!(await accion("quitar_excepcion", { desde: e.desde, hasta: e.hasta, filtro: e.filtro }))) return;
  decir(`Quité: ${describirExcepcion(e)}.`);
  pintar();
  if (hojaAbierta) mostrarMisCosas();
}

/** Hoja con tus días libres y tus actividades: ✕ para quitar, y un campo para agregar una actividad. */
function mostrarMisCosas() {
  const x = ctx();
  if (!x.conocido) return decir(SIN_CONTEXTO);
  const campo = el("input", { type: "text", maxlength: 120, placeholder: "yoga 45 min 2 veces por semana en la tarde",
    "aria-label": "Nueva actividad", enterkeyhint: "done" });
  const agregar = async () => { if (campo.value.trim()) { await agregarActividad(campo.value.trim()); mostrarMisCosas(); } };
  campo.addEventListener("keydown", (e) => { if (e.key === "Enter") agregar(); });
  const filaQuitar = (texto, extra, alQuitar, aria) => el("div", { class: "mi-fila" },
    el("span", {}, el("span", { class: "mi-tit" }, texto), extra && el("span", { class: "mi-det" }, extra)),
    alQuitar && el("button", { class: "b-mini quitar", onclick: alQuitar, "aria-label": aria }, "✕"));
  const hoy = soloFecha(ahora());
  const [semana] = hechasEntre(x, lunesDe(hoy), hoy);
  const nuevoBloque = el("input", { type: "text", maxlength: 160, placeholder: "martes y jueves de 7 a 10 de la noche clase",
    "aria-label": "Nuevo bloque del horario", enterkeyhint: "done" });
  const agregarB = async () => { if (nuevoBloque.value.trim() && (await agregarBloque(nuevoBloque.value.trim()))) mostrarMisCosas(); };
  nuevoBloque.addEventListener("keydown", (e) => { if (e.key === "Enter") agregarB(); });
  const despertar = el("input", { type: "time", value: x.perfil.despertar, "aria-label": "Me despierto" });
  const dormir = el("input", { type: "time", value: x.perfil.dormir, "aria-label": "Me duermo" });
  const meta = el("input", { type: "number", min: 0, max: 600, step: 10, value: x.perfil.meta_estudio, "aria-label": "Meta de estudio (min)" });
  abrirHoja("Tu horario y tu perfil",
    el("h3", { class: "mi-sec" }, "🗓 Horario fijo"),
    x.horario.length ? x.horario.map((b) => filaQuitar(describirBloque(b), b.pendiente ? "esperando a la laptop" : null,
      b.id == null ? null : () => quitarBloque(b), `Quitar ${b.titulo}`))
      : el("p", { class: "sub" }, "Vacío. Agrega tu trabajo y tus clases."),
    el("div", { class: "fila" }, nuevoBloque, el("button", { class: "b-secundario", onclick: agregarB }, "Agregar al horario")),
    el("h3", { class: "mi-sec" }, "😴 Sueño y 📚 meta"),
    el("div", { class: "perfil-campos" },
      el("label", {}, "Me despierto", despertar), el("label", {}, "Me duermo", dormir), el("label", {}, "Meta (min/día)", meta)),
    el("button", { class: "b-secundario", onclick: async () => {
      const datos = {};
      if (despertar.value && despertar.value !== x.perfil.despertar) datos.despertar = despertar.value;
      if (dormir.value && dormir.value !== x.perfil.dormir) datos.dormir = dormir.value;
      if (meta.value !== "" && Number(meta.value) !== x.perfil.meta_estudio) datos.meta_estudio = Math.round(Number(meta.value));
      if (!Object.keys(datos).length) return decir("No cambiaste nada.");
      await guardarPerfil(datos);
      mostrarMisCosas();
    } }, "Guardar sueño y meta"),
    el("h3", { class: "mi-sec" }, "🏖 Días libres"),
    x.excepciones.length ? x.excepciones.map((e) => filaQuitar(describirExcepcion(e),
      e.pendiente ? "esperando a la laptop" : e.filtro ? "solo ese bloque" : "todo el horario",
      () => quitarExcepcion(e), `Quitar ${e.titulo}`))
      : el("p", { class: "sub" }, "Ninguno. Escribe abajo, por ejemplo: «el viernes no trabajo»."),
    el("h3", { class: "mi-sec" }, "🏃 Actividades"),
    x.actividades.map((a) => filaQuitar(describirActividad(a),
      a.pendiente ? "esperando a la laptop" : a.veces_semana ? `esta semana: ${semana[a.id] || 0} de ${a.veces_semana}` : null,
      a.pendiente ? null : () => quitarActividad(a), `Quitar ${a.nombre}`)),
    el("div", { class: "fila" }, campo, el("button", { class: "b-principal", onclick: agregar }, "Agregar actividad")),
    el("p", { class: "sub" }, "Lo que cambias aquí se ve al instante y la laptop lo guarda al sincronizar."));
}

async function marcarHecha(a) {
  const hoy = soloFecha(ahora());
  if (!(await accion("hecha", { actividad_id: a.id, dia: isoDia(hoy) }))) return;
  const [semana] = hechasEntre(ctx(), lunesDe(hoy), hoy);
  const n = semana[a.id] || 0;
  cara.celebrar();
  decir(a.veces_semana ? `💪 ¡Bien! ${a.nombre}: ${n} de ${a.veces_semana} esta semana${n >= a.veces_semana ? " ✅" : ""}.`
    : `💪 ¡Bien! Anoté ${a.nombre} hoy.`);
  pintar();
}

function mostrarPlan(dia, now) {
  const x = ctx();
  const plan = planDelDia(x, estado.tareas, dia, now);
  const cuando = diasEntre(now, dia) === 0 ? "hoy" : "mañana";
  estado.ultimoPlan = { plan, dia };
  const [texto] = describirPlan(plan, cuando);
  decir(plan.sugerencias.length ? `💡 Para ${cuando}:\n${texto}` : texto);
  if (!plan.sugerencias.length) return;
  abrirHoja(`💡 Para ${cuando}`,
    plan.sugerencias.map((s) => opcion(s.nombre, s.clase === "actividad" && cuando === "hoy"
      ? () => { cerrarHoja(); marcarHecha(x.actividades.find((a) => a.id === s.actividad_id)); } : () => {},
    { extra: `${hhmm(s.inicio)}–${hhmm(s.fin)} · ${s.motivo}` })),
    plan.sin_lugar.length && el("p", { class: "sub" }, `No entra: ${plan.sin_lugar.join(", ")}.`),
    el("div", { class: "separador" }),
    el("div", { class: "fila-botones" },
      el("button", { class: "b-secundario", onclick: cerrarHoja }, "Cerrar"),
      el("button", { class: "b-principal", onclick: () => agendar(plan, dia) }, "📌 Agendar")));
}

/** Cada sugerencia pasa a ser una tarea con su hora y duración (y la laptop la marca como 💡). */
async function agendar(plan, dia) {
  const now = ahora();
  let hechas = 0;
  for (const s of plan.sugerencias) {
    let inicio = s.inicio;
    if (inicio <= now) inicio = sumarMinutos(now, 5 - (now.getUTCMinutes() % 5));
    const ya = estado.tareas.some((t) => t.fecha.slice(0, 10) === isoDia(inicio) && normalizarSimple(t.titulo) === normalizarSimple(s.nombre));
    if (ya) continue;
    const minutosS = Math.round((s.fin - s.inicio) / 60000);
    const r = await intentar(() => api("/api/tareas", { metodo: "POST",
      cuerpo: { titulo: s.nombre, fecha: aTexto(inicio), repeticion: null, tipo: "tarea", anticipacion: null, duracion: minutosS } }));
    if (!r) break;
    await accion("sugerida", { tarea: r.tarea.id, actividad_id: s.actividad_id ?? null });
    hechas++;
  }
  estado.ultimoPlan = null;
  cerrarHoja();
  if (hechas) cara.celebrar();
  decir(hechas ? `📌 Agendé ${plural(hechas, "sugerencia", "sugerencias")}. Te aviso a cada hora; si alguna no la haces, mañana se quita sola.`
    : "No había nada nuevo que agendar.");
  await recargar();
}

// ------------------------------------------------------------ calendario (v3.19)
function cambiarVista(vista) {
  estado.vista = vista;
  guardar("vista", vista);
  pintar();
}
$("p-lista").addEventListener("click", () => cambiarVista("lista"));
$("p-calendario").addEventListener("click", () => cambiarVista("calendario"));

function pintarVistaCalendario(now) {
  estado.calDia ||= soloFecha(now);
  estado.calMes ||= conHora(sumarDias(estado.calDia, 1 - estado.calDia.getUTCDate()), 0, 0);
  pintarCalendario($("calendario"), {
    el, ctx: ctx(), tareas: estado.tareas, ahora: now, mes: estado.calMes, dia: estado.calDia, modo: estado.calModo,
    cambiarModo: (m) => { estado.calModo = m; guardar("calModo", m); pintar(); },
    cambiarSemana: (paso) => {
      estado.calDia = sumarDias(estado.calDia, 7 * paso);
      estado.calMes = sumarDias(estado.calDia, 1 - estado.calDia.getUTCDate());
      pintar();
    },
    elegirDia: (d) => {
      estado.calDia = d;
      if (d.getUTCMonth() !== estado.calMes.getUTCMonth()) estado.calMes = sumarDias(d, 1 - d.getUTCDate());
      pintar();
    },
    cambiarMes: (paso) => {
      const m = estado.calMes;
      estado.calMes = new Date(Date.UTC(m.getUTCFullYear(), m.getUTCMonth() + paso, 1));
      pintar();
    },
    tocarTarea: (t) => opcionesDeTarea(t),
    agendar: (plan, dia) => agendar(plan, dia),
    hecha: (s) => marcarHecha(ctx().actividades.find((a) => a.id === s.actividad_id)),
    misCosas: () => mostrarMisCosas(),
  });
}

// ------------------------------------------------------------ hoja inferior
let hojaAbierta = false;

function abrirHoja(titulo, ...contenido) {
  $("hoja-titulo").textContent = titulo;
  $("hoja-cuerpo").replaceChildren(...contenido.flat().filter(Boolean));
  $("hoja").hidden = $("velo").hidden = false;
  $("hoja").focus({ preventScroll: true });          // el foco entra a la hoja (para lectores de pantalla)
  if (!hojaAbierta) history.pushState({ hoja: true }, "");   // así el botón "atrás" de Android la cierra
  hojaAbierta = true;
}

function ocultarHoja() {
  $("hoja").hidden = $("velo").hidden = true;
  hojaAbierta = false;
  if (estado.espera?.falta === "fecha") {            // cerró "¿Para cuándo?" sin elegir: no se anota
    terminarEspera();
    decir("Listo, no la anoté.");
  }
}

function cerrarHoja() {
  if (!hojaAbierta) return;
  ocultarHoja();
  if (history.state?.hoja) history.back();
}

addEventListener("popstate", () => { if (hojaAbierta) ocultarHoja(); });

$("velo").addEventListener("click", cerrarHoja);
addEventListener("keydown", (e) => { if (e.key === "Escape") cerrarHoja(); });

const opcion = (texto, onclick, { extra, clase } = {}) =>
  el("button", { class: `opcion ${clase || ""}`, onclick }, el("span", {}, texto), extra && el("span", { class: "extra" }, extra));

/** Elegir fecha y hora con el selector del celular. */
function selectorFecha(inicial, alGuardar, textoBoton = "Guardar") {
  const campo = el("input", { type: "datetime-local", value: aInput(inicial), "aria-label": "Fecha y hora" });
  return el("div", { class: "fila" }, campo,
    el("button", { class: "b-principal", onclick: () => {
      const valor = deInput(campo.value);
      if (!desdeTexto(valor)) return decir("Elige una fecha y hora.");
      if (valor <= aTexto(ahora())) return decir("Esa hora ya pasó. Elige una futura.");
      alGuardar(valor);
    } }, textoBoton));
}

function pedirFecha(titulo, repeticion, tipo = "tarea", anticipacion = null, duracion = null) {
  estado.espera = { falta: "fecha", titulo, repeticion, tipo, anticipacion, duracion };
  const anotar = (f) => crear(titulo, f, repeticion, tipo, anticipacion || avisosPrevios(tipo, repeticion, null), duracion);
  decir(`¿Para cuándo «${titulo}»?`);
  const now = ahora();
  const atajos = [["En 1 hora", sumarMinutos(now, 60)]];
  if (now.getUTCHours() < 19) atajos.push(["Esta noche", conHora(now, 20, 0)]);
  atajos.push(["Mañana en la mañana", conHora(sumarDias(now, 1), 9, 0)], ["Mañana en la noche", conHora(sumarDias(now, 1), 20, 0)]);
  abrirHoja("¿Para cuándo?",
    el("p", { class: "sub" }, titulo),
    atajos.map(([texto, f]) => opcion(texto, () => anotar(aTexto(f)), { extra: describirFecha(f, now) })),
    el("div", { class: "separador" }),
    selectorFecha(aTexto(conHora(sumarDias(now, 1), 9, 0)), anotar, "Anotar"));
}

function opcionesDeTarea(t) {
  const now = ahora();
  const f = desdeTexto(t.fecha);
  const vencida = t.fecha <= aTexto(now);
  const cuando = vencida ? describirAtraso(f, now)
    : describirFecha(f, now) + (esEvento(t) ? ` · ${describirFaltan(f, now)}` : "") +
      (t.anticipacion ? ` · ${describirAvisos(t.anticipacion)}` : "");
  const reprogramar = vencida
    ? [opcion("+10 minutos", () => posponer(t, 10)),
       ...opcionesReprogramar(f, now).map(([texto, nueva]) => opcion(texto, () => cambiarFecha(t, aTexto(nueva))))]
    : [opcion("Un día después", () => cambiarFecha(t, aTexto(sumarDias(f, 1))), { extra: describirFecha(sumarDias(f, 1), now) })];
  let confirmar = false;
  const borrar = opcion("Eliminar", async (e) => {
    if (!confirmar) {
      confirmar = true;
      e.currentTarget.firstChild.textContent = "Toca otra vez para eliminar";
      return;
    }
    if (await intentar(() => api(`/api/tareas/${t.id}`, { metodo: "DELETE" }))) {
      cerrarHoja(); decir(`Eliminada: ${t.titulo}.`); recargar();
    }
  }, { clase: "peligro" });

  abrirHoja(conIcono(t),
    el("p", { class: "sub" }, capital(cuando)),
    opcion("✓ Hecho", () => { cerrarHoja(); completar(t, document.querySelector(`[data-id="${t.id}"]`)); }, { clase: "principal-op" }),
    reprogramar,
    opcion("Cambiar fecha y hora", () => abrirHoja("Cambiar fecha y hora", el("p", { class: "sub" }, t.titulo),
      selectorFecha(vencida ? aTexto(conHora(sumarDias(now, 1), f.getUTCHours(), f.getUTCMinutes())) : t.fecha,
        (nueva) => cambiarFecha(t, nueva)))),
    opcion("Editar", () => editar(t)),
    el("div", { class: "separador" }),
    borrar);
}

function editar(t) {
  const titulo = el("input", { type: "text", value: t.titulo, maxlength: 200, "aria-label": "Título" });
  const fecha = el("input", { type: "datetime-local", value: aInput(t.fecha), "aria-label": "Fecha y hora" });
  const repeticion = el("select", { "aria-label": "Repetición" },
    Object.entries(REPETICIONES).map(([clave, texto]) =>
      el("option", { value: clave, selected: (t.repeticion || "") === clave }, texto)));
  const tipo = el("select", { "aria-label": "Tarea o evento" },
    Object.entries(TIPOS).map(([clave, texto]) => el("option", { value: clave, selected: (t.tipo || "tarea") === clave }, texto)));
  const nota = el("p", { class: "sub" });
  const explicar = () => {
    nota.textContent = tipo.value === "evento"
      ? `Evento: ${describirAvisos(t.tipo === "evento" && t.anticipacion ? t.anticipacion
        : avisosPrevios("evento", repeticion.value || null, null)) || "solo avisa ese día"} y ese día.`
      : "Tarea: avisa a su hora.";
  };
  tipo.addEventListener("change", explicar);
  repeticion.addEventListener("change", explicar);
  explicar();
  abrirHoja(esEvento(t) ? "Editar evento" : "Editar tarea",
    el("div", { class: "fila" }, titulo, fecha, repeticion, tipo),
    nota,
    el("div", { class: "fila-botones" },
      el("button", { class: "b-secundario", onclick: cerrarHoja }, "Cancelar"),
      el("button", { class: "b-principal", onclick: async () => {
        const datos = { titulo: titulo.value.trim(), fecha: deInput(fecha.value), repeticion: repeticion.value || null };
        if (tipo.value !== (t.tipo || "tarea")) {      // cambió de tarea a evento (o al revés): avisos por defecto
          datos.tipo = tipo.value;
          datos.anticipacion = avisosPrevios(tipo.value, datos.repeticion, null);
        }
        if (!datos.titulo) return decir("El título no puede quedar vacío.");
        const r = await intentar(() => api(`/api/tareas/${t.id}`, { metodo: "PATCH", cuerpo: datos }));
        if (r) { cerrarHoja(); decir(`Guardado: ${datos.titulo}.`); cara.celebrar(); recargar(); }
      } }, "Guardar")));
}

// ------------------------------------------------------------ ajustes
$("b-ajustes").addEventListener("click", ajustes);

async function ajustes() {
  const registro = await registroSW();
  const soporte = Boolean(registro) && "PushManager" in window && "Notification" in window;
  const suscripcion = registro ? await registro.pushManager.getSubscription() : null;
  const instalada = matchMedia("(display-mode: standalone)").matches;

  let notificaciones;
  if (!soporte) {
    notificaciones = el("p", {}, "No están disponibles: abre Lancelot en Chrome (si ya estás en Chrome, recarga la página).");
  } else if (Notification.permission === "denied") {
    notificaciones = el("p", {}, "Las bloqueaste. Para activarlas: candado junto a la dirección → Permisos → Notificaciones → Permitir.");
  } else if (suscripcion) {
    notificaciones = [el("p", {}, "Activadas en este celular."),
      el("div", { class: "fila-botones" },
        el("button", { class: "b-secundario", onclick: desactivarNotificaciones }, "Desactivar"),
        el("button", { class: "b-principal", onclick: probarNotificacion }, "Probar"))];
  } else {
    notificaciones = [el("p", {}, "Te aviso cuando venza una tarea, aunque la app esté cerrada."),
      el("button", { class: "b-principal", onclick: activarNotificaciones }, "Activar notificaciones")];
  }

  abrirHoja("Ajustes",
    el("div", { class: "ajuste" }, el("h3", {}, "Notificaciones"), notificaciones),
    el("div", { class: "ajuste" }, el("h3", {}, "Tu horario (desde la laptop)"),
      el("p", {}, estado.contexto
        ? `Recibido ${cuandoFue(ahoraEn(ZONA, new Date(estado.contexto.recibido)), ahora())}. ` +
          `${plural(estado.contexto.horario.length, "bloque", "bloques")}, ` +
          `${plural(estado.contexto.actividades.length, "actividad", "actividades")}.` +
          (estado.acciones.length ? ` ${plural(estado.acciones.length, "cambio", "cambios")} de aquí esperan a la laptop.` : "")
        : "Todavía no llegó. Abre Lancelot en la laptop con internet: lo sube solo.")),
    el("div", { class: "ajuste" }, el("h3", {}, "Voz"),
      el("p", {}, vozActiva() ? "Al tocar mi cara te digo la frase en voz alta." : "Las frases solo se muestran, sin voz."),
      el("button", { class: "b-secundario", onclick: () => { guardar("voz", vozActiva() ? "0" : "1"); ajustes(); } },
        vozActiva() ? "Desactivar la voz" : "Activar la voz")),
    el("div", { class: "ajuste" }, el("h3", {}, "Si los avisos llegan tarde"),
      el("p", {}, "Los Vivo ahorran batería cerrando apps. En Ajustes → Batería, busca la gestión del consumo " +
        "en segundo plano y permite que Chrome funcione en segundo plano.")),
    el("div", { class: "ajuste" }, el("h3", {}, "Pantalla de inicio"),
      instalada ? el("p", {}, "Lancelot ya está instalado.")
        : estado.instalar ? el("button", { class: "b-principal", onclick: instalar }, "Instalar Lancelot")
          : el("p", {}, "En Chrome: menú ⋮ → «Agregar a la pantalla principal».")),
    el("div", { class: "ajuste" }, el("h3", {}, "Este celular"),
      el("p", {}, `Versión ${VERSION_APP}.`),
      el("button", { class: "b-secundario", onclick: desconectar }, "Desconectar este celular")));
}

/** 'hoy a las 08:15', 'ayer a las 22:00' o 'el 20/10 a las 09:00' (algo que ya pasó). */
function cuandoFue(f, now) {
  const dias = diasEntre(f, now);
  return `${dias === 0 ? "hoy" : dias === 1 ? "ayer" : `el ${String(f.getUTCDate()).padStart(2, "0")}/${String(f.getUTCMonth() + 1).padStart(2, "0")}`} a las ${hhmm(f)}`;
}

/** El registro del service worker, o null si no se pudo instalar (sin esperar para siempre). */
async function registroSW() {
  if (!("serviceWorker" in navigator)) return null;
  return Promise.race([navigator.serviceWorker.ready, new Promise((r) => setTimeout(() => r(null), 3000))]);
}

function claveAplicacion(base64) {
  const s = atob(base64.replace(/-/g, "+").replace(/_/g, "/") + "===".slice((base64.length + 3) % 4));
  return Uint8Array.from(s, (c) => c.charCodeAt(0));
}

async function activarNotificaciones() {
  if ((await Notification.requestPermission()) !== "granted") {
    decir("Sin permiso no puedo avisarte. Puedes activarlo cuando quieras en ⚙.");
    return ajustes();
  }
  await intentar(async () => {
    const { clave } = await api("/api/push/clave");
    if (!clave) throw new Error("El servidor aún no tiene sus claves de notificación. Vuelve a ejecutar la configuración.");
    const registro = await registroSW();
    if (!registro) throw new Error("La app no terminó de instalarse. Recarga la página e inténtalo de nuevo.");
    const s = await registro.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: claveAplicacion(clave) });
    await api("/api/push/suscribir", { metodo: "POST", cuerpo: { suscripcion: s.toJSON(), dispositivo: "Android" } });
    decir("Notificaciones activadas. Te mando una de prueba.");
    await api("/api/push/prueba", { metodo: "POST" });
  });
  ajustes();
}

async function probarNotificacion() {
  const r = await intentar(() => api("/api/push/prueba", { metodo: "POST" }));
  if (r) decir(r.enviadas ? "Te mandé una notificación de prueba." : "No llegó a ningún celular. Desactívalas y vuelve a activarlas.");
}

async function desactivarNotificaciones() {
  const s = await (await registroSW())?.pushManager.getSubscription();
  if (s) {
    await intentar(() => api("/api/push/desuscribir", { metodo: "POST", cuerpo: { endpoint: s.endpoint } }));
    await s.unsubscribe();
  }
  decir("Ya no te mandaré notificaciones a este celular.");
  ajustes();
}

/**
 * Si el servidor cambió sus claves de notificación (por ejemplo, se reconfiguró), la suscripción vieja
 * ya no sirve: se rehace en silencio. Solo si el permiso ya estaba dado.
 */
async function revisarSuscripcion() {
  const registro = await registroSW();
  if (!registro || !("PushManager" in window) || Notification.permission !== "granted") return;
  const s = await registro.pushManager.getSubscription();
  if (!s) return;
  const r = await intentar(() => api("/api/push/clave"));
  if (!r?.clave) return;
  const actual = new Uint8Array(s.options.applicationServerKey || []);
  const nueva = claveAplicacion(r.clave);
  if (actual.length === nueva.length && actual.every((b, i) => b === nueva[i])) return;
  await s.unsubscribe();
  const otra = await registro.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: nueva });
  await intentar(() => api("/api/push/suscribir", { metodo: "POST", cuerpo: { suscripcion: otra.toJSON(), dispositivo: "Android" } }));
}

async function instalar() {
  estado.instalar.prompt();
  await estado.instalar.userChoice;
  estado.instalar = null;
  cerrarHoja();
}

async function desconectar() {
  {
    const s = await (await registroSW())?.pushManager.getSubscription();
    if (s) { await intentar(() => api("/api/push/desuscribir", { metodo: "POST", cuerpo: { endpoint: s.endpoint } })); await s.unsubscribe(); }
  }
  guardar("clave", null);
  estado.clave = null;
  estado.tareas = [];
  cerrarHoja();
  mostrarConectar("Desconectado. Para volver, escribe la clave.");
}

addEventListener("beforeinstallprompt", (e) => { e.preventDefault(); estado.instalar = e; });

// ------------------------------------------------------------ arranque
async function iniciar() {
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("/sw.js").catch(() => { /* sin modo sin conexión: la app igual funciona */ });
    navigator.serviceWorker.addEventListener("message", (e) => {
      if (e.data?.tipo === "actualizar") recargar();
      if (e.data?.mensaje) decir(e.data.mensaje);
    });
  }
  // El código QR de la configuración trae la clave en la dirección: #clave=…
  const enlace = /^#clave=(.+)$/.exec(location.hash);
  if (enlace) {
    history.replaceState(null, "", location.pathname);
    return conectar(decodeURIComponent(enlace[1]));
  }
  if (!estado.clave) return mostrarConectar();
  mostrarPrincipal();
  await recargar();
  cargarPreferencias();
  if (new URLSearchParams(location.search).has("nueva")) entrada.focus();   // atajo "Nueva tarea" del ícono
  revisarSuscripcion().catch(() => { /* se intenta la próxima vez */ });
}

document.addEventListener("visibilitychange", () => { if (!document.hidden) recargar(); });
setInterval(() => { if (!document.hidden) recargar(); }, 60000);
iniciar();
