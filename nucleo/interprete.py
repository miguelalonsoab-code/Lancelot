"""
Intérprete de texto en español -> (título, fecha, repetición).

Ejemplos que entiende:
    "mañana 8pm pagar la luz"
    "en 20 minutos estirar la espalda"
    "el viernes a las 3 llamar al banco"
    "15/10 10:30 entregar informe"
    "cada lunes 9am reunión de equipo"
    "de lunes a viernes a las 7 tomar agua"
    "el 15 de noviembre aniversario"                 -> EVENTO (avisa 1 semana y 1 día antes, y ese día)
    "evento: cena con amigos el sábado, avísame 3 días antes"
    "examen el viernes de 8 a 10"                    -> a las 08:00, dura 2 horas (resta de tus horas libres)
    "reunión mañana a las 3 durante 1 hora"
    "tomar pastilla todos los días a las 10 de la noche"
    "esta noche a las 8 llamar a mamá"

Idea general:
1. Se trabaja sobre una copia del texto en minúsculas y SIN tildes ("mañana" -> "manana").
   Como cada letra se reemplaza por exactamente una letra, las posiciones coinciden
   con el texto original. Eso permite "recortar" del original lo que se reconoció.
2. Cada regla (repetición, tiempo relativo, día, hora) busca su patrón y anota
   el tramo de texto que usó, para que la siguiente regla no lo vuelva a usar.
3. Lo que sobra después de quitar esos tramos es el título de la tarea.
4. Por último se decide si es TAREA o EVENTO (ver _es_evento): un evento avisa además
   con días de anticipación ("avisos previos").

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

NUMEROS_TEXTO = {"un": 1, "una": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6, "siete": 7,
                 "ocho": 8, "nueve": 9, "diez": 10, "quince": 15, "veinte": 20, "treinta": 30}

# Hora que se asume cuando solo se dice el momento del día
HORA_MOMENTO = {"manana": (9, 0), "tarde": (15, 0), "noche": (20, 0)}

# Repeticiones que el planificador sabe manejar (clave -> texto para mostrar)
REPETICIONES = {
    None: "Sin repetir",
    "diaria": "Todos los días",
    "laborables": "Lunes a viernes",
    "semanal": "Cada semana",
    "mensual": "Cada mes",
    "anual": "Cada año",
}

TIPOS = {"tarea": "Tarea", "evento": "Evento"}

# Palabras que convierten algo en EVENTO: cosas que pasan un día (no algo que "haces")
PALABRAS_EVENTO = ("aniversario", "cumpleanos", "cumple", "boda", "matrimonio", "bautizo", "graduacion",
                   "viaje", "vuelo", "examen", "parcial", "exposicion", "sustentacion", "cita", "concierto",
                   "fiesta", "reunion", "entrevista", "conferencia", "evento")
_PALABRA_EVENTO = re.compile(r"\b(?:" + "|".join(PALABRAS_EVENTO) + r")\b")
# Fechas que vuelven cada año: si no dijiste otra repetición, se repiten solas
_PALABRA_ANUAL = re.compile(r"\b(?:aniversario|cumpleanos|cumple)\b")
# Primera palabra que parece un verbo ("estudiar para el examen", "comprar regalo de cumpleaños"):
# entonces es algo que HACES -> tarea, aunque mencione un examen o un cumpleaños
_VERBO = re.compile(r"^(?:ir|[a-z]+(?:ar|er|ir)(?:me|te|le|les|lo|la|los|las|se)?)$")
_NO_VERBOS = {"primer", "tercer", "mujer", "ayer", "taller", "lugar", "hogar", "bar", "alquiler", "familiar",
              "militar", "collar", "altar", "mar", "super", "seminar"}
AVISOS_PREVIOS_POR_DEFECTO = "7,1"        # una semana antes y un día antes (y el mismo día, a su hora)

# Lo aprendido de tus correcciones Tarea/Evento (ver nucleo/aprendizaje.py). La app lo carga al iniciar
# con usar_vocabulario(); las pruebas pueden pasar otro a interpretar(..., vocabulario=...).
#   evento     palabras que también hacen evento ("taller")
#   no_evento  palabras de la lista de arriba que para ti NO son evento ("cita")
#   verbos     primeras palabras que no impiden que sea evento ("ir" en "ir al concierto")
_VOCABULARIO: dict = {}


def usar_vocabulario(vocabulario: dict | None):
    global _VOCABULARIO
    _VOCABULARIO = dict(vocabulario or {})

# Palabras de "relleno" que se quitan del inicio del título
_RELLENO_INICIAL = re.compile(
    r"^(?:recuerdame|recordarme|recordar|avisame|avisarme|anota|anotame|apunta|agrega|"
    r"que|de|del|a|para|y|es)\b\s*"
)


@dataclass
class Interpretacion:
    titulo: str
    fecha: datetime | None          # None = no se encontró ninguna referencia de tiempo
    repeticion: str | None          # una de las claves de REPETICIONES
    tipo: str = "tarea"             # "tarea" | "evento"
    anticipacion: str | None = None  # lo que PEDISTE: "avísame 3 días antes" -> "3"
    duracion: int | None = None     # minutos ("de 8 a 10" -> 120); None = no se dijo

    @property
    def avisos(self) -> str | None:
        """Días de anticipación con que se avisa ("7,1"), o None = solo a su hora."""
        return avisos_previos(self.tipo, self.repeticion, self.anticipacion)


def avisos_previos(tipo: str, repeticion: str | None, pedida: str | None) -> str | None:
    """
    Con cuántos días de anticipación avisar, como texto: "7,1" = una semana antes y un día antes.
    Lo que pediste manda; si no pediste nada, un evento usa el valor por defecto, salvo que se repita
    tan seguido que no tiene sentido (un evento semanal solo avisa un día antes; uno diario, nunca antes).
    """
    if pedida:
        return pedida
    if tipo != "evento" or repeticion in ("diaria", "laborables"):
        return None
    return "1" if repeticion == "semanal" else AVISOS_PREVIOS_POR_DEFECTO


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
    (re.compile(r"\b(?:cada ano|todos los anos|anualmente|anual)\b"), "anual"),
]

# "de 8 a 10", "desde las 7 hasta las 9 de la noche", "14:00-16:30": hora de inicio + duración
_H = r"(\d{1,2})(?::(\d{2}))?(?:\s?(am|pm|a\.m\.|p\.m\.))?"
PATRON_RANGO_HORAS = re.compile(
    r"\b(?:de|desde) (?:las? )?" + _H + r" (?:a|hasta) (?:las? )?" + _H +
    r"(?: (?:de|en|por) la (manana|tarde|noche))?(?: ?(?:hrs|horas|h)\b)?"
)
PATRON_RANGO_GUION = re.compile(r"\b(\d{1,2}):(\d{2}) ?- ?(\d{1,2}):(\d{2})\b")
# "durante 2 horas", "por 45 minutos", "por una hora y media"
PATRON_DURACION = re.compile(
    r"\b(?:durante|por) (\d{1,3}|una?|dos|tres|cuatro|cinco|media) ?(horas?|hrs?|h|minutos?|mins?)( y media)?\b"
)

# "evento: …" al inicio = es un evento, lo diga o no la palabra clave ("evento de la empresa" se queda en el título)
PATRON_MARCA_EVENTO = re.compile(r"^\s*(?:(?:anota|agrega|apunta|crea|nuevo|un) )?evento(?:\s*:\s*|\s*,\s*|\s+(?!de\b|del\b))")
PATRON_MARCA_TAREA = re.compile(r"^\s*(?:nueva )?tarea\s*:\s*")
# "avísame 3 días antes", "con una semana de anticipación", "2 semanas antes"
PATRON_ANTICIPACION = re.compile(
    r"(?:\b(?:y )?(?:avisame|avisarme|recuerdame|recordarme|recuerdamelo|avisamelo) )?(?:\bcon )?"
    r"\b(\d{1,3}|un|una|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez|quince|veinte|treinta) "
    r"(dias?|semanas?) (?:antes|de anticipacion)\b"
)

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


def interpretar(texto: str, ahora: datetime | None = None, vocabulario: dict | None = None) -> Interpretacion:
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

    duracion = None            # minutos, si se dijo "de 8 a 10" o "durante 2 horas"
    tipo = None                # "evento" / "tarea" si se dijo explícito
    anticipacion = None
    repeticion = None
    dia_semana = None          # 0-6 si se dijo "el lunes" o "cada lunes"
    dia: date | None = None
    relativo: timedelta | None = None
    momento = None             # "manana" / "tarde" / "noche" como pista
    hora = None                # (h, m, decidida) -> decidida=False si es ambigua

    # 0) ¿Evento o tarea dicho explícito? ¿Con cuánta anticipación avisar? ------
    if m := buscar(PATRON_MARCA_EVENTO):
        usar(m)
        tipo = "evento"
    elif m := buscar(PATRON_MARCA_TAREA):
        usar(m)
        tipo = "tarea"
    if m := buscar(PATRON_ANTICIPACION):
        usar(m)
        anticipacion = _anticipacion(m.group(1), m.group(2))
    if m := buscar(PATRON_DURACION):
        usar(m)
        duracion = _a_minutos_duracion(m.group(1), m.group(2), m.group(3))

    # 1) Repetición ----------------------------------------------------------
    for patron, clave in PATRONES_REPETICION:
        if m := buscar(patron):
            usar(m)
            repeticion = clave
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

    # 4) Hora (un rango "de 8 a 10" trae la hora Y la duración) -------------------
    if relativo is None:
        rango = None
        if m := buscar(PATRON_RANGO_HORAS):
            rango = _resolver_rango(*m.groups())
        elif m := buscar(PATRON_RANGO_GUION):
            h1, m1, h2, m2 = (int(x) for x in m.groups())
            rango = (h1, m1, h2, m2) if h1 < 24 and h2 < 24 and m1 < 60 and m2 < 60 else None
        if rango and (h2m := rango[2] * 60 + rango[3]) > (h1m := rango[0] * 60 + rango[1]):
            usar(m)
            hora = (rango[0], rango[1], True)
            duracion = h2m - h1m
        if hora is not None:
            pass                                       # ya la dio el rango
        elif m := buscar(PATRON_MEDIODIA):
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
    titulo = _limpiar_titulo(texto, tramos)

    # 6) ¿Tarea o evento? -------------------------------------------------------
    tipo = tipo or ("evento" if es_evento(titulo, _VOCABULARIO if vocabulario is None else vocabulario) else "tarea")
    if tipo == "evento" and repeticion is None and _PALABRA_ANUAL.search(normalizar(titulo)):
        repeticion = "anual"                        # un cumpleaños vuelve cada año
    return Interpretacion(titulo=titulo, fecha=fecha, repeticion=repeticion, tipo=tipo, anticipacion=anticipacion,
                          duracion=duracion)


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


def describir_faltan(fecha: datetime, ahora: datetime | None = None) -> str:
    """Para eventos: 'hoy', 'mañana', 'faltan 5 días', 'falta 1 semana'."""
    ahora = ahora or datetime.now()
    dias = (fecha.date() - ahora.date()).days
    if dias <= 0:
        return "hoy"
    if dias == 1:
        return "mañana"
    if dias % 7 == 0 and dias <= 28:
        semanas = dias // 7
        return "falta 1 semana" if semanas == 1 else f"faltan {semanas} semanas"
    return f"faltan {dias} días"


def describir_avisos(avisos: str | None) -> str:
    """'7,1' -> 'avisa 7 y 1 día antes'. Para mostrar en el panel."""
    if not avisos:
        return ""
    dias = avisos.split(",")
    texto = " y ".join(dias) if len(dias) <= 2 else ", ".join(dias[:-1]) + " y " + dias[-1]
    return f"avisa {texto} día{'s' if dias != ['1'] else ''} antes"


def describir_atraso(fecha: datetime, ahora: datetime | None = None) -> str:
    """Cuánto hace que venció: 'venció hace 12 min', 'venció ayer 20:00', 'venció hace 3 días'."""
    ahora = ahora or datetime.now()
    minutos = int((ahora - fecha).total_seconds() // 60)
    dias = (ahora.date() - fecha.date()).days
    if minutos < 60:
        return f"venció hace {max(minutos, 1)} min"
    if dias == 0:
        return f"venció hoy {fecha:%H:%M}"
    if dias == 1:
        return f"venció ayer {fecha:%H:%M}"
    abrev = ["lun", "mar", "mié", "jue", "vie", "sáb", "dom"][fecha.weekday()]
    return f"venció hace {dias} días ({abrev} {fecha:%d/%m})"


# ---------------------------------------------------------------------------
# Ayudantes internos
# ---------------------------------------------------------------------------
def _indice_dia(nombre: str) -> int:
    if nombre in ("sabados", "domingos"):
        nombre = nombre[:-1]
    return DIAS_SEMANA.index(nombre)


def _ajustar_ampm(h: int, ampm: str) -> int:
    if ampm == "pm" and h < 12:
        return h + 12
    if ampm == "am" and h == 12:
        return 0
    return h


def _resolver_rango(h1, m1, ap1, h2, m2, ap2, momento):
    """
    "de 7 a 10 de la noche" -> (19, 0, 22, 0). Mismas reglas que el horario (nucleo/horario.py):
    sin am/pm, de 1 a 7 es de la tarde ("de 2 a 4" = 14 a 16) y el final nunca queda antes del inicio
    ("de 9 a 6" = 9 a 18). None si no tiene sentido.
    """
    h1, h2, m1, m2 = int(h1), int(h2), int(m1 or 0), int(m2 or 0)
    if h1 > 23 or h2 > 24 or m1 > 59 or m2 > 59:
        return None
    ap1, ap2 = (ap1 or "").replace(".", ""), (ap2 or "").replace(".", "")
    tarde = ap2 == "pm" or momento in ("tarde", "noche")
    h2 = _ajustar_ampm(h2, ap2 or ("pm" if tarde else ""))
    if h2 == 0 and m2 == 0:
        h2 = 24                                       # "hasta las 12am" = medianoche
    if ap1:
        h1 = _ajustar_ampm(h1, ap1)
    elif h1 < 12 and (tarde and h1 + 12 < h2 or (not ap2 and not momento and 1 <= h1 <= 7)):
        h1 += 12
    if not ap2 and not momento and h2 < 12 and h2 <= h1:
        h2 += 12
    if h2 == 24:
        h2, m2 = 23, 59
    return (h1, m1, h2, m2) if h2 < 24 else None


def _a_minutos_duracion(cantidad: str, unidad: str, y_media: str | None) -> int | None:
    n = 0.5 if cantidad == "media" else _numero(cantidad)
    minutos = int(n * 60) if unidad.startswith("h") else int(n)
    if y_media and unidad.startswith("h"):
        minutos += 30
    return minutos if 0 < minutos <= 24 * 60 else None


def describir_rango(fecha: datetime, duracion: int | None) -> str:
    """'08:00–10:00' si tiene duración; si no, '08:00'."""
    if not duracion:
        return f"{fecha:%H:%M}"
    return f"{fecha:%H:%M}–{fecha + timedelta(minutes=duracion):%H:%M}"


def _numero(cantidad: str) -> int:
    return int(cantidad) if cantidad.isdigit() else NUMEROS_TEXTO.get(cantidad, 1)


def _anticipacion(cantidad: str, unidad: str) -> str | None:
    dias = _numero(cantidad) * (7 if unidad.startswith("semana") else 1)
    return str(dias) if 1 <= dias <= 365 else None


def palabras_de_evento(titulo: str, vocabulario: dict | None = None) -> list[str]:
    """Las palabras del título que lo hacen evento, según la lista de fábrica y lo aprendido."""
    v = vocabulario or {}
    t = normalizar(titulo)
    fabrica = [w for w in _PALABRA_EVENTO.findall(t) if w not in v.get("no_evento", ())]
    aprendidas = [w for w in v.get("evento", ()) if re.search(rf"\b{re.escape(w)}\b", t)]
    return list(dict.fromkeys(fabrica + aprendidas))


def primera_palabra(titulo: str) -> str:
    return re.match(r"[a-z]*", normalizar(titulo)).group(0)


def parece_verbo(palabra: str) -> bool:
    return bool(_VERBO.match(palabra)) and palabra not in _NO_VERBOS


def es_evento(titulo: str, vocabulario: dict | None = None) -> bool:
    """Menciona un aniversario, examen, cita… y NO empieza con un verbo ("estudiar para el examen")."""
    claves = palabras_de_evento(titulo, vocabulario)
    if not claves:
        return False
    primera = primera_palabra(titulo)
    if primera in claves or primera in (vocabulario or {}).get("verbos", ()):
        return True
    return not parece_verbo(primera)


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
