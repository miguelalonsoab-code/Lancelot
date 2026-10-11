/**
 * Notificaciones push al celular, sin librerías: solo WebCrypto (viene en Cloudflare y en Node).
 *
 * Cómo llega una notificación a tu Android:
 *   servidor ──(mensaje cifrado)──► servicio de Google (FCM) ──► Chrome del celular ──► sw.js la muestra
 *
 * Dos estándares hacen que sea seguro:
 *   - VAPID (RFC 8292): el servidor firma cada envío con su clave privada. Google comprueba que
 *     la firma corresponde a la clave pública con la que se suscribió el celular: nadie más puede
 *     mandarte notificaciones a nombre de Lancelot.
 *   - Cifrado aes128gcm (RFC 8291): el texto viaja cifrado con claves que solo tiene tu celular.
 *     Google transporta el mensaje pero no puede leer "Pagar la luz".
 */

const texto = new TextEncoder();

export function b64url(bytes) {
  let s = "";
  for (const b of new Uint8Array(bytes)) s += String.fromCharCode(b);
  return btoa(s).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

export function desdeB64url(cadena) {
  const s = atob(cadena.replace(/-/g, "+").replace(/_/g, "/") + "===".slice((cadena.length + 3) % 4));
  return Uint8Array.from(s, (c) => c.charCodeAt(0));
}

function unir(...partes) {
  const total = new Uint8Array(partes.reduce((n, p) => n + p.length, 0));
  let i = 0;
  for (const p of partes) { total.set(p, i); i += p.length; }
  return total;
}

/** HKDF-SHA256: deriva 'largo' bytes de una clave a partir de otra (paso estándar del cifrado). */
async function hkdf(sal, material, info, largo) {
  const clave = await crypto.subtle.importKey("raw", material, "HKDF", false, ["deriveBits"]);
  return new Uint8Array(await crypto.subtle.deriveBits({ name: "HKDF", hash: "SHA-256", salt: sal, info }, clave, largo * 8));
}

/**
 * Cifra el mensaje para UN celular (RFC 8291). Devuelve el cuerpo listo para enviar.
 * p256dh y auth vienen de la suscripción del celular.
 */
export async function cifrar(mensaje, p256dh, auth) {
  const publicaCelular = desdeB64url(p256dh);
  const secretoAuth = desdeB64url(auth);

  // Par de claves de usar y tirar: uno nuevo por mensaje
  const efimeras = await crypto.subtle.generateKey({ name: "ECDH", namedCurve: "P-256" }, true, ["deriveBits"]);
  const publicaServidor = new Uint8Array(await crypto.subtle.exportKey("raw", efimeras.publicKey));
  const claveCelular = await crypto.subtle.importKey("raw", publicaCelular, { name: "ECDH", namedCurve: "P-256" }, false, []);
  const compartido = new Uint8Array(await crypto.subtle.deriveBits({ name: "ECDH", public: claveCelular }, efimeras.privateKey, 256));

  const ikm = await hkdf(secretoAuth, compartido,
    unir(texto.encode("WebPush: info\0"), publicaCelular, publicaServidor), 32);
  const sal = crypto.getRandomValues(new Uint8Array(16));
  const cek = await hkdf(sal, ikm, texto.encode("Content-Encoding: aes128gcm\0"), 16);
  const nonce = await hkdf(sal, ikm, texto.encode("Content-Encoding: nonce\0"), 12);

  const claveAes = await crypto.subtle.importKey("raw", cek, "AES-GCM", false, ["encrypt"]);
  const plano = unir(texto.encode(mensaje), new Uint8Array([2]));      // 2 = "último bloque"
  const cifrado = new Uint8Array(await crypto.subtle.encrypt({ name: "AES-GCM", iv: nonce }, claveAes, plano));

  const tamanoBloque = new Uint8Array(4);
  new DataView(tamanoBloque.buffer).setUint32(0, 4096);
  return unir(sal, tamanoBloque, new Uint8Array([publicaServidor.length]), publicaServidor, cifrado);
}

/** Firma VAPID (un JWT ES256) para el servicio de notificaciones de 'endpoint'. */
export async function firmaVapid(endpoint, vapid) {
  const publica = desdeB64url(vapid.publica);                           // 65 bytes: 0x04 || x || y
  const jwk = { kty: "EC", crv: "P-256", d: vapid.privada,
                x: b64url(publica.slice(1, 33)), y: b64url(publica.slice(33, 65)) };
  const clave = await crypto.subtle.importKey("jwk", jwk, { name: "ECDSA", namedCurve: "P-256" }, false, ["sign"]);
  const cabecera = b64url(texto.encode(JSON.stringify({ typ: "JWT", alg: "ES256" })));
  const datos = b64url(texto.encode(JSON.stringify({
    aud: new URL(endpoint).origin,
    exp: Math.floor(Date.now() / 1000) + 12 * 3600,
    sub: vapid.contacto,
  })));
  const firma = await crypto.subtle.sign({ name: "ECDSA", hash: "SHA-256" }, clave, texto.encode(`${cabecera}.${datos}`));
  return `vapid t=${cabecera}.${datos}.${b64url(firma)}, k=${vapid.publica}`;
}

/**
 * Envía 'datos' (un objeto) a una suscripción. Devuelve el código HTTP del servicio:
 * 201 = entregado al servicio · 404/410 = el celular ya no existe o desactivó las notificaciones.
 */
export async function enviar(suscripcion, datos, vapid, firmas = new Map(), horasDeVida = 24) {
  const cuerpo = await cifrar(JSON.stringify(datos), suscripcion.p256dh, suscripcion.auth);
  const origen = new URL(suscripcion.endpoint).origin;            // una firma por servicio sirve 12 h
  if (!firmas.has(origen)) firmas.set(origen, await firmaVapid(suscripcion.endpoint, vapid));
  const r = await fetch(suscripcion.endpoint, {
    method: "POST",
    headers: {
      Authorization: firmas.get(origen),
      "Content-Encoding": "aes128gcm",
      "Content-Type": "application/octet-stream",
      TTL: String(horasDeVida * 3600),          // si el celular está apagado, Google lo guarda hasta 1 día
      Urgency: "high",                           // que no espere a que el celular "despierte" solo
    },
    body: cuerpo,
  });
  return r.status;
}
