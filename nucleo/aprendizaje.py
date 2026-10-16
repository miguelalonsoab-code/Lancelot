"""
Aprender de tus correcciones Tarea/Evento.

Si Lancelot entendió "evento" y tú lo cambias a "tarea" (o al revés), anota POR QUÉ se equivocó.
Cuando la misma corrección se repite UMBRAL veces, la aprende:

    "Cita con el banco"  evento → tarea  (2 veces)   ⇒ "cita" deja de hacer evento         (no_evento)
    "Taller de pintura"  tarea  → evento (2 veces)   ⇒ "taller" pasa a hacer evento        (evento)
    "Ir al concierto"    tarea  → evento (2 veces)   ⇒ empezar con "ir" ya no lo impide     (verbos)

Si después corriges en sentido contrario, el contador baja: así se puede "desaprender".

Lógica pura: recibe y devuelve diccionarios. La app los guarda en la base (ajuste "aprendizaje")
y sube el vocabulario al servidor para que el celular entienda igual.
"""
from __future__ import annotations

import json
import re

from nucleo.interprete import normalizar, palabras_de_evento, parece_verbo, primera_palabra

UMBRAL = 2
CLASES = ("evento", "no_evento", "verbos")
_RELLENO = {"el", "la", "los", "las", "mi", "mis", "un", "una", "de", "del", "nuestro", "nuestra", "tu", "su", "es"}


def cargar(texto: str | None) -> dict[str, dict[str, int]]:
    """Contadores guardados (JSON), o vacíos si no hay o están dañados."""
    try:
        datos = json.loads(texto or "{}")
    except ValueError:
        datos = {}
    return {c: {str(k): int(v) for k, v in dict(datos.get(c, {})).items() if int(v) > 0} for c in CLASES}


def guardar(contadores: dict) -> str:
    return json.dumps(contadores, ensure_ascii=False, sort_keys=True)


def vocabulario(contadores: dict) -> dict[str, list[str]]:
    """Solo lo que se repitió lo suficiente."""
    return {c: sorted(w for w, n in contadores.get(c, {}).items() if n >= UMBRAL) for c in CLASES}


def registrar_correccion(contadores: dict, titulo: str, detectado: str, elegido: str) -> bool:
    """
    'detectado': lo que entendió Lancelot (con lo aprendido hasta ahora); 'elegido': lo que dejaste tú.
    Modifica 'contadores' y devuelve True si anotó algo.
    """
    if detectado == elegido or elegido not in ("tarea", "evento"):
        return False
    vocab = vocabulario(contadores)
    claves = palabras_de_evento(titulo, vocab)
    primera = primera_palabra(titulo)
    if elegido == "tarea":                                 # dijo evento y no lo era
        if primera in vocab["verbos"]:
            return _bajar(contadores, "verbos", primera)
        anoto = False
        for w in claves:
            anoto = (_bajar(contadores, "evento", w) if w in vocab["evento"] else _subir(contadores, "no_evento", w)) or anoto
        return anoto
    # elegido == "evento": dijo tarea y era evento
    todas = palabras_de_evento(titulo, {**vocab, "no_evento": []})   # incluidas las que "desaprendió"
    bloqueadas = [w for w in todas if w in vocab["no_evento"]]
    if bloqueadas:
        return any([_bajar(contadores, "no_evento", w) for w in bloqueadas])
    if claves and parece_verbo(primera):                    # "ir al concierto": el verbo lo impedía
        return _subir(contadores, "verbos", primera)
    palabra = next((w for w in re.findall(r"[a-z]+", normalizar(titulo)) if w not in _RELLENO), "")
    if 3 <= len(palabra) <= 30 and not parece_verbo(palabra):
        return _subir(contadores, "evento", palabra)        # "taller de pintura": "taller"
    return False


def _subir(contadores: dict, clase: str, palabra: str) -> bool:
    contadores.setdefault(clase, {})[palabra] = contadores[clase].get(palabra, 0) + 1
    return True


def _bajar(contadores: dict, clase: str, palabra: str) -> bool:
    n = contadores.get(clase, {}).get(palabra, 0) - 1
    if n > 0:
        contadores[clase][palabra] = n
    else:
        contadores.get(clase, {}).pop(palabra, None)
    return True
