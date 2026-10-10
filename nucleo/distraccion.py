"""
¿La ventana activa es una distracción?

Solo mira el TÍTULO de la ventana y el nombre del programa, por ejemplo:
    ("(3) YouTube - Google Chrome", "chrome.exe")
No guarda nada ni lo envía a ningún lado. La lista se edita en config.py.
"""
from __future__ import annotations

from nucleo.interprete import normalizar


def detectar_distraccion(titulo: str, proceso: str, palabras: dict[str, str],
                         permitidas: set[str]) -> str | None:
    """
    Devuelve el nombre de la distracción ("YouTube") o None.
    'permitidas' son ventanas que marcaste como "Es para estudiar" en esta sesión.
    """
    if not titulo and not proceso:
        return None
    if clave_ventana(titulo, proceso) in permitidas:
        return None
    texto = normalizar(f"{titulo} {proceso}")
    for palabra, nombre in palabras.items():
        if normalizar(palabra) in texto:
            return nombre
    return None


def clave_ventana(titulo: str, proceso: str) -> str:
    """
    Identifica una ventana para "permitirla". Se usa el título sin el contador
    de notificaciones: "(3) YouTube - Clase de SQL" == "(5) YouTube - Clase de SQL".
    """
    t = titulo
    if t.startswith("(") and ")" in t[:6]:
        t = t[t.index(")") + 1:]
    return f"{proceso}|{t.strip()}".lower()
