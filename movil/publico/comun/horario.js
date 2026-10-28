/**
 * Horario fijo, días libres (excepciones) y horas libres: lo mismo que nucleo/horario.py de la laptop.
 *
 * La laptop es la que guarda tu horario y lo sube en el "contexto" (ver src/index.js). Aquí solo se
 * CALCULA con esos datos, igual que allá: tests/casos_interprete.json trae los resultados de Python y
 * pruebas/horario.test.mjs comprueba que este archivo da exactamente lo mismo.
 *
 * Formatos (los del contexto):
 *   bloque     { dias: [0..6] (0 = lunes), inicio: "08:30", fin: "17:30", titulo, traslado: 45 }
 *   excepcion  { desde: "2026-11-01", hasta: "2026-11-01", filtro: "traba" | "", titulo: "No trabajo" }
 *   hueco      [inicio, fin] como fechas de pared (ver fechas.js)
 */
import { crear, conHora, diaSemana, DIAS_CORTOS, ddmm, soloFecha, sumarDias, sumarMinutos } from "./fechas.js";
import { interpretar, normalizar } from "./interprete.js";

const DIAS = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"];
const MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre",
  "octubre", "noviembre", "diciembre"];
const MIN = 60000;

/** "08:30" -> [8, 30] */
export const hm = (texto) => texto.split(":").map(Number);
/** Fecha (de pared) a 'AAAA-MM-DD' */
export const isoDia = (f) => f.toISOString().slice(0, 10);
/** 'AAAA-MM-DD' -> fecha de pared a las 00:00 */
export const deIsoDia = (t) => { const [a, m, d] = t.split("-").map(Number); return crear(a, m, d); };
const enDia = (dia, texto) => conHora(dia, ...hm(texto));

// ------------------------------------------------------------ duraciones y bloques (v3.21)
const NUMEROS = { un: 1, una: 1, dos: 2, tres: 3, cuatro: 4 };
const NUM = String.raw`(\d{1,3}|una?|dos|tres|cuatro|media)`;
const PATRON_DURACION = new RegExp(
  String.raw`\b(?:${NUM} ?(?:h|hr|hrs|horas?)(?: y (\d{1,2}|media|cuarto)(?: ?(?:min|mins|minutos))?` +
  String.raw`| ?(\d{1,2}) ?(?:min|mins|minutos))?` +
  String.raw`|(\d{1,3}) ?(?:m|min|mins|minutos)` +
  String.raw`|(media hora|hora y media|una hora y media))\b`);
/** '45 min' -> 45 · '1 hora y media' -> 90. Devuelve [minutos, [inicio, fin]] o null. */
export function leerDuracion(texto) {
  const m = PATRON_DURACION.exec(texto);
  if (!m) return null;
  const [, horas, extra1, extraMin, soloMin, frase] = m;
  const extra = extra1 || extraMin;
  let minutos;
  if (frase) minutos = frase === "media hora" ? 30 : 90;
  else if (soloMin) minutos = Number(soloMin);
  else {
    const h = horas === "media" ? 0.5 : /^\d+$/.test(horas) ? Number(horas) : NUMEROS[horas];
    minutos = Math.trunc(h * 60) + ({ media: 30, cuarto: 15 }[extra] || Number(extra || 0));
  }
  return minutos > 0 && minutos <= 1440 ? [minutos, [m.index, m.index + m[0].length]] : null;
}

const PATRON_TRASLADO = /(?:,\s*|\s)(?:(?:con\s+)?(?:traslado|viaje|transporte)(?: de)?\s+([^,]+?)|con\s+([^,]+?)\s+de\s+(?:traslado|viaje|transporte))(?:\s+de ida y vuelta)?(?=,|$)/g;

function leerTraslado(texto) {
  for (const m of texto.matchAll(PATRON_TRASLADO)) {
    const d = leerDuracion(m[1] || m[2]);
    if (d) return [d[0], [m.index, m.index + m[0].length]];
  }
  return null;
}

