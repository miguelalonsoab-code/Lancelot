/**
 * Reglas de tiempo puras: repeticiones y atajos para reprogramar.
 * Traducción de nucleo/planificador.py (mismo comportamiento, mismas pruebas).
 */
import { conHora, crear, diaSemana, esValida, hhmm, soloFecha, sumarDias, sumarMinutos } from "./fechas.js";

/** Próxima ocurrencia de una tarea repetitiva, siempre en el futuro (se salta las perdidas). */
export function siguienteOcurrencia(fecha, repeticion, ahora) {
  if (!repeticion) return null;
  let siguiente = avanzar(fecha, repeticion);
  while (siguiente <= ahora) siguiente = avanzar(siguiente, repeticion);
  return siguiente;
}

function avanzar(f, repeticion) {
  if (repeticion === "diaria") return sumarDias(f, 1);
  if (repeticion === "semanal") return sumarDias(f, 7);
  if (repeticion === "laborables") {
    let d = sumarDias(f, 1);
    while (diaSemana(d) >= 5) d = sumarDias(d, 1);
    return d;
  }
  if (repeticion === "mensual") {
    let anio = f.getUTCFullYear(), mes = f.getUTCMonth() + 2;
    if (mes === 13) { anio += 1; mes = 1; }
    let dia = f.getUTCDate();
    while (!esValida(anio, mes, dia)) dia -= 1;          // 31 -> último día del mes siguiente
    return crear(anio, mes, dia, f.getUTCHours(), f.getUTCMinutes());
  }
  throw new Error(`Repetición desconocida: ${repeticion}`);
}

/** Misma hora, pero mañana ("pasar todas las vencidas a mañana"). */
export const aManana = (fecha, ahora) => conHora(sumarDias(soloFecha(ahora), 1), fecha.getUTCHours(), fecha.getUTCMinutes());

/** Atajos para mover una vencida: [[etiqueta, fecha], ...] sin repetidos. */
export function opcionesReprogramar(fecha, ahora, horaManana = [9, 0]) {
  const hoy = soloFecha(ahora), manana = sumarDias(hoy, 1);
  const h = fecha.getUTCHours(), mi = fecha.getUTCMinutes();
  const candidatas = [["En 1 hora", sumarMinutos(ahora, 60)]];
  const mismaHoy = conHora(hoy, h, mi);
  if (soloFecha(fecha) < hoy && mismaHoy > sumarMinutos(ahora, 30)) {
    candidatas.push([`Hoy a las ${hhmm(mismaHoy)}`, mismaHoy]);
  }
  const noche = conHora(hoy, 20, 0);
  if (noche > sumarMinutos(ahora, 60)) candidatas.push(["Esta noche (20:00)", noche]);
  const mismaManana = conHora(manana, h, mi);
  candidatas.push([`Mañana a las ${hhmm(mismaManana)}`, mismaManana]);
  const fija = conHora(manana, ...horaManana);
  candidatas.push([`Mañana a las ${hhmm(fija)}`, fija]);
  const vistas = new Set();
  return candidatas.filter(([, f]) => !vistas.has(+f) && vistas.add(+f));
}
