/**
 * Lo que el celular sabe de ti gracias a la laptop (v3.19): horario, días libres, perfil y actividades.
 *
 * La laptop sube ese "contexto" al servidor en cada sincronización (solo si cambió). Lo que haces aquí
 * («ya fui al gimnasio», «mañana no trabajo», agendar una sugerencia) se guarda como "acción pendiente"
 * hasta que la laptop la aplica; mientras tanto se SUMA al contexto para que lo veas al instante.
 *
 * Funciones puras (sin pantalla): se prueban en pruebas/contexto.test.mjs. Repiten plan_del_dia() y
 * horas_libres() de interfaz/app.py usando la misma lógica de comun/horario.js y comun/recomendador.js.
 */
import { conHora, desdeTexto, soloFecha, sumarDias, sumarMinutos } from "./comun/fechas.js";
import { coincide, deIsoDia, huecos, isoDia, lunesDe, raiz } from "./comun/horario.js";
import { normalizar } from "./comun/interprete.js";
import { siguienteOcurrencia } from "./comun/planificador.js";
import { recomendar } from "./comun/recomendador.js";

const MIN = 60000;
const vacio = { perfil: { despertar: "06:00", dormir: "23:00", meta_estudio: 0, minutos_para_arrancar: 30 },
  horario: [], excepciones: [], actividades: [], hechas: {}, estudio: {}, evitar: {}, sugeridas: [] };

/** El contexto de la laptop + lo hecho aquí que todavía no llegó allá. */
export function combinar(contexto, acciones = []) {
  const c = { ...vacio, ...(contexto || {}) };
  const hechas = Object.fromEntries(Object.entries(c.hechas).map(([k, v]) => [k, [...v]]));
  let excepciones = [...c.excepciones];
  let actividades = [...c.actividades];
  let horario = [...c.horario];
  let perfil = { ...c.perfil };
  const sugeridas = new Set(c.sugeridas);
  const mismaExc = (x, e) => x.desde === e.desde && x.hasta === e.hasta && x.filtro === e.filtro;
  for (const a of acciones) {                        // en orden: «agregar y después quitar» queda quitado
    if (a.tipo === "quitar_excepcion") excepciones = excepciones.filter((x) => !mismaExc(x, a.datos));
    if (a.tipo === "quitar_actividad") actividades = actividades.filter((x) => x.id !== a.datos.id);
    if (a.tipo === "quitar_bloque") horario = horario.filter((x) => x.id !== a.datos.id);
    if (a.tipo === "bloque") horario.push({ ...a.datos, id: null, pendiente: true });
    if (a.tipo === "perfil") perfil = { ...perfil, ...a.datos, pendiente: true };
    if (a.tipo === "actividad" && !actividades.some((x) => normalizar(x.nombre) === normalizar(a.datos.nombre))) {
      actividades.push({ ...a.datos, id: null, pendiente: true });
    }
    if (a.tipo === "hecha") {
      const k = String(a.datos.actividad_id);
      hechas[k] = [...new Set([...(hechas[k] || []), a.datos.dia])].sort();
    } else if (a.tipo === "excepcion") {
      const e = a.datos;
      if (!excepciones.some((x) => mismaExc(x, e))) {
        excepciones.push({ ...e, pendiente: true });
      }
    } else if (a.tipo === "sugerida") {
      sugeridas.add(a.datos.tarea);
    }
  }
  excepciones.sort((x, y) => (x.desde < y.desde ? -1 : x.desde > y.desde ? 1 : 0));
  horario.sort((x, y) => Math.min(...x.dias) - Math.min(...y.dias) || (x.inicio < y.inicio ? -1 : x.inicio > y.inicio ? 1 : 0));
  return { ...c, hechas, excepciones, actividades, horario, perfil, sugeridas, conocido: Boolean(contexto) };
}

/** Las veces que hiciste cada actividad entre dos días (incluidos): { id: n } y el Set de las de 'dia'. */
export function hechasEntre(ctx, desde, hasta, dia = hasta) {
  const d1 = isoDia(desde), d2 = isoDia(hasta), hoy = isoDia(dia);
  const semana = {}, delDia = new Set();
  for (const [id, dias] of Object.entries(ctx.hechas)) {
    const enRango = dias.filter((d) => d1 <= d && d <= d2);
    if (enRango.length) semana[Number(id)] = enRango.length;
    if (dias.includes(hoy)) delDia.add(Number(id));
  }
  return [semana, delDia];
}

/** Tareas pendientes de ese día (fecha de pared 00:00), con su ocurrencia si se repiten. */
export function tareasDelDia(tareas, dia, maximo = 400) {
  const d = isoDia(dia);
  const salida = [];
  for (const t of tareas) {
    let f = desdeTexto(t.fecha);
    for (let i = 0; f && i < maximo && isoDia(f) <= d; i++) {
      if (isoDia(f) === d) { salida.push({ ...t, ocurrencia: f }); break; }
      if (!t.repeticion) break;
      f = siguienteOcurrencia(f, t.repeticion, f);
    }
  }
  return salida.sort((x, y) => x.ocurrencia - y.ocurrencia);
}

/** Lo ocupado por tareas/eventos con duración ese día: [(inicio, fin, título)] */
const ocupacionesDe = (tareas, dia) => tareasDelDia(tareas, dia).filter((t) => t.duracion)
  .map((t) => [t.ocurrencia, sumarMinutos(t.ocurrencia, t.duracion), t.titulo]);

