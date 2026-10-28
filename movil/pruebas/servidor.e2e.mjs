// Prueba completa del servidor, en tu PC y sin Cloudflare: levanta "wrangler dev" con una base
// de datos temporal y un "celular" falso que recibe y DESCIFRA las notificaciones.
//
//     npm run test:servidor
import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import { spawn, spawnSync } from "node:child_process";
import { createECDH, randomBytes } from "node:crypto";
import { createServer } from "node:http";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import ece from "http_ece";
import { b64url } from "../src/push.js";
import { aTexto, ahoraEn, sumarMinutos } from "../publico/comun/fechas.js";

const PUERTO = 8790 + Math.floor(Math.random() * 100);
const BASE = `http://127.0.0.1:${PUERTO}`;
const CLAVE = b64url(randomBytes(24));
const carpeta = mkdtempSync(join(tmpdir(), "lancelot-"));
let servidor, receptor, recibidas = [], respuestaPush = 201;

// "Celular" falso: claves de suscripción + un servidor HTTP que hace de servicio push
const ecdh = createECDH("prime256v1"); ecdh.generateKeys();
const auth = randomBytes(16);

const api = async (ruta, { metodo = "GET", cuerpo, clave = CLAVE } = {}) => {
  const r = await fetch(BASE + ruta, { method: metodo, headers: { Authorization: `Bearer ${clave}`,
    "Content-Type": "application/json" }, body: cuerpo && JSON.stringify(cuerpo) });
  return { estado: r.status, datos: await r.json().catch(() => null) };
};

before(async () => {
  const par = await crypto.subtle.generateKey({ name: "ECDSA", namedCurve: "P-256" }, true, ["sign"]);
  const jwk = await crypto.subtle.exportKey("jwk", par.privateKey);
  const publica = b64url(await crypto.subtle.exportKey("raw", par.publicKey));
  writeFileSync(join(carpeta, ".dev.vars"),
    `CLAVE=${CLAVE}\nVAPID_PUBLICA=${publica}\nVAPID_PRIVADA=${jwk.d}\nPERMITIR_PUSH_LOCAL=1\nMINUTOS_MAS_TARDE=0\n`);

  const r = spawnSync("npx", ["wrangler", "d1", "migrations", "apply", "lancelot", "--local", "--persist-to", carpeta],
    { encoding: "utf8", shell: process.platform === "win32", env: { ...process.env, CI: "1" } });
  assert.equal(r.status, 0, r.stderr + r.stdout);

  receptor = createServer((req, res) => {
    const partes = [];
    req.on("data", (p) => partes.push(p));
    req.on("end", () => {
      const plano = ece.decrypt(Buffer.concat(partes), { version: "aes128gcm", privateKey: ecdh, authSecret: auth });
      recibidas.push({ autorizacion: req.headers.authorization, datos: JSON.parse(plano.toString()) });
      res.writeHead(respuestaPush).end();
    });
  }).listen(0, "127.0.0.1");

  servidor = spawn("npx", ["wrangler", "dev", "--local", "--port", String(PUERTO), "--ip", "127.0.0.1",
    "--persist-to", carpeta, "--env-file", join(carpeta, ".dev.vars"), "--test-scheduled",
    "--show-interactive-dev-session=false"], { shell: process.platform === "win32", detached: process.platform !== "win32",
    env: { ...process.env, CI: "1", WRANGLER_SEND_METRICS: "false" } });
  let salida = "";
  servidor.stdout.on("data", (d) => (salida += d));
  servidor.stderr.on("data", (d) => (salida += d));
  for (let i = 0; i < 120; i++) {                          // hasta 60 s para arrancar
    try { if ((await fetch(BASE + "/api/estado")).ok) return; } catch { /* aún no */ }
    await new Promise((r) => setTimeout(r, 500));
  }
  throw new Error("wrangler dev no arrancó:\n" + salida);
});

after(() => {
  // wrangler arranca otros procesos (workerd): hay que cerrar el grupo entero, no solo el primero
  if (servidor && process.platform === "win32") spawnSync("taskkill", ["/pid", String(servidor.pid), "/T", "/F"]);
  else if (servidor) process.kill(-servidor.pid);
  receptor?.close();
  rmSync(carpeta, { recursive: true, force: true });
});

const ahora = () => ahoraEn("America/Lima");

test("sin clave no se puede leer nada", async () => {
  assert.equal((await api("/api/tareas", { clave: "otra" })).estado, 401);
  const estado = await api("/api/estado", { clave: "" });
  assert.deepEqual(estado.datos, { ok: true, version: "1.8", configurado: true });
});

