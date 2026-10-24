"""
La agenda de un día y las marcas del mes, para la pestaña 📅 Calendario de la laptop (v3.20).

Es lo mismo que agendaDelDia() y marcasDelMes() de movil/publico/contexto.js (el calendario del celular):
tu horario fijo, tus días libres, tus tareas y eventos (con sus repeticiones) y tus huecos libres, ordenados.

Lógica pura: sin SQLite ni Qt.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta

from nucleo.almacen import Tarea
from nucleo.horario import Bloque, Excepcion, coincide
from nucleo.planificador import siguiente_ocurrencia

ORDEN = {"excepcion": 0, "bloque": 1, "evento": 2, "tarea": 2, "libre": 3}


@dataclass
class Item:
    tipo: str                         # excepcion | bloque | tarea | evento | libre
    inicio: datetime
    titulo: str
    fin: datetime | None = None
    detalle: str = ""
    tarea: Tarea | None = None
    liberado: bool = False            # bloque que ese día no va (por un día libre)
    sugerida: bool = False            # tarea agendada desde una sugerencia (💡)


def tareas_del_dia(tareas: list[Tarea], dia: date, maximo: int = 400) -> list[tuple[Tarea, datetime]]:
    """Las tareas pendientes que caen ese día, con su ocurrencia si se repiten: [(tarea, fecha)]."""
    salida = []
    for t in tareas:
        f = t.fecha
        for _ in range(maximo):
            if f is None or f.date() > dia:
                break
            if f.date() == dia:
                salida.append((t, f))
                break
            if not t.repeticion:
                break
            f = siguiente_ocurrencia(f, t.repeticion, f)
    return sorted(salida, key=lambda x: x[1])


def agenda_del_dia(dia: date, bloques: list[Bloque], excepciones: list[Excepcion], tareas: list[Tarea],
                   libres: list[tuple[datetime, datetime]], sugeridas: set[int] = frozenset()) -> list[Item]:
    items = []
    for e in excepciones:
        if e.desde <= dia <= e.hasta:
            items.append(Item("excepcion", datetime.combine(dia, datetime.min.time()), e.titulo,
                              detalle="Ese bloque no cuenta" if e.filtro else "Todo tu horario libre"))
    for b in bloques:
        if dia.weekday() not in b.dias:
            continue
        libre = any(e.desde <= dia <= e.hasta and coincide(e.filtro, b.titulo) for e in excepciones)
        detalle = "No va (día libre)" if libre else (f"🚌 {b.traslado} min antes y después" if b.traslado else "")
        items.append(Item("bloque", datetime.combine(dia, b.inicio), b.titulo, datetime.combine(dia, b.fin), detalle,
                          liberado=libre))
    for t, f in tareas_del_dia(tareas, dia):
        items.append(Item("evento" if t.es_evento else "tarea", f, t.titulo,
                          f + timedelta(minutes=t.duracion) if t.duracion else None, tarea=t,
                          sugerida=t.id in sugeridas))
    for a, b in libres:
        items.append(Item("libre", a, "Libre", b))
    return sorted(items, key=lambda i: (i.inicio, ORDEN[i.tipo]))


def marcas_del_mes(desde: date, hasta: date, tareas: list[Tarea],
                   excepciones: list[Excepcion]) -> dict[date, tuple[int, int, bool]]:
    """{día: (tareas, eventos, día libre)} entre dos fechas, solo los días con algo."""
    salida = {}
    dia = desde
    while dia <= hasta:
        del_dia = tareas_del_dia(tareas, dia, 62)
        libre = any(e.desde <= dia <= e.hasta for e in excepciones)
        if del_dia or libre:
            eventos = sum(1 for t, _ in del_dia if t.es_evento)
            salida[dia] = (len(del_dia) - eventos, eventos, libre)
        dia += timedelta(days=1)
    return salida
