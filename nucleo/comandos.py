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
    #                           saludo | semana | vencidas | vencidas_manana
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
]
_COMPILADAS = [(re.compile(p), a, t) for p, a, t in REGLAS]


def interpretar_comando(texto: str) -> Comando | None:
    t = normalizar(texto).strip(" .!¡?¿,")
    t = re.sub(r"\s+", " ", t)
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