const P_DIA = "(?:lunes|martes|miercoles|jueves|viernes|sabados?|domingos?)";
const PATRON_DIAS = new RegExp(String.raw`(?:\b(?:todos los dias|cada dia|diario)\b|\b(?:fines? de semana)\b` +
  String.raw`|\b(?:de )?${P_DIA} a ${P_DIA}\b|\b(?:(?:los|cada|el) )?${P_DIA}(?:(?:, ?| y | e )(?:los )?${P_DIA})*\b)`, "g");
const indice = (nombre) => DIAS.indexOf(nombre === "sabados" || nombre === "domingos" ? nombre.slice(0, -1) : nombre);

function leerDias(texto) {
  if (/todos los dias|cada dia|diario/.test(texto)) return [0, 1, 2, 3, 4, 5, 6];
  if (/fines? de semana/.test(texto)) return [5, 6];
  const m = new RegExp(`(${P_DIA}) a (${P_DIA})`).exec(texto);
  if (m) {
    const a = indice(m[1]), b = indice(m[2]);
    const r = [];
    if (a <= b) for (let i = a; i <= b; i++) r.push(i);
    else { for (let i = a; i < 7; i++) r.push(i); for (let i = 0; i <= b; i++) r.push(i); }
    return r;
  }
  const dias = [...new Set((texto.match(new RegExp(P_DIA, "g")) || []).map(indice))].sort((x, y) => x - y);
  return dias.length ? dias : null;
}

const H = String.raw`(\d{1,2})(?::(\d{2}))?(?:\s?(am|pm|a\.m\.|p\.m\.))?`;
const PATRON_RANGO = new RegExp(String.raw`\b(?:de |desde )?(?:las? )?${H}\s?(?:a|-|–|hasta)\s?(?:las? )?${H}` +
  String.raw`(?: (?:de|en|por) la (manana|tarde|noche))?(?: ?(?:hrs|horas|h)\b)?`);
const ajustar = (h, ampm) => (ampm === "pm" && h < 12 ? h + 12 : ampm === "am" && h === 12 ? 0 : h);

function leerRango(texto) {
  const m = PATRON_RANGO.exec(texto);
  if (!m) return null;
  let h1 = Number(m[1]), m1 = Number(m[2] || 0), h2 = Number(m[4]), m2 = Number(m[5] || 0);
  const ap1 = (m[3] || "").replace(/\./g, ""), ap2 = (m[6] || "").replace(/\./g, ""), momento = m[7];
  if (h1 > 23 || h2 > 24 || m1 > 59 || m2 > 59) return null;
  const tarde = ap2 === "pm" || momento === "tarde" || momento === "noche";
  h2 = ajustar(h2, ap2 || (tarde ? "pm" : ""));
  if (h2 === 0 && m2 === 0) h2 = 24;
  if (ap1) h1 = ajustar(h1, ap1);
  else if (h1 < 12 && ((tarde && h1 + 12 < h2) || (!ap2 && !momento && h1 >= 1 && h1 <= 7))) h1 += 12;
  if (!ap2 && !momento && h2 < 12 && h2 <= h1) h2 += 12;
  if (!(h1 * 60 + m1 < h2 * 60 + m2 && h2 * 60 + m2 <= 24 * 60)) return "medianoche";
  const dd = (n) => String(n).padStart(2, "0");
  return [`${dd(h1)}:${dd(m1)}`, h2 === 24 ? "23:59" : `${dd(h2)}:${dd(m2)}`, [m.index, m.index + m[0].length]];
}