test("agregar con texto libre, preguntar lo que falta y listar", async () => {
  const r = await api("/api/tareas", { metodo: "POST", cuerpo: { texto: "mañana 8pm pagar la luz" } });
  assert.equal(r.estado, 201);
  assert.equal(r.datos.tarea.titulo, "Pagar la luz");
  assert.ok(r.datos.tarea.fecha.endsWith("20:00"));

  const sinFecha = await api("/api/tareas", { metodo: "POST", cuerpo: { texto: "comprar pan" } });
  assert.deepEqual([sinFecha.estado, sinFecha.datos.falta, sinFecha.datos.titulo], [422, "fecha", "Comprar pan"]);

  const pasada = await api("/api/tareas", { metodo: "POST", cuerpo: { titulo: "x", fecha: "2020-01-01 10:00" } });
  assert.equal(pasada.estado, 400);

  const lista = await api("/api/tareas");
  assert.deepEqual(lista.datos.tareas.map((t) => t.titulo), ["Pagar la luz"]);
});

test("el reloj de cada minuto avisa al celular, y el botón ✓ funciona sin la clave", async () => {
  assert.equal((await api("/api/push/suscribir", { metodo: "POST", cuerpo: { dispositivo: "prueba", suscripcion: {
    endpoint: `http://127.0.0.1:${receptor.address().port}/push`,
    keys: { p256dh: b64url(ecdh.getPublicKey()), auth: b64url(auth) } } } })).estado, 200);

  const fecha = aTexto(sumarMinutos(ahora(), 2));
  const { datos } = await api("/api/tareas", { metodo: "POST", cuerpo: { titulo: "Llamar al banco", fecha } });
  // Hacemos que "venza" ya (como si hubieran pasado 2 minutos) y disparamos el cron
  const vencida = aTexto(sumarMinutos(ahora(), -1));
  await api(`/api/tareas/${datos.tarea.id}`, { metodo: "PATCH", cuerpo: { titulo: "Llamar al banco", fecha: vencida } });
  recibidas = [];
  await fetch(BASE + "/__scheduled?cron=*+*+*+*+*");
  for (let i = 0; i < 20 && !recibidas.length; i++) await new Promise((r) => setTimeout(r, 250));

  assert.equal(recibidas.length, 1, "llegó una notificación");
  const n = recibidas[0];
  assert.match(n.autorizacion, /^vapid t=.+, k=.+$/);
  assert.equal(n.datos.titulo, "Llamar al banco");

  // Una segunda pasada del reloj no repite el aviso
  await fetch(BASE + "/__scheduled?cron=*+*+*+*+*");
  await new Promise((r) => setTimeout(r, 500));
  assert.equal(recibidas.length, 1);

  // Firma falsificada: rechazada
  const falsa = await fetch(BASE + "/api/accion", { method: "POST", body: JSON.stringify(
    { id: n.datos.id, fecha: n.datos.fecha, accion: "hecho", firma: "inventada" }) });
  assert.equal(falsa.status, 403);

  // Botón "✓ Hecho" de la notificación
  const ok = await fetch(BASE + "/api/accion", { method: "POST", body: JSON.stringify(
    { id: n.datos.id, fecha: n.datos.fecha, accion: "hecho", firma: n.datos.firmas.hecho }) });
  assert.equal((await ok.json()).mensaje, "✓ Llamar al banco");
  assert.ok(!(await api("/api/tareas")).datos.tareas.some((t) => t.titulo === "Llamar al banco"));
});

test("posponer, reprogramar, repetir, vencidas a mañana y borrar", async () => {
  const crear = async (cuerpo) => (await api("/api/tareas", { metodo: "POST", cuerpo })).datos.tarea;
  const diaria = await crear({ texto: "todos los días a las 7am tomar agua" });
  assert.equal(diaria.repeticion, "diaria");
  const hecha = (await api(`/api/tareas/${diaria.id}/hecho`, { metodo: "POST" })).datos.tarea;
  assert.equal(hecha.estado, "pendiente");                          // se repite: pasa al día siguiente
  assert.ok(hecha.fecha > diaria.fecha);

  const t = await crear({ titulo: "Revisar correo", fecha: aTexto(sumarMinutos(ahora(), 5)) });
  const pospuesta = (await api(`/api/tareas/${t.id}/posponer`, { metodo: "POST", cuerpo: { minutos: 60 } })).datos.tarea;
  assert.equal(pospuesta.fecha, aTexto(sumarMinutos(ahora(), 60)));

  await api(`/api/tareas/${t.id}`, { metodo: "PATCH", cuerpo: { titulo: "Revisar correo", fecha: aTexto(sumarMinutos(ahora(), -30)) } });
  const movidas = await api("/api/vencidas/manana", { metodo: "POST" });
  assert.ok(movidas.datos.movidas >= 1);
  const lista = (await api("/api/tareas")).datos;
  assert.ok(lista.tareas.every((x) => x.fecha > lista.ahora), "ya no quedan vencidas");

  assert.equal((await api(`/api/tareas/${t.id}`, { metodo: "DELETE" })).estado, 200);
  assert.equal((await api(`/api/tareas/${t.id}`, { metodo: "DELETE" })).estado, 404);
  assert.equal((await api(`/api/tareas/no-existe/hecho`, { metodo: "POST" })).estado, 404);
});

const esperar = (ms) => new Promise((r) => setTimeout(r, ms));
const reloj = async () => { await fetch(BASE + "/__scheduled?cron=*+*+*+*+*"); await esperar(600); };
const suscribir = () => api("/api/push/suscribir", { metodo: "POST", cuerpo: { dispositivo: "prueba", suscripcion: {
  endpoint: `http://127.0.0.1:${receptor.address().port}/push`,
  keys: { p256dh: b64url(ecdh.getPublicKey()), auth: b64url(auth) } } } });

