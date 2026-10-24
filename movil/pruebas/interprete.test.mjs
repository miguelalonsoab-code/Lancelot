// El intérprete JavaScript debe dar lo mismo que el de Python en todos los casos compartidos.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { aTexto, describirFaltan, desdeTexto } from "../publico/comun/fechas.js";
import { describirAvisos, interpretar } from "../publico/comun/interprete.js";
import { avisoPrevioPendiente, siguienteOcurrencia } from "../publico/comun/planificador.js";

const datos = JSON.parse(readFileSync(new URL("../../tests/casos_interprete.json", import.meta.url), "utf8"));

for (const c of datos.casos) {
  test(`${c.ahora} · ${c.texto}`, () => {
    const r = interpretar(c.texto, desdeTexto(c.ahora));
    assert.deepEqual(
      { titulo: r.titulo, fecha: r.fecha && aTexto(r.fecha), repeticion: r.repeticion, tipo: r.tipo,
        anticipacion: r.anticipacion, avisos: r.avisos, duracion: r.duracion },
      { titulo: c.titulo, fecha: c.fecha, repeticion: c.repeticion, tipo: c.tipo, anticipacion: c.anticipacion,
        avisos: c.avisos, duracion: c.duracion });
  });
}

test("avisos previos: mismos resultados que la laptop", () => {
  for (const c of datos.avisos_previos) {
    const toca = avisoPrevioPendiente(desdeTexto(c.fecha), c.avisos, desdeTexto(c.desde), desdeTexto(c.ahora));
    assert.equal(toca, c.toca, JSON.stringify(c));
  }
});

test("'faltan N días' y 'avisa N días antes'", () => {
  for (const c of datos.faltan) assert.equal(describirFaltan(desdeTexto(c.fecha), desdeTexto(c.ahora)), c.texto);
  for (const [avisos, texto] of Object.entries(datos.textos_avisos)) {
    assert.equal(describirAvisos(avisos === "None" ? null : avisos), texto);
  }
});

test("repeticiones (anual, 29 de febrero, fin de mes)", () => {
  for (const c of datos.repeticiones) {
    assert.equal(aTexto(siguienteOcurrencia(desdeTexto(c.fecha), c.repeticion, desdeTexto(c.ahora))), c.siguiente);
  }
});

test("vocabulario aprendido de las correcciones: igual que en la laptop", () => {
  for (const c of datos.con_vocabulario) {
    assert.equal(interpretar(c.texto, desdeTexto("2026-10-07 06:30"), undefined, datos.vocabulario).tipo, c.tipo, c.texto);
    assert.equal(interpretar(c.texto, desdeTexto("2026-10-07 06:30")).tipo, c.sin_vocabulario, c.texto);
  }
});

test("las frases del celular son las mismas de la laptop, y la bolsa no repite", async () => {
  const { REFLEXIONES, BolsaFrases } = await import("../publico/comun/frases.js");
  assert.deepEqual(REFLEXIONES, datos.reflexiones);
  const bolsa = new BolsaFrases(["a", "b", "c"]);
  assert.deepEqual([bolsa.sacar(), bolsa.sacar(), bolsa.sacar()].sort(), ["a", "b", "c"]);
});
