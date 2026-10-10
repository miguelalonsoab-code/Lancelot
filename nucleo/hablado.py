"""
Fechas y horas como se dicen en voz alta (para la voz del asistente).

    20:40 -> "a las 8 y 40 de la noche"
    13:00 -> "a la 1 de la tarde"
    mañana 09:30 -> "mañana a las 9 y media de la mañana"
"""
from __future__ import annotations

from datetime import datetime

_DIAS = ["el lunes", "el martes", "el miércoles", "el jueves", "el viernes", "el sábado", "el domingo"]
_MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
          "septiembre", "octubre", "noviembre", "diciembre"]


def hora_hablada(fecha: datetime, con_articulo: bool = True) -> str:
    h, m = fecha.hour, fecha.minute
    if h == 0:
        momento = "de la noche"
    elif h < 12:
        momento = "de la mañana"
    elif h == 12:
        momento = "del mediodía"
    elif h < 19:
        momento = "de la tarde"
    else:
        momento = "de la noche"
    h12 = h % 12 or 12
    minutos = {0: "", 15: " y cuarto", 30: " y media"}.get(m, f" y {m}")
    articulo = ("a la " if h12 == 1 else "a las ") if con_articulo else ("la " if h12 == 1 else "las ")
    return f"{articulo}{h12}{minutos} {momento}"


def fecha_hablada(fecha: datetime, ahora: datetime | None = None) -> str:
    ahora = ahora or datetime.now()
    dias = (fecha.date() - ahora.date()).days
    if dias == 0:
        dia = "hoy"
    elif dias == 1:
        dia = "mañana"
    elif dias == 2:
        dia = "pasado mañana"
    elif 2 < dias < 7:
        dia = _DIAS[fecha.weekday()]
    else:
        dia = f"el {fecha.day} de {_MESES[fecha.month - 1]}"
    return f"{dia} {hora_hablada(fecha)}"
