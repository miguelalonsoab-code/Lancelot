/**
 * Separar palabras en sílabas (v3.24): lo mismo que nucleo/silabas.py de la laptop (ver allí las reglas).
 *
 * El celular lo usa para partir el nombre de los bloques en la vista Semana con guiones suaves (U+00AD):
 * así no depende de que el navegador tenga el diccionario de español para «hyphens: auto».
 * tests/casos_interprete.json (clave "silabas") trae los resultados de Python y pruebas/silabas.test.mjs
 * comprueba que aquí sale exactamente lo mismo.
 */
const VOCALES = new Set("aeiouáéíóúü");
const FUERTES = new Set("aeoáéíóú");
const INSEPARABLES = new Set(["pr", "br", "tr", "dr", "cr", "gr", "fr", "pl", "bl", "cl", "gl", "fl", "kr", "kl"]);
export const GUION_SUAVE = "­";
const MINIMO_A_CADA_LADO = 2;
const PALABRA = /[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+/g;

/** La palabra en unidades [texto original, ¿es vocal?]: «guitarra» -> gu i t a rr a. */
function unidades(palabra) {
  const p = palabra.toLowerCase();
  const salida = [];
  let i = 0;
  while (i < p.length) {
    const dos = p.slice(i, i + 2);
    if (dos === "ch" || dos === "ll" || dos === "rr") {
      salida.push([palabra.slice(i, i + 2), false]);
      i += 2;
    } else if ((dos === "qu" || dos === "gu") && i + 2 < p.length && "eiéí".includes(p[i + 2])) {
      salida.push([palabra.slice(i, i + 2), false]);          // «que», «gui»: la u no suena
      i += 2;
    } else {
      const c = p[i];
      const vocal = VOCALES.has(c) || (c === "y" && i === p.length - 1 && i > 0);
      salida.push([palabra[i], vocal]);
      i += 1;
    }
  }
  return salida;
}

const hiato = (a, b) => {
  a = a.toLowerCase(); b = b.toLowerCase();
  return (FUERTES.has(a) && FUERTES.has(b)) || a === b;
};

/** 'Computación' -> ['Com', 'pu', 'ta', 'ción'] */
export function silabas(palabra) {
  const u = unidades(palabra);
  const cortes = [];
  let i = 0;
  while (i < u.length && !u[i][1]) i += 1;
  while (i < u.length) {
    let j = i + 1;
    while (j < u.length && u[j][1]) {
      if (hiato(u[j - 1][0], u[j][0])) break;
      j += 1;
    }
    if (j < u.length && u[j][1]) { cortes.push(j); i = j; continue; }
    let k = j;
    while (k < u.length && !u[k][1]) k += 1;
    if (k === u.length) break;
    const n = k - j;
    const grupo = (a, b) => INSEPARABLES.has((u[a][0] + u[b][0]).toLowerCase());
    let corte;
    if (n <= 1) corte = j;
    else if (n === 2) corte = grupo(j, j + 1) ? j : j + 1;
    else if (n === 3) corte = grupo(j + 1, j + 2) ? j + 1 : j + 2;
    else corte = j + 2;
    cortes.push(corte);
    i = k;
  }
  const partes = [];
  let desde = 0;
  for (const c of cortes) { partes.push(u.slice(desde, c).map((x) => x[0]).join("")); desde = c; }
  partes.push(u.slice(desde).map((x) => x[0]).join(""));
  return partes.filter(Boolean);
}

/** Posiciones (en letras) donde se puede partir con guion, dejando 2 letras a cada lado. */
export function puntosDeCorte(palabra) {
  const salida = [];
  let pos = 0;
  for (const s of silabas(palabra).slice(0, -1)) {
    pos += s.length;
    if (pos >= MINIMO_A_CADA_LADO && pos <= palabra.length - MINIMO_A_CADA_LADO) salida.push(pos);
  }
  return salida;
}

/** El texto con 'marca' (guion suave, invisible) en cada punto de corte de cada palabra. */
export function conGuiones(texto, marca = GUION_SUAVE) {
  return texto.replace(PALABRA, (palabra) => {
    const cortes = puntosDeCorte(palabra);
    if (!cortes.length) return palabra;
    const trozos = [];
    let desde = 0;
    for (const c of cortes) { trozos.push(palabra.slice(desde, c)); desde = c; }
    trozos.push(palabra.slice(desde));
    return trozos.join(marca);
  });
}
