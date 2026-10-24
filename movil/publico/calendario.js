/**
 * Vista Calendario del celular (v3.19): el mes con puntitos y, debajo, la agenda del día elegido.
 *
 *   ‹  octubre 2026  ›
 *   L  M  M  J  V  S  D
 *         1• 2  3  4 …          • tarea   • evento (lila)   🏖 día libre
 *
 *   Jueves 22 de octubre
 *   08:30–17:30  Trabajo en Sanna      (gris: tu horario fijo)
 *   18:15–23:00  🕒 Libre · 4 h 45 min  (verde)
 *   19:00        📅 Examen de redes     (tocar = opciones de la tarea)
 *   💡 Te sugiero …  [📌 Agendar]       (hoy y días que vienen)
 *
 * Solo pinta: los datos y las acciones vienen de app.js (parámetro 'h').
 */
import { DIAS, MESES, conHora, crear, diasEntre, diaSemana, hhmm, sumarDias } from "./comun/fechas.js";
import { describirExcepcion, duracion, isoDia, lunesDe } from "./comun/horario.js";
import { describirSugerencia } from "./comun/recomendador.js";
import { agendaDelDia, marcasDelMes, planDelDia } from "./contexto.js";

const INICIALES = ["L", "M", "M", "J", "V", "S", "D"];
const capital = (s) => s.charAt(0).toUpperCase() + s.slice(1);

/**
 * h = { el, ctx, tareas, ahora, modo ("mes" | "semana"), mes (1.er día del mes), dia, elegirDia(d),
 *       cambiarMes(±1), cambiarSemana(±1), cambiarModo(m), tocarTarea(t), agendar(plan), hecha(sugerencia), misCosas() }
 */
export function pintarCalendario(contenedor, h) {
  const { el } = h;
  const modos = el("div", { class: "cal-modos", role: "group", "aria-label": "Ver por" },
    ["mes", "semana"].map((m) => el("button", { "aria-pressed": h.modo === m, onclick: () => h.cambiarModo(m) },
      m === "mes" ? "Mes" : "Semana")));
  contenedor.replaceChildren(modos, ...(h.modo === "semana" ? vistaSemana(h) : vistaMes(h)), agenda(h));
}

// ------------------------------------------------------------ semana (v3.20)
/**
 * 7 columnas (lunes a domingo) con el día de arriba a abajo, de que despiertas a que duermes:
 * gris = tu horario, verde suave = libre, turquesa = tareas, lila = eventos. Tocar un día = su agenda abajo.
 */
