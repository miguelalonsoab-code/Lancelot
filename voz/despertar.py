"""
¿Me llamaron? Separa el nombre del asistente de la orden.

    "lancelot abre spotify"     -> (True, "abre spotify")
    "oye lance modo estudio"    -> (True, "modo estudio")
    "lancelot"                  -> (True, "")        -> se queda esperando la orden
    "hoy llueve en lima"        -> (False, "")

El reconocedor no siempre escribe el nombre igual ("lance lot", "lanzelot"...),
por eso se acepta una lista de variantes (PALABRAS_ACTIVACION en config.py).
Si al probar ves que te entiende otra cosa, agrégala ahí.
"""
from __future__ import annotations

from nucleo.interprete import normalizar

_SALUDOS = ("oye ", "hey ", "ey ", "hola ", "ok ", "okey ")


def separar_orden(texto: str, variantes: list[str]) -> tuple[bool, str]:
    t = " ".join(normalizar(texto).split())
    for saludo in _SALUDOS:
        if t.startswith(saludo):
            t = t[len(saludo):]
            break
    # Primero las variantes más largas: "lancelot" antes que "lance"
    for v in sorted((normalizar(x) for x in variantes), key=len, reverse=True):
        if t == v:
            return True, ""
        if t.startswith(v + " "):
            return True, t[len(v) + 1:].strip(" ,")
    return False, ""
