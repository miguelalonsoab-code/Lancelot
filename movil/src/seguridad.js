/**
 * Quién puede usar el servidor.
 *
 *  - La app del celular (y más adelante la laptop) mandan la CLAVE en cada pedido:
 *      Authorization: Bearer <clave>
 *    La clave es un secreto de Cloudflare (no está en el código ni en GitHub).
 *
 *  - Los botones de una notificación ("✓ Hecho") no pueden llevar la clave, así que cada
 *    notificación trae una FIRMA que solo sirve para esa tarea, esa fecha y esa acción.
 *    Aunque alguien la viera, no podría hacer nada más con ella.
 */
import { b64url } from "./push.js";

const texto = new TextEncoder();

/** Compara dos textos sin que el tiempo de respuesta revele cuántas letras coinciden. */
async function igualesSeguro(a, b) {
  const [ha, hb] = await Promise.all([a, b].map((s) => crypto.subtle.digest("SHA-256", texto.encode(s))));
  const x = new Uint8Array(ha), y = new Uint8Array(hb);
  let diferencia = 0;
  for (let i = 0; i < x.length; i++) diferencia |= x[i] ^ y[i];
  return diferencia === 0;
}

export async function autorizado(request, env) {
  const m = /^Bearer (.+)$/.exec(request.headers.get("Authorization") || "");
  return Boolean(m && env.CLAVE && (await igualesSeguro(m[1], env.CLAVE)));
}

async function hmac(env, mensaje) {
  const clave = await crypto.subtle.importKey("raw", texto.encode(env.CLAVE), { name: "HMAC", hash: "SHA-256" },
    false, ["sign"]);
  return b64url(await crypto.subtle.sign("HMAC", clave, texto.encode(mensaje)));
}

/** Firma para el botón de una notificación. */
export const firmarAccion = (env, id, fecha, accion) => hmac(env, `${id}|${fecha}|${accion}`);

export async function accionValida(env, id, fecha, accion, firma) {
  return typeof firma === "string" && (await igualesSeguro(firma, await firmarAccion(env, id, fecha, accion)));
}
