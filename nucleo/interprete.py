"""
Intérprete de texto en español -> (título, fecha, repetición).

Ejemplos que entiende:
    "mañana 8pm pagar la luz"
    "en 20 minutos estirar la espalda"
    "el viernes a las 3 llamar al banco"
    "15/10 10:30 entregar informe"
    "cada lunes 9am reunión de equipo"
    "de lunes a viernes a las 7 tomar agua"
    "tomar pastilla todos los días a las 10 de la noche"
    "esta noche a las 8 llamar a mamá"

Idea general:
1. Se trabaja sobre una copia del texto en minúsculas y SIN tildes ("mañana" -> "manana").
   Como cada letra se reemplaza por exactamente una letra, las posiciones coinciden
   con el texto original. Eso permite "recortar" del original lo que se reconoció.
2. Cada regla (repetición, tiempo relativo, día, hora) busca su patrón y anota
   el tramo de texto que usó, para que la siguiente regla no lo vuelva a usar.
3. Lo que sobra después de quitar esos tramos es el título de la tarea.

No se usa ninguna librería externa a propósito: el comportamiento es predecible
y cada regla se puede explicar.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from config import HORA_POR_DEFECTO

# ---------------------------------------------------------------------------
# Tablas de apoyo
# ---------------------------------------------------------------------------
_SIN_TILDES = str.maketrans("áéíóúüñ", "aeiouun")

DIAS_SEMANA = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"]
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre"]

NUMEROS_TEXTO = {"un": 1, "una": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5,
                 "diez": 10, "quince": 15, "veinte": 20, "treinta": 30}

# Hora que se asume cuando solo se dice el momento del día
HORA_MOMENTO = {"manana": (9, 0), "tarde": (15, 0), "noche": (20, 0)}

# Repeticiones que el planificador sabe manejar (clave -> texto para mostrar)
REPETICIONES = {
    None: "Sin repetir",
    "diaria": "Todos los días",
    "laborables": "Lunes a viernes",
    "semanal": "Cada semana",
    "mensual": "Cada mes",
}

# Palabras de "relleno" que se quitan del inicio del título
_RELLENO_INICIAL = re.compile(
    r"^(?:recuerdame|recordarme|recordar|avisame|avisarme|anota|anotame|apunta|agrega|"
    r"que|de|a|para|y)\b\s*"
)


@dataclass
class Interpretacion:
    titulo: str
    fecha: datetime | None          # None = no se encontró ninguna referencia de tiempo
    repeticion: str | None          # una de las claves de REPETICIONES


# ---------------------------------------------------------------------------
# Patrones (se aplican sobre el texto normalizado: minúsculas y sin tildes)
# ---------------------------------------------------------------------------
_P_DIA = r"(lunes|martes|miercoles|jueves|viernes|sabados?|domingos?)"

PATRONES_REPETICION = [
    (re.compile(r"\b(?:todos los dias|cada dia|diariamente|a diario|diario)\b"), "diaria"),
    (re.compile(r"\b(?:de lunes a viernes|dias laborables|entre semana)\b"), "laborables"),
    (re.compile(r"\b(?:cada|todos los) " + _P_DIA + r"\b"), "semanal"),  # captura el día
    (re.compile(r"\b(?:cada semana|semanalmente|semanal)\b"), "semanal"),
    (re.compile(r"\b(?:cada mes|mensualmente|mensual)\b"), "mensual"),
]

# "en 20 minutos", "dentro de 2 horas", "en media hora", "en 5m"
PATRON_RELATIVO = re.compile(
    r"\b(?:en|dentro de) (\d+|un|una|dos|tres|cuatro|cinco|diez|quince|veinte|treinta|media) ?"
    r"(minutos?|mins?|m|horas?|hrs?|h|dias?)\b"
)

PATRON_PASADO_MANANA = re.compile(r"\bpasado manana\b")
PATRON_MANANA = re.compile(r"(?<!la )\bmanana\b")      # día, pero NO "de la mañana"
PATRON_HOY = re.compile(r"\b(?:hoy|esta (tarde|noche))\b")
PATRON_DIA_SEMANA = re.compile(r"\b(?:(?:el|este|el proximo|proximo) )?" + _P_DIA + r"\b")
PATRON_FECHA_NUM = re.compile(r"\b(?:el )?(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?\b")
PATRON_FECHA_TEXTO = re.compile(
    r"\b(?:el )?(\d{1,2}) de (" + "|".join(MESES) + r")(?: (?:de|del) (\d{4}))?\b"
)

PATRON_MEDIODIA = re.compile(r"\b(?:al |a (?:la )?)?(mediodia|medianoche)\b")
# "a las 8", "8pm", "20:30", "a la 1 y media", "a las 7 de la noche", "18 hrs"
PATRON_HORA = re.compile(
    r"(?P<prefijo>\b(?:a las?|a eso de las?|tipo|como a las?) )?"
    r"\b(?P<h>\d{1,2})(?::(?P<m>\d{2}))?"
    r"(?: y (?P<fraccion>media|cuarto|\d{1,2}))?"
    r"(?:\s?(?P<ampm>am|pm|a\.m\.|p\.m\.))?"
    r"(?: (?:de|en|por) la (?P<momento>manana|tarde|noche))?"
    r"(?P<sufijo> ?(?:hrs|horas|h)\b)?"
)
# "por la tarde", "en la noche" sin número
PATRON_MOMENTO = re.compile(r"\b(?:en|por|de) la (manana|tarde|noche)\b")


# ---------------------------------------------------------------------------
# Funciones públicas
# ---------------------------------------------------------------------------
def normalizar(texto: str) -> str:
    """Minúsculas y sin tildes, conservando la longitud del texto."""
    return texto.lower().translate(_SIN_TILDES)


def interpretar(texto: str, ahora: datetime | None = None) -> Interpretacion:
    ahora = (ahora or datetime.now()).replace(second=0, microsecond=0)
    t = normalizar(texto)
    tramos: list[tuple[int, int]] = []     # partes del texto ya reconocidas

    def libre(ini: int, fin: int) -> bool:
        return all(fin <= a or ini >= b for a, b in tramos)

    def buscar(patron: re.Pattern):
        """Primer match que no se cruce con algo ya reconocido."""
        for m in patron.finditer(t):
            if libre(*m.span()):
                return m
        return None

    def usar(m: re.Match):
        tramos.append(m.span())
        return m

    repeticion = None
    dia_semana = None          # 0-6 si se dijo "el lunes" o "cada lunes"
    dia: date | None = None
    relativo: timedelta | None = None
    momento = None             # "manana" / "tarde" / "noche" como pista
    hora = None                # (h, m, decidida) -> decidida=False si es ambigua

    # 1) Repetición ----------------------------------------------------------
    for patron, tipo in PATRONES_REPETICION:
        if m := buscar(patron):
            usar(m)
            repeticion = tipo
            if m.groups():
                dia_semana = _indice_dia(m.group(1))
            break

    # 2) Tiempo relativo ("en 20 min") ---------------------------------------
    if m := buscar(PATRON_RELATIVO):
        usar(m)
        relativo = _a_timedelta(m.group(1), m.group(2))

    # 3) Día -------------------------------------------------------------------
    if relativo is None:
        if m := buscar(PATRON_PASADO_MANANA):
            usar(m)
            dia = ahora.date() + timedelta(days=2)
        elif m := buscar(PATRON_MANANA):
            usar(m)
            dia = ahora.date() + timedelta(days=1)
        elif m := buscar(PATRON_HOY):
            usar(m)
            dia = ahora.date()
            momento = m.group(1)                      # "esta noche" -> noche
        elif (m := buscar(PATRON_FECHA_TEXTO)) and (
                d := _fecha_valida(int(m.group(1)), MESES.index(m.group(2)) + 1, m.group(3), ahora)):
            usar(m)
            dia = d
        elif (m := buscar(PATRON_FECHA_NUM)) and (
                d := _fecha_valida(int(m.group(1)), int(m.group(2)), m.group(3), ahora)):
            usar(m)
            dia = d
        elif m := buscar(PATRON_DIA_SEMANA):
            usar(m)
            dia_semana = _indice_dia(m.group(1))

    # 4) Hora ------------------------------------------------------------------
    if relativo is None:
        if m := buscar(PATRON_MEDIODIA):
            usar(m)
            hora = (12, 0, True) if m.group(1) == "mediodia" else (0, 0, True)
        else:
            for m in PATRON_HORA.finditer(t):
                if libre(*m.span()) and (h := _hora_desde_match(m)):
                    usar(m)
                    hora = h
                    break
        if m := buscar(PATRON_MOMENTO):               # "por la tarde" suelto
            usar(m)
            momento = momento or m.group(1)

    hora_final = _resolver_hora(hora, momento)

    # 5) Combinar todo en una fecha ---------------------------------------------
    fecha = _combinar(ahora, dia, dia_semana, hora_final, relativo, repeticion)
    return Interpretacion(titulo=_limpiar_titulo(texto, tramos), fecha=fecha, repeticion=repeticion)


def describir_fecha(fecha: datetime, ahora: datetime | None = None) -> str:
    """Texto corto y humano: 'hoy 20:00', 'mañana 09:00', 'vie 10/10 15:00'."""
    ahora = ahora or datetime.now()
    hora = fecha.strftime("%H:%M")
    dias = (fecha.date() - ahora.date()).days
    if fecha < ahora:
        return f"atrasada · {fecha.strftime('%d/%m')} {hora}"
    if dias == 0:
        return f"hoy {hora}"
    if dias == 1:
        return f"mañana {hora}"
    abrev = ["lun", "mar", "mié", "jue", "vie", "sáb", "dom"][fecha.weekday()]
    return f"{abrev} {fecha.strftime('%d/%m')} {hora}"


# ---------------------------------------------------------------------------
# Ayudantes internos
# ---------------------------------------------------------------------------
def _indice_dia(nombre: str) -> int:
    if nombre in ("sabados", "domingos"):
        nombre = nombre[:-1]
    return DIAS_SEMANA.index(nombre)


def _a_timedelta(cantidad: str, unidad: str) -> timedelta:
    if cantidad == "media":
        n = 0.5
    elif cantidad.isdigit():
        n = int(cantidad)
    else:
        n = NUMEROS_TEXTO.get(cantidad, 1)
    if unidad.startswith("m"):
        return timedelta(minutes=n)
    if unidad.startswith("h"):
        return timedelta(hours=n)
    return timedelta(days=n)


def _fecha_valida(d: int, mes: int, anio: str | None, ahora: datetime) -> date | None:
    try:
        if anio:
            a = int(anio)
            return date(a + 2000 if a < 100 else a, mes, d)
        candidata = date(ahora.year, mes, d)
        if candidata < ahora.date():               # ya pasó este año -> el próximo
            candidata = date(ahora.year + 1, mes, d)
        return candidata
    except ValueError:
        return None                                # 31/02 o "2/45": no es fecha


def _hora_desde_match(m: re.Match):
    """
    Devuelve (hora, minutos, decidida) o None.
    Un número suelto ("comprar 2 panes") NO es una hora: solo se acepta si trae
    alguna pista ("a las", ":30", am/pm, "de la tarde", "y media", "hrs").
    'decidida' indica si ya sabemos si es AM o PM.
    """
    if not any(m.group(g) for g in ("prefijo", "m", "ampm", "momento", "fraccion", "sufijo")):
        return None
    h = int(m.group("h"))
    minutos = int(m.group("m") or 0)
    fraccion = m.group("fraccion")
    if fraccion:          # "y media", "y cuarto" o "y 40" (cuando se dicta por voz)
        minutos = {"media": 30, "cuarto": 15}.get(fraccion) or int(fraccion)
    if h > 23 or minutos > 59:
        return None

    ampm = (m.group("ampm") or "").replace(".", "")
    momento = m.group("momento")
    if ampm == "pm" or momento in ("tarde", "noche"):
        return (h + 12 if h < 12 else h), minutos, True
    if ampm == "am" or momento == "manana":
        return (0 if h == 12 else h), minutos, True
    # "20:30" o "13 hrs" ya son inequívocos; "a las 8" no
    return h, minutos, h >= 13 or h == 0


def _resolver_hora(hora, momento):
    """Decide AM/PM cuando la hora quedó ambigua ("a las 8")."""
    if hora is None:
        return HORA_MOMENTO.get(momento)           # puede quedar None
    h, mi, decidida = hora
    if not decidida:
        if momento in ("tarde", "noche") and h < 12:
            h += 12
        elif momento is None and 1 <= h <= 7:
            h += 12                                 # "a las 3" casi siempre es 15:00
    return h, mi


def _combinar(ahora, dia, dia_semana, hora, relativo, repeticion) -> datetime | None:
    if relativo is not None:
        return ahora + relativo
    if dia is None and dia_semana is None and hora is None and repeticion is None:
        return None                                 # no se dijo nada de tiempo

    h, mi = hora or HORA_POR_DEFECTO
    dia_explicito = dia is not None
    if dia is None:
        dia = ahora.date()
        if dia_semana is not None:                  # "el viernes" / "cada lunes"
            dia += timedelta(days=(dia_semana - dia.weekday()) % 7)
        elif repeticion == "laborables":
            while dia.weekday() >= 5:
                dia += timedelta(days=1)

    fecha = datetime.combine(dia, datetime.min.time()).replace(hour=h, minute=mi)

    # Si quedó en el pasado, se mueve a la siguiente ocasión que tenga sentido
    if fecha <= ahora and not dia_explicito:
        if dia_semana is not None:
            fecha += timedelta(days=7)
        else:
            fecha += timedelta(days=1)
            while repeticion == "laborables" and fecha.weekday() >= 5:
                fecha += timedelta(days=1)
    elif fecha <= ahora and fecha.date() == ahora.date():
        fecha += timedelta(days=1)                  # "hoy 8am" cuando ya son las 10
    return fecha


def _limpiar_titulo(original: str, tramos: list[tuple[int, int]]) -> str:
    texto = original
    for ini, fin in sorted(tramos, reverse=True):   # de atrás hacia adelante
        texto = texto[:ini] + " " + texto[fin:]
    texto = re.sub(r"\s+", " ", texto).strip(" ,.;:-")
    # Quitar relleno del inicio ("recuérdame que ...")
    while (nuevo := _RELLENO_INICIAL.sub("", normalizar(texto))) != normalizar(texto):
        texto = texto[len(texto) - len(nuevo):]
    # Conectores que quedaron colgando al final
    texto = re.sub(r"\s+(?:a las?|el|de|para|a|y)$", "", texto, flags=re.IGNORECASE)
    texto = texto.strip(" ,.;:-")
    return texto[:1].upper() + texto[1:]
