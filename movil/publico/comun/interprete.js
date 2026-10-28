/**
 * Intérprete de texto en español -> { titulo, fecha, repeticion, tipo, anticipacion, avisos }.
 *
 * Es una traducción línea por línea de nucleo/interprete.py (la laptop). Las dos versiones
 * se prueban contra los mismos casos (tests/casos_interprete.json), así que
 * "mañana 8pm pagar la luz" se entiende igual en la laptop, en el servidor y en el celular.
 *
 * Idea general (igual que en Python):
 *  1. Se trabaja sobre una copia en minúsculas y SIN tildes, del mismo largo que el original.
 *  2. Cada regla (repetición, tiempo relativo, día, hora) anota el tramo de texto que usó.
 *  3. Lo que sobra es el título de la tarea.
 *  4. Por último se decide si es TAREA o EVENTO (un evento avisa además con días de anticipación).
 */
import { conHora, crear, diaSemana, esValida, soloFecha, sumarDias, sumarMinutos } from "./fechas.js";

const SIN_TILDES = { "á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u", "ü": "u", "ñ": "n" };
export const DIAS_SEMANA = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"];
const MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
  "agosto", "septiembre", "octubre", "noviembre", "diciembre"];
const NUMEROS_TEXTO = { un: 1, una: 1, dos: 2, tres: 3, cuatro: 4, cinco: 5, seis: 6, siete: 7, ocho: 8,
  nueve: 9, diez: 10, quince: 15, veinte: 20, treinta: 30 };
const HORA_MOMENTO = { manana: [9, 0], tarde: [15, 0], noche: [20, 0] };
export const HORA_POR_DEFECTO = [9, 0];

/** Repeticiones (clave -> texto para mostrar). "" = sin repetir. */
export const REPETICIONES = {
  "": "Sin repetir", diaria: "Todos los días", laborables: "Lunes a viernes",
  semanal: "Cada semana", mensual: "Cada mes", anual: "Cada año",
};

export const TIPOS = { tarea: "Tarea", evento: "Evento" };

/** Palabras que convierten algo en EVENTO (cosas que pasan un día, no algo que "haces"). */
const PALABRAS_EVENTO = ["aniversario", "cumpleanos", "cumple", "boda", "matrimonio", "bautizo", "graduacion",
  "viaje", "vuelo", "examen", "parcial", "exposicion", "sustentacion", "cita", "concierto", "fiesta", "reunion",
  "entrevista", "conferencia", "evento"];
const PALABRA_EVENTO = new RegExp(String.raw`\b(?:` + PALABRAS_EVENTO.join("|") + String.raw`)\b`);
const PALABRA_ANUAL = /\b(?:aniversario|cumpleanos|cumple)\b/;          // vuelven cada año
const VERBO = /^(?:ir|[a-z]+(?:ar|er|ir)(?:me|te|le|les|lo|la|los|las|se)?)$/;
const NO_VERBOS = new Set(["primer", "tercer", "mujer", "ayer", "taller", "lugar", "hogar", "bar", "alquiler",
  "familiar", "militar", "collar", "altar", "mar", "super", "seminar"]);
export const AVISOS_PREVIOS_POR_DEFECTO = "7,1";

/**
 * Con cuántos días de anticipación avisar ("7,1"), o null = solo a su hora.
 * Lo pedido manda; si no, un evento usa el valor por defecto (un evento semanal solo 1 día antes; uno diario, nunca).
 */
export function avisosPrevios(tipo, repeticion, pedida) {
  if (pedida) return pedida;
  if (tipo !== "evento" || repeticion === "diaria" || repeticion === "laborables") return null;
  return repeticion === "semanal" ? "1" : AVISOS_PREVIOS_POR_DEFECTO;
}

/** "7,1" -> "avisa 7 y 1 días antes". */
export function describirAvisos(avisos) {
  if (!avisos) return "";
  const dias = avisos.split(",");
  const texto = dias.length <= 2 ? dias.join(" y ") : dias.slice(0, -1).join(", ") + " y " + dias[dias.length - 1];
  return `avisa ${texto} día${dias.length === 1 && dias[0] === "1" ? "" : "s"} antes`;
}

const RELLENO_INICIAL = /^(?:recuerdame|recordarme|recordar|avisame|avisarme|anota|anotame|apunta|agrega|que|de|del|a|para|y|es)\b\s*/;

