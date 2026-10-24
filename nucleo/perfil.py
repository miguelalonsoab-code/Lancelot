"""
Tu perfil: lo que Lancelot sabe de ti para organizar tu tiempo.

    a qué hora te despiertas y te duermes   -> "me despierto a las 6:30", "me duermo a las 11 de la noche"
    tu meta de estudio diaria                -> "meta de estudio 120 minutos"
    actividades que te gustan o quieres hacer -> "actividad: gimnasio 1 hora 3 veces por semana en la tarde"

Con esto (y tu horario) Lancelot calcula tus horas libres reales y te recomienda qué hacer
en ellas (nucleo/recomendador.py).

Lógica pura: sin SQLite ni ventanas. Se guarda en nucleo/almacen.py (ajustes y tabla 'actividades').
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import time

from nucleo.horario import duracion_minutos, hablar_duracion, leer_duracion
from nucleo.interprete import normalizar

MOMENTOS = {"manana": "en la mañana", "tarde": "en la tarde", "noche": "en la noche", None: "cuando puedas"}
_NUMEROS = {"una": 1, "un": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6, "siete": 7}


@dataclass
class Actividad:
    nombre: str
    minutos: int = 60                 # cuánto dura cada vez
    veces_semana: int | None = None   # meta: cuántas veces por semana (None = sin meta)
    momento: str | None = None        # "manana" | "tarde" | "noche" | None = cuando sea
    id: int | None = None

    def describir(self) -> str:
        """'Gimnasio · 1 h · 3 veces por semana · en la tarde'"""
        partes = [self.nombre, duracion_minutos(self.minutos)]
        if self.veces_semana:
            partes.append("todos los días" if self.veces_semana == 7
                          else f"{self.veces_semana} {'vez' if self.veces_semana == 1 else 'veces'} por semana")
        partes.append(MOMENTOS[self.momento])
        return " · ".join(partes)


@dataclass
class Perfil:
    despertar: time = time(6, 0)
    dormir: time = time(23, 0)
    meta_estudio: int = 100           # minutos de estudio al día
    actividades: list[Actividad] = field(default_factory=list)


# --------------------------------------------------------------------------- horas
_HORA = re.compile(r"\b(\d{1,2})(?::(\d{2}))?(?:\s?(am|pm|a\.m\.|p\.m\.))?(?: (?:de|en|por) la (manana|tarde|noche))?")


def leer_hora(texto: str, para: str) -> time | None:
    """
    'a las 6:30' -> 06:30 · 'las 11 de la noche' -> 23:00 · '11pm' -> 23:00.
    para = "despertar" | "dormir": sin am/pm, "me duermo a las 11" se entiende como 23:00
    y "me despierto a las 6" como 06:00.
    """
    m = _HORA.search(normalizar(texto))
    if not m:
        return None
    h, mi, ampm, momento = int(m.group(1)), int(m.group(2) or 0), (m.group(3) or "").replace(".", ""), m.group(4)
    if h > 23 or mi > 59:
        return None
    if ampm == "pm" or momento in ("tarde", "noche"):
        h = h + 12 if h < 12 else h
    elif ampm == "am" or momento == "manana":
        h = 0 if h == 12 else h
    elif para == "dormir" and 7 <= h <= 11:
        h += 12                                       # "me duermo a las 11" = 23:00
    elif para == "dormir" and h == 12:
        h = 0                                         # "a las 12" = medianoche
    return time(h, mi)


# --------------------------------------------------------------------------- actividades
_VECES = re.compile(r"\b(\d|una|dos|tres|cuatro|cinco|seis|siete) (?:veces|vez) (?:por|a la|cada|en la) semana\b"
                    r"|\b(todos los dias|diario|diariamente|cada dia)\b")
_MOMENTO = re.compile(r"\b(?:en|por|de) la (manana|tarde|noche)\b|\b(?:(?:en|por|de) )?(?:las )?(mananas|tardes|noches)\b")
_RELLENO = re.compile(r"^(?:(?:hacer|ir al?|ir a la|practicar|el|la|los|las|de|un|una)\s+)+", re.I)


def interpretar_actividad(texto: str) -> Actividad | str:
    """
    "gimnasio 1 hora 3 veces por semana en la tarde" -> Actividad.
    Solo el nombre es obligatorio (sin duración se asume 1 hora). Si no hay nombre, devuelve la explicación.
    """
    t = normalizar(texto)
    tramos = []
    minutos = 60
    if d := leer_duracion(t):
        minutos, tramo = d
        tramos.append(tramo)
    veces = None
    if m := _VECES.search(t):
        veces = 7 if m.group(2) else (int(m.group(1)) if m.group(1).isdigit() else _NUMEROS[m.group(1)])
        tramos.append(m.span())
    momento = None
    if m := _MOMENTO.search(t):
        momento = m.group(1) or m.group(2)[:-1]
        tramos.append(m.span())
    nombre = texto
    for a, b in sorted(tramos, reverse=True):
        nombre = nombre[:a] + " " + nombre[b:]
    nombre = re.sub(r"\s+", " ", nombre).strip(" ,.;:-")
    nombre = _RELLENO.sub("", nombre).strip(" ,.;:-")
    if not nombre:
        return "¿Qué actividad? Por ejemplo: «actividad: gimnasio 1 hora 3 veces por semana en la tarde»."
    return Actividad(nombre[:1].upper() + nombre[1:60], minutos, veces if veces and 1 <= veces <= 7 else None,
                     momento)


# --------------------------------------------------------------------------- resumen
def describir_perfil(p: Perfil, bloques: list | None = None) -> tuple[str, str]:
    """(texto para la burbuja, texto para la voz) de "¿qué sabes de mí?"."""
    lineas = [f"😴 Duermes de {p.dormir:%H:%M} a {p.despertar:%H:%M}",
              f"📚 Meta de estudio: {duracion_minutos(p.meta_estudio)} al día"]
    if bloques:
        lineas.append("🗓 Horario:")
        lineas += [f"  • {b.describir()}" for b in bloques]
    if p.actividades:
        lineas.append("🏃 Actividades:")
        lineas += [f"  • {a.describir()}" for a in p.actividades]
    if not bloques and not p.actividades:
        lineas.append("Cuéntame más: tu horario («horario: …») y lo que te gusta hacer («actividad: …»).")
    hablado = (f"Te despiertas a las {p.despertar:%H:%M} y te duermes a las {p.dormir:%H:%M}. "
               f"Tu meta es estudiar {hablar_duracion(p.meta_estudio)} al día.")
    if bloques:
        hablado += (f" Tienes {len(bloques)} {'bloque' if len(bloques) == 1 else 'bloques'} en tu horario, "
                    f"como {bloques[0].titulo}.")
    if p.actividades:
        hablado += " Te gusta: " + ", ".join(a.nombre for a in p.actividades[:4]) + "."
    return "\n".join(lineas), hablado
