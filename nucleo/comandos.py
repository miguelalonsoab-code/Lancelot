"""
Comandos que entiende el asistente, escritos en el panel o dichos por voz.

Los comandos son estrictos a propósito: tienen que ser la frase completa.
Así "estudiar para el examen mañana 8pm" sigue siendo una TAREA, y solo
"modo estudio" (o variantes) activa el modo.

Si algún día conectas una IA, ella podrá producir estos mismos objetos Comando
a partir de lenguaje libre, y el resto del programa no cambia.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from nucleo.interprete import normalizar


@dataclass
class Comando:
    accion: str               # estudio | pausa | seguir | terminar | silencio | normal | resumen
    #                           abrir | hora | agenda | escucha_on | escucha_off
    #                           apodo | olvidar_apodo | apodos | abrir_web | buscar
    #                           saludo | semana | vencidas | vencidas_manana | actualizacion
    #                           frase | guardar_frase | horario_ver | horario_agregar | horario_borrar | libre
    #                           excepcion | excepciones
    #                           perfil | despertar | dormir | meta_estudio | actividad | actividades
    #                           borrar_actividad | traslado
    minutos: int | None = None
    texto: str | None = None  # p. ej. el nombre de la app en "abre spotify", o el apodo
    destino: str | None = None  # a qué app apunta un apodo nuevo, o dónde buscar (youtube, google)
    navegador: str | None = None  # "chrome", "edge"... si dijiste "desde chrome"


_PREFIJO = r"(?:ponte en |pon(?:er)? |activa(?:r)? (?:el )?|entra(?:r)? (?:en|al) |modo )?"

# (patrón, acción, qué capturan los grupos: None | "minutos" | "texto" | "dos_textos" |
#  "sitio_navegador" | "busqueda")
REGLAS = [
    (r"^" + _PREFIJO + r"(?:modo )?(?:estudio|estudiar|enfoque|concentracion|pomodoro)"
     r"(?: (?:de |por )?(\d{1,3})(?: ?(?:min|mins|minutos))?)?$", "estudio", "minutos"),
    (r"^(?:a estudiar|vamos a estudiar|hora de estudiar)$", "estudio", None),
    (r"^(?:pausa|pausar|pausalo|para un rato|espera)$", "pausa", None),
    (r"^(?:seguir|sigue|continuar|continua|reanudar|sigamos|vamos|listo)$", "seguir", None),
    (r"^(?:terminar|termina|parar|detener|ya termine|fin|salir del modo(?: \w+)?|"
     r"terminar (?:sesion|estudio))$", "terminar", None),
    (r"^" + _PREFIJO + r"(?:modo )?(?:silencio|silencioso|no molestar)$", "silencio", None),
    (r"^" + _PREFIJO + r"modo normal$|^(?:quita|quitar|desactiva(?:r)?) (?:el )?silencio$", "normal", None),
    (r"^(?:resumen|como voy|cuanto estudie(?: hoy)?)$", "resumen", None),
    (r"^(?:resumen (?:de (?:la |esta )?)?semana(?:l)?|como voy (?:esta|en la) semana|"
     r"cuanto estudie (?:esta|en la) semana|mi semana)$", "semana", None),
    (r"^(?:hola|buenos dias|buen dia|buenas tardes|buenas noches|saludame|como empieza mi dia)$",
     "saludo", None),
    (r"^(?:que tengo vencido|(?:mis |las )?(?:tareas )?vencidas|que se me paso|que tareas se me pasaron)$",
     "vencidas", None),
    (r"^(?:busca(?:r)? actualizacion(?:es)?|hay (?:alguna )?actualizacion|actualizate|"
     r"que version (?:tienes|eres)|(?:tu )?version)$", "actualizacion", None),
    (r"^(?:pasa|pasar|mueve|mover|reprograma|reprogramar|deja|dejar)(?: todas)? las (?:tareas )?vencidas "
     r"(?:para |a )?manana$", "vencidas_manana", None),
    # "cuando diga el código abre visual studio code" -> apodo
    #   (.+?) es "perezoso": corta en el PRIMER "abre"; sin el ? se comería hasta el último
    (r"^(?:cuando|si) (?:te )?(?:diga|digo) (.+?),? (?:abre|abres|abrir|abras) "
     r"(?:el |la |los |las |mi |un |una )?(.+)$", "apodo", "dos_textos"),
    (r"^(?:olvida|borra|elimina|quita) el apodo (.+)$", "olvidar_apodo", "texto"),
    (r"^(?:mis apodos|que apodos tienes|cuales son mis apodos|lista de apodos)$", "apodos", None),
    # "abre netflix desde chrome" / "entra a youtube en edge"
    (r"^(?:abre|abrir|abreme|abrime|entra a|entra en|ve a) (?:el |la |mi )?(.+?) "
     r"(?:en|desde|con|por) (?:el )?(google chrome|chrome|microsoft edge|edge|mozilla firefox|firefox|"
     r"mozilla|brave|opera|navegador)$", "abrir_web", "sitio_navegador"),
    # "busca lofi para estudiar en youtube" / "... en google desde chrome"
    (r"^(?:busca|buscame|buscar) (.+?) en (youtube|google|wikipedia)"
     r"(?: (?:en|desde|con) (?:el )?(google chrome|chrome|edge|firefox|brave|opera))?$", "buscar", "busqueda"),
    (r"^(?:abre|abrir|abreme|abrime|ejecuta|inicia|iniciar)\s+(?:el |la |los |las |mi |un |una )?(.+)$",
     "abrir", "texto"),
    (r"^(?:que hora es|la hora|dime la hora|hora)$", "hora", None),
    (r"^(?:que tengo(?: para)? hoy|que tengo pendiente|mis tareas|mis pendientes|"
     r"pendientes(?: de hoy)?|agenda(?: de hoy)?)$", "agenda", None),
    (r"^(?:escuchame|escucha|activa(?:r)? la escucha|empieza a escuchar)$", "escucha_on", None),
    (r"^(?:deja de escuchar|no escuches|desactiva(?:r)? la escucha)$", "escucha_off", None),
    # Perfil (v3.13): lo que Lancelot sabe de ti
    (r"^(?:que sabes de mi|que sabes sobre mi|mi perfil|perfil|quien soy)$", "perfil", None),
    (r"^(?:me despierto|me levanto|despierto|me paro)(?: a eso de las?| a las?)? (.+)$", "despertar", "texto"),
    (r"^(?:me duermo|me acuesto|duermo|me voy a dormir)(?: a eso de las?| a las?)? (.+)$", "dormir", "texto"),
    (r"^(?:mi )?meta (?:de estudio|diaria)(?: diaria)?(?: es| de)?:? (.+)$", "meta_estudio", "texto"),
    (r"^(?:mis actividades|que actividades tengo)$", "actividades", None),
    (r"^(?:actividad|nueva actividad|agrega(?:r)? (?:la )?actividad|me gusta(?: hacer)?)\s*:?\s+(.+)$", "actividad",
     "original"),
    (r"^(?:borra|borrar|elimina|quita) (?:la )?actividad (?:de )?(.+)$", "borrar_actividad", "texto"),
    (r"^(?:al|a la|hasta el|hasta la) (.+?) (?:tardo|me demoro|demoro|me toma|son) (.+)$", "traslado", "dos_textos"),
    # Horario fijo y horas libres (v3.12)
    (r"^(?:mi horario|horario|ver (?:mi )?horario|muestrame mi horario|cual es mi horario)$", "horario_ver", None),
    (r"^(?:cuando estoy libre|que tiempo libre tengo|cuanto tiempo libre tengo|tiempo libre|mis horas libres|"
     r"horas libres|estoy libre)(?: (hoy|manana))?$", "libre", "texto"),
    (r"^(?:horario|ocupado|estoy ocupado|mi horario(?: es)?|agrega(?:r)? (?:a mi |al |en mi )?horario|"
     r"anota en (?:mi|el) horario)\s*:?\s+(.+)$", "horario_agregar", "original"),
    (r"^(?:borra|borrar|elimina|quita) (?:el |del )?(?:bloque|horario) (?:de |del )?(.+)$", "horario_borrar", "texto"),
    # Excepciones al horario (v3.14): "el 1 de noviembre no trabajo", "vacaciones del 20 al 30 de diciembre"
    (r"^(?:mis dias libres|dias libres|mis excepciones|excepciones|mis vacaciones|mis feriados)$", "excepciones", None),
    (r"^(?!(?:que|cuanto|cuando|cual|cuales) )((?:vacaciones|feriado|dia libre) .+|"
     r"(?:.+ )?(?:no trabajo|no (?:tengo|hay) (?:clases?|trabajo|universidad|turno)|"
     r"no (?:voy|asisto) (?:a|al) (?:la |el )?[a-z]+|es feriado|(?:tengo|es) (?:mi |el )?(?:dia )?libre|"
     r"(?:estoy|me voy) de vacaciones|son mis vacaciones)(?: .+)?)$", "excepcion", "original"),
    # Sugerencias (v3.15): "¿qué hago hoy?" y "ya fui al gimnasio" (cuenta para tu meta semanal)
    (r"^(?:que (?:hago|puedo hacer|me recomiendas|me sugieres)|recomiendame algo|recomiendame que hacer|sugiereme algo|dame (?:una |unas )?sugerencias?|sugerencias|que hago con mi tiempo libre|plan del dia)(?: (?:para )?(hoy|manana|ahora))?$",
     "sugerir", "texto"),
    (r"^(?:agendalo|agendala|agendalas|agendalos|agenda(?:r)? (?:las sugerencias|el plan|eso|todo)|si,? agendalo)$", "agendar_plan", None),
    (r"^(?:vuelve a sugerirme todo|olvida (?:mis rechazos|lo que rechace)|reinicia (?:las )?sugerencias)$", "olvidar_rechazos", None),
    (r"^(?:mas tarde|despues|luego|mejor|proponmelo|recuerdamelo)(?: mas tarde)?,? (?:a las?|a eso de las?) (\d{1,2}(?::\d{2})?(?: ?(?:am|pm))?(?: de la (?:manana|tarde|noche))?)$",
     "posponer_hasta", "texto"),
    (r"^(?:ya )?(?:hice|fui (?:a la|al|a)|termine de|complete) (.+)$", "actividad_hecha", "texto"),
    # Frases (v3.10). "guarda esta frase: …" conserva tus mayúsculas y tildes (ver "original")
    (r"^(?:guarda|guardar|guardame|anota|agrega|aprende|aprendete|recuerda) (?:esta|la|una|mi|esta otra|otra) "
     r"frase:? (.+)$", "guardar_frase", "original"),
    (r"^(?:dime una frase|una frase|frase del dia|dame una frase|me (?:dices|das) una frase|motivame|dame animos|necesito animos|"
     r"dime algo bonito|inspirame)$", "frase", None),
]
_COMPILADAS = [(re.compile(p), a, t) for p, a, t in REGLAS]


def interpretar_comando(texto: str) -> Comando | None:
    # 'original' y 't' tienen el mismo largo (normalizar no cambia la cantidad de letras):
    # lo encontrado en 't' se puede recortar de 'original' con sus tildes y mayúsculas.
    original = re.sub(r"\s+", " ", texto.strip(" .!¡?¿,\t\n"))
    original = original.strip(" .!¡?¿,")
    t = normalizar(original)
    for patron, accion, captura in _COMPILADAS:
        m = patron.match(t)
        if not m:
            continue
        valor = m.group(1) if m.groups() else None
        if captura == "minutos":
            minutos = int(valor) if valor else None
            if minutos is not None and not 5 <= minutos <= 180:
                minutos = None        # "modo estudio 2" o "900" no tiene sentido
            return Comando(accion, minutos=minutos)
        if captura == "texto":
            return Comando(accion, texto=valor.strip(" .") if valor else None)
        if captura == "original":
            return Comando(accion, texto=original[m.start(1):m.end(1)].strip(" ."))
        if captura == "sitio_navegador":
            navegador = None if m.group(2) == "navegador" else m.group(2)
            return Comando(accion, texto=m.group(1).strip(" ."), navegador=navegador)
        if captura == "busqueda":
            return Comando(accion, texto=m.group(1).strip(" ."), destino=m.group(2), navegador=m.group(3))
        if captura == "dos_textos":
            apodo = m.group(1).strip(" ,.")
            return Comando(accion, texto=apodo, destino=m.group(2).strip(" ."))
        return Comando(accion)
    return None
