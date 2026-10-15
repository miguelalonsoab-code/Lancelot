/**
 * Lancelot en el celular.
 *
 *   - Escribes como en la laptop: "mañana 8pm pagar la luz". Si falta algo, pregunta.
 *   - La lista se agrupa en: vencidas, hoy, mañana y los días siguientes.
 *   - Tocar el círculo = hecho. Tocar la tarea = más opciones (posponer, reprogramar, editar, borrar).
 *   - Los EVENTOS (aniversario, examen, viaje…) llevan 📅 y "faltan N días"; avisan con anticipación.
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
import { avisosPrevios, describirAvisos, interpretar, REPETICIONES, TIPOS } from "./comun/interprete.js";
import { opcionesReprogramar } from "./comun/planificador.js";

const ZONA = "America/Lima";
const NOMBRE = "Miguel";
const VERSION_APP = "1.1";

const $ = (id) => document.getElementById(id);
const ahora = () => ahoraEn(ZONA);
const cara = new Cara($("cara"));

const estado = {
  clave: leer("clave"),
  tareas: [],
  espera: null,          // { falta: "titulo" | "fecha", titulo, fecha, repeticion, tipo, anticipacion } mientras pregunta
  saludado: false,
  instalar: null,        // aviso de "instalar app" que ofrece Chrome
};

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
    decir(`¡Listo, ${NOMBRE}! Ya estamos conectados. Activa las notificaciones en ⚙.`);
    cara.celebrar();
  } catch (e) {
    if (e instanceof SinConexion) decir(e.message);
  }
}

// ------------------------------------------------------------ lista
function agrupar(tareas, now) {
  const limite = aTexto(now);
  const grupos = new Map();
  for (const t of tareas) {
    const f = desdeTexto(t.fecha);
    let clave, titulo, tipo;
    if (t.fecha <= limite) {
      clave = "vencidas"; tipo = "vencidas";
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
  if (vencidas) vencidas.titulo = plural(vencidas.tareas.length, "vencida", "vencidas");
  return [...grupos.values()].sort((a, b) => (a.tipo === "vencidas" ? -1 : b.tipo === "vencidas" ? 1 : 0));
}

function pintar() {
  const now = ahora();
  const lista = $("lista");
  lista.replaceChildren();
  const grupos = agrupar(estado.tareas, now);
  if (!grupos.length) {
    lista.append(el("p", { class: "vacio" }, "No tienes nada pendiente. Escribe abajo, por ejemplo: «el viernes a las 3 llamar al banco»."));
  }
  for (const g of grupos) {
    const cabeza = el("div", { class: "grupo-cabeza" }, el("h3", {}, g.titulo),
      g.tipo === "vencidas" && el("button", { class: "enlace", onclick: todasAManana }, "Pasar todas a mañana"));
    lista.append(el("section", { class: "grupo", "data-tipo": g.tipo }, cabeza, g.tareas.map((t) => fila(t, g.tipo, now))));
  }
  actualizarCara(now);
}

function fila(t, tipo, now) {
  const f = desdeTexto(t.fecha);
  const faltan = esEvento(t) && tipo === "futuro" ? describirFaltan(f, now) : null;
  const detalle = [tipo === "vencidas" ? describirAtraso(f, now) : null,
    faltan && capital(faltan),
    t.repeticion ? `Se repite: ${REPETICIONES[t.repeticion].toLowerCase()}` : null].filter(Boolean).join(". ");
  const nodo = el("div", { class: "tarea", "data-id": t.id, "data-evento": esEvento(t) },
    el("span", { class: "hora" }, hhmm(f)),
    el("button", { class: "que", onclick: () => opcionesDeTarea(t) },
      el("span", { class: "titulo" }, conIcono(t)), detalle && el("span", { class: "detalle" }, detalle)),
    el("button", { class: "hecho", "aria-label": `Marcar «${t.titulo}» como hecha`, onclick: () => completar(t, nodo) }));
  return nodo;
}

function actualizarCara(now) {
  const limite = aTexto(now);
  const vencidas = estado.tareas.filter((t) => t.fecha <= limite);
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
  const vencidas = estado.tareas.filter((t) => t.fecha <= limite);
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

async function crear(titulo, fecha, repeticion, tipo = "tarea", anticipacion = null) {
  const r = await intentar(() => api("/api/tareas", { metodo: "POST", cuerpo: { titulo, fecha, repeticion, tipo, anticipacion } }));
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
    return crear(titulo, espera.fecha, repeticion, tipo, espera.anticipacion || avisosPrevios(tipo, repeticion, null));
  }
  if (espera?.falta === "fecha") {
    const r = interpretar(texto, now);
    if (!r.fecha) { decir("No entendí la fecha. Prueba con «mañana a las 5» o «en 2 horas»."); return false; }
    const repeticion = r.repeticion || espera.repeticion;
    return crear(espera.titulo, aTexto(r.fecha), repeticion, espera.tipo,
      espera.anticipacion || avisosPrevios(espera.tipo, repeticion, null));
  }
  const c = interpretarComando(texto);
  if (c) { await comando(c); return true; }

  const r = interpretar(texto, now);
  if (!r.titulo && r.fecha) {
    estado.espera = { falta: "titulo", fecha: aTexto(r.fecha), repeticion: r.repeticion, tipo: r.tipo,
                      anticipacion: r.anticipacion };
    decir(`¿Qué te recuerdo ${describirFecha(r.fecha, now)}? (Escribe «olvídalo» para cancelar.)`);
    entrada.placeholder = "Por ejemplo: pagar la luz";
    return true;
  }
  if (!r.fecha) { pedirFecha(r.titulo, r.repeticion, r.tipo, r.anticipacion); return true; }
  if (aTexto(r.fecha) <= aTexto(now) && !r.repeticion) { decir("Esa hora ya pasó. Dime una hora futura."); return false; }
  return crear(r.titulo, aTexto(r.fecha), r.repeticion, r.tipo, r.avisos);
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
  if (c.accion === "vencidas") {
    const v = estado.tareas.filter((t) => t.fecha <= limite);
    return decir(v.length ? `${capital(plural(v.length, "vencida", "vencidas"))}:\n${v.map((t) => t.titulo).join("\n")}`
      : "No tienes tareas vencidas.");
  }
  if (c.accion === "vencidas_manana") return todasAManana();
  decir("Eso lo hago en la laptop. Aquí anoto tareas y te digo tu agenda, tus vencidas o la hora.");
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

function pedirFecha(titulo, repeticion, tipo = "tarea", anticipacion = null) {
  estado.espera = { falta: "fecha", titulo, repeticion, tipo, anticipacion };
  const anotar = (f) => crear(titulo, f, repeticion, tipo, anticipacion || avisosPrevios(tipo, repeticion, null));
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
  if (new URLSearchParams(location.search).has("nueva")) entrada.focus();   // atajo "Nueva tarea" del ícono
  revisarSuscripcion().catch(() => { /* se intenta la próxima vez */ });
}

document.addEventListener("visibilitychange", () => { if (!document.hidden) recargar(); });
setInterval(() => { if (!document.hidden) recargar(); }, 60000);
iniciar();
