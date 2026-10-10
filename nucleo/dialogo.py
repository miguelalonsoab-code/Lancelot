"""
Diálogo para completar una tarea por voz: Lancelot pregunta lo que falta.

    Tú:       "Lancelot, recuérdame comprar pan"
    Lancelot: "¿Para cuándo?"
    Tú:       "mañana a las ocho"
    Lancelot: "Listo. Te aviso mañana a las 8 de la mañana: Comprar pan."

    Tú:       "Lance, recuérdame mañana a las 5"
    Lancelot: "¿Qué te recuerdo?"
    Tú:       "llamar al banco"

Es lógica pura (sin Qt, sin micrófono): recibe texto y devuelve qué hacer.
Así se puede probar escribiendo, y la app solo se encarga de hablar y escuchar.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from nucleo.interprete import interpretar, normalizar
from nucleo.numeros import numeros_a_digitos

_CANCELAR = re.compile(r"^(?:cancela|cancelar|cancelalo|olvidalo|olvida(?:lo)?|nada|dejalo|deja|"
                       r"no importa|ya no|mejor no|no)$")


@dataclass
class Paso:
    tipo: str                         # "preguntar" | "crear" | "cancelar" | "rendirse"
    texto: str = ""                   # lo que dice Lancelot (pregunta o motivo)
    titulo: str = ""
    fecha: datetime | None = None
    repeticion: str | None = None


class DialogoTarea:
    def __init__(self, texto_original: str, titulo: str, fecha: datetime | None,
                 repeticion: str | None, intentos_max: int = 2):
        self.texto_original = texto_original      # para dejarlo en el panel si no se logra
        self.titulo = titulo
        self.fecha = fecha
        self.repeticion = repeticion
        self.intentos_max = intentos_max
        self._fallos = 0

    # --------------------------------------------------------------- estado
    def falta(self) -> str | None:
        if not self.titulo:
            return "titulo"
        if self.fecha is None:
            return "fecha"
        return None

    def siguiente(self) -> Paso:
        """Qué hacer ahora: preguntar lo que falta o crear la tarea."""
        falta = self.falta()
        if falta == "titulo":
            return Paso("preguntar", "¿Qué te recuerdo?")
        if falta == "fecha":
            return Paso("preguntar", f"¿Para cuándo te recuerdo «{self.titulo}»?")
        return Paso("crear", titulo=self.titulo, fecha=self.fecha, repeticion=self.repeticion)

    # ------------------------------------------------------------ respuesta
    def responder(self, texto: str, ahora: datetime | None = None) -> Paso:
        ahora = ahora or datetime.now()
        t = normalizar(texto).strip(" .!¡?¿,")
        if _CANCELAR.match(t):
            return Paso("cancelar", "Listo, no lo anoto.")

        if self.falta() == "titulo":
            titulo = texto.strip(" .")
            if not titulo:
                return self._fallo("No te escuché. ¿Qué te recuerdo?")
            # Si en la misma respuesta dijo cuándo ("llamar al banco a las 5"), también se usa
            r = interpretar(numeros_a_digitos(titulo), ahora)
            self.titulo = r.titulo or titulo[:1].upper() + titulo[1:]
            if self.fecha is None and r.fecha:
                self.fecha, self.repeticion = r.fecha, r.repeticion or self.repeticion
            return self.siguiente()

        # Falta la fecha: la respuesta debe decir cuándo ("mañana a las 8", "en 20 minutos")
        r = interpretar(numeros_a_digitos(texto), ahora)
        if r.fecha is None:
            return self._fallo("No entendí cuándo. Dime, por ejemplo, «mañana a las 8» o «en 20 minutos».")
        if r.fecha <= ahora and not (r.repeticion or self.repeticion):
            return self._fallo("Esa hora ya pasó. ¿Para cuándo entonces?")
        self.fecha = r.fecha
        self.repeticion = r.repeticion or self.repeticion
        return self.siguiente()

    def _fallo(self, pregunta: str) -> Paso:
        self._fallos += 1
        if self._fallos >= self.intentos_max:
            return Paso("rendirse", "No logré entenderte. Te dejé la tarea en el panel para que la completes.")
        return Paso("preguntar", pregunta)
