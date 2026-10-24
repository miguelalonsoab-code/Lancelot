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
