"""
Horario fijo de la semana y horas libres.

Tu horario son BLOQUES que se repiten cada semana:

    "de lunes a viernes de 9am a 6pm trabajo"        -> lun-vie 09:00-18:00 · Trabajo
    "martes y jueves de 7 a 10 de la noche clase de redes"  -> mar, jue 19:00-22:00 · Clase de redes
    "sábados de 8 a 12 inglés"                       -> sáb 08:00-12:00 · Inglés

Con esos bloques, huecos() calcula tus horas LIBRES de un día (entre que despiertas y te duermes),
que es la base para que Lancelot te recomiende actividades.

Lógica pura: sin SQLite ni ventanas. Se guarda en la tabla 'horario' (nucleo/almacen.py).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from nucleo.interprete import normalizar

DIAS = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"]
DIAS_CORTOS = ["lun", "mar", "mié", "jue", "vie", "sáb", "dom"]
_P_DIA = r"(?:lunes|martes|miercoles|jueves|viernes|sabados?|domingos?)"


@dataclass
class Bloque:
    dias: tuple[int, ...]        # 0 = lunes … 6 = domingo
    inicio: time
    fin: time
    titulo: str
    id: int | None = None

    def describir(self) -> str:
        """'lun a vie 09:00–18:00 · Trabajo'"""
        return f"{describir_dias(self.dias)} {self.inicio:%H:%M}–{self.fin:%H:%M} · {self.titulo}"


# --------------------------------------------------------------------------- días
_PATRON_DIAS = re.compile(
    r"(?:\b(?:todos los dias|cada dia|diario)\b"
    r"|\b(?:fines? de semana)\b"
    r"|\b(?:de )?" + _P_DIA + r" a " + _P_DIA + r"\b"
    r"|\b(?:(?:los|cada|el) )?" + _P_DIA + r"(?:(?:, ?| y | e )(?:los )?" + _P_DIA + r")*\b)"
)


def _indice(nombre: str) -> int:
    return DIAS.index(nombre[:-1] if nombre in ("sabados", "domingos") else nombre)


def _leer_dias(texto: str) -> tuple[int, ...] | None:
    if re.search(r"todos los dias|cada dia|diario", texto):
        return tuple(range(7))
    if re.search(r"fines? de semana", texto):
        return (5, 6)
    if m := re.search(r"(" + _P_DIA + r") a (" + _P_DIA + r")", texto):
        a, b = _indice(m.group(1)), _indice(m.group(2))
        return tuple(range(a, b + 1)) if a <= b else tuple(list(range(a, 7)) + list(range(0, b + 1)))
    dias = sorted({_indice(d) for d in re.findall(_P_DIA, texto)})
    return tuple(dias) or None


def describir_dias(dias: tuple[int, ...]) -> str:
    """(0,1,2,3,4) -> 'lun a vie'; (1,3) -> 'mar y jue'; todos -> 'todos los días'."""
    d = sorted(dias)
    if len(d) == 7:
        return "todos los días"
    if len(d) >= 3 and d == list(range(d[0], d[-1] + 1)):
        return f"{DIAS_CORTOS[d[0]]} a {DIAS_CORTOS[d[-1]]}"
    nombres = [DIAS_CORTOS[i] for i in d]
    return nombres[0] if len(nombres) == 1 else ", ".join(nombres[:-1]) + " y " + nombres[-1]


# --------------------------------------------------------------------------- horas
_H = r"(\d{1,2})(?::(\d{2}))?(?:\s?(am|pm|a\.m\.|p\.m\.))?"
_PATRON_RANGO = re.compile(
    r"\b(?:de |desde )?(?:las? )?" + _H + r"\s?(?:a|-|–|hasta)\s?(?:las? )?" + _H +
    r"(?: (?:de|en|por) la (manana|tarde|noche))?(?: ?(?:hrs|horas|h)\b)?"
)


def _leer_rango(texto: str) -> tuple[time, time, tuple[int, int]] | str | None:
    """
    'de 9am a 6pm' -> (09:00, 18:00, tramo usado). None si no hay rango;
    "medianoche" si termina al día siguiente (un turno de noche se anota en dos partes).
    """
    m = _PATRON_RANGO.search(texto)
    if not m:
        return None
    h1, m1, ap1, h2, m2, ap2, momento = m.groups()
    h1, h2, m1, m2 = int(h1), int(h2), int(m1 or 0), int(m2 or 0)
    if h1 > 23 or h2 > 24 or m1 > 59 or m2 > 59:
        return None
    ap1 = (ap1 or "").replace(".", "")
    ap2 = (ap2 or "").replace(".", "")
    tarde = ap2 == "pm" or momento in ("tarde", "noche")
    h2 = _ajustar(h2, ap2 or ("pm" if tarde else ""))
    if h2 == 0 and m2 == 0:
        h2 = 24                                      # "hasta las 12am" = hasta la medianoche
    if ap1:
        h1 = _ajustar(h1, ap1)
    elif h1 < 12 and (tarde and h1 + 12 < h2 or (not ap2 and not momento and 1 <= h1 <= 7)):
        h1 += 12                                     # "de 7 a 10 de la noche" -> 19 a 22
    if not ap2 and not momento and h2 < 12 and h2 <= h1:
        h2 += 12                                     # "de 9 a 6" -> 9 a 18
    if not (h1 * 60 + m1 < h2 * 60 + m2 <= 24 * 60):
        return "medianoche"                          # termina al día siguiente
    fin = time(23, 59) if h2 == 24 else time(h2, m2)
    return time(h1, m1), fin, m.span()


def _ajustar(h: int, ampm: str) -> int:
    if ampm == "pm" and h < 12:
        return h + 12
    if ampm == "am" and h == 12:
        return 0
    return h


# --------------------------------------------------------------------------- texto
def interpretar_bloque(texto: str) -> Bloque | str:
    """
    "de lunes a viernes de 9am a 6pm trabajo" -> Bloque.
    Si falta algo devuelve un texto que explica qué (para mostrarlo tal cual).
    """
    t = normalizar(texto)
    rango = _leer_rango(t)
    if rango == "medianoche":
        return ("Ese bloque termina pasada la medianoche. Anótalo en dos partes, por ejemplo: "
                "«lunes de 10pm a 12am turno» y «martes de 12am a 6am turno».")
    if rango is None:
        return "No entendí las horas. Escribe, por ejemplo: «de lunes a viernes de 9am a 6pm trabajo»."
    inicio, fin, (a, b) = rango
    resto = t[:a] + " " * (b - a) + t[b:]
    dias = _leer_dias(resto)
    if not dias:
        return "¿Qué días? Por ejemplo: «de lunes a viernes», «martes y jueves» o «sábados»."
    tramos = [(a, b)] + [m.span() for m in _PATRON_DIAS.finditer(resto)]
    titulo = texto
    for ini, fin_t in sorted(tramos, reverse=True):
        titulo = titulo[:ini] + " " + titulo[fin_t:]
    titulo = re.sub(r"\s+", " ", titulo).strip(" ,.;:-")
    titulo = re.sub(r"^(?:(?:tengo|hay|de|el|los|y)\s+)+", "", titulo, flags=re.I).strip(" ,.;:-") or "Ocupado"
    return Bloque(dias, inicio, fin, titulo[:1].upper() + titulo[1:80])


# --------------------------------------------------------------------------- libre
def ocupado(dia: date, bloques: list[Bloque]) -> list[tuple[datetime, datetime, str]]:
    """Los bloques de ese día, ordenados: [(inicio, fin, título)]."""
    salida = [(datetime.combine(dia, b.inicio), datetime.combine(dia, b.fin), b.titulo)
              for b in bloques if dia.weekday() in b.dias]
    return sorted(salida)


def huecos(dia: date, bloques: list[Bloque], despertar: int, dormir: int,
           ahora: datetime | None = None, minimo: int = 30) -> list[tuple[datetime, datetime]]:
    """
    Horas libres de un día: desde que despiertas hasta que te duermes, menos tus bloques.
    Si es hoy, empieza desde 'ahora'. Se descartan los huecos de menos de 'minimo' minutos.
    """
    desde = datetime.combine(dia, time(despertar))
    hasta = datetime.combine(dia, time(dormir)) if dormir < 24 else datetime.combine(dia, time(23, 59))
    if ahora and ahora.date() == dia:
        desde = max(desde, ahora.replace(second=0, microsecond=0))
    libres, cursor = [], desde
    for ini, fin, _ in ocupado(dia, bloques):
        if ini > cursor:
            libres.append((cursor, min(ini, hasta)))
        cursor = max(cursor, fin)
    if cursor < hasta:
        libres.append((cursor, hasta))
    return [(a, b) for a, b in libres if (b - a) >= timedelta(minutes=minimo)]


def duracion(a: datetime, b: datetime) -> str:
    """'1 h 30 min', '45 min', '3 h'."""
    minutos = int((b - a).total_seconds() // 60)
    h, m = divmod(minutos, 60)
    return f"{h} h {m} min" if h and m else f"{h} h" if h else f"{m} min"


def describir_libre(libres: list[tuple[datetime, datetime]]) -> str:
    """'14:00–16:30 (2 h 30 min) · 19:00–23:00 (4 h)' o 'nada' si no hay."""
    if not libres:
        return "nada"
    return " · ".join(f"{a:%H:%M}–{b:%H:%M} ({duracion(a, b)})" for a, b in libres)


def total_libre(libres: list[tuple[datetime, datetime]]) -> str:
    total = sum(((b - a) for a, b in libres), timedelta())
    return duracion(datetime.min, datetime.min + total)


def hablar_duracion(minutos: int) -> str:
    """Para la voz: 'media hora', 'una hora', '2 horas y 15 minutos', '45 minutos'."""
    h, m = divmod(int(minutos), 60)
    if h == 0:
        return "media hora" if m == 30 else f"{m} minutos"
    horas = "una hora" if h == 1 else f"{h} horas"
    if m == 0:
        return horas
    return f"{horas} y media" if m == 30 else f"{horas} y {m} minutos"


def minutos(libres: list[tuple[datetime, datetime]]) -> int:
    return int(sum(((b - a) for a, b in libres), timedelta()).total_seconds() // 60)
