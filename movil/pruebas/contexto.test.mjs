// El contexto en el celular (v3.19): lo de la laptop + lo hecho aquí, horas libres, plan y agenda del día.
import { test } from "node:test";
import assert from "node:assert/strict";
import { aTexto, desdeTexto } from "../publico/comun/fechas.js";
import { deIsoDia } from "../publico/comun/horario.js";
import { actividadesQueNombra, agendaDelDia, combinar, hechasEntre, horasLibres, marcasDelMes, planDelDia, tareasDelDia }
  from "../publico/contexto.js";

const f = desdeTexto;
const LAPTOP = {
  version: 1,
  perfil: { despertar: "06:00", dormir: "23:00", meta_estudio: 100, minutos_para_arrancar: 30 },
  horario: [{ dias: [0, 1, 2, 3, 4], inicio: "08:30", fin: "17:30", titulo: "Trabajo en Sanna", traslado: 45 }],
  excepciones: [{ desde: "2026-11-02", hasta: "2026-11-02", filtro: "traba", titulo: "No trabajo" }],
  actividades: [{ id: 1, nombre: "Gimnasio", minutos: 60, veces_semana: 3, momento: "tarde" },
                { id: 2, nombre: "Leer", minutos: 30, veces_semana: null, momento: "noche" }],
  hechas: { 1: ["2026-10-19", "2026-10-12"] }, estudio: { "2026-10-22": 40 }, evitar: {}, sugeridas: ["s-1"],
};
const TAREAS = [
  { id: "t-1", titulo: "Examen de redes", fecha: "2026-10-23 19:00", tipo: "evento", duracion: 120, repeticion: null },
  { id: "t-2", titulo: "Pagar la luz", fecha: "2026-10-22 09:00", tipo: "tarea", duracion: null, repeticion: null },
  { id: "t-3", titulo: "Regar plantas", fecha: "2026-10-20 07:00", tipo: "tarea", duracion: null, repeticion: "diaria" },
];

test("combinar: lo pendiente del celular se suma al contexto", () => {
  const ctx = combinar(LAPTOP, [
    { id: 1, tipo: "hecha", datos: { actividad_id: 1, dia: "2026-10-22" } },
    { id: 2, tipo: "excepcion", datos: { desde: "2026-10-23", hasta: "2026-10-23", filtro: "", titulo: "Feriado" } },
    { id: 3, tipo: "sugerida", datos: { tarea: "s-2", actividad_id: 1 } }]);
  assert.deepEqual(ctx.hechas["1"], ["2026-10-12", "2026-10-19", "2026-10-22"]);
  assert.deepEqual(ctx.excepciones.map((e) => e.titulo), ["Feriado", "No trabajo"]);
  assert.ok(ctx.excepciones[0].pendiente);
  assert.deepEqual([...ctx.sugeridas], ["s-1", "s-2"]);
  assert.deepEqual(hechasEntre(ctx, deIsoDia("2026-10-19"), deIsoDia("2026-10-22")), [{ 1: 2 }, new Set([1])]);
  assert.equal(combinar(null).conocido, false);
});

test("tareas del día, con repeticiones", () => {
  assert.deepEqual(tareasDelDia(TAREAS, deIsoDia("2026-10-22")).map((t) => [t.id, aTexto(t.ocurrencia)]),
    [["t-3", "2026-10-22 07:00"], ["t-2", "2026-10-22 09:00"]]);
  assert.deepEqual(tareasDelDia(TAREAS, deIsoDia("2026-10-19")), []);
});

test("horas libres: horario, excepción y tareas con duración", () => {
  const ctx = combinar(LAPTOP);
  const txt = (l) => l.map(([a, b]) => `${aTexto(a).slice(11)}-${aTexto(b).slice(11)}`);
  assert.deepEqual(txt(horasLibres(ctx, TAREAS, deIsoDia("2026-10-23"), null)), ["06:00-07:45", "18:15-19:00", "21:00-23:00"]);
  assert.deepEqual(txt(horasLibres(ctx, TAREAS, deIsoDia("2026-11-02"), null)), ["06:00-23:00"]);   // no trabaja
});

