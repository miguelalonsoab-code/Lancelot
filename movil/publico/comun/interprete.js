/**
 * Intérprete de texto en español -> { titulo, fecha, repeticion }.
 *
 * Es una traducción línea por línea de nucleo/interprete.py (la laptop). Las dos versiones
 * se prueban contra los mismos casos (tests/casos_interprete.json), así que
 * "mañana 8pm pagar la luz" se entiende igual en la laptop, en el servidor y en el celular.
 *
 * Idea general (igual que en Python):
 *  1. Se trabaja sobre una copia en minúsculas y SIN tildes, del mismo largo que el original.
 *  2. Cada regla (repetición, tiempo relativo, día, hora) anota el tramo de texto que usó.
 *  3. Lo que sobra es el título de la tarea.
 */
import { conHora, crear, diaSemana, esValida, soloFecha, sumarDias, sumarMinutos } from "./fechas.js";

const SIN_TILDES = { "á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u", "ü": "u", "ñ": "n" };
export const DIAS_SEMANA = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"];
const MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
  "agosto", "septiembre", "octubre", "noviembre", "diciembre"];
const NUMEROS_TEXTO = { un: 1, una: 1, dos: 2, tres: 3, cuatro: 4, cinco: 5, diez: 10, quince: 15,
  veinte: 20, treinta: 30 };
const HORA_MOMENTO = { manana: [9, 0], tarde: [15, 0], noche: [20, 0] };
export const HORA_POR_DEFECTO = [9, 0];

/** Repeticiones (clave -> texto para mostrar). "" = sin repetir. */
export const REPETICIONES = {
  "": "Sin repetir", diaria: "Todos los días", laborables: "Lunes a viernes",
  semanal: "Cada semana", mensual: "Cada mes",
};

const RELLENO_INICIAL = /^(?:recuerdame|recordarme|recordar|avisame|avisarme|anota|anotame|apunta|agrega|que|de|a|para|y)\b\s*/;

