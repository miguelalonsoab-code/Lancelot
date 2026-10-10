"""
Estadísticas de estudio por semana. Lógica pura: recibe números, devuelve números y textos.

La "semana" son los 7 días que terminan en `fin` (por defecto hoy), no de lunes a domingo:
así el gráfico siempre muestra los últimos 7 días, aunque hoy sea lunes.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

DIAS_CORTOS = ["L", "M", "M", "J", "V", "S", "D"]
DIAS_LARGOS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
_MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]


@dataclass
class DiaEstudio:
    fecha: date
    minutos: int
    pomodoros: int


@dataclass
class ResumenSemana:
    dias: list[DiaEstudio]          # 7 días, del más antiguo al más reciente
    total: int                      # minutos de la semana
    total_anterior: int             # minutos de los 7 días previos (para comparar)
    meta: int                       # minutos por día que cuentan como "cumplido"

    @property
    def inicio(self) -> date:
        return self.dias[0].fecha

    @property
    def fin(self) -> date:
        return self.dias[-1].fecha

    @property
    def dias_con_estudio(self) -> int:
        return sum(1 for d in self.dias if d.minutos > 0)

    @property
    def dias_meta(self) -> int:
        return sum(1 for d in self.dias if self.meta and d.minutos >= self.meta)

    @property
    def promedio(self) -> int:
        """Promedio por día de los 7 días (los días sin estudio cuentan como 0: es más honesto)."""
        return round(self.total / 7)

    @property
    def mejor(self) -> DiaEstudio | None:
        mejor = max(self.dias, key=lambda d: d.minutos)
        return mejor if mejor.minutos > 0 else None


def resumen_semana(datos: dict[date, tuple[int, int]], fin: date, meta: int = 0) -> ResumenSemana:
    """
    datos: {día: (pomodoros, minutos)}, como lo devuelve Almacen.estudio_por_dia.
    Debe incluir también los 7 días anteriores a la semana, para la comparación.
    """
    def dia(f: date) -> DiaEstudio:
        pomos, mins = datos.get(f, (0, 0))
        return DiaEstudio(f, mins, pomos)

    dias = [dia(fin - timedelta(days=6 - i)) for i in range(7)]
    anterior = sum(datos.get(fin - timedelta(days=7 + i), (0, 0))[1] for i in range(7))
    return ResumenSemana(dias, sum(d.minutos for d in dias), anterior, meta)


def horas(minutos: int) -> str:
    """95 -> '1 h 35', 40 -> '40 min'."""
    return f"{minutos} min" if minutos < 60 else f"{minutos // 60} h {minutos % 60:02d}"


def rango(r: ResumenSemana) -> str:
    """'4 – 10 oct' o '29 sep – 5 oct'."""
    a, b = r.inicio, r.fin
    if a.month == b.month:
        return f"{a.day} – {b.day} {_MESES[b.month - 1]}"
    return f"{a.day} {_MESES[a.month - 1]} – {b.day} {_MESES[b.month - 1]}"


def variacion(r: ResumenSemana) -> str:
    """Comparación con los 7 días anteriores."""
    if r.total_anterior == 0:
        return "sin datos de la semana anterior" if r.total == 0 else "la semana anterior no estudiaste"
    cambio = round((r.total - r.total_anterior) * 100 / r.total_anterior)
    if cambio == 0:
        return "igual que la semana anterior"
    return f"{'+' if cambio > 0 else '−'}{abs(cambio)} % que la semana anterior"


def describir_semana(r: ResumenSemana) -> tuple[str, str]:
    """(texto para el panel o la burbuja, texto para decir en voz alta)."""
    if r.total == 0:
        texto = "Sin sesiones de estudio en estos 7 días."
        return texto, "En los últimos 7 días no registraste sesiones de estudio."
    lineas = [f"Total: {horas(r.total)} · promedio {horas(r.promedio)} por día",
              f"Estudiaste {r.dias_con_estudio} de 7 días · {variacion(r)}"]
    if r.mejor:
        lineas.append(f"Mejor día: {DIAS_LARGOS[r.mejor.fecha.weekday()]} ({horas(r.mejor.minutos)})")
    if r.meta:
        lineas.append(f"Meta diaria ({horas(r.meta)}) cumplida {r.dias_meta} de 7 días")

    hablado = f"En los últimos 7 días estudiaste {_horas_habladas(r.total)}, {r.dias_con_estudio} de 7 días"
    if r.total_anterior:
        cambio = round((r.total - r.total_anterior) * 100 / r.total_anterior)
        if cambio > 0:
            hablado += f". Es un {cambio} por ciento más que la semana anterior"
        elif cambio < 0:
            hablado += f". Es un {-cambio} por ciento menos que la semana anterior"
    if r.mejor:
        hablado += f". Tu mejor día fue el {DIAS_LARGOS[r.mejor.fecha.weekday()]}"
    return "\n".join(lineas), hablado + "."


def _horas_habladas(minutos: int) -> str:
    h, m = divmod(minutos, 60)
    if h == 0:
        return f"{m} minutos"
    texto = "1 hora" if h == 1 else f"{h} horas"
    return texto + (f" y {m} minutos" if m else "")