test("si Google falla, el aviso se reintenta; si rechaza la suscripción, se borra", async () => {
  await suscribir();
  const { datos } = await api("/api/tareas", { metodo: "POST", cuerpo: { titulo: "Reintento", fecha: aTexto(sumarMinutos(ahora(), 5)) } });
  await api(`/api/tareas/${datos.tarea.id}`, { metodo: "PATCH", cuerpo: { titulo: "Reintento", fecha: aTexto(sumarMinutos(ahora(), -1)) } });
  recibidas = []; respuestaPush = 500;
  await reloj();
  assert.equal(recibidas.length, 1);
  respuestaPush = 201;
  await reloj();                                                     // al minuto siguiente, otra vez
  assert.equal(recibidas.length, 2);
  await reloj();                                                     // ya llegó: no se repite
  assert.equal(recibidas.length, 2);

  respuestaPush = 403;                                               // claves de notificación cambiadas
  await api(`/api/tareas/${datos.tarea.id}/posponer`, { metodo: "POST", cuerpo: { minutos: 1 } });
  await api(`/api/tareas/${datos.tarea.id}`, { metodo: "PATCH", cuerpo: { titulo: "Reintento", fecha: aTexto(sumarMinutos(ahora(), -1)) } });
  await reloj();
  recibidas = []; respuestaPush = 201;
  await reloj();
  assert.equal(recibidas.length, 0, "la suscripción rechazada se borró");
});

test("seguridad: solo servicios push reales, fechas normalizadas, sin completar dos veces", async () => {
  const mala = await api("/api/push/suscribir", { metodo: "POST", cuerpo: { suscripcion: {
    endpoint: "https://sitio-raro.com/x", keys: { p256dh: "a", auth: "b" } } } });
  assert.equal(mala.estado, 400);

  const manana = aTexto(sumarMinutos(ahora(), 1440));
  const conT = await api("/api/tareas", { metodo: "POST", cuerpo: { titulo: "ISO", fecha: manana.replace(" ", "T") } });
  assert.equal(conT.datos.tarea.fecha, manana);                      // se guarda siempre igual
  const basura = await api("/api/tareas", { metodo: "POST", cuerpo: { titulo: "x", fecha: manana + ":59" } });
  assert.equal(basura.estado, 400);

  const diaria = (await api("/api/tareas", { metodo: "POST", cuerpo: { texto: "todos los días a las 6am estirar" } })).datos.tarea;
  const una = await api(`/api/tareas/${diaria.id}/hecho`, { metodo: "POST", cuerpo: { fecha: diaria.fecha } });
  assert.equal(una.estado, 200);
  const dos = await api(`/api/tareas/${diaria.id}/hecho`, { metodo: "POST", cuerpo: { fecha: diaria.fecha } });
  assert.equal(dos.estado, 409, "el doble toque no salta otro día");
});

test("una tarea repetitiva olvidada pasa sola a su próxima vez", async () => {
  const t = (await api("/api/tareas", { metodo: "POST", cuerpo: { texto: "todos los días a las 7am tomar pastilla" } })).datos.tarea;
  const anteayer = aTexto(sumarMinutos(ahora(), -2 * 1440));
  await api(`/api/tareas/${t.id}`, { metodo: "PATCH", cuerpo: { titulo: t.titulo, fecha: anteayer, repeticion: "diaria" } });
  await reloj();                                   // primero se avisa (y queda marcada)…
  await reloj();                                   // …y en la siguiente pasada se adelanta
  const ahoraTxt = aTexto(ahora());
  const tarea = (await api("/api/tareas")).datos.tareas.find((x) => x.id === t.id);
  assert.ok(tarea.fecha > ahoraTxt, `debería estar en el futuro: ${tarea.fecha}`);
});

