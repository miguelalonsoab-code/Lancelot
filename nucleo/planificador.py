"""
Planificador: reglas de tiempo puras, sin base de datos ni interfaz.

Por estar aislado así se puede probar fácilmente, y en la Fase 2 es justo
la lógica que se traslada al servidor (Cloudflare Worker con Cron Trigger).
"""
from __future__ import annotations

import calendar
from datetime import datetime, time, timedelta


def siguiente_ocurrencia(fecha: datetime, repeticion: str | None, ahora: datetime) -> datetime | None:
    """
    Próxima fecha de una tarea repetitiva, siempre en el futuro.
    Si la laptop estuvo apagada varios días, se salta las ocurrencias perdidas
    en vez de soltarte cinco avisos atrasados de golpe.
    Devuelve None si la tarea no se repite.
    """
    if not repeticion:
        return None
    siguiente = _avanzar(fecha, repeticion)
    while siguiente <= ahora:
        siguiente = _avanzar(siguiente, repeticion)
    return siguiente


def _avanzar(fecha: datetime, repeticion: str) -> datetime:
    if repeticion == "diaria":
        return fecha + timedelta(days=1)
    if repeticion == "semanal":
        return fecha + timedelta(weeks=1)
    if repeticion == "laborables":
        fecha += timedelta(days=1)
        while fecha.weekday() >= 5:            # 5 = sábado, 6 = domingo
            fecha += timedelta(days=1)
        return fecha
    if repeticion == "mensual":
        anio, mes = (fecha.year + 1, 1) if fecha.month == 12 else (fecha.year, fecha.month + 1)
        # Si era día 31 y el mes siguiente tiene 30, se usa el último día del mes
        dia = min(fecha.day, calendar.monthrange(anio, mes)[1])
        return fecha.replace(year=anio, month=mes, day=dia)
    if repeticion == "anual":
        # Un 29 de febrero pasa al 28 (y desde ahí queda en 28: es lo más simple y predecible)
        dia = min(fecha.day, calendar.monthrange(fecha.year + 1, fecha.month)[1])
        return fecha.replace(year=fecha.year + 1, day=dia)
    raise ValueError(f"Repetición desconocida: {repeticion}")


def estado_del_dia(fechas_pendientes: list[datetime], hay_alertas: bool, ahora: datetime,
                   hora_dormir: int, hora_despertar: int) -> str:
    """
    Decide el "ánimo" de la cara a partir de las tareas:
      alerta     -> hay algo vencido esperando respuesta
      pendiente  -> quedan tareas para hoy
      dormido    -> es de noche y no hay nada para hoy
      tranquilo  -> nada para hoy
    """
    if hay_alertas:
        return "alerta"
    if any(f.date() == ahora.date() for f in fechas_pendientes):
        return "pendiente"
    if ahora.hour >= hora_dormir or ahora.hour < hora_despertar:
        return "dormido"
    return "tranquilo"

# ------------------------------------------------------------ avisos previos
HORA_AVISO_PREVIO = (9, 0)


def dias_de_aviso(avisos: str | None) -> list[int]:
    """'7,1' -> [7, 1] (de mayor a menor, sin repetidos ni basura)."""
    dias = {int(x) for x in (avisos or "").split(",") if x.strip().isdigit()}
    return sorted((d for d in dias if 1 <= d <= 365), reverse=True)


def aviso_previo_pendiente(fecha: datetime, avisos: str | None, desde: datetime, ahora: datetime,
                           hora: tuple[int, int] = HORA_AVISO_PREVIO) -> int | None:
    """
    ¿Toca avisar con anticipación? Cada aviso previo sale a las 9:00 del día (fecha − N días).

    'desde': lo que tocaba antes de este momento ya se avisó o no correspondía. Es el más reciente
    entre el último aviso previo y la última vez que se creó o cambió el evento: así, un evento
    creado 3 días antes no avisa "falta 1 semana" justo al crearlo.

    Devuelve N (los días de anticipación) del aviso que toca, o None. Si se juntaron varios
    (la laptop estuvo apagada), solo el más cercano a la fecha: un aviso, no tres seguidos.
    """
    if fecha <= ahora:
        return None                               # ya es la hora: ahora avisa el aviso normal
    toca = None
    for n in dias_de_aviso(avisos):               # de mayor a menor: se queda con el más chico
        momento = datetime.combine(fecha.date() - timedelta(days=n), time(*hora))
        if desde < momento <= ahora:
            toca = n
    return toca


# ------------------------------------------------------------------ vencidas
def a_manana(fecha: datetime, ahora: datetime) -> datetime:
    """Misma hora que tenía, pero mañana. Para "pasar todas las vencidas a mañana"."""
    return datetime.combine(ahora.date() + timedelta(days=1), fecha.time().replace(second=0, microsecond=0))


def opciones_reprogramar(fecha: datetime, ahora: datetime,
                         hora_manana: tuple[int, int] = (9, 0)) -> list[tuple[str, datetime]]:
    """
    Atajos para mover una tarea vencida, del más cercano al más lejano:
      En 1 hora · Hoy a las HH:MM (si vencía otro día y esa hora aún no pasó hoy)
      Esta noche (20:00) · Mañana a la misma hora · Mañana a las 09:00
    Se quitan los repetidos (p. ej. si vencía a las 20:00, "hoy" y "esta noche" son lo mismo).
    """
    base = ahora.replace(second=0, microsecond=0)
    hoy, manana = base.date(), base.date() + timedelta(days=1)
    hora = fecha.time().replace(second=0, microsecond=0)

    candidatas = [("En 1 hora", base + timedelta(hours=1))]
    misma_hoy = datetime.combine(hoy, hora)
    if fecha.date() < hoy and misma_hoy > base + timedelta(minutes=30):
        candidatas.append((f"Hoy a las {hora:%H:%M}", misma_hoy))
    noche = datetime.combine(hoy, time(20, 0))
    if noche > base + timedelta(hours=1):
        candidatas.append(("Esta noche (20:00)", noche))
    candidatas.append((f"Mañana a las {hora:%H:%M}", datetime.combine(manana, hora)))
    candidatas.append((f"Mañana a las {hora_manana[0]:02d}:{hora_manana[1]:02d}",
                       datetime.combine(manana, time(*hora_manana))))

    opciones, vistas = [], set()
    for etiqueta, cuando in candidatas:
        if cuando not in vistas:
            vistas.add(cuando)
            opciones.append((etiqueta, cuando))
    return opciones
