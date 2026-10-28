/**
 * Iconos de línea (v3.23): los mismos de la laptop (interfaz/iconos.py). Trazo de 1.5 px y currentColor,
 * así toman el color del texto que los rodea. Sin emoji, como pide el sistema de diseño de Lancelot.
 *
 * Formas de Lucide (https://lucide.dev), licencia ISC: «Copyright (c) for portions of Lucide are held by Cole
 * Bemis 2013-2022 as part of Feather (MIT). All other copyright (c) for Lucide are held by Lucide Contributors
 * 2022.» Se permite usar, copiar y modificar con este aviso.
 *
 * Se arman con createElementNS (un <svg> hecho con createElement no se dibuja) y sin innerHTML.
 */
const NS = "http://www.w3.org/2000/svg";

/** Cada icono: lista de [etiqueta, atributos] dentro de un viewBox de 24×24. */
export const TRAZOS = {
  maletin: [["path", { d: "M16 20V4a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16" }], ["rect", { width: 20, height: 14, x: 2, y: 6, rx: 2 }]],
  birrete: [
    ["path", { d: "M21.42 10.922a1 1 0 0 0-.019-1.838L12.83 5.18a2 2 0 0 0-1.66 0L2.6 9.08a1 1 0 0 0 0 1.832l8.57 3.908a2 2 0 0 0 1.66 0z" }],
    ["path", { d: "M22 10v6" }], ["path", { d: "M6 12.5V16a6 3 0 0 0 12 0v-3.5" }]],
  etiqueta: [
    ["path", { d: "M12.586 2.586A2 2 0 0 0 11.172 2H4a2 2 0 0 0-2 2v7.172a2 2 0 0 0 .586 1.414l8.704 8.704a2.426 2.426 0 0 0 3.42 0l6.58-6.58a2.426 2.426 0 0 0 0-3.42z" }],
    ["circle", { cx: 7.5, cy: 7.5, r: 0.5, fill: "currentColor" }]],

  // v3.24: los que reemplazan a los emoji de la interfaz
  reloj: [["circle", {"cx": "12", "cy": "12", "r": "10"}], ["path", {"d": "M12 6v6l4 2"}]],
  calendario: [["path", {"d": "M8 2v4"}], ["path", {"d": "M16 2v4"}], ["rect", {"width": "18", "height": "18", "x": "3", "y": "4", "rx": "2"}], ["path", {"d": "M3 10h18"}]],
  bombilla: [["path", {"d": "M15 14c.2-1 .7-1.7 1.5-2.5 1-.9 1.5-2.2 1.5-3.5A6 6 0 0 0 6 8c0 1 .2 2.2 1.5 3.5.7.7 1.3 1.5 1.5 2.5"}], ["path", {"d": "M9 18h6"}], ["path", {"d": "M10 22h4"}]],
  check: [["path", {"d": "M20 6 9 17l-5-5"}]],
  x: [["path", {"d": "M18 6 6 18"}], ["path", {"d": "m6 6 12 12"}]],
  lapiz: [["path", {"d": "M21.174 6.812a1 1 0 0 0-3.986-3.987L3.842 16.174a2 2 0 0 0-.5.83l-1.321 4.352a.5.5 0 0 0 .623.622l4.353-1.32a2 2 0 0 0 .83-.497z"}], ["path", {"d": "m15 5 4 4"}]],
  libro: [["path", {"d": "M12 7v14"}], ["path", {"d": "M3 18a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h5a4 4 0 0 1 4 4 4 4 0 0 1 4-4h5a1 1 0 0 1 1 1v13a1 1 0 0 1-1 1h-6a3 3 0 0 0-3 3 3 3 0 0 0-3-3z"}]],
  campana_off: [["path", {"d": "M10.268 21a2 2 0 0 0 3.464 0"}], ["path", {"d": "M17 17H4a1 1 0 0 1-.74-1.673C4.59 13.956 6 12.499 6 8a6 6 0 0 1 .258-1.742"}], ["path", {"d": "m2 2 20 20"}], ["path", {"d": "M8.668 3.01A6 6 0 0 1 18 8c0 2.687.77 4.653 1.707 6.05"}]],
  oreja: [["path", {"d": "M6 8.5a6.5 6.5 0 1 1 13 0c0 6-6 6-6 10a3.5 3.5 0 1 1-7 0"}], ["path", {"d": "M15 8.5a2.5 2.5 0 0 0-5 0v1a2 2 0 1 1 0 4"}]],
  microfono: [["path", {"d": "M12 19v3"}], ["path", {"d": "M19 10v2a7 7 0 0 1-14 0v-2"}], ["rect", {"x": "9", "y": "2", "width": "6", "height": "13", "rx": "3"}]],
  pausa: [["rect", {"x": "14", "y": "4", "width": "4", "height": "16", "rx": "1"}], ["rect", {"x": "6", "y": "4", "width": "4", "height": "16", "rx": "1"}]],
  play: [["polygon", {"points": "6 3 20 12 6 21 6 3"}]],
  repetir: [["path", {"d": "m17 2 4 4-4 4"}], ["path", {"d": "M3 11v-1a4 4 0 0 1 4-4h14"}], ["path", {"d": "m7 22-4-4 4-4"}], ["path", {"d": "M21 13v1a4 4 0 0 1-4 4H3"}]],
  alerta: [["path", {"d": "m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3"}], ["path", {"d": "M12 9v4"}], ["path", {"d": "M12 17h.01"}]],
};

/** <svg> del icono 'nombre' de 'lado' px, decorativo (aria-hidden): siempre va junto a una palabra. */
export function icono(nombre, lado = 16) {
  const svg = document.createElementNS(NS, "svg");
  const attrs = { width: lado, height: lado, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", "stroke-width": 1.5,
    "stroke-linecap": "round", "stroke-linejoin": "round", "aria-hidden": "true", class: "icono" };
  for (const [k, v] of Object.entries(attrs)) svg.setAttribute(k, String(v));
  for (const [etiqueta, a] of TRAZOS[nombre] || []) {
    const n = document.createElementNS(NS, etiqueta);
    for (const [k, v] of Object.entries(a)) n.setAttribute(k, String(v));
    svg.append(n);
  }
  return svg;
}
