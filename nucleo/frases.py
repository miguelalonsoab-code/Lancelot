"""
Frases de aliento, elegidas según el momento (modo estudio), y frases para cualquier momento
(REFLEXIONES: las que dice si dejas el mouse sobre la cara).

Variables que se reemplazan solas:
  {n}      -> pomodoros completados en la sesión
  {min}    -> minutos de enfoque de la sesión
  {hoy}    -> minutos de enfoque de todo el día
  {racha}  -> días seguidos estudiando

Agrega o cambia las que quieras: es solo texto. La idea es que sean concretas
(hablan de lo que hiciste) en vez de frases genéricas.
"""
from __future__ import annotations

import random
from pathlib import Path

FRASES = {
    "inicio": [
        "Arrancamos. {mf} minutos, una sola cosa a la vez.",
        "Modo estudio activado. El celular lejos ayuda más de lo que parece.",
        "Vamos. Solo tienes que llegar al final de este bloque.",
        "Empieza por lo más pequeño que puedas terminar. Lo demás se destraba solo.",
    ],
    "fin_enfoque": [
        "Pomodoro {n} listo. Levántate, toma agua, estira la espalda.",
        "¡Bloque terminado! {min} minutos de enfoque en esta sesión.",
        "Eso fue concentración de verdad. Descansa, te lo ganaste.",
        "Listo el {n}. Mira algo lejos de la pantalla un rato: tus ojos lo agradecen.",
        "Otro más. Lo difícil era empezar, y ya vas {n}.",
    ],
    "descanso_largo": [
        "{n} pomodoros. Tómate un descanso largo de verdad: camina, come algo.",
        "Meta de ciclo cumplida: {min} minutos enfocado. Descanso largo.",
    ],
    "fin_descanso": [
        "Se acabó el descanso. ¿Seguimos?",
        "¿Listo para el siguiente bloque? Solo uno más.",
        "Descanso terminado. Retoma justo donde lo dejaste.",
    ],
    "distraccion": [
        "Eso parece {app} 👀 ¿Volvemos al estudio?",
        "{app} puede esperar {resta} minutos. ¿Vuelves?",
        "Te vi en {app}. Sin culpa: solo regresa.",
    ],
    "fin_sesion": [
        "Sesión cerrada: {n} pomodoro(s), {min} min. Hoy llevas {hoy} min en total.",
        "Buen trabajo: {min} minutos de enfoque. Hoy suma {hoy} min.",
    ],
    "racha": [
        "Llevas {racha} días seguidos estudiando. No rompas la cadena.",
        "Racha de {racha} días. La constancia gana a la motivación.",
    ],
}


class SelectorFrases:
    """Elige una frase al azar del contexto, evitando repetir la última."""

    def __init__(self, frases: dict[str, list[str]] | None = None):
        self.frases = frases or FRASES
        self._ultima: dict[str, str] = {}

    def elegir(self, contexto: str, **datos) -> str:
        opciones = self.frases.get(contexto, [""])
        if len(opciones) > 1 and contexto in self._ultima:
            opciones = [f for f in opciones if f != self._ultima[contexto]]
        frase = random.choice(opciones)
        self._ultima[contexto] = frase
        try:
            return frase.format(**datos)
        except (KeyError, IndexError):
            return frase           # si falta un dato, mejor la frase cruda que un error


# ===================================================================== reflexiones
# Frases para cuando dejas el mouse sobre la cara (v3.10). Las tres primeras son tuyas.
# Las que agregues en frases.txt (carpeta de datos) se suman a estas.
REFLEXIONES = [
    "No dejes para mañana lo que puedes hacer hoy.",
    "El día depende de ti, puedes hacerlo grandioso.",
    "No dejes que tus malos pensamientos te controlen, tú puedes controlarlos.",
    "Un paso pequeño hoy vale más que un plan perfecto mañana.",
    "No tienes que hacerlo todo hoy. Solo lo siguiente.",
    "Respira. Una cosa a la vez.",
    "Lo que hoy te cuesta, mañana te sale solo.",
    "Empezar es la mitad del camino.",
    "Hecho es mejor que perfecto.",
    "Tu yo del futuro te va a agradecer lo que hagas ahora.",
    "Equivocarse también es avanzar: es aprender qué no funciona.",
    "La disciplina es elegir entre lo que quieres ahora y lo que más quieres.",
    "Descansar también es parte del trabajo.",
    "No te compares con otros; compárate con quien eras ayer.",
    "Los días difíciles también terminan. Este también.",
    "Si no sabes por dónde empezar, empieza por lo más pequeño.",
    "Cada tarea terminada es una preocupación menos.",
    "Hoy es un buen día para tachar algo de la lista.",
    "Tu mente es un jardín: cuida lo que siembras en ella.",
    "No esperes a tener ganas. Las ganas llegan cuando ya empezaste.",
    "Poco a poco se llega lejos.",
    "Lo importante no es ir rápido, es no detenerse.",
    "Agradece algo de hoy, por pequeño que sea.",
    "Eres más capaz de lo que crees.",
    "Un error no te define; lo que haces después, sí.",
    "Ordena tu espacio y tu mente se ordena con él.",
    "Toma agua, endereza la espalda y sigue.",
    "La motivación te hace empezar; el hábito te hace seguir.",
    "Pregúntate: ¿qué es lo más importante ahora mismo?",
    "Celebra tus avances, aunque sean pequeños.",
    "Lo que hoy siembras, mañana lo cosechas.",
    "Si te caes siete veces, levántate ocho.",
    "Hoy no tiene que ser perfecto para ser un buen día.",
    "Descansa si lo necesitas, pero no te rindas.",
    "La paciencia también es avanzar.",
    "Háblate con el cariño con que le hablarías a un amigo.",
    "Haz hoy algo que te acerque a quien quieres ser.",
    "Cinco minutos de enfoque valen más que una hora de distracción.",
    "Confía en el proceso: los resultados llegan.",
    "Un buen día empieza con una buena decisión.",
    "Si algo te preocupa, anótalo: tu mente descansa cuando no tiene que recordarlo todo.",
    "La constancia le gana a la prisa.",
]