test("sincronización con la laptop: último cambio gana, borrados y cursor", async () => {
  const sync = (cuerpo) => api("/api/sync", { metodo: "POST", cuerpo });
  const inicio = await sync({ desde: 0, cambios: [] });
  assert.equal(inicio.estado, 200);
  const cursor0 = inicio.datos.cursor;

  // La laptop sube una tarea nueva (con su propio id)
  const id = "laptop-" + Date.now();
  const manana = aTexto(sumarMinutos(ahora(), 1440));
  const base = { id, titulo: "Desde la laptop", fecha: manana, repeticion: null, estado: "pendiente",
                 creada: aTexto(ahora()), completada: null, borrada: false };
  const r1 = await sync({ desde: cursor0, cambios: [{ ...base, actualizada: Date.now() - 5000 }] });
  assert.equal(r1.datos.aceptados, 1);
  assert.ok((await api("/api/tareas")).datos.tareas.some((t) => t.id === id), "el celular la ve");

  // El celular la edita DESPUÉS: un cambio viejo de la laptop no la pisa
  await api(`/api/tareas/${id}`, { metodo: "PATCH", cuerpo: { titulo: "Editada en el celular", fecha: manana } });
  const r2 = await sync({ desde: r1.datos.cursor, cambios: [{ ...base, titulo: "Viejo", actualizada: Date.now() - 4000 }] });
  assert.equal(r2.datos.aceptados, 0);
  const vuelta = r2.datos.cambios.find((t) => t.id === id);
  assert.equal(vuelta.titulo, "Editada en el celular", "la laptop recibe la versión ganadora");

  // La laptop la borra (más reciente): desaparece del celular, pero el borrado viaja
  const r3 = await sync({ desde: r2.datos.cursor, cambios: [{ ...base, borrada: true, actualizada: Date.now() + 1000 }] });
  assert.equal(r3.datos.aceptados, 1);
  assert.ok(!(await api("/api/tareas")).datos.tareas.some((t) => t.id === id));
  assert.equal(r3.datos.cambios.find((t) => t.id === id).borrada, true);

  // Un cambio inválido se rechaza sin frenar a los demás
  const r4 = await sync({ desde: r3.datos.cursor, cambios: [
    { ...base, id: "malo", actualizada: Date.now() },
    { ...base, id: "bueno-" + Date.now(), titulo: "Válida", actualizada: Date.now() }] });
  assert.equal(r4.datos.aceptados, 1);
  assert.deepEqual(r4.datos.rechazados.map((x) => x.id), ["malo"]);
  assert.ok(r4.datos.cursor >= r3.datos.cursor);
});

test("eventos: texto libre, aviso anticipado una sola vez, sincronización y cierre", async () => {
  // Texto libre: el servidor reconoce el evento y sus avisos por defecto
  const examen = (await api("/api/tareas", { metodo: "POST", cuerpo: { texto: "examen de cálculo pasado mañana a las 8am" } }))
    .datos.tarea;
  assert.deepEqual([examen.titulo, examen.tipo, examen.anticipacion], ["Examen de cálculo", "evento", "7,1"]);
  const tarea = (await api("/api/tareas", { metodo: "POST", cuerpo: { texto: "mañana limpiar la sala" } })).datos.tarea;
  assert.deepEqual([tarea.tipo, tarea.anticipacion], ["tarea", null]);

  // Desde la laptop llega un evento creado hace días, en 2 días, que avisa 3 días antes:
  // su aviso anticipado (ayer a las 9:00) quedó pendiente -> sale en la próxima pasada del reloj
  const sync = (cuerpo) => api("/api/sync", { metodo: "POST", cuerpo });
  const id = "evento-" + Date.now();
  const enDosDias = aTexto(sumarMinutos(ahora(), 2 * 1440));
  const evento = { id, titulo: "Aniversario", fecha: enDosDias, repeticion: "anual", estado: "pendiente",
    creada: aTexto(ahora()), completada: null, borrada: false, tipo: "evento", anticipacion: "3",
    actualizada: Date.now() - 10 * 86400000 };
  const r1 = await sync({ desde: 0, cambios: [evento] });
  assert.equal(r1.datos.aceptados, 1);
  const visto = (await api("/api/tareas")).datos.tareas.find((t) => t.id === id);
  assert.deepEqual([visto.tipo, visto.anticipacion, visto.repeticion], ["evento", "3", "anual"]);

  await suscribir();
  recibidas = [];
  await reloj();
  const previos = recibidas.filter((n) => n.datos.tipo === "previo");
  assert.equal(previos.length, 1, "llegó el aviso anticipado");
  assert.equal(previos[0].datos.titulo, "📅 Aniversario");
  assert.match(previos[0].datos.cuerpo, /^Faltan 2 días · /);
  await reloj();
  assert.equal(recibidas.filter((n) => n.datos.tipo === "previo").length, 1, "no se repite");

  // Avisar no es una edición (no cambia 'actualizada'), pero la laptop se entera (v3.11: no lo repite)
  const r2 = await sync({ desde: r1.datos.cursor + 1, cambios: [] });
  const avisado = r2.datos.cambios.find((t) => t.id === id);
  assert.ok(avisado?.aviso_previo);
  assert.equal(avisado.actualizada, evento.actualizada);

  // Una laptop vieja (sin tipo ni anticipación) edita el título: el evento sigue siendo evento
  const { tipo: _t, anticipacion: _a, ...viejo } = evento;
  await sync({ desde: 0, cambios: [{ ...viejo, titulo: "Nuestro aniversario", actualizada: Date.now() }] });
  const editado = (await api("/api/tareas")).datos.tareas.find((t) => t.id === id);
  assert.deepEqual([editado.titulo, editado.tipo, editado.anticipacion], ["Nuestro aniversario", "evento", "3"]);

  // PATCH desde el celular: de evento a tarea
  await api(`/api/tareas/${examen.id}`, { metodo: "PATCH", cuerpo: { titulo: examen.titulo, fecha: examen.fecha,
    tipo: "tarea", anticipacion: null } });
  const cambiado = (await api("/api/tareas")).datos.tareas.find((t) => t.id === examen.id);
  assert.deepEqual([cambiado.tipo, cambiado.anticipacion], ["tarea", null]);
  assert.equal((await api(`/api/tareas/${examen.id}`, { metodo: "PATCH",
    cuerpo: { titulo: "x", fecha: examen.fecha, tipo: "cumple" } })).estado, 400);

  // Un evento de ayer se cierra solo (no queda como "vencida")
  const ayer = { ...evento, id: "ayer-" + Date.now(), titulo: "Concierto", repeticion: null,
    fecha: aTexto(sumarMinutos(ahora(), -1440)), actualizada: Date.now() };
  await sync({ desde: 0, cambios: [ayer] });
  await reloj();
  assert.ok(!(await api("/api/tareas")).datos.tareas.some((t) => t.id === ayer.id));
});