const P_DIA = "(lunes|martes|miercoles|jueves|viernes|sabados?|domingos?)";
const PATRONES_REPETICION = [
  [/\b(?:todos los dias|cada dia|diariamente|a diario|diario)\b/g, "diaria"],
  [/\b(?:de lunes a viernes|dias laborables|entre semana)\b/g, "laborables"],
  [new RegExp(String.raw`\b(?:cada|todos los) ` + P_DIA + String.raw`\b`, "g"), "semanal"],
  [/\b(?:cada semana|semanalmente|semanal)\b/g, "semanal"],
  [/\b(?:cada mes|mensualmente|mensual)\b/g, "mensual"],
  [/\b(?:cada ano|todos los anos|anualmente|anual)\b/g, "anual"],
];
// "de 8 a 10", "14:00-16:30": hora de inicio + duración · "durante 2 horas", "por 45 minutos"
const _H = String.raw`(\d{1,2})(?::(\d{2}))?(?:\s?(am|pm|a\.m\.|p\.m\.))?`;
const PATRON_RANGO_HORAS = new RegExp(String.raw`\b(?:de|desde) (?:las? )?` + _H + String.raw` (?:a|hasta) (?:las? )?` + _H +
  String.raw`(?: (?:de|en|por) la (manana|tarde|noche))?(?: ?(?:hrs|horas|h)\b)?`, "g");
const PATRON_RANGO_GUION = /\b(\d{1,2}):(\d{2}) ?- ?(\d{1,2}):(\d{2})\b/g;
const PATRON_DURACION = /\b(?:durante|por) (\d{1,3}|una?|dos|tres|cuatro|cinco|media) ?(horas?|hrs?|h|minutos?|mins?)( y media)?\b/g;
const PATRON_MARCA_EVENTO = /^\s*(?:(?:anota|agrega|apunta|crea|nuevo|un) )?evento(?:\s*:\s*|\s*,\s*|\s+(?!de\b|del\b))/g;
const PATRON_MARCA_TAREA = /^\s*(?:nueva )?tarea\s*:\s*/g;
const PATRON_ANTICIPACION = new RegExp(
  String.raw`(?:\b(?:y )?(?:avisame|avisarme|recuerdame|recordarme|recuerdamelo|avisamelo) )?(?:\bcon )?` +
  String.raw`\b(\d{1,3}|un|una|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez|quince|veinte|treinta) ` +
  String.raw`(dias?|semanas?) (?:antes|de anticipacion)\b`, "g");
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
/**
 * vocabulario: lo aprendido de tus correcciones en la laptop ({ evento, no_evento, verbos }), o null.
 */