/** "de lunes a viernes de 9am a 6pm trabajo" -> bloque (sin id), o el texto que explica qué falta. */
export function interpretarBloque(texto) {
  let t = normalizar(texto);
  let traslado = 0;
  const tr = leerTraslado(t);
  if (tr) {
    const [a, b] = tr[1];
    traslado = tr[0];
    t = t.slice(0, a) + " ".repeat(b - a) + t.slice(b);
    texto = texto.slice(0, a) + " ".repeat(b - a) + texto.slice(b);
  }
  const rango = leerRango(t);
  if (rango === "medianoche") {
    return "Ese bloque termina pasada la medianoche. Anótalo en dos partes, por ejemplo: " +
      "«lunes de 10pm a 12am turno» y «martes de 12am a 6am turno».";
  }
  if (rango === null) return "No entendí las horas. Escribe, por ejemplo: «de lunes a viernes de 9am a 6pm trabajo».";
  const [inicio, fin, [a, b]] = rango;
  const resto = t.slice(0, a) + " ".repeat(b - a) + t.slice(b);
  const dias = leerDias(resto);
  if (!dias) return "¿Qué días? Por ejemplo: «de lunes a viernes», «martes y jueves» o «sábados».";
  const tramos = [[a, b], ...[...resto.matchAll(PATRON_DIAS)].map((x) => [x.index, x.index + x[0].length])];
  let titulo = texto;
  for (const [i, f] of tramos.sort((x, y) => y[0] - x[0] || y[1] - x[1])) titulo = titulo.slice(0, i) + " " + titulo.slice(f);
  const limpiar = (s) => s.replace(/^[ ,.;:-]+|[ ,.;:-]+$/g, "");
  titulo = limpiar(titulo.replace(/\s+/g, " "));
  titulo = limpiar(titulo.replace(/^(?:(?:tengo|hay|de|el|los|y)\s+)+/i, "")) || "Ocupado";
  return { dias, inicio, fin, titulo: titulo.charAt(0).toUpperCase() + titulo.slice(1, 80), traslado };
}

// ------------------------------------------------------------ textos
/** 90 -> '1 h 30 min' */
export function duracionMinutos(minutos) {
  const h = Math.floor(minutos / 60), m = minutos % 60;
  return h && m ? `${h} h ${m} min` : h ? `${h} h` : `${m} min`;
}

export const duracion = (a, b) => duracionMinutos(Math.floor((b - a) / MIN));

/** [0,1,2,3,4] -> 'lun a vie'; [1,3] -> 'mar y jue' */
export function describirDias(dias) {
  const d = [...dias].sort((x, y) => x - y);
  if (d.length === 7) return "todos los días";
  if (d.length >= 3 && d.every((x, i) => x === d[0] + i)) return `${DIAS_CORTOS[d[0]]} a ${DIAS_CORTOS[d.at(-1)]}`;
  const n = d.map((i) => DIAS_CORTOS[i]);
  return n.length === 1 ? n[0] : `${n.slice(0, -1).join(", ")} y ${n.at(-1)}`;
}

/** 'lun a vie 09:00–18:00 · Trabajo' (+ ' · 🚌 45 min') */
export function describirBloque(b) {
  return `${describirDias(b.dias)} ${b.inicio}–${b.fin} · ${b.titulo}` + (b.traslado ? ` · 🚌 ${duracionMinutos(b.traslado)}` : "");
}

/** 'sáb 01/11 · No trabajo' o '20/12–30/12 · Vacaciones' */
export function describirExcepcion(e) {
  const d = deIsoDia(e.desde), h = deIsoDia(e.hasta);
  return e.desde === e.hasta ? `${DIAS_CORTOS[diaSemana(d)]} ${ddmm(d)} · ${e.titulo}` : `${ddmm(d)}–${ddmm(h)} · ${e.titulo}`;
}

const dosDig = (n) => String(n).padStart(2, "0");
const hhmm = (f) => `${dosDig(f.getUTCHours())}:${dosDig(f.getUTCMinutes())}`;

/** '14:00–16:30 (2 h 30 min) · 19:00–23:00 (4 h)' o 'nada' */
export function describirLibre(libres) {
  return libres.length ? libres.map(([a, b]) => `${hhmm(a)}–${hhmm(b)} (${duracion(a, b)})`).join(" · ") : "nada";
}

export const minutos = (libres) => libres.reduce((s, [a, b]) => s + Math.floor((b - a) / MIN), 0);

/** Para la voz: 'media hora', 'una hora', '2 horas y 15 minutos' */
export function hablarDuracion(min) {
  const h = Math.floor(min / 60), m = min % 60;
  if (h === 0) return m === 30 ? "media hora" : `${m} minutos`;
  const horas = h === 1 ? "una hora" : `${h} horas`;
  if (m === 0) return horas;
  return m === 30 ? `${horas} y media` : `${horas} y ${m} minutos`;
}

