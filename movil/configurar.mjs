/**
 * Instala (o actualiza) Lancelot en tu cuenta de Cloudflare. Desde la carpeta movil:
 *
 *     npm install            <- solo la primera vez
 *     npm run configurar
 *
 * Qué hace, en orden (si algo ya está hecho, lo salta):
 *   1. Inicia sesión en Cloudflare (se abre el navegador la primera vez).
 *   2. Crea la base de datos "lancelot" (D1) y anota su id en wrangler.jsonc.
 *   3. Crea las tablas (migraciones).
 *   4. Sube el servidor y la app del celular.
 *   5. Genera la CLAVE y las claves de notificación, y las guarda como secretos en Cloudflare.
 *   6. Muestra un código QR: lo escaneas con el celular y la app se abre ya conectada.
 *
 * La dirección y la clave quedan en movil/.lancelot-local.json (NO se sube a GitHub).
 *
 *     npm run configurar -- --nueva-clave     <- cambia la clave (si perdiste el celular, por ejemplo)
 *     npm run configurar -- --nuevas-claves-push  <- regenera las claves de notificación (casi nunca hace falta)
 */
import { spawnSync } from "node:child_process";
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { createInterface } from "node:readline/promises";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const AQUI = dirname(fileURLToPath(import.meta.url));
const CONFIG = join(AQUI, "wrangler.jsonc");
const LOCAL = join(AQUI, ".lancelot-local.json");
const EN_WINDOWS = process.platform === "win32";

const paso = (n, texto) => console.log(`\n=== ${n}. ${texto} ===`);
const b64url = (bytes) => Buffer.from(bytes).toString("base64url");

/**
 * Ejecuta wrangler. 'ver': mostrar la salida en vivo (y permitir que pregunte cosas).
 * 'entrada': texto que se le pasa por la entrada estándar (así los secretos nunca tocan el disco).
 */
function wrangler(args, { ver = false, entrada } = {}) {
  const r = spawnSync("npx", ["wrangler", ...args], {
    cwd: AQUI, shell: EN_WINDOWS, encoding: "utf8", input: entrada,
    stdio: ver ? "inherit" : [entrada === undefined ? "ignore" : "pipe", "pipe", "pipe"],
    env: { ...process.env, WRANGLER_SEND_METRICS: "false" },
  });
  return { ok: r.status === 0, stdout: r.stdout || "", salida: `${r.stdout || ""}${r.stderr || ""}` };
}

function fallar(mensaje, detalle = "") {
  console.error(`\n✗ ${mensaje}`);
  if (detalle) console.error(detalle.trim().split("\n").slice(-15).join("\n"));
  process.exit(1);
}

async function preguntar(texto) {
  const rl = createInterface({ input: process.stdin, output: process.stdout });
  const r = await rl.question(texto);
  rl.close();
  return r.trim();
}

/**
 * Clave fácil de escribir en el celular: 20 caracteres en grupos, sin letras que se confundan
 * (sin l, 1, o, 0, i). Ejemplo: k7m2p-x9qrt-4hvwe-a8sdn  (~99 bits: imposible de adivinar).
 */
function claveFacil() {
  const letras = "abcdefghjkmnpqrstuvwxyz23456789";
  const elegidas = [];
  while (elegidas.length < 20) {
    const [n] = crypto.getRandomValues(new Uint8Array(1));
    if (n < 248) elegidas.push(letras[n % letras.length]);              // 248 = 8 × 31: sin sesgo
  }
  return elegidas.join("").match(/.{5}/g).join("-");
}

function leerLocal() {
  try { return JSON.parse(readFileSync(LOCAL, "utf8")); } catch { return {}; }
}