test("v3.11: 'ya avisé' compartido, espera antes de avisar, preferencias y sincronización grande", async () => {
  const sync = (cuerpo) => api("/api/sync", { metodo: "POST", cuerpo });
  await suscribir();
  const enDosDias = aTexto(sumarMinutos(ahora(), 2 * 1440));
  const base = { titulo: "Concierto", fecha: enDosDias, repeticion: null, estado: "pendiente", creada: aTexto(ahora()),
    completada: null, borrada: false, tipo: "evento", anticipacion: "3", actualizada: Date.now() - 10 * 86400000 };

  // La laptop ya mostró el aviso anticipado: el celular no lo repite
  const visto = { ...base, id: "visto-" + Date.now(), aviso_previo: aTexto(ahora()) };
  // Este no lo vio nadie: el celular sí avisa (su hora ya pasó hace más de 5 minutos)
  const nuevo = { ...base, id: "nuevo-" + Date.now(), titulo: "Graduación" };
  const r1 = await sync({ desde: 0, cambios: [visto, nuevo] });
  assert.equal(r1.datos.aceptados, 2);
  recibidas = [];
  await reloj();
  const previos = recibidas.filter((n) => n.datos.tipo === "previo").map((n) => n.datos.titulo);
  assert.ok(previos.includes("📅 Graduación"));
  assert.ok(!previos.includes("📅 Concierto"), "lo que la laptop ya mostró no se repite");

  // …y la laptop se entera de que el celular avisó la Graduación (sin que cuente como edición)
  const r2 = await sync({ desde: r1.datos.cursor + 1, cambios: [] });
  const vuelta = r2.datos.cambios.find((t) => t.id === nuevo.id);
  assert.ok(vuelta?.aviso_previo, "viaja 'ya avisé'");
  assert.equal(vuelta.actualizada, nuevo.actualizada);

  // Preferencias: frases y vocabulario de la laptop (limpios) para el celular y el texto libre
  await sync({ desde: 0, cambios: [], preferencias: { frases: ["Hoy toca brillar", 5, ""],
    vocabulario: { evento: ["taller"], no_evento: ["cita", "<script>"], verbos: [] } } });
  const prefs = (await api("/api/preferencias")).datos;
  assert.deepEqual(prefs, { frases: ["Hoy toca brillar"], vocabulario: { evento: ["taller"], no_evento: ["cita"], verbos: [] } });
  const cita = (await api("/api/tareas", { metodo: "POST", cuerpo: { texto: "cita con el banco mañana a las 10am" } })).datos.tarea;
  assert.equal(cita.tipo, "tarea", "usa lo aprendido en la laptop");

  // Una primera sincronización grande (muchas tareas viejas) ya no se rechaza por tamaño
  const muchas = Array.from({ length: 300 }, (_, i) => ({ ...base, id: `vieja-${Date.now()}-${i}`, tipo: "tarea",
    anticipacion: null, titulo: `Tarea vieja número ${i} con un título bastante largo para pesar`, estado: "hecha" }));
  const grande = await sync({ desde: 0, cambios: muchas });
  assert.equal(grande.estado, 200);
  assert.equal(grande.datos.aceptados, 300);

  // "Pasar las vencidas a mañana" no mueve eventos
  const hoyTemprano = { ...base, id: "ev-hoy-" + Date.now(), titulo: "Examen", fecha: aTexto(sumarMinutos(ahora(), -5)),
    actualizada: Date.now() };
  await sync({ desde: 0, cambios: [hoyTemprano] });
  await api("/api/vencidas/manana", { metodo: "POST" });
  const examen = (await api("/api/tareas")).datos.tareas.find((t) => t.id === hoyTemprano.id);
  assert.equal(examen.fecha, hoyTemprano.fecha);
});

