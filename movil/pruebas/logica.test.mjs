// Comandos, repeticiones, reprogramar y textos de fecha: lo mismo que prueban los tests de Python.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { interpretarComando } from "../publico/comun/comandos.js";
import { aTexto, ahoraEn, describirAtraso, describirFecha, desdeTexto, horaHablada } from "../publico/comun/fechas.js";
import { aManana, opcionesReprogramar, siguienteOcurrencia } from "../publico/comun/planificador.js";

const f = desdeTexto;
const { comandos } = JSON.parse(readFileSync(new URL("../../tests/casos_interprete.json", import.meta.url), "utf8"));

for (const c of comandos) {
  test(`comando · ${c.texto}`, () => assert.deepEqual(interpretarComando(c.texto), c.comando));
}

test("repeticiones", () => {
  assert.equal(aTexto(siguienteOcurrencia(f("2026-10-09 07:00"), "laborables", f("2026-10-09 07:00"))), "2026-10-12 07:00");
  assert.equal(aTexto(siguienteOcurrencia(f("2027-01-31 09:00"), "mensual", f("2027-01-31 09:00"))), "2027-02-28 09:00");
  assert.equal(aTexto(siguienteOcurrencia(f("2026-10-04 22:00"), "diaria", f("2026-10-07 06:30"))), "2026-10-07 22:00");
  assert.equal(siguienteOcurrencia(f("2026-10-04 22:00"), null, f("2026-10-07 06:30")), null);
});

test("reprogramar una vencida", () => {
  const ahora = f("2026-10-10 10:00");
  const op = opcionesReprogramar(f("2026-10-09 20:00"), ahora).map(([e, d]) => [e, aTexto(d)]);
  assert.deepEqual(op, [["En 1 hora", "2026-10-10 11:00"], ["Hoy a las 20:00", "2026-10-10 20:00"],
    ["Mañana a las 20:00", "2026-10-11 20:00"], ["Mañana a las 09:00", "2026-10-11 09:00"]]);
  const tarde = opcionesReprogramar(f("2026-10-10 09:00"), f("2026-10-10 19:30")).map(([e]) => e);
  assert.deepEqual(tarde, ["En 1 hora", "Mañana a las 09:00"]);
  assert.equal(aTexto(aManana(f("2026-10-03 07:15"), ahora)), "2026-10-11 07:15");
});

test("textos de fecha", () => {
  const ahora = f("2026-10-10 10:00");
  assert.equal(describirFecha(f("2026-10-10 20:00"), ahora), "hoy 20:00");
  assert.equal(describirFecha(f("2026-10-11 09:00"), ahora), "mañana 09:00");
  assert.equal(describirFecha(f("2026-10-16 15:00"), ahora), "vie 16/10 15:00");
  assert.equal(describirAtraso(f("2026-10-10 09:48"), ahora), "venció hace 12 min");
  assert.equal(describirAtraso(f("2026-10-09 20:00"), ahora), "venció ayer 20:00");
  assert.equal(describirAtraso(f("2026-10-07 09:00"), ahora), "venció hace 3 días (mié 07/10)");
  assert.equal(horaHablada(f("2026-10-10 14:30")), "a las 2 y media de la tarde");
  assert.equal(horaHablada(f("2026-10-10 13:00")), "a la 1 de la tarde");
});

test("hora de Lima, aunque el servidor viva en UTC", () => {
  const instante = new Date(Date.UTC(2026, 9, 11, 3, 30));       // 03:30 UTC = 22:30 del día anterior en Lima
  assert.equal(aTexto(ahoraEn("America/Lima", instante)), "2026-10-10 22:30");
  assert.equal(f("2026-02-31 10:00"), null);                       // fecha imposible
});
