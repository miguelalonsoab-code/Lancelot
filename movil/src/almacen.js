/**
 * Las tareas en D1. Mismas operaciones que nucleo/almacen.py de la laptop
 * (agregar, completar, posponer, editar, eliminar…), así se pueden sincronizar en la etapa 3.
 *
 * Las fechas se guardan como texto 'AAAA-MM-DD HH:MM' en hora de Lima:
 * compararlas como texto ordena igual que compararlas como fechas.
 */
import { aTexto, desdeTexto, sumarMinutos } from "../publico/comun/fechas.js";
import { siguienteOcurrencia } from "../publico/comun/planificador.js";

export const REPETICIONES_VALIDAS = new Set(["diaria", "laborables", "semanal", "mensual"]);

export class Almacen {
  constructor(db) {
    this.db = db;
  }

  async pendientes() {
    const { results } = await this.db.prepare(
      "SELECT * FROM tareas WHERE estado = 'pendiente' AND borrada = 0 ORDER BY fecha").all();
    return results.map(aTarea);
  }

  async obtener(id) {
    const fila = await this.db.prepare("SELECT * FROM tareas WHERE id = ? AND borrada = 0").bind(id).first();
    return fila ? aTarea(fila) : null;
  }

  async agregar(titulo, fecha, repeticion, ahora) {
    const id = crypto.randomUUID();
    await this.db.prepare(
      "INSERT INTO tareas (id, titulo, fecha, repeticion, creada, actualizada) VALUES (?, ?, ?, ?, ?, ?)")
      .bind(id, titulo, fecha, repeticion, aTexto(ahora), Date.now()).run();
    return this.obtener(id);
  }

  /**
   * Si se repite, pasa a la siguiente ocurrencia; si no, queda 'hecha' (sirve de historial).
   * fechaEsperada: la ocurrencia que el usuario vio. Si ya cambió (doble toque, o la completó desde
   * la notificación), no se hace nada: así una tarea diaria no salta dos días.
   * Devuelve la tarea, null si no existe, o { yaResuelta: true }.
   */
  async completar(id, ahora, fechaEsperada = null) {
    const t = await this.obtener(id);
    if (!t) return null;
    if (t.estado !== "pendiente" || (fechaEsperada && t.fecha !== fechaEsperada)) return { yaResuelta: true, tarea: t };
    const siguiente = siguienteOcurrencia(desdeTexto(t.fecha), t.repeticion, ahora);
    const cambio = siguiente
      ? await this.cambiarSi(id, t.fecha, "fecha = ?, avisada = 0", aTexto(siguiente))
      : await this.cambiarSi(id, t.fecha, "estado = 'hecha', completada = ?", aTexto(ahora));
    return cambio ? this.obtener(id) : { yaResuelta: true, tarea: t };
  }

  posponer(id, minutos, ahora) {
    return this.reprogramar(id, aTexto(sumarMinutos(ahora, minutos)));
  }

  reprogramar(id, fecha) {
    return this.cambiar(id, "fecha = ?, avisada = 0", fecha);
  }

  editar(id, titulo, fecha, repeticion) {
    return this.cambiar(id, "titulo = ?, fecha = ?, repeticion = ?, avisada = 0", titulo, fecha, repeticion);
  }

  eliminar(id) {
    return this.cambiar(id, "borrada = 1");
  }

  async porAvisar(ahora, limite = 20) {
    const { results } = await this.db.prepare(
      "SELECT * FROM tareas WHERE estado = 'pendiente' AND borrada = 0 AND avisada = 0 AND fecha <= ? " +
      "ORDER BY fecha LIMIT ?").bind(aTexto(ahora), limite).all();
    return results.map(aTarea);
  }

  /** Solo si sigue siendo ESA ocurrencia: si mientras tanto la completaste o pospusiste, no se toca. */
  marcarAvisada(id, fecha) {
    return this.cambiarSi(id, fecha, "avisada = 1");
  }

  /**
   * Tareas que se repiten y quedaron atrás sin atender (p. ej. "tomar pastilla" de ayer):
   * pasan a su próxima ocurrencia para que el aviso de hoy no se pierda.
   */
  async adelantarRepetitivasOlvidadas(ahora) {
    const limite = aTexto(sumarMinutos(ahora, -12 * 60));
    const { results } = await this.db.prepare(
      "SELECT * FROM tareas WHERE estado = 'pendiente' AND borrada = 0 AND avisada = 1 AND repeticion IS NOT NULL " +
      "AND fecha <= ?").bind(limite).all();
    for (const t of results) {
      const siguiente = siguienteOcurrencia(desdeTexto(t.fecha), t.repeticion, ahora);
      if (siguiente) await this.cambiarSi(t.id, t.fecha, "fecha = ?, avisada = 0", aTexto(siguiente));
    }
    return results.length;
  }

  /** UPDATE de una tarea que además anota cuándo cambió (para la sincronización). Devuelve si existía. */
  async cambiar(id, asignaciones, ...valores) {
    const r = await this.db.prepare(`UPDATE tareas SET ${asignaciones}, actualizada = ? WHERE id = ? AND borrada = 0`)
      .bind(...valores, Date.now(), id).run();
    return r.meta.changes > 0;
  }

  /** Como cambiar(), pero solo si la tarea sigue en 'fecha' (evita pisar un cambio hecho entre medio). */
  async cambiarSi(id, fecha, asignaciones, ...valores) {
    const r = await this.db.prepare(
      `UPDATE tareas SET ${asignaciones}, actualizada = ? WHERE id = ? AND fecha = ? AND borrada = 0`)
      .bind(...valores, Date.now(), id, fecha).run();
    return r.meta.changes > 0;
  }

  // -------------------------------------------------------------- suscripciones
  async suscripciones() {
    return (await this.db.prepare("SELECT * FROM suscripciones").all()).results;
  }

  async contarSuscripciones() {
    return (await this.db.prepare("SELECT COUNT(*) AS n FROM suscripciones").first()).n;
  }

  guardarSuscripcion(s, dispositivo, ahora) {
    return this.db.prepare(
      "INSERT INTO suscripciones (endpoint, p256dh, auth, dispositivo, creada) VALUES (?, ?, ?, ?, ?) " +
      "ON CONFLICT(endpoint) DO UPDATE SET p256dh = excluded.p256dh, auth = excluded.auth")
      .bind(s.endpoint, s.keys.p256dh, s.keys.auth, dispositivo, aTexto(ahora)).run();
  }

  borrarSuscripcion(endpoint) {
    return this.db.prepare("DELETE FROM suscripciones WHERE endpoint = ?").bind(endpoint).run();
  }
}

function aTarea(f) {
  return { id: f.id, titulo: f.titulo, fecha: f.fecha, repeticion: f.repeticion, estado: f.estado,
           avisada: Boolean(f.avisada) };
}
