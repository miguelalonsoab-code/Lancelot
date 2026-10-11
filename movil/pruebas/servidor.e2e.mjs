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
    `CLAVE=${CLAVE}\nVAPID_PUBLICA=${publica}\nVAPID_PRIVADA=${jwk.d}\nPERMITIR_PUSH_LOCAL=1\n`);

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
  assert.deepEqual(estado.datos, { ok: true, version: "1.0", configurado: true });
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
