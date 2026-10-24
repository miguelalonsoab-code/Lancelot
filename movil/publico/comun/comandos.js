/**
 * Comandos (frases que no son tareas): traducción de nucleo/comandos.py, con los mismos casos de prueba.
 *
 * El celular entiende TODOS los comandos, pero solo resuelve los de ACCIONES_CELULAR.
 * Los demás (modo estudio, abrir apps…) son cosas de la laptop: la app lo dice en vez de
 * guardarlos como si fueran una tarea.
 */
import { normalizar } from "./interprete.js";

export const ACCIONES_CELULAR = new Set(["agenda", "vencidas", "vencidas_manana", "hora", "saludo", "frase",
  // v3.19: con el contexto que sube la laptop
  "sugerir", "agendar_plan", "actividad_hecha", "excepcion", "excepciones", "libre", "horario_ver",
  // v3.20
  "actividad", "actividades", "borrar_actividad"]);

const PREFIJO = "(?:ponte en |pon(?:er)? |activa(?:r)? (?:el )?|entra(?:r)? (?:en|al) |modo )?";

// [patrón, acción, qué capturan los grupos]
const REGLAS = [
  ["^" + PREFIJO + String.raw`(?:modo )?(?:estudio|estudiar|enfoque|concentracion|pomodoro)(?: (?:de |por )?(\d{1,3})(?: ?(?:min|mins|minutos))?)?$`, "estudio", "minutos"],
  ["^(?:a estudiar|vamos a estudiar|hora de estudiar)$", "estudio", null],
  ["^(?:pausa|pausar|pausalo|para un rato|espera)$", "pausa", null],
  ["^(?:seguir|sigue|continuar|continua|reanudar|sigamos|vamos|listo)$", "seguir", null],
  [String.raw`^(?:terminar|termina|parar|detener|ya termine|fin|salir del modo(?: \w+)?|terminar (?:sesion|estudio))$`, "terminar", null],
  ["^" + PREFIJO + "(?:modo )?(?:silencio|silencioso|no molestar)$", "silencio", null],
  ["^" + PREFIJO + "modo normal$|^(?:quita|quitar|desactiva(?:r)?) (?:el )?silencio$", "normal", null],
  ["^(?:resumen|como voy|cuanto estudie(?: hoy)?)$", "resumen", null],
  ["^(?:resumen (?:de (?:la |esta )?)?semana(?:l)?|como voy (?:esta|en la) semana|cuanto estudie (?:esta|en la) semana|mi semana)$", "semana", null],
  ["^(?:hola|buenos dias|buen dia|buenas tardes|buenas noches|saludame|como empieza mi dia)$", "saludo", null],
  ["^(?:que tengo vencido|(?:mis |las )?(?:tareas )?vencidas|que se me paso|que tareas se me pasaron)$", "vencidas", null],
  ["^(?:busca(?:r)? actualizacion(?:es)?|hay (?:alguna )?actualizacion|actualizate|que version (?:tienes|eres)|(?:tu )?version)$", "actualizacion", null],
  ["^(?:pasa|pasar|mueve|mover|reprograma|reprogramar|deja|dejar)(?: todas)? las (?:tareas )?vencidas (?:para |a )?manana$", "vencidas_manana", null],
  ["^(?:cuando|si) (?:te )?(?:diga|digo) (.+?),? (?:abre|abres|abrir|abras) (?:el |la |los |las |mi |un |una )?(.+)$", "apodo", "dos_textos"],
  ["^(?:olvida|borra|elimina|quita) el apodo (.+)$", "olvidar_apodo", "texto"],
  ["^(?:mis apodos|que apodos tienes|cuales son mis apodos|lista de apodos)$", "apodos", null],
  ["^(?:abre|abrir|abreme|abrime|entra a|entra en|ve a) (?:el |la |mi )?(.+?) (?:en|desde|con|por) (?:el )?(google chrome|chrome|microsoft edge|edge|mozilla firefox|firefox|mozilla|brave|opera|navegador)$", "abrir_web", "sitio_navegador"],
  ["^(?:busca|buscame|buscar) (.+?) en (youtube|google|wikipedia)(?: (?:en|desde|con) (?:el )?(google chrome|chrome|edge|firefox|brave|opera))?$", "buscar", "busqueda"],
  [String.raw`^(?:abre|abrir|abreme|abrime|ejecuta|inicia|iniciar)\s+(?:el |la |los |las |mi |un |una )?(.+)$`, "abrir", "texto"],
  ["^(?:que hora es|la hora|dime la hora|hora)$", "hora", null],
  ["^(?:que tengo(?: para)? hoy|que tengo pendiente|mis tareas|mis pendientes|pendientes(?: de hoy)?|agenda(?: de hoy)?)$", "agenda", null],
  ["^(?:escuchame|escucha|activa(?:r)? la escucha|empieza a escuchar)$", "escucha_on", null],
  ["^(?:deja de escuchar|no escuches|desactiva(?:r)? la escucha)$", "escucha_off", null],
  ["^(?:que sabes de mi|que sabes sobre mi|mi perfil|perfil|quien soy)$", "perfil", null],
  ["^(?:me despierto|me levanto|despierto|me paro)(?: a eso de las?| a las?)? (.+)$", "despertar", "texto"],
  ["^(?:me duermo|me acuesto|duermo|me voy a dormir)(?: a eso de las?| a las?)? (.+)$", "dormir", "texto"],
  ["^(?:mi )?meta (?:de estudio|diaria)(?: diaria)?(?: es| de)?:? (.+)$", "meta_estudio", "texto"],
  ["^(?:mis actividades|que actividades tengo)$", "actividades", null],
  [String.raw`^(?:actividad|nueva actividad|agrega(?:r)? (?:la )?actividad|me gusta(?: hacer)?)\s*:?\s+(.+)$`, "actividad", "original"],
  ["^(?:borra|borrar|elimina|quita) (?:la )?actividad (?:de )?(.+)$", "borrar_actividad", "texto"],
  ["^(?:al|a la|hasta el|hasta la) (.+?) (?:tardo|me demoro|demoro|me toma|son) (.+)$", "traslado", "dos_textos"],
  ["^(?:mi horario|horario|ver (?:mi )?horario|muestrame mi horario|cual es mi horario)$", "horario_ver", null],
  ["^(?:cuando estoy libre|que tiempo libre tengo|cuanto tiempo libre tengo|tiempo libre|mis horas libres|horas libres|estoy libre)(?: (hoy|manana))?$",
    "libre", "texto"],
  [String.raw`^(?:horario|ocupado|estoy ocupado|mi horario(?: es)?|agrega(?:r)? (?:a mi |al |en mi )?horario|anota en (?:mi|el) horario)\s*:?\s+(.+)$`,
    "horario_agregar", "original"],
  ["^(?:borra|borrar|elimina|quita) (?:el |del )?(?:bloque|horario) (?:de |del )?(.+)$", "horario_borrar", "texto"],
  // Excepciones al horario (v3.14)
  ["^(?:mis dias libres|dias libres|mis excepciones|excepciones|mis vacaciones|mis feriados)$", "excepciones", null],
  ["^(?!(?:que|cuanto|cuando|cual|cuales) )((?:vacaciones|feriado|dia libre) .+|" +
    "(?:.+ )?(?:no trabajo|no (?:tengo|hay) (?:clases?|trabajo|universidad|turno)|" +
    "no (?:voy|asisto) (?:a|al) (?:la |el )?[a-z]+|es feriado|(?:tengo|es) (?:mi |el )?(?:dia )?libre|" +
    "(?:estoy|me voy) de vacaciones|son mis vacaciones)(?: .+)?)$", "excepcion", "original"],
  // Sugerencias (v3.15)
  ["^(?:que (?:hago|puedo hacer|me recomiendas|me sugieres)|recomiendame algo|recomiendame que hacer|sugiereme algo|dame (?:una |unas )?sugerencias?|sugerencias|que hago con mi tiempo libre|plan del dia)(?: (?:para )?(hoy|manana|ahora))?$",
    "sugerir", "texto"],
  ["^(?:agendalo|agendala|agendalas|agendalos|agenda(?:r)? (?:las sugerencias|el plan|eso|todo)|si,? agendalo)$", "agendar_plan", null],
  ["^(?:vuelve a sugerirme todo|olvida (?:mis rechazos|lo que rechace)|reinicia (?:las )?sugerencias)$", "olvidar_rechazos", null],
  [String.raw`^(?:mas tarde|despues|luego|mejor|proponmelo|recuerdamelo)(?: mas tarde)?,? (?:a las?|a eso de las?) (\d{1,2}(?::\d{2})?(?: ?(?:am|pm))?(?: de la (?:manana|tarde|noche))?)$`,
    "posponer_hasta", "texto"],
  ["^(?:ya )?(?:hice|fui (?:a la|al|a)|termine de|complete) (.+)$", "actividad_hecha", "texto"],
  ["^(?:guarda|guardar|guardame|anota|agrega|aprende|aprendete|recuerda) (?:esta|la|una|mi|esta otra|otra) frase:? (.+)$",
    "guardar_frase", "original"],
  ["^(?:dime una frase|una frase|frase del dia|dame una frase|me (?:dices|das) una frase|motivame|dame animos|necesito animos|dime algo bonito|inspirame)$",
    "frase", null],
].map(([p, a, c]) => [new RegExp(p), a, c]);

