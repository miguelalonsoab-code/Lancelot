// Horario, días libres y sugerencias (v3.19): el celular debe calcular exactamente lo mismo que la laptop.
// Los resultados de referencia los genera Python: python tests/generar_casos.py (clave "horario").
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { aTexto, desdeTexto } from "../publico/comun/fechas.js";
import {
  choque, deIsoDia, describirDias, describirLibre, duracionMinutos, hablarDuracion, huecos, interpretarExcepcion,
} from "../publico/comun/horario.js";
import { describirPlan, recomendar } from "../publico/comun/recomendador.js";

const { horario } = JSON.parse(readFileSync(new URL("../../tests/casos_interprete.json", import.meta.url), "utf8"));
const f = desdeTexto;
const libresDe = (c, minimo = c.minimo) => huecos(deIsoDia(c.dia), c.bloques, c.despertar, c.dormir, c.ahora ? f(c.ahora) : null,
  minimo, c.excepciones || [], (c.extras || []).map(([a, b, t]) => [f(a), f(b), t]));

for (const c of horario.excepciones) {
  test(`excepción · ${c.texto} (hoy ${c.hoy})`, () => assert.deepEqual(interpretarExcepcion(c.texto, deIsoDia(c.hoy)), c.resultado));
}

horario.huecos.forEach((c, i) => {
  test(`huecos · caso ${i + 1} (${c.dia})`, () => {
    const libres = libresDe(c);
    assert.deepEqual(libres.map(([a, b]) => [aTexto(a), aTexto(b)]), c.libres);
    assert.equal(describirLibre(libres), c.texto);
  });
});

horario.choques.forEach((c, i) => {
  test(`choque · caso ${i + 1}`, () => assert.equal(choque(f(c.inicio), c.minutos, c.bloques, c.excepciones)?.titulo ?? null, c.choca));
});

horario.planes.forEach((c, i) => {
  test(`sugerencias · caso ${i + 1} (${c.dia})`, () => {
    const libres = libresDe({ ...c, excepciones: [], extras: [] }, 30);
    const semana = Object.fromEntries(Object.entries(c.hechas_semana).map(([k, v]) => [Number(k), v]));
    const p = recomendar(deIsoDia(c.dia), libres, c.actividades, semana, new Set(c.hechas_hoy), c.estudio, c.meta,
      { evitar: c.evitar });
    assert.deepEqual(p.sugerencias.map((s) => ({ ...s, inicio: aTexto(s.inicio), fin: aTexto(s.fin) })), c.sugerencias);
    assert.deepEqual(p.sin_lugar, c.sin_lugar);
    assert.deepEqual(describirPlan(p), [c.texto, c.hablado]);
  });
});

test("textos de horario", () => {
  for (const [dias, texto] of Object.entries(horario.textos.dias)) assert.equal(describirDias(dias.split(",").map(Number)), texto);
  for (const [m, texto] of Object.entries(horario.textos.duracion)) assert.equal(duracionMinutos(Number(m)), texto);
  for (const [m, texto] of Object.entries(horario.textos.hablar)) assert.equal(hablarDuracion(Number(m)), texto);
});

// v3.20: actividades escritas en el celular
import { describirActividad, interpretarActividad } from "../publico/comun/perfil.js";

for (const c of horario.actividades) {
  test(`actividad · ${c.texto}`, () => {
    const a = interpretarActividad(c.texto);
    assert.deepEqual(a, c.resultado);
    if (c.descripcion) assert.equal(describirActividad(a), c.descripcion);
  });
}

// v3.21: horario y horas de sueño escritos en el celular
import { categoriaDe, inferirCategoria, interpretarBloque } from "../publico/comun/horario.js";
import { leerHora } from "../publico/comun/perfil.js";

for (const c of horario.bloques) {
  test(`bloque · ${c.texto}`, () => assert.deepEqual(interpretarBloque(c.texto), c.resultado));
}
for (const c of horario.horas) {
  test(`hora · ${c.texto} (${c.para})`, () => assert.equal(leerHora(c.texto, c.para), c.hora));
}

// v3.22: la categoría del bloque (trabajo | clase | otro) sale del título, igual que en Python
for (const c of horario.categorias) {
  test(`categoría · «${c.titulo}»`, () => assert.equal(inferirCategoria(c.titulo), c.categoria));
}
test("categoriaDe: usa la que trae el bloque y, si falta o es rara, la deduce del título", () => {
  assert.equal(categoriaDe({ titulo: "Trabajo en Sanna", categoria: "otro" }), "otro", "la elegida por ti manda");
  assert.equal(categoriaDe({ titulo: "Clase de redes" }), "clase", "un contexto de antes de la v3.22 no la trae");
  assert.equal(categoriaDe({ titulo: "Clase de redes", categoria: "estudio" }), "clase");
  assert.equal(categoriaDe({ titulo: "Inglés", categoria: null }), "otro");
});

// v3.23: cada categoría tiene un icono de línea que existe (los mismos nombres que interfaz/iconos.py)
import { TRAZOS } from "../publico/iconos.js";
import { CATEGORIAS, ICONO_CATEGORIA } from "../publico/comun/horario.js";
test("iconos de las categorías: sin emoji y todos dibujables", () => {
  for (const c of CATEGORIAS) {
    assert.match(ICONO_CATEGORIA[c], /^[a-z]+$/);
    assert.ok(TRAZOS[ICONO_CATEGORIA[c]]?.length, c);
  }
  assert.deepEqual(ICONO_CATEGORIA, horario.iconos, "los mismos nombres que en Python");
});

import { heredarCategoria } from "../publico/comun/horario.js";
test("v3.23: un bloque nuevo con el mismo nombre hereda la categoría (como heredar_categoria en Python)", () => {
  const hay = [{ id: 1, titulo: "Computación Gráfica", categoria: "clase" }, { id: 2, titulo: "Clase de redes" }];
  assert.equal(heredarCategoria({ titulo: "computacion grafica ", categoria: "otro" }, hay).categoria, "clase");
  assert.equal(heredarCategoria({ titulo: "Clase de Redes", categoria: "otro" }, hay).categoria, "clase", "sin categoría: la deduce");
  assert.equal(heredarCategoria({ titulo: "Inglés", categoria: "otro" }, hay).categoria, "otro");
});
