/**
 * Las tareas en D1. Mismas operaciones que nucleo/almacen.py de la laptop
 * (agregar, completar, posponer, editar, eliminar…), así se pueden sincronizar en la etapa 3.
 * Desde la v3.10 también eventos: tipo 'evento' + anticipacion ('7,1' = avisar 7 y 1 días antes).
 *
 * Las fechas se guardan como texto 'AAAA-MM-DD HH:MM' en hora de Lima:
 * compararlas como texto ordena igual que compararlas como fechas.
 */
import { aTexto, ahoraEn, desdeTexto, soloFecha, sumarMinutos } from "../publico/comun/fechas.js";
import { avisoPrevioPendiente, siguienteOcurrencia } from "../publico/comun/planificador.js";

export const REPETICIONES_VALIDAS = new Set(["diaria", "laborables", "semanal", "mensual", "anual"]);
export const TIPOS_VALIDOS = new Set(["tarea", "evento"]);

/** '7,1' se acepta; cualquier otra cosa queda en null = sin avisos previos (igual que limpiar_anticipacion). */
export function limpiarAnticipacion(valor) {
  const texto = String(valor ?? "").replace(/ /g, "");
  return /^\d{1,3}(?:,\d{1,3})*$/.test(texto) ? texto : null;
}

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

  async agregar(titulo, fecha, repeticion, ahora, tipo = "tarea", anticipacion = null) {
    const id = crypto.randomUUID();
    await this.db.prepare(
      "INSERT INTO tareas (id, titulo, fecha, repeticion, creada, actualizada, recibida, tipo, anticipacion) " +
      "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)")
      .bind(id, titulo, fecha, repeticion, aTexto(ahora), Date.now(), Date.now(),
            TIPOS_VALIDOS.has(tipo) ? tipo : "tarea", limpiarAnticipacion(anticipacion)).run();
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

  /** tipo / anticipacion: undefined = dejar lo que tenía. */
  editar(id, titulo, fecha, repeticion, tipo, anticipacion) {
    let asignaciones = "titulo = ?, fecha = ?, repeticion = ?, avisada = 0";
    const valores = [titulo, fecha, repeticion];
    if (TIPOS_VALIDOS.has(tipo)) { asignaciones += ", tipo = ?"; valores.push(tipo); }
    if (anticipacion !== undefined) { asignaciones += ", anticipacion = ?"; valores.push(limpiarAnticipacion(anticipacion)); }
    return this.cambiar(id, asignaciones, ...valores);
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

  /**
   * Eventos a los que les toca un aviso ANTICIPADO ahora: [{ tarea, dias }]. Igual que por_avisar_antes de la laptop.
   * 'zona': para pasar 'actualizada' (milisegundos) a hora de pared.
   */
  async porAvisarAntes(ahora, zona, limite = 50) {
    const { results } = await this.db.prepare(
      "SELECT * FROM tareas WHERE estado = 'pendiente' AND borrada = 0 AND anticipacion IS NOT NULL " +
      "AND anticipacion <> '' AND fecha > ? ORDER BY fecha LIMIT ?").bind(aTexto(ahora), limite).all();
    const tocan = [];
    for (const f of results) {
      let desde = f.actualizada ? ahoraEn(zona, new Date(f.actualizada)) : new Date(0);
      const previo = desdeTexto(f.aviso_previo);
      if (previo && previo > desde) desde = previo;
      const dias = avisoPrevioPendiente(desdeTexto(f.fecha), f.anticipacion, desde, ahora);
      if (dias !== null) tocan.push({ tarea: aTarea(f), dias });
    }
    return tocan;
  }

  /** Ya se avisó con anticipación. No cuenta como cambio: no se sincroniza. */
  marcarAvisoPrevio(id, ahora) {
    return this.db.prepare("UPDATE tareas SET aviso_previo = ? WHERE id = ?").bind(aTexto(ahora), id).run();
  }

  /** Eventos cuyo día ya pasó: si se repiten, al próximo; si no, quedan hechos (no se acumulan en vencidas). */
  async cerrarEventosPasados(ahora) {
    const { results } = await this.db.prepare(
      "SELECT * FROM tareas WHERE estado = 'pendiente' AND borrada = 0 AND tipo = 'evento' AND fecha < ?")
      .bind(aTexto(soloFecha(ahora))).all();
    for (const t of results) {
      const siguiente = siguienteOcurrencia(desdeTexto(t.fecha), t.repeticion, ahora);
      if (siguiente) await this.cambiarSi(t.id, t.fecha, "fecha = ?, avisada = 0", aTexto(siguiente));
      else await this.cambiarSi(t.id, t.fecha, "estado = 'hecha', completada = ?", aTexto(ahora));
    }
    return results.length;
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
    const r = await this.db.prepare(
      `UPDATE tareas SET ${asignaciones}, actualizada = ?, recibida = ? WHERE id = ? AND borrada = 0`)
      .bind(...valores, Date.now(), Date.now(), id).run();
    return r.meta.changes > 0;
  }

  /** Como cambiar(), pero solo si la tarea sigue en 'fecha' (evita pisar un cambio hecho entre medio). */
  async cambiarSi(id, fecha, asignaciones, ...valores) {
    const r = await this.db.prepare(
      `UPDATE tareas SET ${asignaciones}, actualizada = ?, recibida = ? WHERE id = ? AND fecha = ? AND borrada = 0`)
      .bind(...valores, Date.now(), Date.now(), id, fecha).run();
    return r.meta.changes > 0;
  }

  // ------------------------------------------------------------ sincronización
  /**
   * Un cambio que viene de la laptop. Gana el más reciente ("el último cambio gana"):
   * si aquí la tarea cambió DESPUÉS que en la laptop, se ignora y la laptop recibirá la versión de aquí.
   * Devuelve true si se aplicó.
   */
  async aplicarCambio(c, ahora) {
    // Si la fecha ya pasó hace rato (la laptop ya avisó), el celular no vuelve a avisar de algo viejo
    const avisada = c.estado !== "pendiente" || c.fecha <= aTexto(sumarMinutos(ahora, -10)) ? 1 : 0;
    // Una laptop vieja (sin eventos) no manda tipo ni anticipación: entonces se deja lo que había aquí
    const conTipo = c.tipo !== undefined ? 1 : 0, conAnticipacion = c.anticipacion !== undefined ? 1 : 0;
    const r = await this.db.prepare(
      "INSERT INTO tareas (id, titulo, fecha, repeticion, estado, avisada, creada, completada, actualizada, borrada, " +
      "recibida, tipo, anticipacion) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) " +
      "ON CONFLICT(id) DO UPDATE SET titulo = excluded.titulo, fecha = excluded.fecha, " +
      "repeticion = excluded.repeticion, estado = excluded.estado, completada = excluded.completada, " +
      "borrada = excluded.borrada, actualizada = excluded.actualizada, recibida = excluded.recibida, " +
      "tipo = CASE WHEN ? THEN excluded.tipo ELSE tareas.tipo END, " +
      "anticipacion = CASE WHEN ? THEN excluded.anticipacion ELSE tareas.anticipacion END, " +
      "avisada = CASE WHEN excluded.fecha <> tareas.fecha THEN excluded.avisada ELSE tareas.avisada END " +
      "WHERE excluded.actualizada > tareas.actualizada")
      .bind(c.id, c.titulo, c.fecha, c.repeticion, c.estado, avisada, c.creada, c.completada, c.actualizada,
            c.borrada, Date.now(), c.tipo ?? "tarea", c.anticipacion ?? null, conTipo, conAnticipacion).run();
    return r.meta.changes > 0;
  }

  /** Todo lo que llegó o cambió desde 'desde' (milisegundos), incluidas hechas y borradas. */
  async cambiosDesde(desde, limite = 1000) {
    const { results } = await this.db.prepare(
      "SELECT id, titulo, fecha, repeticion, estado, creada, completada, actualizada, borrada, tipo, anticipacion, " +
      "recibida " +
      "FROM tareas WHERE recibida >= ? ORDER BY recibida LIMIT ?").bind(desde, limite).all();
    return results;
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
           avisada: Boolean(f.avisada), tipo: f.tipo || "tarea", anticipacion: f.anticipacion ?? null };
}