function vistaSemana(h) {
  const { el, ctx, tareas, ahora, dia } = h;
  const lunes = lunesDe(dia);
  const hoy = conHora(ahora, 0, 0);
  const [d1, d2] = [ctx.perfil.despertar, ctx.perfil.dormir].map((x) => x.split(":").map(Number));
  const desde = d1[0] * 60 + d1[1];
  const hasta = Math.max(desde + 60, d2[0] * 60 + d2[1] <= desde ? 24 * 60 : d2[0] * 60 + d2[1]);
  const pos = (f, fin) => {
    const a = Math.max(desde, f.getUTCHours() * 60 + f.getUTCMinutes());
    const b = Math.min(hasta, fin ? (fin.getUTCDate() !== f.getUTCDate() ? 24 * 60 : fin.getUTCHours() * 60 + fin.getUTCMinutes()) : a + 30);
    return b <= a ? null : { top: `${((a - desde) / (hasta - desde)) * 100}%`, height: `${((b - a) / (hasta - desde)) * 100}%` };
  };
  // La política de seguridad (CSP) no deja usar style="…" en el HTML: la posición se pone por JavaScript (CSSOM)
  const ubicar = (n, estilo) => { Object.assign(n.style, estilo); return n; };
  const columnas = [];
  for (let i = 0; i < 7; i++) {
    const d = sumarDias(lunes, i);
    const dd = d;
    const piezas = agendaDelDia(ctx, tareas, d, null)
      .filter((x) => x.tipo !== "excepcion")
      .map((x) => { const estilo = pos(x.inicio, x.fin); return estilo && ubicar(el("i", { class: `sem-${x.tipo}`,
        "data-liberado": x.liberado, title: `${hhmm(x.inicio)} ${x.titulo}` }), estilo); });
    const libre = ctx.excepciones.some((e) => e.desde <= isoDia(d) && isoDia(d) <= e.hasta);
    columnas.push(el("button", { class: "sem-col", "data-hoy": isoDia(d) === isoDia(hoy), "data-elegido": isoDia(d) === isoDia(dia),
      "data-libre": libre, onclick: () => h.elegirDia(dd), "aria-label": `${capital(DIAS[i])} ${d.getUTCDate()}` },
    el("span", { class: "sem-dia" }, `${INICIALES[i]} ${d.getUTCDate()}`),
    el("span", { class: "sem-linea" }, piezas)));
  }
  const domingo = sumarDias(lunes, 6);
  const rango = `${lunes.getUTCDate()} ${MESES[lunes.getUTCMonth()].slice(0, 3)} – ${domingo.getUTCDate()} ${MESES[domingo.getUTCMonth()].slice(0, 3)}`;
  const horas = [];
  for (let m = Math.ceil(desde / 180) * 180; m < hasta; m += 180) {
    horas.push(ubicar(el("span", {}, `${m / 60}h`), { top: `${((m - desde) / (hasta - desde)) * 100}%` }));
  }
  return [
    el("div", { class: "cal-cabeza" },
      el("button", { class: "b-mes", "aria-label": "Semana anterior", onclick: () => h.cambiarSemana(-1) }, "‹"),
      el("h3", {}, rango),
      el("button", { class: "b-mes", "aria-label": "Semana siguiente", onclick: () => h.cambiarSemana(1) }, "›")),
    el("div", { class: "sem" }, el("div", { class: "sem-horas", "aria-hidden": "true" }, horas), columnas),
    el("p", { class: "sem-leyenda" }, el("i", { class: "sem-bloque" }), "horario ", el("i", { class: "sem-libre" }), "libre ",
      el("i", { class: "sem-tarea" }), "tareas ", el("i", { class: "sem-evento" }), "eventos"),
  ];
}

// ------------------------------------------------------------ mes
function vistaMes(h) {
  const { el, ctx, tareas, ahora, mes, dia } = h;
  const hoy = conHora(ahora, 0, 0);
  const primero = crear(mes.getUTCFullYear(), mes.getUTCMonth() + 1, 1);
  const inicio = sumarDias(primero, -diaSemana(primero));                 // lunes de la primera semana
  const ultimo = crear(mes.getUTCFullYear(), mes.getUTCMonth() + 2, 0);
  const fin = sumarDias(ultimo, 6 - diaSemana(ultimo));
  const marcas = marcasDelMes(ctx, tareas, inicio, fin);

  const celdas = [];
  for (let d = inicio; d <= fin; d = sumarDias(d, 1)) {
    const m = marcas[isoDia(d)];
    const fuera = d.getUTCMonth() !== mes.getUTCMonth();
    const dd = d;
    celdas.push(el("button", {
      class: "cal-dia", "data-fuera": fuera, "data-hoy": isoDia(d) === isoDia(hoy), "data-elegido": isoDia(d) === isoDia(dia),
      "data-libre": m?.libre, "data-pasado": d < hoy, "aria-label": `${capital(DIAS[diaSemana(d)])} ${d.getUTCDate()} de ${MESES[d.getUTCMonth()]}` +
        (m ? `: ${m.tareas} tareas, ${m.eventos} eventos${m.libre ? ", día libre" : ""}` : ""),
      onclick: () => h.elegirDia(dd),
    }, el("span", { class: "num" }, String(d.getUTCDate())),
      el("span", { class: "puntos" }, m?.tareas ? el("i", { class: "p-tarea" }) : null, m?.eventos ? el("i", { class: "p-evento" }) : null)));
  }

  return [
    el("div", { class: "cal-cabeza" },
      el("button", { class: "b-mes", "aria-label": "Mes anterior", onclick: () => h.cambiarMes(-1) }, "‹"),
      el("h3", {}, `${capital(MESES[mes.getUTCMonth()])} ${mes.getUTCFullYear()}`),
      el("button", { class: "b-mes", "aria-label": "Mes siguiente", onclick: () => h.cambiarMes(1) }, "›")),
    el("div", { class: "cal-semana", "aria-hidden": "true" }, INICIALES.map((x) => el("span", {}, x))),
    el("div", { class: "cal-grilla" }, celdas)];
}

