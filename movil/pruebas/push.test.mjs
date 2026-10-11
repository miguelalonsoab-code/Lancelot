// El cifrado y la firma de las notificaciones, comprobados con herramientas independientes:
// http_ece (la librería de referencia del cifrado Web Push) y el módulo crypto de Node.
import { test } from "node:test";
import assert from "node:assert/strict";
import { createECDH, createPublicKey, randomBytes, verify } from "node:crypto";
import ece from "http_ece";
import { b64url, cifrar, desdeB64url, firmaVapid } from "../src/push.js";

/** Un "celular" de mentira: sus claves de suscripción, como las crea Chrome. */
function celularFalso() {
  const ecdh = createECDH("prime256v1");
  ecdh.generateKeys();
  const auth = randomBytes(16);
  return { ecdh, auth, p256dh: b64url(ecdh.getPublicKey()), authB64: b64url(auth) };
}

async function clavesVapid() {
  const par = await crypto.subtle.generateKey({ name: "ECDSA", namedCurve: "P-256" }, true, ["sign"]);
  const jwk = await crypto.subtle.exportKey("jwk", par.privateKey);
  const publica = new Uint8Array(await crypto.subtle.exportKey("raw", par.publicKey));
  return { publica: b64url(publica), privada: jwk.d, contacto: "https://github.com/miguelalonsoab-code/Lancelot" };
}

test("el celular puede descifrar el mensaje (y solo él)", async () => {
  const cel = celularFalso();
  const mensaje = JSON.stringify({ titulo: "Pagar la luz ⚡", hora: "20:00" });
  const cuerpo = await cifrar(mensaje, cel.p256dh, cel.authB64);
  const plano = ece.decrypt(Buffer.from(cuerpo), { version: "aes128gcm", privateKey: cel.ecdh, authSecret: cel.auth });
  assert.equal(plano.toString("utf8"), mensaje);

  const otro = celularFalso();                                         // otro celular no puede leerlo
  assert.throws(() => ece.decrypt(Buffer.from(cuerpo), { version: "aes128gcm", privateKey: otro.ecdh, authSecret: otro.auth }));
});

test("cada mensaje se cifra distinto (claves de un solo uso)", async () => {
  const cel = celularFalso();
  const a = await cifrar("hola", cel.p256dh, cel.authB64);
  const b = await cifrar("hola", cel.p256dh, cel.authB64);
  assert.notDeepEqual(a, b);
});

test("la firma VAPID es un JWT ES256 válido para el servicio correcto", async () => {
  const vapid = await clavesVapid();
  const cabecera = await firmaVapid("https://fcm.googleapis.com/fcm/send/abc123", vapid);
  const [, jwt, k] = /^vapid t=([^,]+), k=(.+)$/.exec(cabecera);
  assert.equal(k, vapid.publica);
  const [h, p, firma] = jwt.split(".");
  const datos = JSON.parse(Buffer.from(desdeB64url(p)).toString());
  assert.equal(datos.aud, "https://fcm.googleapis.com");
  assert.ok(datos.exp > Date.now() / 1000 && datos.exp <= Date.now() / 1000 + 24 * 3600);
  const publica = desdeB64url(vapid.publica);
  const clave = createPublicKey({ key: { kty: "EC", crv: "P-256", x: b64url(publica.slice(1, 33)), y: b64url(publica.slice(33)) }, format: "jwk" });
  assert.ok(verify("sha256", Buffer.from(`${h}.${p}`), { key: clave, dsaEncoding: "ieee-p1363" }, Buffer.from(desdeB64url(firma))));
});
