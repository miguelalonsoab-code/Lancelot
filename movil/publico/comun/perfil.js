/**
 * Actividades de tu perfil (v3.20): lo mismo que interpretar_actividad() de nucleo/perfil.py, para poder
 * agregarlas desde el celular. Comparado con Python en pruebas/horario.test.mjs (clave "horario.actividades").
 *
 *   "gimnasio 1 hora 3 veces por semana en la tarde" -> { nombre: "Gimnasio", minutos: 60, veces_semana: 3, momento: "tarde" }
 */
import { duracionMinutos, leerDuracion } from "./horario.js";
import { normalizar } from "./interprete.js";

export const MOMENTOS = { manana: "en la mañana", tarde: "en la tarde", noche: "en la noche" };
const NUMEROS = { un: 1, una: 1, dos: 2, tres: 3, cuatro: 4, cinco: 5, seis: 6, siete: 7 };
const VECES = /\b(\d|una|dos|tres|cuatro|cinco|seis|siete) (?:veces|vez) (?:por|a la|cada|en la) semana\b|\b(todos los dias|diario|diariamente|cada dia)\b/;
const MOMENTO = /\b(?:en|por|de) la (manana|tarde|noche)\b|\b(?:(?:en|por|de) )?(?:las )?(mananas|tardes|noches)\b/;
const RELLENO = /^(?:(?:hacer|ir al?|ir a la|practicar|el|la|los|las|de|un|una)\s+)+/i;

/** "gimnasio 1 hora 3 veces por semana en la tarde" -> actividad (sin id), o el texto de lo que falta. */
export function interpretarActividad(texto) {
  const t = normalizar(texto);
  const tramos = [];
  let minutos = 60, veces = null, momento = null;
  const d = leerDuracion(t);
  if (d) { minutos = d[0]; tramos.push(d[1]); }
  const v = VECES.exec(t);
  if (v) {
    veces = v[2] ? 7 : /^\d$/.test(v[1]) ? Number(v[1]) : NUMEROS[v[1]];
    tramos.push([v.index, v.index + v[0].length]);
  }
  const mo = MOMENTO.exec(t);
  if (mo) {
    momento = mo[1] || mo[2].slice(0, -1);
    tramos.push([mo.index, mo.index + mo[0].length]);
  }
  let nombre = texto;
  for (const [a, b] of tramos.sort((x, y) => y[0] - x[0] || y[1] - x[1])) nombre = nombre.slice(0, a) + " " + nombre.slice(b);
  const limpiar = (s) => s.replace(/^[\s,.;:-]+|[\s,.;:-]+$/g, "");
  nombre = limpiar(nombre.replace(/\s+/g, " "));
  nombre = limpiar(nombre.replace(RELLENO, ""));
  if (!nombre) return "¿Qué actividad? Por ejemplo: «actividad: gimnasio 1 hora 3 veces por semana en la tarde».";
  return { nombre: nombre.charAt(0).toUpperCase() + nombre.slice(1, 60), minutos,
           veces_semana: veces && veces >= 1 && veces <= 7 ? veces : null, momento };
}

/** 'Gimnasio · 1 h · 3 veces por semana · en la tarde' */
export function describirActividad(a) {
  const partes = [a.nombre, duracionMinutos(a.minutos)];
  if (a.veces_semana) {
    partes.push(a.veces_semana === 7 ? "todos los días" : `${a.veces_semana} ${a.veces_semana === 1 ? "vez" : "veces"} por semana`);
  }
  partes.push(MOMENTOS[a.momento] || "cuando puedas");
  return partes.join(" · ");
}

export { leerDuracion };

// ------------------------------------------------------------ horas de sueño (v3.21)
const HORA = /\b(\d{1,2})(?::(\d{2}))?(?:\s?(am|pm|a\.m\.|p\.m\.))?(?: (?:de|en|por) la (manana|tarde|noche))?/;

/**
 * Igual que leer_hora() de nucleo/perfil.py: 'a las 6:30' -> "06:30" · 'las 11 de la noche' -> "23:00".
 * para = "despertar" | "dormir": sin am/pm, "me duermo a las 11" es 23:00 y "me despierto a las 6" es 06:00.
 */
export function leerHora(texto, para) {
  const m = HORA.exec(normalizar(texto));
  if (!m) return null;
  let h = Number(m[1]);
  const mi = Number(m[2] || 0), ampm = (m[3] || "").replace(/\./g, ""), momento = m[4];
  if (h > 23 || mi > 59) return null;
  if (ampm === "pm" || momento === "tarde" || momento === "noche") h = h < 12 ? h + 12 : h;
  else if (ampm === "am" || momento === "manana") h = h === 12 ? 0 : h;
  else if (para === "dormir" && h >= 7 && h <= 11) h += 12;
  else if (para === "dormir" && h === 12) h = 0;
  return `${String(h).padStart(2, "0")}:${String(mi).padStart(2, "0")}`;
}