function agenda(h) {
  const { el, ctx, tareas, ahora, dia } = h;
  const hoy = conHora(ahora, 0, 0);
  const dias = diasEntre(hoy, dia);
  const titulo = dias === 0 ? "Hoy" : dias === 1 ? "Mañana" : dias === -1 ? "Ayer"
    : `${capital(DIAS[diaSemana(dia)])} ${dia.getUTCDate()} de ${MESES[dia.getUTCMonth()]}`;
  const items = agendaDelDia(ctx, tareas, dia, dias === 0 ? ahora : null);
  const filas = items.map((i) => fila(el, i, h));
  const partes = [el("h3", { class: "ag-titulo" }, titulo)];
  if (!ctx.conocido) {
    partes.push(el("p", { class: "nota" }, "Tu horario todavía no llegó desde la laptop. Ábrela con internet y aparece aquí solo."));
  }
  partes.push(...(filas.length ? filas : [el("p", { class: "nada" }, "Nada anotado.")]));
  if (dias >= 0 && ctx.conocido && (ctx.actividades.length || ctx.perfil.meta_estudio)) {
    const plan = planDelDia(ctx, tareas, dia, ahora);
    if (plan.sugerencias.length) {
      partes.push(el("div", { class: "sugerencias" },
        el("h4", {}, "💡 Te sugiero"),
        plan.sugerencias.map((s) => el("div", { class: "sug" },
          el("span", {}, describirSugerencia(s)),
          dias === 0 && s.clase === "actividad" && s.actividad_id !== null && el("button", { class: "b-mini", onclick: () => h.hecha(s),
            "aria-label": `Ya hice ${s.nombre}` }, "✓"))),
        el("button", { class: "b-secundario", onclick: () => h.agendar(plan, dia) }, "📌 Agendar como tareas")));
    } else if (plan.sin_lugar.length) {
      partes.push(el("p", { class: "nota" }, `No entra: ${plan.sin_lugar.join(", ")}.`));
    }
  }
  partes.push(el("button", { class: "enlace mis-cosas", onclick: h.misCosas }, "🏖 Días libres y 🏃 actividades"));
  return el("section", { class: "agenda" }, partes);
}

function fila(el, i, h) {
  const hora = i.tipo === "excepcion" ? "🏖" : hhmm(i.inicio) + (i.fin && i.tipo !== "tarea" && i.tipo !== "evento" ? `–${hhmm(i.fin)}` : "");
  let titulo = i.titulo, detalle = i.detalle || "";
  if (i.tipo === "libre") { titulo = `🕒 Libre · ${duracion(i.inicio, i.fin)}`; }
  if (i.tipo === "evento") titulo = `📅 ${i.titulo}`;
  if (i.sugerida) titulo = `💡 ${i.titulo}`;
  if ((i.tipo === "tarea" || i.tipo === "evento") && i.fin) detalle = `Hasta las ${hhmm(i.fin)}`;
  if (i.tipo === "excepcion" && i.pendiente) detalle += " · se guarda cuando la laptop sincronice";
  const contenido = [el("span", { class: "ag-hora" }, hora),
    el("span", { class: "ag-que" }, el("span", { class: "ag-tit" }, titulo), detalle && el("span", { class: "ag-det" }, detalle))];
  return i.tarea
    ? el("button", { class: "ag-fila", "data-tipo": i.tipo, onclick: () => h.tocarTarea(i.tarea) }, contenido)
    : el("div", { class: "ag-fila", "data-tipo": i.tipo, "data-liberado": i.liberado }, contenido);
}

export { describirExcepcion };