test("v3.14: duración por texto libre, POST, PATCH y sincronización (sin la clave no se pierde)", async () => {
  const sync = (cuerpo) => api("/api/sync", { metodo: "POST", cuerpo });
  const examen = (await api("/api/tareas", { metodo: "POST", cuerpo: { texto: "examen final pasado mañana de 8 a 10" } }))
    .datos.tarea;
  assert.deepEqual([examen.titulo, examen.duracion, examen.fecha.slice(11)], ["Examen final", 120, "08:00"]);
  const cine = (await api("/api/tareas", { metodo: "POST", cuerpo: { titulo: "Cine", fecha: aTexto(sumarMinutos(ahora(), 1440)),
    tipo: "evento", duracion: 150 } })).datos.tarea;
  assert.equal(cine.duracion, 150);
  const rara = await api("/api/tareas", { metodo: "POST", cuerpo: { titulo: "X", fecha: aTexto(sumarMinutos(ahora(), 60)),
    duracion: 99999 } });
  assert.equal(rara.datos.tarea.duracion, null, "fuera de rango: se ignora");

  // PATCH sin 'duracion' la conserva; con null la quita
  await api(`/api/tareas/${cine.id}`, { metodo: "PATCH", cuerpo: { titulo: "Cine con Dagi", fecha: cine.fecha } });
  let visto = (await api("/api/tareas")).datos.tareas.find((t) => t.id === cine.id);
  assert.deepEqual([visto.titulo, visto.duracion], ["Cine con Dagi", 150]);

  // La laptop vieja (sin 'duracion') edita: se conserva. La nueva la cambia.
  const r = await sync({ desde: 0, cambios: [] });
  const remoto = r.datos.cambios.find((t) => t.id === examen.id);
  assert.equal(remoto.duracion, 120);
  const { duracion: _d, ...viejo } = remoto;
  await sync({ desde: 0, cambios: [{ ...viejo, titulo: "Examen final de redes", actualizada: Date.now() }] });
  visto = (await api("/api/tareas")).datos.tareas.find((t) => t.id === examen.id);
  assert.deepEqual([visto.titulo, visto.duracion], ["Examen final de redes", 120]);
  await sync({ desde: 0, cambios: [{ ...remoto, duracion: 90, actualizada: Date.now() + 5 }] });
  visto = (await api("/api/tareas")).datos.tareas.find((t) => t.id === examen.id);
  assert.equal(visto.duracion, 90);

  await api(`/api/tareas/${cine.id}`, { metodo: "PATCH", cuerpo: { titulo: "Cine con Dagi", fecha: cine.fecha, duracion: null } });
  visto = (await api("/api/tareas")).datos.tareas.find((t) => t.id === cine.id);
  assert.equal(visto.duracion, null);
});

test("v3.19: contexto de la laptop y acciones del celular", async () => {
  const sync = (cuerpo) => api("/api/sync", { metodo: "POST", cuerpo });
  let r = await api("/api/contexto");
  assert.equal(r.datos.contexto, null, "sin laptop todavía no hay contexto");

  // El celular pide cosas (validadas)
  const hecha = await api("/api/acciones", { metodo: "POST", cuerpo: { tipo: "hecha", datos: { actividad_id: 1, dia: "2026-10-21" } } });
  assert.equal(hecha.estado, 201);
  await api("/api/acciones", { metodo: "POST", cuerpo: { tipo: "excepcion",
    datos: { desde: "2026-11-01", hasta: "2026-11-01", filtro: "traba", titulo: "No trabajo" } } });
  for (const mala of [{ tipo: "hecha", datos: { actividad_id: "1", dia: "2026-10-21" } },
    { tipo: "excepcion", datos: { desde: "2026-11-02", hasta: "2026-11-01", filtro: "", titulo: "x" } },
    { tipo: "excepcion", datos: { desde: "2026-01-01", hasta: "2026-12-31", filtro: "", titulo: "Año libre" } },
    { tipo: "excepcion", datos: { desde: "2026-11-01", hasta: "2026-11-01", filtro: "<b>", titulo: "x" } },
    { tipo: "sugerida", datos: { tarea: "../../x", actividad_id: null } },
    { tipo: "borrar_todo", datos: {} }]) {
    const e = await api("/api/acciones", { metodo: "POST", cuerpo: mala });
    assert.equal(e.estado, 400, JSON.stringify(mala));
  }

  // La laptop sincroniza: recibe las acciones…
  const r1 = await sync({ desde: 0, cambios: [] });
  assert.deepEqual(r1.datos.acciones.map((a) => a.tipo), ["hecha", "excepcion"]);
  // …las aplica y en la siguiente sube su contexto nuevo y avisa cuáles ya aplicó
  const contexto = { version: 1, perfil: { despertar: "06:00", dormir: "23:00", meta_estudio: 100, minutos_para_arrancar: 30 },
    horario: [{ dias: [0, 1, 2, 3, 4], inicio: "08:30", fin: "17:30", titulo: "Trabajo", traslado: 45 }],
    excepciones: [{ desde: "2026-11-01", hasta: "2026-11-01", filtro: "traba", titulo: "No trabajo" }],
    actividades: [{ id: 1, nombre: "Gimnasio", minutos: 60, veces_semana: 3, momento: "tarde" }],
    hechas: { 1: ["2026-10-21"] }, estudio: {}, evitar: {}, sugeridas: [] };
  const r2 = await sync({ desde: r1.datos.cursor, cambios: [], contexto, acciones_ok: r1.datos.acciones.map((a) => a.id) });
  assert.deepEqual(r2.datos.acciones, []);
  r = await api("/api/contexto");
  assert.deepEqual(r.datos.contexto.horario, contexto.horario);
  assert.deepEqual(r.datos.contexto.hechas, { 1: ["2026-10-21"] });
  assert.deepEqual(r.datos.acciones, []);
  const malo = await sync({ desde: 0, cambios: [], contexto: { version: 2 } });
  assert.equal(malo.estado, 400, "un contexto con otra forma no se guarda");
});