/** Horas libres de ese día (si es hoy, desde 'ahora'), igual que horas_libres() de la laptop. */
export function horasLibres(ctx, tareas, dia, ahora, minimo = 30) {
  return huecos(dia, ctx.horario, ctx.perfil.despertar, ctx.perfil.dormir, ahora, minimo, ctx.excepciones,
    ocupacionesDe(tareas, dia));
}

/** «fui al gimnasio» -> [Gimnasio] */
export function actividadesQueNombra(ctx, texto) {
  const palabras = normalizar(texto).split(/\s+/).filter((p) => p.length >= 4).map(raiz);
  return ctx.actividades.filter((a) => palabras.some((p) => coincide(p, a.nombre)));
}

/** Igual que plan_del_dia() de la laptop: margen al despertar, lo ya agendado cuenta, lo rechazado se evita. */
export function planDelDia(ctx, tareas, dia, ahora) {
  dia = soloFecha(dia);
  const arranque = sumarMinutos(conHora(dia, ...ctx.perfil.despertar.split(":").map(Number)), ctx.perfil.minutos_para_arrancar || 0);
  const libres = horasLibres(ctx, tareas, dia, ahora)
    .map(([a, b]) => [new Date(Math.max(a, arranque)), b]).filter(([a, b]) => b - a >= 15 * MIN);
  const delDia = tareasDelDia(tareas, dia);
  const planificadas = new Set(delDia.flatMap((t) => actividadesQueNombra(ctx, t.titulo).map((a) => a.id)));
  const estudioAgendado = delDia.filter((t) => normalizar(t.titulo).includes("estudi")).reduce((s, t) => s + (t.duracion || 0), 0);
  const estudio = (isoDia(dia) === isoDia(ahora) ? ctx.estudio[isoDia(dia)] || 0 : 0) + estudioAgendado;
  const [semana, hoy] = hechasEntre(ctx, lunesDe(dia), dia);
  return recomendar(dia, libres, ctx.actividades, semana, new Set([...hoy, ...planificadas]), estudio,
    ctx.perfil.meta_estudio, { evitar: ctx.evitar });
}

/** ¿Esa tarea vino de una sugerencia? (no "vence": mañana se quita sola) */
export const esSugerida = (ctx, t) => ctx.sugeridas.has(t.id);

/**
 * La agenda de un día, lista para pintar: excepciones, bloques del horario, tareas/eventos y huecos libres,
 * ordenados por hora. Cada elemento: { tipo, inicio, fin, titulo, detalle, tarea? }.
 */
export function agendaDelDia(ctx, tareas, dia, ahora) {
  dia = soloFecha(dia);
  const d = isoDia(dia);
  const items = [];
  for (const e of ctx.excepciones.filter((x) => x.desde <= d && d <= x.hasta)) {
    items.push({ tipo: "excepcion", inicio: dia, titulo: e.titulo, detalle: e.filtro ? "Ese bloque no cuenta" : "Todo tu horario libre",
                 pendiente: Boolean(e.pendiente) });
  }
  const dow = (dia.getUTCDay() + 6) % 7;
  for (const b of ctx.horario.filter((x) => x.dias.includes(dow))) {
    const libre = ctx.excepciones.some((e) => e.desde <= d && d <= e.hasta && coincide(e.filtro, b.titulo));
    const [h1, m1] = b.inicio.split(":").map(Number), [h2, m2] = b.fin.split(":").map(Number);
    items.push({ tipo: "bloque", inicio: conHora(dia, h1, m1), fin: conHora(dia, h2, m2), titulo: b.titulo, liberado: libre,
                 detalle: libre ? "No va (día libre)" : b.traslado ? `🚌 ${b.traslado} min antes y después` : "" });
  }
  for (const t of tareasDelDia(tareas, dia)) {
    items.push({ tipo: t.tipo === "evento" ? "evento" : "tarea", inicio: t.ocurrencia,
                 fin: t.duracion ? sumarMinutos(t.ocurrencia, t.duracion) : null, titulo: t.titulo, tarea: t,
                 sugerida: esSugerida(ctx, t) });
  }
  if (ctx.horario.length || ctx.conocido) {
    for (const [a, b] of horasLibres(ctx, tareas, dia, ahora)) items.push({ tipo: "libre", inicio: a, fin: b, titulo: "Libre" });
  }
  const orden = { excepcion: 0, bloque: 1, evento: 2, tarea: 2, libre: 3 };
  return items.sort((x, y) => x.inicio - y.inicio || orden[x.tipo] - orden[y.tipo]);
}

/** Para los puntitos del calendario: { 'AAAA-MM-DD': { tareas, eventos, libre } } entre dos días. */
export function marcasDelMes(ctx, tareas, desde, hasta) {
  const marcas = {};
  for (let dia = soloFecha(desde); dia <= hasta; dia = sumarDias(dia, 1)) {
    const del = tareasDelDia(tareas, dia, 62);
    const d = isoDia(dia);
    const libre = ctx.excepciones.some((e) => e.desde <= d && d <= e.hasta);
    if (del.length || libre) {
      marcas[d] = { tareas: del.filter((t) => t.tipo !== "evento").length, eventos: del.filter((t) => t.tipo === "evento").length, libre };
    }
  }
  return marcas;
}

export { deIsoDia, isoDia };
