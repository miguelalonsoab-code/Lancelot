"""
Recomendaciones (v3.15): qué hacer en tus horas libres.

Junta lo que Lancelot ya sabe de ti:
    - tus horas libres del día (horario fijo + excepciones + tareas con duración)  -> nucleo/horario.py
    - tu meta de estudio diaria y cuánto estudiaste hoy                           -> modo estudio
    - tus actividades ("gimnasio 1 h, 3 veces por semana, en la tarde") y cuántas veces las hiciste esta semana

y arma un plan corto:

    18:15–19:15 · Gimnasio (llevas 1 de 3 esta semana)
    19:25–21:05 · Estudiar (te faltan 1 h 40 min para tu meta)

Cómo decide (de más a menos importante):
    1. Estudiar, si no llegaste a tu meta de hoy (en sesiones de hasta 100 min).
    2. Las actividades con meta semanal, primero las más "atrasadas": te faltan 2 de 3 y quedan 2 días
       es más urgente que te falta 1 de 3 y quedan 5 días.
    3. Las actividades sin meta, solo si sobra tiempo.
Cada cosa va en el primer hueco donde entra entera, en su momento preferido (mañana, tarde, noche)
si se puede; si no, en cualquier hueco, avisando que no es su momento. Entre una y otra deja una pausa.

Lógica pura: sin SQLite ni ventanas (se prueba sola en tests/test_v315.py).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from nucleo.hablado import hora_hablada
from nucleo.horario import duracion_minutos
from nucleo.interprete import normalizar
from nucleo.perfil import Actividad

# Horas de cada momento del día (fin exclusivo)
MOMENTO_HORAS = {"manana": (5, 12), "tarde": (12, 19), "noche": (19, 24)}
NOMBRE_MOMENTO = {"manana": "la mañana", "tarde": "la tarde", "noche": "la noche"}
SESION_ESTUDIO = 100          # minutos máximos de una sesión de estudio sugerida
ESTUDIO_MINIMO = 25           # si no entra la sesión entera, al menos esto (un pomodoro)


@dataclass
class Sugerencia:
    nombre: str
    inicio: datetime
    fin: datetime
    motivo: str                       # "llevas 1 de 3 esta semana"
    clase: str = "actividad"          # "estudio" | "actividad"
    actividad_id: int | None = None

    def describir(self) -> str:
        """'18:15–19:15 · Gimnasio (llevas 1 de 3 esta semana)'"""
        return f"{self.inicio:%H:%M}–{self.fin:%H:%M} · {self.nombre} ({self.motivo})"


@dataclass
class Plan:
    sugerencias: list[Sugerencia]
    sin_lugar: list[str]              # lo que te convenía hacer pero no entra hoy

    def __bool__(self) -> bool:
        return bool(self.sugerencias)


@dataclass
class _Candidato:
    nombre: str
    minutos: int
    prioridad: float
    motivo: str
    clase: str
    momento: str | None = None
    actividad_id: int | None = None
    minimo: int | None = None         # si no entra entero, se acepta hasta este largo


def momento_de(fecha: datetime) -> str:
    """'manana' | 'tarde' | 'noche' según la hora (de madrugada cuenta como noche)."""
    for nombre, (a, b) in MOMENTO_HORAS.items():
        if a <= fecha.hour < b:
            return nombre
    return "noche"


def clave(nombre: str) -> str:
    """Cómo se guarda un nombre para aprender de él: 'Gimnasio' -> 'gimnasio'."""
    return normalizar(nombre).strip()


def lunes_de(dia: date) -> date:
    return dia - timedelta(days=dia.weekday())


def _candidatos(dia: date, actividades: list[Actividad], hechas_semana: dict[int, int], hechas_hoy: set[int],
                estudio_hoy: int, meta_estudio: int) -> list[_Candidato]:
    salida = []
    falta = meta_estudio - estudio_hoy
    sesion = 1
    while falta >= 15 and sesion <= 2:
        m = min(falta, SESION_ESTUDIO)
        motivo = (f"te faltan {duracion_minutos(meta_estudio - estudio_hoy)} para tu meta" if sesion == 1
                  else "segunda parte de tu meta")
        salida.append(_Candidato("Estudiar", m, 2.0 if sesion == 1 else 0.6, motivo, "estudio",
                                 minimo=min(m, ESTUDIO_MINIMO)))
        falta -= m
        sesion += 1
    quedan_dias = 7 - dia.weekday()                       # contando hoy: lunes 7 … domingo 1
    for a in actividades:
        if a.id in hechas_hoy:
            continue                                      # ya la hiciste hoy
        if a.veces_semana:
            hechas = hechas_semana.get(a.id, 0)
            faltan = a.veces_semana - hechas
            if faltan <= 0:
                continue                                  # meta de la semana cumplida
            urgencia = min(faltan / quedan_dias, 1.5)     # 1 = hay que hacerla todos los días que quedan
            motivo = f"llevas {hechas} de {a.veces_semana} esta semana"
            salida.append(_Candidato(a.nombre, a.minutos, 0.3 + urgencia, motivo, "actividad", a.momento, a.id))
        else:
            salida.append(_Candidato(a.nombre, a.minutos, 0.2, "te gusta y hoy hay tiempo", "actividad",
                                     a.momento, a.id))
    return sorted(salida, key=lambda c: -c.prioridad)    # sorted es estable: a igual prioridad, el orden de antes


def _ventana(dia: date, momento: str | None) -> tuple[datetime, datetime]:
    if not momento:
        return datetime.combine(dia, time(0)), datetime.combine(dia, time(23, 59))
    a, b = MOMENTO_HORAS[momento]
    return datetime.combine(dia, time(a)), datetime.combine(dia, time(23, 59) if b == 24 else time(b))


def _ubicar(libres: list[tuple[datetime, datetime]], minutos: int, desde: datetime,
            hasta: datetime) -> datetime | None:
    """Primer inicio posible para 'minutos' dentro de un hueco y de la ventana [desde, hasta]."""
    for a, b in libres:
        ini, fin = max(a, desde), min(b, hasta)
        if fin - ini >= timedelta(minutes=minutos):
            return ini
    return None


def _ocupar(libres: list[tuple[datetime, datetime]], ini: datetime, fin: datetime,
            pausa: int) -> list[tuple[datetime, datetime]]:
    """Saca [ini, fin] (+ la pausa de después) de los huecos; los pedacitos de menos de 15 min se descartan."""
    salida = []
    corte = fin + timedelta(minutes=pausa)
    for a, b in libres:
        if b <= ini or a >= corte:
            salida.append((a, b))
            continue
        for x, y in ((a, ini), (corte, b)):
            if y - x >= timedelta(minutes=15):
                salida.append((x, y))
    return salida


def _sin_momentos(dia: date, libres: list[tuple[datetime, datetime]],
                  momentos: set[str]) -> list[tuple[datetime, datetime]]:
    """Los huecos sin las partes que caen en esos momentos del día (los que rechazaste)."""
    for m in momentos:
        desde, hasta = _ventana(dia, m)
        libres = _ocupar(libres, desde, hasta, 0)
    return libres


def _ubicar_candidato(dia: date, libres: list[tuple[datetime, datetime]], c: _Candidato,
                      solo_su_momento: bool = False, evitar: set[str] = frozenset()) -> Sugerencia | None:
    motivo, minutos = c.motivo, c.minutos
    if evitar:
        libres = _sin_momentos(dia, libres, evitar)
    inicio = _ubicar(libres, minutos, *_ventana(dia, c.momento))
    if solo_su_momento and inicio is None:
        return None
    if inicio is None and c.momento:                      # no entra en su momento: en cualquier hueco
        inicio = _ubicar(libres, minutos, *_ventana(dia, None))
        if inicio is not None:
            motivo += f"; no hay hueco en {NOMBRE_MOMENTO[c.momento]}"
    if inicio is None and c.minimo:                       # estudio: mejor un poco que nada
        for a, b in libres:
            largo = int((b - a).total_seconds() // 60)
            if largo >= c.minimo:
                inicio, minutos = a, min(largo, c.minutos)
                break
    if inicio is None:
        return None
    return Sugerencia(c.nombre, inicio, inicio + timedelta(minutes=minutos), motivo, c.clase, c.actividad_id)


def _ubicar_rondas(dia: date, libres: list[tuple[datetime, datetime]], rondas: list, maximo: int,
                   pausa: int, evitar: dict[str, set[str]]) -> tuple[list[tuple[Sugerencia, _Candidato]], set[int]]:
    hechas, ubicados = [], set()
    for grupo, solo_su_momento in rondas:
        for c in grupo:
            if id(c) in ubicados or len(hechas) >= maximo:
                continue
            s = _ubicar_candidato(dia, libres, c, solo_su_momento, evitar.get(clave(c.nombre), set()))
            if s:
                ubicados.add(id(c))
                hechas.append((s, c))
                libres = _ocupar(libres, s.inicio, s.fin, pausa)
    return hechas, ubicados


def _puntaje(hechas: list[tuple[Sugerencia, _Candidato]], elegidos: list[_Candidato]) -> float:
    """Importancia de lo ubicado (+ un poquito por cada cosa en su momento preferido)."""
    ids = {id(c) for c in elegidos}
    return sum(c.prioridad * (1 if id(c) in ids else 0.5) + (0.05 if "no hay hueco" not in s.motivo else 0)
               for s, c in hechas)


def recomendar(dia: date, libres: list[tuple[datetime, datetime]], actividades: list[Actividad],
               hechas_semana: dict[int, int], hechas_hoy: set[int], estudio_hoy: int, meta_estudio: int,
               maximo: int = 4, pausa: int = 10, evitar: dict[str, set[str]] | None = None) -> Plan:
    """
    El plan sugerido para 'dia' dentro de 'libres' (los huecos de horario.huecos()).
    hechas_semana: {id de actividad: veces que la hiciste desde el lunes}; hechas_hoy: ids hechas (o ya
    agendadas) hoy. estudio_hoy / meta_estudio en minutos.
    evitar: {clave(nombre): {"tarde", …}} lo que rechazaste seguido en ese momento del día: ahí no se sugiere.
    """
    libres = sorted(libres)
    candidatos = _candidatos(dia, actividades, hechas_semana, hechas_hoy, estudio_hoy, meta_estudio)
    # Primero se ELIGEN los 'maximo' más importantes y después se UBICAN. Se prueban dos formas y gana
    # la que deja ubicado lo más importante (y más cosas en su momento preferido):
    #   A) por rondas: 1) lo que tiene momento, solo en su momento; 2) lo que va en cualquier hueco;
    #      3) lo de la ronda 1 que no entró, en cualquier hueco. Así estudiar no le quita "su" mañana a correr.
    #   B) simplemente de lo más a lo menos importante (por si en A algo menor le quitó el lugar a algo mayor).
    # Al final, si sobra lugar, entran los menos importantes que no fueron elegidos.
    elegidos, resto = candidatos[:maximo], candidatos[maximo:]
    con_momento = [c for c in elegidos if c.momento]
    rondas_a = [(con_momento, True), ([c for c in elegidos if not c.momento], False), (con_momento, False),
                (resto, False)]
    rondas_b = [(elegidos, False), (resto, False)]
    planes = [_ubicar_rondas(dia, libres, r, maximo, pausa, evitar or {}) for r in (rondas_a, rondas_b)]
    sugerencias, ubicados = max(planes, key=lambda p: _puntaje(p[0], elegidos))
    sin_lugar = [c.nombre for c in elegidos
                 if id(c) not in ubicados and (c.clase == "estudio" or c.prioridad >= 0.5)]
    ubicadas = {s.nombre for s, _ in sugerencias}                      # la 2.ª sesión de estudio que no entra
    sin_lugar = [n for n in dict.fromkeys(sin_lugar) if n not in ubicadas]   # no es "no entra: Estudiar"
    return Plan(sorted((s for s, _ in sugerencias), key=lambda s: s.inicio), sin_lugar)


def describir_plan(plan: Plan, cuando: str = "hoy") -> tuple[str, str]:
    """(texto para la burbuja, frase para la voz)."""
    if not plan.sugerencias:
        texto = (f"No encontré un buen hueco para sugerirte algo {cuando}."
                 if plan.sin_lugar else f"{cuando.capitalize()} no tengo nada que sugerirte: vas al día. 👌")
        if plan.sin_lugar:
            texto += " No entra: " + ", ".join(plan.sin_lugar) + "."
        return texto, texto.replace(" 👌", "")
    lineas = [f"• {s.describir()}" for s in plan.sugerencias]
    if plan.sin_lugar:
        lineas.append("No entra " + cuando + ": " + ", ".join(plan.sin_lugar) + ".")
    partes = [f"{s.nombre.lower() if s.clase == 'estudio' else s.nombre} {hora_hablada(s.inicio)}"
              for s in plan.sugerencias[:3]]
    hablado = "Te sugiero " + (", ".join(partes[:-1]) + " y " + partes[-1] if len(partes) > 1 else partes[0]) + "."
    return "\n".join(lineas), hablado
