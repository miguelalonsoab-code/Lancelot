"""
Frases de aliento, elegidas según el momento.

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