test("v3.20: aviso de hueco libre en el celular (una vez, y no si la laptop ya lo dio)", async (t) => {
  const sync = (cuerpo) => api("/api/sync", { metodo: "POST", cuerpo });
  const now = ahora();
  if (now.getUTCHours() * 60 + now.getUTCMinutes() < 15) return t.skip("justo después de medianoche no hay bloque posible");
  const dos = (n) => String(n).padStart(2, "0");
  const hm = (f) => `${dos(f.getUTCHours())}:${dos(f.getUTCMinutes())}`;
  const fin = sumarMinutos(now, -10);                       // "saliste del trabajo" hace 10 minutos
  const base = { version: 1, perfil: { despertar: "00:00", dormir: "23:59", meta_estudio: 0, minutos_para_arrancar: 0,
    avisar_huecos: true }, horario: [{ dias: [0, 1, 2, 3, 4, 5, 6], inicio: hm(new Date(Math.max(sumarMinutos(fin, -120), Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate())))), fin: hm(fin),
    titulo: "Trabajo", traslado: 0 }], excepciones: [], hechas: {}, estudio: {}, evitar: {}, sugeridas: [],
    actividades: [{ id: 9, nombre: "Caminar", minutos: 30, veces_semana: 7, momento: null }] };
  await sync({ desde: 0, cambios: [], contexto: { ...base, hueco_avisado: aTexto(fin) } });
  await suscribir();
  recibidas = [];
  await reloj();
  assert.equal(recibidas.filter((n) => n.datos.tipo === "hueco").length, 0, "la laptop ya lo avisó: no se repite");

  await sync({ desde: 0, cambios: [], contexto: { ...base, hueco_avisado: null } });
  await reloj();
  const huecos = recibidas.filter((n) => n.datos.tipo === "hueco");
  assert.equal(huecos.length, 1);
  assert.equal(huecos[0].datos.titulo, "💡 Tienes un hueco libre");
  assert.match(huecos[0].datos.cuerpo, /^Hasta las 23:59\. ¿Qué tal Caminar\? \(llevas 0 de 7 esta semana\)$/);
  await reloj();
  assert.equal(recibidas.filter((n) => n.datos.tipo === "hueco").length, 1, "una sola vez por hueco");

  // v3.21: los botones de la notificación (sin la clave: con la firma que trae)
  const n = huecos[0].datos;
  assert.equal(n.que, "9");
  const boton = (accion, extra = {}) => fetch(BASE + "/api/accion", { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ id: n.id, fecha: n.que, accion, firma: n.firmas[accion], nombre: n.nombre, ...extra }) });
  assert.equal((await boton("lo_hago", { fecha: "1" })).status, 403, "la firma no sirve para otra actividad");
  assert.equal((await boton("luego", { firma: n.firmas.lo_hago })).status, 403, "ni para otro botón");
  const hecho = await (await boton("lo_hago")).json();
  assert.equal(hecho.mensaje, "💪 ¡Vamos! Cuento Caminar como hecho hoy.");
  const acciones = (await api("/api/contexto")).datos.acciones;
  assert.deepEqual(acciones.at(-1).datos, { actividad_id: 9, dia: aTexto(now).slice(0, 10) });
  const luego = await (await boton("luego")).json();
  assert.match(luego.mensaje, /^⏰ Te lo vuelvo a proponer desde las \d\d:\d\d/);
  recibidas = [];
  await reloj();                                           // MINUTOS_MAS_TARDE=0 en las pruebas: ya toca
  const otra = recibidas.filter((x) => x.datos.tipo === "hueco");
  assert.equal(otra.length, 1);
  assert.equal(otra[0].datos.titulo, "⏰ Lo dejaste para más tarde");
  assert.match(otra[0].datos.cuerpo, /^¿Ahora sí, Caminar\? Estás libre hasta las 23:59\.$/);
  await reloj();
  assert.equal(recibidas.filter((x) => x.datos.tipo === "hueco").length, 1, "lo pospuesto se repite una sola vez");
  await api("/api/sync", { metodo: "POST", cuerpo: { desde: 0, cambios: [], acciones_ok: acciones.map((a) => a.id) } });

  await sync({ desde: 0, cambios: [], contexto: { ...base, perfil: { ...base.perfil, avisar_huecos: false } } });
});

