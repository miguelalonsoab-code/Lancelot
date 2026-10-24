/**
 * Actividades de tu perfil (v3.20): lo mismo que interpretar_actividad() de nucleo/perfil.py, para poder
 * agregarlas desde el celular. Comparado con Python en pruebas/horario.test.mjs (clave "horario.actividades").
 *
 *   "gimnasio 1 hora 3 veces por semana en la tarde" -> { nombre: "Gimnasio", minutos: 60, veces_semana: 3, momento: "tarde" }
 */
import { duracionMinutos } from "./horario.js";
import { normalizar } from "./interprete.js";

export const MOMENTOS = { manana: "en la mañana", tarde: "en la tarde", noche: "en la noche" };
const NUMEROS = { un: 1, una: 1, dos: 2, tres: 3, cuatro: 4, cinco: 5, seis: 6, siete: 7 };
const NUM = String.raw`(\d{1,3}|una?|dos|tres|cuatro|media)`;
const PATRON_DURACION = new RegExp(
  String.raw`\b(?:${NUM} ?(?:h|hr|hrs|horas?)(?: y (\d{1,2}|media|cuarto)(?: ?(?:min|mins|minutos))?` +
  String.raw`| ?(\d{1,2}) ?(?:min|mins|minutos))?` +
  String.raw`|(\d{1,3}) ?(?:m|min|mins|minutos)` +
  String.raw`|(media hora|hora y media|una hora y media))\b`);
const VECES = /\b(\d|una|dos|tres|cuatro|cinco|seis|siete) (?:veces|vez) (?:por|a la|cada|en la) semana\b|\b(todos los dias|diario|diariamente|cada dia)\b/;
const MOMENTO = /\b(?:en|por|de) la (manana|tarde|noche)\b|\b(?:(?:en|por|de) )?(?:las )?(mananas|tardes|noches)\b/;
const RELLENO = /^(?:(?:hacer|ir al?|ir a la|practicar|el|la|los|las|de|un|una)\s+)+/i;

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
