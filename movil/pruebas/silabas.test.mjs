// Sílabas (v3.24): el celular debe partir las palabras exactamente igual que la laptop (nucleo/silabas.py).
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { GUION_SUAVE, conGuiones, silabas } from "../publico/comun/silabas.js";

const { silabas: casos } = JSON.parse(readFileSync(new URL("../../tests/casos_interprete.json", import.meta.url), "utf8"));

for (const c of casos.palabras) {
  test(`sílabas · ${c.palabra}`, () => assert.deepEqual(silabas(c.palabra), c.silabas));
}
for (const c of casos.guiones) {
  test(`guiones · «${c.texto}»`, () => assert.equal(conGuiones(c.texto, "-"), c.resultado));
}
test("el guion por defecto es invisible (U+00AD) y no cambia el texto visible", () => {
  const t = conGuiones("Computación Gráfica");
  assert.ok(t.includes(GUION_SUAVE));
  assert.equal(t.replaceAll(GUION_SUAVE, ""), "Computación Gráfica");
});
