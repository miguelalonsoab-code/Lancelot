/**
 * Fechas "de reloj de pared", igual que en la laptop.
 *
 * Las tareas se guardan como texto 'AAAA-MM-DD HH:MM' en hora de Lima, sin zona horaria
 * (exactamente como en tareas.db de la laptop). Para calcular con ellas se usa un Date
 * cuyos campos UTC contienen esa hora de pared: así sumar días u horas nunca se ve
 * afectado por la zona horaria del servidor (que vive en UTC) ni del celular.
 *
 * Este archivo lo usan el servidor (Cloudflare) y la app del celular.
 */

export const DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"];
export const DIAS_CORTOS = ["lun", "mar", "mié", "jue", "vie", "sáb", "dom"];
export const MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
  "septiembre", "octubre", "noviembre", "diciembre"];

const dos = (n) => String(n).padStart(2, "0");

/** Fecha de pared. mes: 1-12. */
export function crear(anio, mes, dia, hora = 0, minuto = 0) {
  return new Date(Date.UTC(anio, mes - 1, dia, hora, minuto));
}

/** ¿Existe esa fecha? (31/02 no existe; Date la convertiría en 3 de marzo sin avisar) */
export function esValida(anio, mes, dia) {
  const f = crear(anio, mes, dia);
  return f.getUTCFullYear() === anio && f.getUTCMonth() === mes - 1 && f.getUTCDate() === dia;
}

export function desdeTexto(texto) {
  const m = /^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})$/.exec(texto || "");
  if (!m) return null;
  const [a, me, d, h, mi] = m.slice(1).map(Number);
  if (!esValida(a, me, d) || h > 23 || mi > 59) return null;
  return crear(a, me, d, h, mi);
}

export function aTexto(f) {
  return `${f.getUTCFullYear()}-${dos(f.getUTCMonth() + 1)}-${dos(f.getUTCDate())} ` +
    `${dos(f.getUTCHours())}:${dos(f.getUTCMinutes())}`;
}

export const hhmm = (f) => `${dos(f.getUTCHours())}:${dos(f.getUTCMinutes())}`;
export const ddmm = (f) => `${dos(f.getUTCDate())}/${dos(f.getUTCMonth() + 1)}`;

export const sumarMinutos = (f, n) => new Date(f.getTime() + n * 60000);
export const sumarDias = (f, n) => sumarMinutos(f, n * 1440);

/** Lunes = 0 … domingo = 6 (como weekday() de Python). */
export const diaSemana = (f) => (f.getUTCDay() + 6) % 7;

/** La misma fecha a las 00:00. */
export const soloFecha = (f) => crear(f.getUTCFullYear(), f.getUTCMonth() + 1, f.getUTCDate());

/** Días de calendario entre dos fechas (sin importar la hora). */
export const diasEntre = (desde, hasta) => Math.round((soloFecha(hasta) - soloFecha(desde)) / 86400000);

export const conHora = (f, h, mi) => crear(f.getUTCFullYear(), f.getUTCMonth() + 1, f.getUTCDate(), h, mi);

/** Hora de pared actual en una zona (p. ej. "America/Lima"), redondeada al minuto. */
export function ahoraEn(zona = "America/Lima", instante = new Date()) {
  const partes = Object.fromEntries(
    new Intl.DateTimeFormat("en-US", {
      timeZone: zona, hourCycle: "h23", year: "numeric", month: "2-digit", day: "2-digit",
      hour: "2-digit", minute: "2-digit",
    }).formatToParts(instante).map((p) => [p.type, p.value]));
  return crear(+partes.year, +partes.month, +partes.day, +partes.hour, +partes.minute);
}

/** 'hoy 20:00', 'mañana 09:00', 'vie 10/10 15:00' (igual que describir_fecha de la laptop). */
export function describirFecha(f, ahora) {
  if (f < ahora) return `atrasada · ${ddmm(f)} ${hhmm(f)}`;
  const dias = diasEntre(ahora, f);
  if (dias === 0) return `hoy ${hhmm(f)}`;
  if (dias === 1) return `mañana ${hhmm(f)}`;
  return `${DIAS_CORTOS[diaSemana(f)]} ${ddmm(f)} ${hhmm(f)}`;
}

/** 'venció hace 12 min', 'venció ayer 20:00', 'venció hace 3 días (mié 07/10)'. */
export function describirAtraso(f, ahora) {
  const minutos = Math.floor((ahora - f) / 60000);
  const dias = diasEntre(f, ahora);
  if (minutos < 60) return `venció hace ${Math.max(minutos, 1)} min`;
  if (dias === 0) return `venció hoy ${hhmm(f)}`;
  if (dias === 1) return `venció ayer ${hhmm(f)}`;
  return `venció hace ${dias} días (${DIAS_CORTOS[diaSemana(f)]} ${ddmm(f)})`;
}

/** 20:40 -> "a las 8 y 40 de la noche" (para la voz). */
export function horaHablada(f, conArticulo = true) {
  const h = f.getUTCHours(), m = f.getUTCMinutes();
  const momento = h === 0 ? "de la noche" : h < 12 ? "de la mañana" : h === 12 ? "del mediodía"
    : h < 19 ? "de la tarde" : "de la noche";
  const h12 = h % 12 || 12;
  const minutos = m === 0 ? "" : m === 15 ? " y cuarto" : m === 30 ? " y media" : ` y ${m}`;
  const articulo = conArticulo ? (h12 === 1 ? "a la " : "a las ") : (h12 === 1 ? "la " : "las ");
  return `${articulo}${h12}${minutos} ${momento}`;
}