// ------------------------------------------------------------ excepciones
/** "traba" coincide con "Trabajo en Sanna"; "" coincide con todo. */
export function coincide(filtro, titulo) {
  return !filtro || normalizar(titulo).split(/\s+/).some((p) => p.length >= 4 && p.slice(0, 5) === filtro.slice(0, 5));
}

export const raiz = (palabra) => normalizar(palabra).slice(0, 5);

/** ¿Ese día (fecha de pared) la excepción libera ese bloque? */
export function libera(e, dia, bloque) {
  const d = isoDia(dia);
  return e.desde <= d && d <= e.hasta && coincide(e.filtro, bloque.titulo);
}

const P_MES = String.raw`(?: de (${MESES.join("|")}|setiembre))?`;
const PATRON_DEL_AL = new RegExp(String.raw`\b(?:del?|desde el) (\d{1,2})${P_MES} (?:al|hasta el) (\d{1,2})${P_MES}\b`);
const PATRON_EL_DIA = new RegExp(String.raw`\b(?:el|este|el dia) (\d{1,2})${P_MES}\b`);
const PATRON_NO = /\bno (?:(?:tengo|hay) |(?:voy|asisto) (?:a |al )?(?:la |el )?)?([a-z]{3,})/;
const PATRON_TIPO = /\b(vacaciones|feriado|libre)\b/;
const DIAS_ANTES = new RegExp(String.raw`\b(?:${DIAS.join("|")}|sabado|domingo)\b`);

const mesDe = (nombre) => (!nombre ? null : nombre === "setiembre" ? 9 : MESES.indexOf(nombre) + 1);

function fecha(anio, mes, dia) {
  const f = crear(anio, mes, dia);
  return f.getUTCMonth() === mes - 1 && f.getUTCDate() === dia ? f : null;   // 31/02 no existe
}

/** El próximo 'dia' (del 'mes' si se dijo) que no haya pasado. */
function fechaProxima(dia, mes, hoy) {
  const anioHoy = hoy.getUTCFullYear(), mesHoy = hoy.getUTCMonth() + 1;
  for (let salto = 0; salto < 14; salto++) {
    const m = mes || ((mesHoy - 1 + salto) % 12) + 1;
    const anio = mes ? anioHoy : anioHoy + Math.floor((mesHoy - 1 + salto) / 12);
    const f = fecha(anio, m, dia);
    if (!f) { if (mes) return null; continue; }
    if (f >= hoy) return f;
    if (mes) return fecha(anioHoy + 1, m, dia);
  }
  return null;
}

/**
 * "el 1 de noviembre no trabajo" / "vacaciones del 20 al 30 de diciembre" / "mañana no tengo clases".
 * hoy: fecha de pared (00:00). Devuelve la excepción o un texto con la explicación.
 */
export function interpretarExcepcion(texto, hoy) {
  hoy = soloFecha(hoy);
  const t = normalizar(texto);
  let desde = null, hasta = null, resto;
  const m = PATRON_DEL_AL.exec(t);
  if (m) {
    const mes2 = mesDe(m[4]) || mesDe(m[2]);
    const mes1 = mesDe(m[2]) || mes2;
    hasta = fechaProxima(Number(m[3]), mes2, hoy);
    if (hasta && mes1) {
      desde = fecha(hasta.getUTCFullYear() - (mes1 > hasta.getUTCMonth() + 1 ? 1 : 0), mes1, Number(m[1]));
    } else if (hasta) {
      desde = fechaProxima(Number(m[1]), null, hoy);
    }
    if (desde && hasta && desde > hasta) {
      return "La fecha de inicio queda después del final. Revisa el rango (por ejemplo: «del 20 al 30 de diciembre»).";
    }
    resto = t.slice(0, m.index) + " " + t.slice(m.index + m[0].length);
  } else {
    const d = PATRON_EL_DIA.exec(t);
    if (d && !DIAS_ANTES.test(t.slice(0, d.index))) {
      desde = hasta = fechaProxima(Number(d[1]), mesDe(d[2]), hoy);
    } else {
      const r = interpretar(texto, conHora(hoy, 0, 1));
      if (r.fecha) desde = hasta = soloFecha(r.fecha);
    }
    resto = t;
  }
  if (!desde || !hasta) {
    return "¿Qué día? Escribe la fecha, por ejemplo: «el 1 de noviembre no trabajo» o «vacaciones del 20 al 30 de diciembre».";
  }
  if (Math.round((hasta - desde) / 86400000) > 120) return "Es un rango muy largo (más de 4 meses). Revisa las fechas.";
  const no = PATRON_NO.exec(resto);
  if (no) {
    const original = texto.trim().replace(/\s+/g, " ");
    const inicio = normalizar(original).indexOf(no[0]);
    const titulo = inicio >= 0 ? original.slice(inicio, inicio + no[0].length) : no[0];
    return { desde: isoDia(desde), hasta: isoDia(hasta), filtro: raiz(no[1]),
             titulo: titulo.charAt(0).toUpperCase() + titulo.slice(1, 60) };
  }
  const tipo = PATRON_TIPO.exec(resto);
  const titulo = { vacaciones: "Vacaciones", feriado: "Feriado" }[tipo?.[1]] || "Día libre";
  return { desde: isoDia(desde), hasta: isoDia(hasta), filtro: "", titulo };
}

