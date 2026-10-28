/**
 * Sugerencias: qué hacer en tus horas libres. Lo mismo que nucleo/recomendador.py de la laptop
 * (ahí está la explicación completa de cómo decide). pruebas/horario.test.mjs compara ambos.
 *
 *   actividad   { id, nombre, minutos, veces_semana, momento: "manana" | "tarde" | "noche" | null }
 *   sugerencia  { nombre, inicio, fin, motivo, clase: "estudio" | "actividad", actividad_id }
 */
import { conHora, diaSemana, horaHablada, soloFecha, sumarMinutos } from "./fechas.js";
import { duracionMinutos } from "./horario.js";
import { normalizar } from "./interprete.js";

export const MOMENTO_HORAS = { manana: [5, 12], tarde: [12, 19], noche: [19, 24] };
export const NOMBRE_MOMENTO = { manana: "la mañana", tarde: "la tarde", noche: "la noche" };
const SESION_ESTUDIO = 100;
const ESTUDIO_MINIMO = 25;
const MIN = 60000;
const dos = (n) => String(n).padStart(2, "0");
const hhmm = (f) => `${dos(f.getUTCHours())}:${dos(f.getUTCMinutes())}`;

export function momentoDe(f) {
  const h = f.getUTCHours();
  for (const [nombre, [a, b]] of Object.entries(MOMENTO_HORAS)) if (a <= h && h < b) return nombre;
  return "noche";
}

export const clave = (nombre) => normalizar(nombre).trim();

/** '18:15–19:15 · Gimnasio (llevas 1 de 3 esta semana)' */
export const describirSugerencia = (s) => `${hhmm(s.inicio)}–${hhmm(s.fin)} · ${s.nombre} (${s.motivo})`;

function candidatos(dia, actividades, hechasSemana, hechasHoy, estudioHoy, metaEstudio) {
  const salida = [];
  let falta = metaEstudio - estudioHoy;
  for (let sesion = 1; falta >= 15 && sesion <= 2; sesion++) {
    const m = Math.min(falta, SESION_ESTUDIO);
    const motivo = sesion === 1 ? `te faltan ${duracionMinutos(metaEstudio - estudioHoy)} para tu meta` : "segunda parte de tu meta";
    salida.push({ nombre: "Estudiar", minutos: m, prioridad: sesion === 1 ? 2.0 : 0.6, motivo, clase: "estudio",
                  momento: null, actividad_id: null, minimo: Math.min(m, ESTUDIO_MINIMO) });
    falta -= m;
  }
  const quedanDias = 7 - diaSemana(dia);
  for (const a of actividades) {
    if (hechasHoy.has(a.id)) continue;
    if (a.veces_semana) {
      const hechas = hechasSemana[a.id] || 0;
      const faltan = a.veces_semana - hechas;
      if (faltan <= 0) continue;
      const urgencia = Math.min(faltan / quedanDias, 1.5);
      salida.push({ nombre: a.nombre, minutos: a.minutos, prioridad: 0.3 + urgencia,
                    motivo: `llevas ${hechas} de ${a.veces_semana} esta semana`, clase: "actividad",
                    momento: a.momento || null, actividad_id: a.id, minimo: null });
    } else {
      salida.push({ nombre: a.nombre, minutos: a.minutos, prioridad: 0.2, motivo: "te gusta y hoy hay tiempo",
                    clase: "actividad", momento: a.momento || null, actividad_id: a.id, minimo: null });
    }
  }
  return salida.sort((x, y) => y.prioridad - x.prioridad);          // estable, como sorted() de Python
}

function ventana(dia, momento) {
  if (!momento) return [conHora(dia, 0, 0), conHora(dia, 23, 59)];
  const [a, b] = MOMENTO_HORAS[momento];
  return [conHora(dia, a, 0), b === 24 ? conHora(dia, 23, 59) : conHora(dia, b, 0)];
}

function ubicar(libres, minutos, desde, hasta) {
  for (const [a, b] of libres) {
    const ini = new Date(Math.max(a, desde)), fin = new Date(Math.min(b, hasta));
    if (fin - ini >= minutos * MIN) return ini;
  }
  return null;
}

function ocupar(libres, ini, fin, pausa) {
  const salida = [];
  const corte = sumarMinutos(fin, pausa);
  for (const [a, b] of libres) {
    if (b <= ini || a >= corte) { salida.push([a, b]); continue; }
    for (const [x, y] of [[a, ini], [corte, b]]) if (y - x >= 15 * MIN) salida.push([x, y]);
  }
  return salida;
}

function sinMomentos(dia, libres, momentos) {
  for (const m of momentos) libres = ocupar(libres, ...ventana(dia, m), 0);
  return libres;
}