async function main() {
  if (Number(process.versions.node.split(".")[0]) < 20) fallar("Necesitas Node.js 20 o más nuevo (winget install OpenJS.NodeJS.LTS).");
  if (!existsSync(join(AQUI, "node_modules", "wrangler"))) fallar("Primero ejecuta:  npm install");
  const local = leerLocal();

  // 1 ---------------------------------------------------------------- sesión
  paso(1, "Cuenta de Cloudflare");
  let quien = wrangler(["whoami"]);
  if (!quien.ok || /not authenticated|You are not/i.test(quien.salida)) {
    console.log("Se abrirá el navegador: entra a Cloudflare (con tu GitHub) y pulsa «Allow».");
    wrangler(["login"], { ver: true });
    quien = wrangler(["whoami"]);
    if (!quien.ok || /not authenticated/i.test(quien.salida)) fallar("No se pudo iniciar sesión en Cloudflare.", quien.salida);
  }
  console.log("Sesión iniciada.");

  // 2 ---------------------------------------------------------- base de datos
  paso(2, "Base de datos");
  let config = readFileSync(CONFIG, "utf8");
  if (config.includes('"database_id": "PENDIENTE"')) {
    const uuid = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/;
    const creada = wrangler(["d1", "create", "lancelot"]);
    let id = uuid.exec(creada.salida)?.[0];
    if (!id) {                                           // ¿ya existía de un intento anterior?
      const lista = wrangler(["d1", "list", "--json"]);
      try { id = JSON.parse(lista.stdout.slice(lista.stdout.indexOf("["))).find((d) => d.name === "lancelot")?.uuid; } catch { /* sigue */ }
    }
    if (!id) fallar("No pude crear la base de datos.", creada.salida);
    config = config.replace('"database_id": "PENDIENTE"', `"database_id": "${id}"`);
    writeFileSync(CONFIG, config);
    console.log(`Creada (id ${id}) y anotada en wrangler.jsonc.`);
  } else {
    console.log("Ya existe.");
  }
  const migraciones = wrangler(["d1", "migrations", "apply", "lancelot", "--remote"]);
  if (!migraciones.ok) fallar("No pude crear las tablas.", migraciones.salida);
  console.log(/No migrations to apply/i.test(migraciones.salida) ? "Tablas al día." : "Tablas creadas.");

  // 3 ------------------------------------------------------------- publicar
  paso(3, "Subiendo el servidor y la app");
  const subida = wrangler(["deploy"]);
  if (!subida.ok) {
    if (/subdomain/i.test(subida.salida)) {
      fallar("Tu cuenta aún no tiene un subdominio workers.dev. Entra a dash.cloudflare.com → Workers & Pages, " +
        "elige uno (por ejemplo «miguel») y vuelve a ejecutar: npm run configurar", subida.salida);
    }
    fallar("No se pudo subir.", subida.salida);
  }
  let url = /https:\/\/[\w.-]+\.workers\.dev/.exec(subida.salida)?.[0] || local.url;
  if (!url) url = (await preguntar("Pega la dirección que termina en .workers.dev: ")).replace(/\/$/, "");
  console.log(`Publicado en ${url}`);

  // 4 ------------------------------------------------------------- secretos
  paso(4, "Claves");
  // Las claves de notificación (VAPID) solo se crean UNA vez: si cambiaran, los celulares suscritos dejarían
  // de recibir avisos. La CLAVE se crea si no la tienes guardada aquí (o si pides una nueva).
  const estadoRemoto = await fetch(`${url}/api/estado`).then((r) => r.json()).catch(() => ({}));
  const cambios = {};
  let { clave } = local;
  if (!clave || process.argv.includes("--nueva-clave") || !estadoRemoto.configurado) {
    if (!clave || process.argv.includes("--nueva-clave")) clave = claveFacil();
    cambios.CLAVE = clave;
  }
  if (!estadoRemoto.configurado || process.argv.includes("--nuevas-claves-push")) {
    const par = await crypto.subtle.generateKey({ name: "ECDSA", namedCurve: "P-256" }, true, ["sign"]);
    cambios.VAPID_PRIVADA = (await crypto.subtle.exportKey("jwk", par.privateKey)).d;
    cambios.VAPID_PUBLICA = b64url(await crypto.subtle.exportKey("raw", par.publicKey));
  }
  if (Object.keys(cambios).length) {
    const r = wrangler(["secret", "bulk"], { entrada: JSON.stringify(cambios) });   // por la entrada: sin archivos
    if (!r.ok) fallar("No pude guardar las claves en Cloudflare.", r.salida);
    console.log(`Guardadas en Cloudflare: ${Object.keys(cambios).join(", ")}`);
  } else {
    console.log("Ya estaban guardadas.");
  }
  writeFileSync(LOCAL, JSON.stringify({ url, clave }, null, 2));

  // 5 ------------------------------------------------------------ comprobar
  paso(5, "Comprobando");
  let listo = false;
  for (let i = 0; i < 10 && !listo; i++) {               // los secretos tardan unos segundos en activarse
    const r = await fetch(`${url}/api/tareas`, { headers: { Authorization: `Bearer ${clave}` } }).catch(() => null);
    listo = r?.ok;
    if (!listo) await new Promise((res) => setTimeout(res, 2000));
  }
  if (!listo) fallar(`El servidor no responde bien todavía. Espera un minuto y abre ${url}/api/estado`);
  console.log("Todo funciona.");

  // 6 ------------------------------------------------------------ celular
  paso(6, "Tu celular");
  const enlace = `${url}/#clave=${encodeURIComponent(clave)}`;
  const { default: qr } = await import("qrcode-terminal");
  qr.generate(enlace, { small: true }, (dibujo) => console.log(dibujo));
  console.log("Escanéalo con la cámara del celular y ábrelo en Chrome. O entra a:");
  console.log(`  ${url}`);
  console.log(`  y escribe la clave: ${clave}`);
  console.log("\nLuego, en la app: ⚙ → Activar notificaciones, y menú ⋮ de Chrome → «Agregar a la pantalla principal».");
  if (cambios.CLAVE && local.clave && local.clave !== clave) {
    console.log("\nLa clave cambió: los celulares conectados te la pedirán de nuevo (vuelve a escanear el QR).");
  }
}

main().catch((e) => fallar(e.message, e.stack));