test("plan del día: margen al despertar, estudio de hoy y lo ya agendado", () => {
  const ctx = combinar(LAPTOP);
  const p = planDelDia(ctx, TAREAS, deIsoDia("2026-10-22"), f("2026-10-22 05:00"));
  assert.equal(aTexto(p.sugerencias[0].inicio), "2026-10-22 06:30");                // 30 min después de despertar
  assert.ok(p.sugerencias.find((s) => s.nombre === "Estudiar").motivo.includes("1 h"));   // 100 - 40
  const agendado = [...TAREAS, { id: "x", titulo: "Gimnasio", fecha: "2026-10-22 18:15", tipo: "tarea", duracion: 60 }];
  assert.ok(!planDelDia(ctx, agendado, deIsoDia("2026-10-22"), f("2026-10-22 05:00")).sugerencias.some((s) => s.nombre === "Gimnasio"));
  assert.deepEqual(actividadesQueNombra(ctx, "ya fui al gimnasio").map((a) => a.nombre), ["Gimnasio"]);
});

test("agenda y marcas del calendario", () => {
  const ctx = combinar(LAPTOP);
  const agenda = agendaDelDia(ctx, TAREAS, deIsoDia("2026-10-23"), f("2026-10-22 10:00"));
  assert.deepEqual(agenda.map((i) => `${i.tipo} ${aTexto(i.inicio).slice(11)} ${i.titulo}`), [
    "libre 06:00 Libre", "tarea 07:00 Regar plantas", "bloque 08:30 Trabajo en Sanna", "libre 18:15 Libre",
    "evento 19:00 Examen de redes", "libre 21:00 Libre"]);
  const libre = agendaDelDia(ctx, TAREAS, deIsoDia("2026-11-02"), f("2026-10-22 10:00"));
  assert.equal(libre[0].tipo, "excepcion");
  assert.ok(libre.find((i) => i.tipo === "bloque").liberado);
  const marcas = marcasDelMes(ctx, TAREAS, deIsoDia("2026-10-21"), deIsoDia("2026-11-02"));
  assert.deepEqual(marcas["2026-10-23"], { tareas: 1, eventos: 1, libre: false });
  assert.deepEqual(marcas["2026-11-02"], { tareas: 1, eventos: 0, libre: true });
});

test("v3.20: quitar días libres y agregar/quitar actividades desde el celular", () => {
  const ctx = combinar(LAPTOP, [
    { id: 1, tipo: "quitar_excepcion", datos: { desde: "2026-11-02", hasta: "2026-11-02", filtro: "traba" } },
    { id: 2, tipo: "actividad", datos: { nombre: "Yoga", minutos: 45, veces_semana: 2, momento: null } },
    { id: 3, tipo: "actividad", datos: { nombre: "gimnasio", minutos: 30, veces_semana: 1, momento: null } },   // ya existe
    { id: 4, tipo: "quitar_actividad", datos: { id: 2 } },
    { id: 5, tipo: "excepcion", datos: { desde: "2026-11-05", hasta: "2026-11-05", filtro: "", titulo: "Feriado" } },
    { id: 6, tipo: "quitar_excepcion", datos: { desde: "2026-11-05", hasta: "2026-11-05", filtro: "" } }]);
  assert.deepEqual(ctx.excepciones, []);
  assert.deepEqual(ctx.actividades.map((a) => [a.nombre, a.id, Boolean(a.pendiente)]), [["Gimnasio", 1, false], ["Yoga", null, true]]);
  // Una actividad nueva (sin id todavía) ya entra en las sugerencias
  const p = planDelDia(ctx, [], deIsoDia("2026-10-24"), f("2026-10-24 05:00"));
  assert.ok(p.sugerencias.some((s) => s.nombre === "Yoga"));
});