export function interpretar(texto, ahora, horaPorDefecto = HORA_POR_DEFECTO, vocabulario = null) {
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
  let tipo = null, anticipacion = null, duracion = null;
  let m;

  // 0) ¿Evento o tarea dicho explícito? ¿Con cuánta anticipación avisar?
  if ((m = buscar(PATRON_MARCA_EVENTO))) { usar(m); tipo = "evento"; }
  else if ((m = buscar(PATRON_MARCA_TAREA))) { usar(m); tipo = "tarea"; }
  if ((m = buscar(PATRON_ANTICIPACION))) { usar(m); anticipacion = aAnticipacion(m[1], m[2]); }
  if ((m = buscar(PATRON_DURACION))) { usar(m); duracion = aMinutosDuracion(m[1], m[2], m[3]); }

  // 1) Repetición
  for (const [patron, clave] of PATRONES_REPETICION) {
    if ((m = buscar(patron))) {
      usar(m);
      repeticion = clave;
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

  // 4) Hora (un rango "de 8 a 10" trae la hora Y la duración)
  if (relativo === null) {
    let rango = null;
    if ((m = buscar(PATRON_RANGO_HORAS))) {
      rango = resolverRango(m[1], m[2], m[3], m[4], m[5], m[6], m[7]);
    } else if ((m = buscar(PATRON_RANGO_GUION))) {
      const [h1, m1, h2, m2] = [m[1], m[2], m[3], m[4]].map(Number);
      rango = h1 < 24 && h2 < 24 && m1 < 60 && m2 < 60 ? [h1, m1, h2, m2] : null;
    }
    if (rango && rango[2] * 60 + rango[3] > rango[0] * 60 + rango[1]) {
      usar(m);
      hora = [rango[0], rango[1], true];
      duracion = rango[2] * 60 + rango[3] - (rango[0] * 60 + rango[1]);
    }
    if (hora !== null) {
      // ya la dio el rango
    } else if ((m = buscar(PATRON_MEDIODIA))) {
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
  const titulo = limpiarTitulo(texto, tramos);

  // 6) ¿Tarea o evento?
  tipo = tipo || (esEvento(titulo, vocabulario) ? "evento" : "tarea");
  if (tipo === "evento" && repeticion === null && PALABRA_ANUAL.test(normalizar(titulo))) repeticion = "anual";
  return { titulo, fecha, repeticion, tipo, anticipacion, avisos: avisosPrevios(tipo, repeticion, anticipacion), duracion };
}

// ----------------------------------------------------------------- ayudantes
function indiceDia(nombre) {
  if (nombre === "sabados" || nombre === "domingos") nombre = nombre.slice(0, -1);
  return DIAS_SEMANA.indexOf(nombre);
}

const ajustarAmPm = (h, ampm) => (ampm === "pm" && h < 12 ? h + 12 : ampm === "am" && h === 12 ? 0 : h);

/** "de 7 a 10 de la noche" -> [19, 0, 22, 0]. Mismas reglas que _resolver_rango de la laptop. */
function resolverRango(h1, m1, ap1, h2, m2, ap2, momento) {
  h1 = +h1; h2 = +h2; m1 = +(m1 || 0); m2 = +(m2 || 0);
  if (h1 > 23 || h2 > 24 || m1 > 59 || m2 > 59) return null;
  ap1 = (ap1 || "").replace(/\./g, ""); ap2 = (ap2 || "").replace(/\./g, "");
  const tarde = ap2 === "pm" || momento === "tarde" || momento === "noche";
  h2 = ajustarAmPm(h2, ap2 || (tarde ? "pm" : ""));
  if (h2 === 0 && m2 === 0) h2 = 24;
  if (ap1) h1 = ajustarAmPm(h1, ap1);
  else if (h1 < 12 && ((tarde && h1 + 12 < h2) || (!ap2 && !momento && h1 >= 1 && h1 <= 7))) h1 += 12;
  if (!ap2 && !momento && h2 < 12 && h2 <= h1) h2 += 12;
  if (h2 === 24) { h2 = 23; m2 = 59; }
  return h2 < 24 ? [h1, m1, h2, m2] : null;
}

function aMinutosDuracion(cantidad, unidad, yMedia) {
  const n = cantidad === "media" ? 0.5 : numero(cantidad);
  let minutos = unidad.startsWith("h") ? Math.floor(n * 60) : Math.floor(n);
  if (yMedia && unidad.startsWith("h")) minutos += 30;
  return minutos > 0 && minutos <= 1440 ? minutos : null;
}

/** "08:00–10:00" si tiene duración; si no, "08:00". */
export function describirRango(fecha, duracion) {
  const hh = (f) => `${String(f.getUTCHours()).padStart(2, "0")}:${String(f.getUTCMinutes()).padStart(2, "0")}`;
  return duracion ? `${hh(fecha)}–${hh(new Date(fecha.getTime() + duracion * 60000))}` : hh(fecha);
}

const numero = (c) => (/^\d+$/.test(c) ? +c : (NUMEROS_TEXTO[c] ?? 1));

function aAnticipacion(cantidad, unidad) {
  const dias = numero(cantidad) * (unidad.startsWith("semana") ? 7 : 1);
  return dias >= 1 && dias <= 365 ? String(dias) : null;
}

/** Las palabras del título que lo hacen evento: las de fábrica (menos las "desaprendidas") y las aprendidas. */
export function palabrasDeEvento(titulo, vocabulario = null) {
  const v = vocabulario || {};
  const t = normalizar(titulo);
  const fabrica = (t.match(new RegExp(PALABRA_EVENTO.source, "g")) || []).filter((w) => !(v.no_evento || []).includes(w));
  const aprendidas = (v.evento || []).filter((w) => /^[a-z]+$/.test(w) && new RegExp(String.raw`\b${w}\b`).test(t));
  return [...new Set([...fabrica, ...aprendidas])];
}

/** Menciona un aniversario, examen, cita… y NO empieza con un verbo ("estudiar para el examen"). */
export function esEvento(titulo, vocabulario = null) {
  const claves = palabrasDeEvento(titulo, vocabulario);
  if (!claves.length) return false;
  const primera = /^[a-z]*/.exec(normalizar(titulo))[0];
  if (claves.includes(primera) || (vocabulario?.verbos || []).includes(primera)) return true;
  return !(VERBO.test(primera) && !NO_VERBOS.has(primera));
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