test("v3.20: acciones para quitar días libres y editar actividades", async () => {
  const pedir = (tipo, datos) => api("/api/acciones", { metodo: "POST", cuerpo: { tipo, datos } });
  assert.equal((await pedir("actividad", { nombre: "Yoga", minutos: 45, veces_semana: 2, momento: "tarde" })).estado, 201);
  assert.equal((await pedir("quitar_actividad", { id: 3 })).estado, 201);
  assert.equal((await pedir("quitar_excepcion", { desde: "2026-11-01", hasta: "2026-11-01", filtro: "traba" })).estado, 201);
  for (const [tipo, datos] of [["actividad", { nombre: "", minutos: 45 }], ["actividad", { nombre: "X", minutos: 0 }],
    ["actividad", { nombre: "X", minutos: 30, veces_semana: 9 }], ["actividad", { nombre: "X", minutos: 30, momento: "madrugada" }],
    ["quitar_actividad", { id: "3" }], ["quitar_excepcion", { desde: "ayer", hasta: "2026-11-01", filtro: "" }]]) {
    assert.equal((await pedir(tipo, datos)).estado, 400, JSON.stringify(datos));
  }
  // v3.21: horario fijo y perfil
  assert.equal((await pedir("bloque", { dias: [2, 2], inicio: "19:30", fin: "22:40", titulo: "Computación Gráfica", traslado: 0 })).estado, 201);
  assert.equal((await pedir("perfil", { dormir: "23:30" })).estado, 201);
  for (const [tipo, datos] of [["bloque", { dias: [7], inicio: "08:00", fin: "09:00", titulo: "X" }],
    ["bloque", { dias: [1], inicio: "10:00", fin: "09:00", titulo: "X" }], ["bloque", { dias: [1], inicio: "8:00", fin: "09:00", titulo: "X" }],
    ["bloque", { dias: [1], inicio: "08:00", fin: "09:00", titulo: "" }], ["quitar_bloque", { id: 0 }], ["perfil", {}],
    ["perfil", { dormir: "25:00" }], ["perfil", { meta_estudio: 5000 }]]) {
    assert.equal((await pedir(tipo, datos)).estado, 400, JSON.stringify(datos));
  }
  const r = await api("/api/sync", { metodo: "POST", cuerpo: { desde: 0, cambios: [] } });
  assert.deepEqual(r.datos.acciones.at(-2).datos, { dias: [2], inicio: "19:30", fin: "22:40", titulo: "Computación Gráfica", traslado: 0 });
  const nuevas = r.datos.acciones.slice(-5, -2);
  assert.deepEqual(nuevas.map((a) => a.tipo), ["actividad", "quitar_actividad", "quitar_excepcion"]);
  assert.deepEqual(nuevas[0].datos, { nombre: "Yoga", minutos: 45, veces_semana: 2, momento: "tarde" });
  await api("/api/sync", { metodo: "POST", cuerpo: { desde: 0, cambios: [], acciones_ok: r.datos.acciones.map((a) => a.id) } });
});

test("v3.22: el bloque del horario trae su categoría (opcional) y solo acepta las tres conocidas", async () => {
  const pedir = (datos) => api("/api/acciones", { metodo: "POST", cuerpo: { tipo: "bloque", datos } });
  const base = { dias: [4], inicio: "18:00", fin: "20:00", traslado: 0 };
  assert.equal((await pedir({ ...base, titulo: "Taller de robótica", categoria: "clase" })).estado, 201);
  assert.equal((await pedir({ ...base, titulo: "Guardia" })).estado, 201, "un celular sin actualizar no manda categoría");
  for (const categoria of ["estudio", "", null, 3, "Trabajo"]) {
    assert.equal((await pedir({ ...base, titulo: "X", categoria })).estado, 400, JSON.stringify(categoria));
  }
  const r = await api("/api/sync", { metodo: "POST", cuerpo: { desde: 0, cambios: [] } });
  const bloques = r.datos.acciones.filter((a) => a.tipo === "bloque").map((a) => a.datos);
  assert.deepEqual(bloques, [
    { dias: [4], inicio: "18:00", fin: "20:00", titulo: "Taller de robótica", traslado: 0, categoria: "clase" },
    { dias: [4], inicio: "18:00", fin: "20:00", titulo: "Guardia", traslado: 0 },   // sin la clave: la laptop la deduce del título
  ]);
  await api("/api/sync", { metodo: "POST", cuerpo: { desde: 0, cambios: [], acciones_ok: r.datos.acciones.map((a) => a.id) } });
});

test("v3.23: cambiar la categoría de un bloque desde el celular", async () => {
  const pedir = (datos) => api("/api/acciones", { metodo: "POST", cuerpo: { tipo: "categoria_bloque", datos } });
  assert.equal((await pedir({ id: 4, categoria: "clase" })).estado, 201);
  for (const datos of [{ id: 0, categoria: "clase" }, { id: "4", categoria: "clase" }, { id: 4, categoria: "estudio" },
    { id: 4 }, { categoria: "otro" }]) {
    assert.equal((await pedir(datos)).estado, 400, JSON.stringify(datos));
  }
  const r = await api("/api/sync", { metodo: "POST", cuerpo: { desde: 0, cambios: [] } });
  assert.deepEqual(r.datos.acciones.filter((a) => a.tipo === "categoria_bloque").map((a) => a.datos), [{ id: 4, categoria: "clase" }]);
  await api("/api/sync", { metodo: "POST", cuerpo: { desde: 0, cambios: [], acciones_ok: r.datos.acciones.map((a) => a.id) } });
});