// ------------------------------------------------------------ libre
/** Los bloques que SÍ se cumplen ese día (su día de la semana, menos las excepciones). */
export function delDia(dia, bloques, excepciones = []) {
  return bloques.filter((b) => b.dias.includes(diaSemana(dia)) && !excepciones.some((e) => libera(e, dia, b)));
}

/** Lo ocupado de ese día, ordenado: bloques (con traslado) y extras [(inicio, fin, título)]. */
export function ocupado(dia, bloques, excepciones = [], extras = []) {
  const salida = delDia(dia, bloques, excepciones).map((b) => [
    sumarMinutos(enDia(dia, b.inicio), -(b.traslado || 0)), sumarMinutos(enDia(dia, b.fin), b.traslado || 0), b.titulo]);
  const d = isoDia(dia);
  salida.push(...extras.filter((x) => isoDia(x[0]) === d));
  return salida.sort((x, y) => x[0] - y[0] || x[1] - y[1] || (x[2] < y[2] ? -1 : x[2] > y[2] ? 1 : 0));
}

/** El bloque que se cruza con algo que empieza en 'inicio' y dura 'min' (sin duración: si cae dentro). */
export function choque(inicio, min, bloques, excepciones = []) {
  const fin = sumarMinutos(inicio, min || 0);
  const dia = soloFecha(inicio);
  for (const b of delDia(dia, bloques, excepciones)) {
    const bi = enDia(dia, b.inicio), bf = enDia(dia, b.fin);
    if (min ? inicio < bf && fin > bi : bi <= inicio && inicio < bf) return b;
  }
  return null;
}

/**
 * Horas libres de un día: de despertar a dormir ("HH:MM"), menos bloques (y traslados), menos 'extras',
 * sin los bloques que libera una excepción. Si es hoy, desde 'ahora'. Descarta huecos de menos de 'minimo'.
 */
export function huecos(dia, bloques, despertar, dormir, ahora = null, minimo = 30, excepciones = [], extras = []) {
  dia = soloFecha(dia);
  let [dh, dm] = hm(despertar), [nh, nm] = hm(dormir);
  if (nh * 60 + nm <= dh * 60 + dm) [nh, nm] = [23, 59];
  let desde = conHora(dia, dh, dm);
  const hasta = conHora(dia, nh, nm);
  if (ahora && isoDia(ahora) === isoDia(dia)) desde = new Date(Math.max(desde, ahora));
  const libres = [];
  let cursor = desde;
  for (const [ini, fin] of ocupado(dia, bloques, excepciones, extras)) {
    if (ini > cursor) libres.push([cursor, new Date(Math.min(ini, hasta))]);
    cursor = new Date(Math.max(cursor, fin));
  }
  if (cursor < hasta) libres.push([cursor, hasta]);
  return libres.filter(([a, b]) => b - a >= minimo * MIN);
}

export const lunesDe = (dia) => sumarDias(soloFecha(dia), -diaSemana(dia));