const limpiar = (s) => s.replace(/^[ .]+|[ .]+$/g, "");

/** Devuelve { accion, minutos, texto, destino, navegador } o null si es una tarea. */
export function interpretarComando(texto) {
  // Mismo largo que el original: lo encontrado en 't' se recorta del original con sus tildes ("guarda esta frase")
  const original = texto.replace(/\s+/g, " ").replace(/^[ .!¡?¿,]+|[ .!¡?¿,]+$/g, "");
  const t = normalizar(original);
  for (const [patron, accion, captura] of REGLAS) {
    const m = patron.exec(t);
    if (!m) continue;
    const c = { accion, minutos: null, texto: null, destino: null, navegador: null };
    if (captura === "minutos") {
      const n = m[1] ? +m[1] : null;
      c.minutos = n !== null && n >= 5 && n <= 180 ? n : null;
    } else if (captura === "texto") {
      c.texto = m[1] ? limpiar(m[1]) : null;
    } else if (captura === "sitio_navegador") {
      c.texto = limpiar(m[1]);
      c.navegador = m[2] === "navegador" ? null : m[2];
    } else if (captura === "busqueda") {
      c.texto = limpiar(m[1]); c.destino = m[2]; c.navegador = m[3] || null;
    } else if (captura === "original") {
      const inicio = m.index + m[0].length - m[1].length;            // el grupo llega hasta el final
      c.texto = limpiar(original.slice(inicio));
    } else if (captura === "dos_textos") {
      c.texto = m[1].replace(/^[ ,.]+|[ ,.]+$/g, ""); c.destino = limpiar(m[2]);
    }
    return c;
  }
  return null;
}