const P_DIA = "(lunes|martes|miercoles|jueves|viernes|sabados?|domingos?)";
const PATRONES_REPETICION = [
  [/\b(?:todos los dias|cada dia|diariamente|a diario|diario)\b/g, "diaria"],
  [/\b(?:de lunes a viernes|dias laborables|entre semana)\b/g, "laborables"],
  [new RegExp(String.raw`\b(?:cada|todos los) ` + P_DIA + String.raw`\b`, "g"), "semanal"],
  [/\b(?:cada semana|semanalmente|semanal)\b/g, "semanal"],
  [/\b(?:cada mes|mensualmente|mensual)\b/g, "mensual"],
];
const PATRON_RELATIVO = /\b(?:en|dentro de) (\d+|un|una|dos|tres|cuatro|cinco|diez|quince|veinte|treinta|media) ?(minutos?|mins?|m|horas?|hrs?|h|dias?)\b/g;
const PATRON_PASADO_MANANA = /\bpasado manana\b/g;
const PATRON_MANANA = /(?<!la )\bmanana\b/g;
const PATRON_HOY = /\b(?:hoy|esta (tarde|noche))\b/g;
const PATRON_DIA_SEMANA = new RegExp(String.raw`\b(?:(?:el|este|el proximo|proximo) )?` + P_DIA + String.raw`\b`, "g");
const PATRON_FECHA_NUM = /\b(?:el )?(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?\b/g;
const PATRON_FECHA_TEXTO = new RegExp(String.raw`\b(?:el )?(\d{1,2}) de (` + MESES.join("|") +
  String.raw`)(?: (?:de|del) (\d{4}))?\b`, "g");
const PATRON_MEDIODIA = /\b(?:al |a (?:la )?)?(mediodia|medianoche)\b/g;
const PATRON_HORA = new RegExp(
  String.raw`(?<prefijo>\b(?:a las?|a eso de las?|tipo|como a las?) )?` +
  String.raw`\b(?<h>\d{1,2})(?::(?<m>\d{2}))?` +
  String.raw`(?: y (?<fraccion>media|cuarto|\d{1,2}))?` +
  String.raw`(?:\s?(?<ampm>am|pm|a\.m\.|p\.m\.))?` +
  String.raw`(?: (?:de|en|por) la (?<momento>manana|tarde|noche))?` +
  String.raw`(?<sufijo> ?(?:hrs|horas|h)\b)?`, "g");
const PATRON_MOMENTO = /\b(?:en|por|de) la (manana|tarde|noche)\b/g;

/** Minúsculas y sin tildes, conservando el largo del texto. */
export function normalizar(texto) {
  return texto.toLowerCase().replace(/[áéíóúüñ]/g, (c) => SIN_TILDES[c]);
}

/**
 * ahora: fecha de pared (ver fechas.js). Devuelve { titulo, fecha (Date o null), repeticion (texto o null) }.
 */
export function interpretar(texto, ahora, horaPorDefecto = HORA_POR_DEFECTO) {
  ahora = crear(ahora.getUTCFullYear(), ahora.getUTCMonth() + 1, ahora.getUTCDate(),
    ahora.getUTCHours(), ahora.getUTCMinutes());
  const t = normalizar(texto);
  const tramos = [];                                   // [inicio, fin] ya reconocidos
  const libre = (ini, fin) => tramos.every(([a, b]) => fin <= a || ini >= b);
  const buscar = (patron) => {
    for (const m of t.matchAll(patron)) if (libre(m.index, m.index + m[0].length)) return m;
    return null;
  };
  const usar = (m) => { tramos.push([m.index, m.index + m[0].length]); return m; };

  let repeticion = null, diaSem = null, dia = null, relativo = null, momento = null, hora = null;
  let m;

  // 1) Repetición
  for (const [patron, tipo] of PATRONES_REPETICION) {
    if ((m = buscar(patron))) {
      usar(m);
      repeticion = tipo;
      if (m.length > 1 && m[1]) diaSem = indiceDia(m[1]);
      break;
    }
  }

  // 2) Tiempo relativo ("en 20 min")
  if ((m = buscar(PATRON_RELATIVO))) {
    usar(m);
    relativo = aMinutos(m[1], m[2]);
  }

  // 3) Día
  if (relativo === null) {
    let d;
    if ((m = buscar(PATRON_PASADO_MANANA))) {
      usar(m); dia = sumarDias(soloFecha(ahora), 2);
    } else if ((m = buscar(PATRON_MANANA))) {
      usar(m); dia = sumarDias(soloFecha(ahora), 1);
    } else if ((m = buscar(PATRON_HOY))) {
      usar(m); dia = soloFecha(ahora); momento = m[1] || null;
    } else if ((m = buscar(PATRON_FECHA_TEXTO)) &&
               (d = fechaValida(+m[1], MESES.indexOf(m[2]) + 1, m[3], ahora))) {
      usar(m); dia = d;
    } else if ((m = buscar(PATRON_FECHA_NUM)) && (d = fechaValida(+m[1], +m[2], m[3], ahora))) {
      usar(m); dia = d;
    } else if ((m = buscar(PATRON_DIA_SEMANA))) {
      usar(m); diaSem = indiceDia(m[1]);
    }
  }

  // 4) Hora
  if (relativo === null) {
    if ((m = buscar(PATRON_MEDIODIA))) {
      usar(m);
      hora = m[1] === "mediodia" ? [12, 0, true] : [0, 0, true];
    } else {
      for (const mh of t.matchAll(PATRON_HORA)) {
        const h = libre(mh.index, mh.index + mh[0].length) ? horaDesdeMatch(mh) : null;
        if (h) { usar(mh); hora = h; break; }
      }
    }
    if ((m = buscar(PATRON_MOMENTO))) {
      usar(m);
      momento = momento || m[1];
    }
  }

  const horaFinal = resolverHora(hora, momento);
  const fecha = combinar(ahora, dia, diaSem, horaFinal, relativo, repeticion, horaPorDefecto);
  return { titulo: limpiarTitulo(texto, tramos), fecha, repeticion };
}

// ----------------------------------------------------------------- ayudantes
function indiceDia(nombre) {
  if (nombre === "sabados" || nombre === "domingos") nombre = nombre.slice(0, -1);
  return DIAS_SEMANA.indexOf(nombre);
}

function aMinutos(cantidad, unidad) {
  const n = cantidad === "media" ? 0.5 : /^\d+$/.test(cantidad) ? +cantidad : (NUMEROS_TEXTO[cantidad] ?? 1);
  if (unidad.startsWith("m")) return n;
  if (unidad.startsWith("h")) return n * 60;
  return n * 1440;
}

function fechaValida(d, mes, anio, ahora) {
  if (anio) {
    let a = +anio;
    if (a < 100) a += 2000;
    return esValida(a, mes, d) ? crear(a, mes, d) : null;
  }
  const y = ahora.getUTCFullYear();
  if (!esValida(y, mes, d)) return null;
  let candidata = crear(y, mes, d);
  if (candidata < soloFecha(ahora)) {                  // ya pasó este año -> el próximo
    if (!esValida(y + 1, mes, d)) return null;
    candidata = crear(y + 1, mes, d);
  }
  return candidata;
}

function horaDesdeMatch(m) {
  const g = m.groups;
  if (!["prefijo", "m", "ampm", "momento", "fraccion", "sufijo"].some((k) => g[k])) return null;
  const h = +g.h;
  let minutos = +(g.m || 0);
  if (g.fraccion) minutos = { media: 30, cuarto: 15 }[g.fraccion] || +g.fraccion;
  if (h > 23 || minutos > 59) return null;
  const ampm = (g.ampm || "").replace(/\./g, "");
  const momento = g.momento;
  if (ampm === "pm" || momento === "tarde" || momento === "noche") return [h < 12 ? h + 12 : h, minutos, true];
  if (ampm === "am" || momento === "manana") return [h === 12 ? 0 : h, minutos, true];
  return [h, minutos, h >= 13 || h === 0];
}

function resolverHora(hora, momento) {
  if (hora === null) return HORA_MOMENTO[momento] || null;
  let [h, mi, decidida] = hora;
  if (!decidida) {
    if ((momento === "tarde" || momento === "noche") && h < 12) h += 12;
    else if (momento === null && h >= 1 && h <= 7) h += 12;   // "a las 3" casi siempre es 15:00
  }
  return [h, mi];
}

function combinar(ahora, dia, diaSem, hora, relativo, repeticion, horaPorDefecto) {
  if (relativo !== null) return sumarMinutos(ahora, relativo);
  if (dia === null && diaSem === null && hora === null && repeticion === null) return null;
  const [h, mi] = hora || horaPorDefecto;
  const diaExplicito = dia !== null;
  if (dia === null) {
    dia = soloFecha(ahora);
    if (diaSem !== null) dia = sumarDias(dia, (diaSem - diaSemana(dia) + 7) % 7);
    else if (repeticion === "laborables") while (diaSemana(dia) >= 5) dia = sumarDias(dia, 1);
  }
  let fecha = conHora(dia, h, mi);
  if (fecha <= ahora && !diaExplicito) {
    if (diaSem !== null) fecha = sumarDias(fecha, 7);
    else {
      fecha = sumarDias(fecha, 1);
      while (repeticion === "laborables" && diaSemana(fecha) >= 5) fecha = sumarDias(fecha, 1);
    }
  } else if (fecha <= ahora && soloFecha(fecha).getTime() === soloFecha(ahora).getTime()) {
    fecha = sumarDias(fecha, 1);                          // "hoy 8am" cuando ya son las 10
  }
  return fecha;
}

const QUITAR = " ,.;:-";
function recortar(s) {
  let i = 0, j = s.length;
  while (i < j && QUITAR.includes(s[i])) i++;
  while (j > i && QUITAR.includes(s[j - 1])) j--;
  return s.slice(i, j);
}

function limpiarTitulo(original, tramos) {
  let texto = original;
  for (const [ini, fin] of [...tramos].sort((a, b) => b[0] - a[0])) {
    texto = texto.slice(0, ini) + " " + texto.slice(fin);
  }
  texto = recortar(texto.replace(/\s+/g, " "));
  for (;;) {                                            // relleno del inicio ("recuérdame que ...")
    const nuevo = normalizar(texto).replace(RELLENO_INICIAL, "");
    if (nuevo === normalizar(texto)) break;
    texto = texto.slice(texto.length - nuevo.length);
  }
  texto = recortar(texto.replace(/\s+(?:a las?|el|de|para|a|y)$/i, ""));
  return texto.charAt(0).toUpperCase() + texto.slice(1);
}