ENCABEZADO_ARCHIVO = """\
# Tus frases para Lancelot: una por línea.
# Te dirá una al azar cuando dejes el mouse sobre su cara (junto con las que ya trae).
# Las líneas que empiezan con # se ignoran. También puedes decirle: «guarda esta frase: …».
"""
MAX_LARGO_FRASE = 300


def leer_frases_usuario(ruta: Path) -> list[str]:
    """Las frases de frases.txt (sin comentarios ni líneas vacías). Si no existe, ninguna."""
    try:
        lineas = ruta.read_text(encoding="utf-8-sig").splitlines()
    except (OSError, UnicodeDecodeError):
        return []
    frases = [l.strip() for l in lineas if l.strip() and not l.lstrip().startswith("#")]
    return [f[:MAX_LARGO_FRASE] for f in frases[:500]]


def guardar_frase_usuario(ruta: Path, frase: str) -> bool:
    """Agrega la frase al final de frases.txt. Devuelve False si estaba vacía o ya existía."""
    frase = " ".join(frase.split())[:MAX_LARGO_FRASE]
    if not frase:
        return False
    frase = frase[0].upper() + frase[1:]
    conocidas = {_comparable(f) for f in REFLEXIONES + leer_frases_usuario(ruta)}
    if _comparable(frase) in conocidas:
        return False
    ruta.parent.mkdir(parents=True, exist_ok=True)
    previo = ruta.read_text(encoding="utf-8-sig") if ruta.exists() else ENCABEZADO_ARCHIVO
    if previo and not previo.endswith("\n"):
        previo += "\n"
    ruta.write_text(previo + frase + "\n", encoding="utf-8")
    return True


def crear_archivo_frases(ruta: Path):
    """La primera vez deja frases.txt con las instrucciones, para que sepas dónde escribir las tuyas."""
    if not ruta.exists():
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text(ENCABEZADO_ARCHIVO, encoding="utf-8")


def _comparable(frase: str) -> str:
    """Para no guardar dos veces la misma frase con otra puntuación o mayúsculas."""
    return "".join(c for c in frase.lower().translate(str.maketrans("áéíóúüñ", "aeiouun")) if c.isalnum())


class BolsaFrases:
    """
    Como sacar papelitos de una bolsa: al azar y SIN repetir hasta que se acaban todos;
    entonces se vuelve a llenar (sin que la primera nueva sea igual a la última que salió).
    """

    def __init__(self, frases: list[str], azar: random.Random | None = None):
        self.azar = azar or random.Random()
        self.frases: list[str] = []
        self._bolsa: list[str] = []
        self._ultima: str | None = None
        self.cambiar_frases(frases)

    def cambiar_frases(self, frases: list[str]):
        """Nuevas frases (p. ej. editaste frases.txt): las nuevas entran a la bolsa, las borradas salen."""
        unicas = list(dict.fromkeys(f for f in frases if f))
        nuevas = [f for f in unicas if f not in self.frases]
        self.frases = unicas
        self._bolsa = [f for f in self._bolsa if f in unicas] + nuevas
        self.azar.shuffle(self._bolsa)

    def sacar(self) -> str | None:
        if not self.frases:
            return None
        if not self._bolsa:
            self._bolsa = list(self.frases)
            self.azar.shuffle(self._bolsa)
            if len(self._bolsa) > 1 and self._bolsa[-1] == self._ultima:
                self._bolsa[0], self._bolsa[-1] = self._bolsa[-1], self._bolsa[0]
        self._ultima = self._bolsa.pop()
        return self._ultima
