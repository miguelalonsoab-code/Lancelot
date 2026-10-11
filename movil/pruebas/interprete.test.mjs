// El intérprete JavaScript debe dar lo mismo que el de Python en todos los casos compartidos.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { aTexto, desdeTexto } from "../publico/comun/fechas.js";
import { interpretar } from "../publico/comun/interprete.js";

const { casos } = JSON.parse(readFileSync(new URL("../../tests/casos_interprete.json", import.meta.url), "utf8"));

for (const c of casos) {
  test(`${c.ahora} · ${c.texto}`, () => {
    const r = interpretar(c.texto, desdeTexto(c.ahora));
    assert.deepEqual({ titulo: r.titulo, fecha: r.fecha && aTexto(r.fecha), repeticion: r.repeticion },
      { titulo: c.titulo, fecha: c.fecha, repeticion: c.repeticion });
  });
}
