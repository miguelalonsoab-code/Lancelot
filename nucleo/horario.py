"""
Horario fijo de la semana y horas libres.

Tu horario son BLOQUES que se repiten cada semana:

    "de lunes a viernes de 9am a 6pm trabajo"        -> lun-vie 09:00-18:00 · Trabajo
    "martes y jueves de 7 a 10 de la noche clase de redes"  -> mar, jue 19:00-22:00 · Clase de redes
    "sábados de 8 a 12 inglés"                       -> sáb 08:00-12:00 · Inglés
    "de lunes a viernes de 8:30 a 5:30 trabajo, traslado 45 min"
                                                     -> además resta 45 min antes y 45 min después (el viaje)

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


# --------------------------------------------------------------------------- categorías (v3.22)
CATEGORIAS = ("trabajo", "clase", "otro")
NOMBRE_CATEGORIA = {"trabajo": "Trabajo", "clase": "Clase", "otro": "Otro"}
# El nombre del icono de línea de cada categoría (v3.23: antes eran emoji). Se dibujan en interfaz/iconos.py
# y movil/publico/iconos.js, con la forma de los iconos de Lucide: maletín, birrete y etiqueta.
ICONO_CATEGORIA = {"trabajo": "maletin", "clase": "birrete", "otro": "etiqueta"}
TEXTO_OSCURO, TEXTO_CLARO = "#07112a", "#eaf1ff"


def texto_sobre(color: str) -> str:
    """
    El color del texto que se escribe ENCIMA de un bloque de ese color (v3.23): oscuro sobre colores claros
    (el lavanda de las clases) y claro sobre oscuros. Usa la luminancia relativa de WCAG: así, si cambias los
    colores en config.py, el nombre del bloque se sigue leyendo.
    """
    def lineal(v: int) -> float:
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    n = int(color.lstrip("#")[:6], 16)
    luz = 0.2126 * lineal(n >> 16 & 255) + 0.7152 * lineal(n >> 8 & 255) + 0.0722 * lineal(n & 255)
    return TEXTO_OSCURO if luz > 0.3 else TEXTO_CLARO

# Se compara el PRINCIPIO de cada palabra del título (ya sin tildes ni mayúsculas): "trabaj" cubre
# trabajo/trabajar/trabajando. La primera palabra del título que coincida decide: «Clase de trabajo
# social» es clase, «Trabajo en la universidad» es trabajo. Lo que no coincide queda como «otro».
_RAICES_CATEGORIA = (
    ("trabajo", ("trabaj", "oficina", "turno", "chamba")),
    ("clase", ("clase", "curso", "univers", "upn", "taller", "laborat", "semin")),
)


def inferir_categoria(titulo: str) -> str:
    """'Trabajo en Sanna' -> 'trabajo' · 'Clase de redes' -> 'clase' · 'Inglés' -> 'otro'."""
    for palabra in normalizar(titulo).split():
        for categoria, raices in _RAICES_CATEGORIA:
            if palabra.startswith(raices):
                return categoria
    return "otro"


def heredar_categoria(nuevo: "Bloque", existentes: list["Bloque"]) -> "Bloque":
    """
    v3.23: si ya tienes un bloque con el mismo nombre («Computación Gráfica» el miércoles), el nuevo («… el viernes»)
    toma la categoría que le diste a ese, en vez de la deducida por palabras (que no sabe que un curso es clase).
    """
    clave = normalizar(nuevo.titulo).strip()
    igual = next((b for b in existentes if normalizar(b.titulo).strip() == clave), None)
    if igual:
        nuevo.categoria = igual.categoria
    return nuevo


def buscar_por_nombre(nombre: str, bloques: list["Bloque"]) -> list["Bloque"]:
    """
    v3.24: los bloques a los que se refiere 'nombre' («computación gráfica», «redes»): los que se llaman igual
    (sin tildes ni mayúsculas) y, si no hay ninguno, los que lo contienen. Así «trabajo» encuentra
    «Trabajo en Sanna», pero «clase» no se lleva también «Clase de redes» si tienes un bloque llamado «Clase».
    """
    buscado = " ".join(normalizar(nombre).split())
    if not buscado:
        return []
    iguales = [b for b in bloques if " ".join(normalizar(b.titulo).split()) == buscado]
    return iguales or [b for b in bloques if buscado in normalizar(b.titulo)]


def siguiente_categoria(categoria: str) -> str:
    """Para el botón que cambia la categoría: trabajo -> clase -> otro -> trabajo."""
    return CATEGORIAS[(CATEGORIAS.index(categoria) + 1) % len(CATEGORIAS)] if categoria in CATEGORIAS else "otro"


@dataclass
class Bloque:
    dias: tuple[int, ...]        # 0 = lunes … 6 = domingo
    inicio: time
    fin: time
    titulo: str
    id: int | None = None
    traslado: int = 0            # minutos de viaje: se restan ANTES y DESPUÉS del bloque
    categoria: str = "otro"      # 'trabajo' | 'clase' | 'otro' (v3.22): solo cambia colores y avisos, no las horas libres

    def __post_init__(self):
        if self.categoria not in CATEGORIAS:         # un dato raro (de la base o de la red) nunca rompe la vista
            self.categoria = "otro"

    def describir(self) -> str:
        """'lun a vie 09:00–18:00 · Trabajo' (+ ' · traslado 45 min' si tiene traslado)"""
        texto = f"{describir_dias(self.dias)} {self.inicio:%H:%M}–{self.fin:%H:%M} · {self.titulo}"
        return texto + (f" · traslado {duracion_minutos(self.traslado)}" if self.traslado else "")

    @property
    def cuando(self) -> str:
        """Solo días y horas: 'lun a vie 09:00–18:00'."""
        return f"{describir_dias(self.dias)} {self.inicio:%H:%M}–{self.fin:%H:%M}"


# --------------------------------------------------------------------------- duraciones
_NUM = r"(\d{1,3}|una?|dos|tres|cuatro|media)"
_PATRON_DURACION = re.compile(
    r"\b(?:" + _NUM + r" ?(?:h|hr|hrs|horas?)(?: y (\d{1,2}|media|cuarto)(?: ?(?:min|mins|minutos))?"
    r"| ?(\d{1,2}) ?(?:min|mins|minutos))?"
    r"|(\d{1,3}) ?(?:m|min|mins|minutos)"
    r"|(media hora|hora y media|una hora y media))\b"
)
_NUMEROS = {"un": 1, "una": 1, "dos": 2, "tres": 3, "cuatro": 4}


def leer_duracion(texto: str) -> tuple[int, tuple[int, int]] | None:
    """'45 min' -> 45 · '1 hora y media' -> 90 · 'media hora' -> 30 · '2h 15min' -> 135. Devuelve (minutos, tramo)."""
    m = _PATRON_DURACION.search(texto)
    if not m:
        return None
    horas, extra, extra_min, solo_min, frase = m.groups()
    extra = extra or extra_min
    if frase:
        minutos = 30 if frase == "media hora" else 90
    elif solo_min:
        minutos = int(solo_min)
    else:
        h = 0.5 if horas == "media" else int(horas) if horas.isdigit() else _NUMEROS[horas]
        minutos = int(h * 60) + ({"media": 30, "cuarto": 15}.get(extra) or int(extra or 0))
    return (minutos, m.span()) if 0 < minutos <= 24 * 60 else None


def duracion_minutos(minutos: int) -> str:
    """90 -> '1 h 30 min'."""
    h, m = divmod(int(minutos), 60)
    return f"{h} h {m} min" if h and m else f"{h} h" if h else f"{m} min"


_PATRON_TRASLADO = re.compile(
    r"(?:,\s*|\s)(?:(?:con\s+)?(?:traslado|viaje|transporte)(?: de)?\s+(?P<a>[^,]+?)"
    r"|con\s+(?P<b>[^,]+?)\s+de\s+(?:traslado|viaje|transporte))(?:\s+de ida y vuelta)?(?=,|$)"
)


def _leer_traslado(texto: str) -> tuple[int, tuple[int, int]] | None:
    """', traslado 45 min' / 'con 1 hora de viaje' -> (minutos, tramo)."""
    for m in _PATRON_TRASLADO.finditer(texto):
        if d := leer_duracion(m.group("a") or m.group("b")):
            return d[0], m.span()
    return None


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
    traslado = 0
    if tr := _leer_traslado(t):                      # primero el viaje, para que "45 min" no se lea como hora
        traslado, (a, b) = tr
        t = t[:a] + " " * (b - a) + t[b:]
        texto = texto[:a] + " " * (b - a) + texto[b:]
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
    titulo = titulo[:1].upper() + titulo[1:80]
    return Bloque(dias, inicio, fin, titulo, traslado=traslado, categoria=inferir_categoria(titulo))


# --------------------------------------------------------------------------- excepciones (v3.14)
@dataclass
class Excepcion:
    """Días en que tu horario NO se cumple: "el 1 de noviembre no trabajo", "vacaciones del 20 al 30 de diciembre"."""
    desde: date
    hasta: date                  # inclusive (un solo día: desde == hasta)
    filtro: str                  # "traba" = solo los bloques cuyo título tiene una palabra que empieza así; "" = todos
    titulo: str                  # "No trabajo", "Vacaciones", "Feriado"…
    id: int | None = None

    def describir(self) -> str:
        """'sáb 01/11 · No trabajo' o '20/12–30/12 · Vacaciones'."""
        if self.desde == self.hasta:
            return f"{DIAS_CORTOS[self.desde.weekday()]} {self.desde:%d/%m} · {self.titulo}"
        return f"{self.desde:%d/%m}–{self.hasta:%d/%m} · {self.titulo}"

    def libera(self, dia: date, bloque: Bloque) -> bool:
        """¿Ese día este bloque NO se cumple?"""
        return self.desde <= dia <= self.hasta and coincide(self.filtro, bloque.titulo)


def coincide(filtro: str, titulo: str) -> bool:
    """"traba" coincide con "Trabajo en Sanna"; "" coincide con todo."""
    return not filtro or any(p[:5] == filtro[:5] for p in normalizar(titulo).split() if len(p) >= 4)


def raiz(palabra: str) -> str:
    """Lo que se compara de una palabra: 'trabajo' y 'trabajar' -> 'traba'; 'clases' -> 'clase'."""
    return normalizar(palabra)[:5]


_MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre",
          "octubre", "noviembre", "diciembre"]
_P_MES = r"(?: de (" + "|".join(_MESES) + r"|setiembre))?"
_PATRON_DEL_AL = re.compile(r"\b(?:del?|desde el) (\d{1,2})" + _P_MES + r" (?:al|hasta el) (\d{1,2})" + _P_MES + r"\b")
_PATRON_EL_DIA = re.compile(r"\b(?:el|este|el dia) (\d{1,2})" + _P_MES + r"\b")
_PATRON_NO = re.compile(r"\bno (?:(?:tengo|hay) |(?:voy|asisto) (?:a |al )?(?:la |el )?)?([a-z]{3,})")
_PATRON_TIPO = re.compile(r"\b(vacaciones|feriado|libre)\b")


def _mes(nombre: str | None) -> int | None:
    if not nombre:
        return None
    return 9 if nombre == "setiembre" else _MESES.index(nombre) + 1


def _fecha_proxima(dia: int, mes: int | None, hoy: date) -> date | None:
    """El próximo 'dia' (de 'mes' si se dijo) que no haya pasado."""
    for salto in range(0, 14):
        m = mes or ((hoy.month - 1 + salto) % 12 + 1)
        anio = hoy.year + (hoy.month - 1 + salto) // 12 if not mes else hoy.year
        try:
            f = date(anio, m, dia)
        except ValueError:
            if mes:
                return None
            continue
        if f >= hoy:
            return f
        if mes:
            try:
                return date(hoy.year + 1, m, dia)
            except ValueError:
                return None
    return None


def interpretar_excepcion(texto: str, hoy: date) -> Excepcion | str:
    """
    "el 1 de noviembre no trabajo"            -> 01/11 · solo bloques con "traba…"
    "vacaciones del 20 al 30 de diciembre"    -> 20/12–30/12 · todos tus bloques
    "mañana no tengo clases"                  -> mañana · solo bloques con "clase…"
    "el viernes es feriado" / "el 15 tengo libre" -> ese día, todos tus bloques
    Si falta algo devuelve la explicación (str).
    """
    from nucleo.interprete import interpretar           # aquí: interprete no depende de horario
    t = normalizar(texto)
    desde = hasta = None
    m = _PATRON_DEL_AL.search(t)
    if m:
        mes2 = _mes(m.group(4)) or _mes(m.group(2))
        mes1 = _mes(m.group(2)) or mes2
        hasta = _fecha_proxima(int(m.group(3)), mes2, hoy)
        if hasta and mes1:
            desde = date(hasta.year - (1 if mes1 > hasta.month else 0), mes1, 1)
            try:
                desde = desde.replace(day=int(m.group(1)))
            except ValueError:
                desde = None
        elif hasta:
            desde = _fecha_proxima(int(m.group(1)), None, hoy)
        if desde and hasta and desde > hasta:
            return "La fecha de inicio queda después del final. Revisa el rango (por ejemplo: «del 20 al 30 de diciembre»)."
        resto = t[:m.start()] + " " + t[m.end():]
    else:
        m = _PATRON_EL_DIA.search(t)
        if m and not re.search(r"\b(?:" + "|".join(DIAS) + r"|sabado|domingo)\b", t[:m.start()]):
            desde = hasta = _fecha_proxima(int(m.group(1)), _mes(m.group(2)), hoy)
        else:
            r = interpretar(texto, datetime.combine(hoy, time(0, 1)))
            if r.fecha:
                desde = hasta = r.fecha.date()
        resto = t
    if not desde or not hasta:
        return ("¿Qué día? Escribe la fecha, por ejemplo: «el 1 de noviembre no trabajo» o "
                "«vacaciones del 20 al 30 de diciembre».")
    if (hasta - desde).days > 120:
        return "Es un rango muy largo (más de 4 meses). Revisa las fechas."
    no = _PATRON_NO.search(resto)
    if no:
        original = re.sub(r"\s+", " ", texto.strip())       # normalizar no cambia el largo: se recorta con tildes
        inicio = normalizar(original).find(no.group(0))
        titulo = original[inicio:inicio + len(no.group(0))] if inicio >= 0 else no.group(0)
        return Excepcion(desde, hasta, raiz(no.group(1)), titulo[:1].upper() + titulo[1:60])
    tipo = _PATRON_TIPO.search(resto)
    titulo = {"vacaciones": "Vacaciones", "feriado": "Feriado"}.get(tipo.group(1) if tipo else "", "Día libre")
    return Excepcion(desde, hasta, "", titulo)


# --------------------------------------------------------------------------- libre
def del_dia(dia: date, bloques: list[Bloque], excepciones: list[Excepcion] = ()) -> list[Bloque]:
    """Los bloques que SÍ se cumplen ese día (su día de la semana, menos las excepciones)."""
    return [b for b in bloques if dia.weekday() in b.dias and not any(e.libera(dia, b) for e in excepciones)]


def ocupado(dia: date, bloques: list[Bloque], excepciones: list[Excepcion] = (),
            extras: list[tuple[datetime, datetime, str]] = ()) -> list[tuple[datetime, datetime, str]]:
    """
    Lo ocupado de ese día, ordenado: tus bloques (con traslado, sin los liberados por una excepción)
    y los 'extras' (tareas y eventos con duración, "examen de 8 a 10"): [(inicio, fin, título)].
    """
    salida = [(datetime.combine(dia, b.inicio) - timedelta(minutes=b.traslado),
               datetime.combine(dia, b.fin) + timedelta(minutes=b.traslado), b.titulo)
              for b in del_dia(dia, bloques, excepciones)]
    salida += [x for x in extras if x[0].date() == dia]
    return sorted(salida)


def choque(inicio: datetime, minutos_: int | None, bloques: list[Bloque],
           excepciones: list[Excepcion] = ()) -> Bloque | None:
    """
    El bloque de tu horario que se cruza con algo que empieza en 'inicio' y dura 'minutos_'
    (sin duración: si cae dentro de un bloque). Sin contar traslados. None si no choca.
    """
    fin = inicio + timedelta(minutes=minutos_ or 0)
    for b in del_dia(inicio.date(), bloques, excepciones):
        b_ini, b_fin = datetime.combine(inicio.date(), b.inicio), datetime.combine(inicio.date(), b.fin)
        if (inicio < b_fin and fin > b_ini) if minutos_ else (b_ini <= inicio < b_fin):
            return b
    return None


def huecos(dia: date, bloques: list[Bloque], despertar: int | time, dormir: int | time,
           ahora: datetime | None = None, minimo: int = 30, excepciones: list[Excepcion] = (),
           extras: list[tuple[datetime, datetime, str]] = ()) -> list[tuple[datetime, datetime]]:
    """
    Horas libres de un día: desde que despiertas hasta que te duermes, menos tus bloques (y sus traslados),
    menos los 'extras' (tareas/eventos con duración) y sin los bloques que una excepción libera ese día.
    Si es hoy, empieza desde 'ahora'. Se descartan los huecos de menos de 'minimo' minutos.
    despertar/dormir: hora entera (6) o time (6:30). Si te duermes pasada la medianoche, cuenta hasta las 23:59.
    """
    despertar = despertar if isinstance(despertar, time) else time(despertar)
    dormir = dormir if isinstance(dormir, time) else (time(dormir) if dormir < 24 else time(23, 59))
    if dormir <= despertar:
        dormir = time(23, 59)
    desde = datetime.combine(dia, despertar)
    hasta = datetime.combine(dia, dormir)
    if ahora and ahora.date() == dia:
        desde = max(desde, ahora.replace(second=0, microsecond=0))
    libres, cursor = [], desde
    for ini, fin, _ in ocupado(dia, bloques, excepciones, extras):
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