function ubicarCandidato(dia, libres, c, soloSuMomento = false, evitar = []) {
  let motivo = c.motivo, minutos = c.minutos;
  if (evitar.length) libres = sinMomentos(dia, libres, evitar);
  let inicio = ubicar(libres, minutos, ...ventana(dia, c.momento));
  if (soloSuMomento && inicio === null) return null;
  if (inicio === null && c.momento) {
    inicio = ubicar(libres, minutos, ...ventana(dia, null));
    if (inicio !== null) motivo += `; no hay hueco en ${NOMBRE_MOMENTO[c.momento]}`;
  }
  if (inicio === null && c.minimo) {
    for (const [a, b] of libres) {
      const largo = Math.floor((b - a) / MIN);
      if (largo >= c.minimo) { inicio = a; minutos = Math.min(largo, c.minutos); break; }
    }
  }
  if (inicio === null) return null;
  return { nombre: c.nombre, inicio, fin: sumarMinutos(inicio, minutos), motivo, clase: c.clase, actividad_id: c.actividad_id };
}

function ubicarRondas(dia, libres, rondas, maximo, pausa, evitar) {
  const hechas = [], ubicados = new Set();
  for (const [grupo, soloSuMomento] of rondas) {
    for (const c of grupo) {
      if (ubicados.has(c) || hechas.length >= maximo) continue;
      const s = ubicarCandidato(dia, libres, c, soloSuMomento, [...(evitar[clave(c.nombre)] || [])]);
      if (s) { ubicados.add(c); hechas.push([s, c]); libres = ocupar(libres, s.inicio, s.fin, pausa); }
    }
  }
  return [hechas, ubicados];
}

function puntaje(hechas, elegidos) {
  return hechas.reduce((t, [s, c]) => t + c.prioridad * (elegidos.includes(c) ? 1 : 0.5)
    + (s.motivo.includes("no hay hueco") ? 0 : 0.05), 0);
}

/**
 * El plan para 'dia' dentro de 'libres' (de huecos()). hechasSemana: { id: veces desde el lunes };
 * hechasHoy: Set de ids; estudioHoy/metaEstudio en minutos; evitar: { clave: ["tarde", …] }.
 * Devuelve { sugerencias: [...], sin_lugar: [...] }.
 */
export function recomendar(dia, libres, actividades, hechasSemana, hechasHoy, estudioHoy, metaEstudio,
                           { maximo = 4, pausa = 10, evitar = {} } = {}) {
  dia = soloFecha(dia);
  libres = [...libres].sort((x, y) => x[0] - y[0] || x[1] - y[1]);
  const todos = candidatos(dia, actividades, hechasSemana, new Set(hechasHoy), estudioHoy, metaEstudio);
  const elegidos = todos.slice(0, maximo), resto = todos.slice(maximo);
  const conMomento = elegidos.filter((c) => c.momento);
  const rondasA = [[conMomento, true], [elegidos.filter((c) => !c.momento), false], [conMomento, false], [resto, false]];
  const rondasB = [[elegidos, false], [resto, false]];
  const planes = [rondasA, rondasB].map((r) => ubicarRondas(dia, libres, r, maximo, pausa, evitar));
  let [sugerencias, ubicados] = planes[0];
  if (puntaje(planes[1][0], elegidos) > puntaje(planes[0][0], elegidos)) [sugerencias, ubicados] = planes[1];
  const ubicadas = new Set(sugerencias.map(([s]) => s.nombre));    // la 2.ª sesión de estudio que no entra
  const sinLugar = [...new Set(elegidos.filter((c) => !ubicados.has(c) && (c.clase === "estudio" || c.prioridad >= 0.5))
    .map((c) => c.nombre))].filter((n) => !ubicadas.has(n));
  return { sugerencias: sugerencias.map(([s]) => s).sort((x, y) => x.inicio - y.inicio), sin_lugar: sinLugar };
}

/** [texto para mostrar, frase para la voz] */
export function describirPlan(plan, cuando = "hoy") {
  if (!plan.sugerencias.length) {
    let texto = plan.sin_lugar.length ? `No encontré un buen hueco para sugerirte algo ${cuando}.`
      : `${cuando.charAt(0).toUpperCase() + cuando.slice(1)} no tengo nada que sugerirte: vas al día.`;
    if (plan.sin_lugar.length) texto += ` No entra: ${plan.sin_lugar.join(", ")}.`;
    return [texto, texto];
  }
  const lineas = plan.sugerencias.map((s) => `• ${describirSugerencia(s)}`);
  if (plan.sin_lugar.length) lineas.push(`No entra ${cuando}: ${plan.sin_lugar.join(", ")}.`);
  const partes = plan.sugerencias.slice(0, 3).map((s) => `${s.clase === "estudio" ? s.nombre.toLowerCase() : s.nombre} ${horaHablada(s.inicio)}`);
  const hablado = "Te sugiero " + (partes.length > 1 ? `${partes.slice(0, -1).join(", ")} y ${partes.at(-1)}` : partes[0]) + ".";
  return [lineas.join("\n"), hablado];
}
