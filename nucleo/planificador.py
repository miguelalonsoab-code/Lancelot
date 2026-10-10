"""
Planificador: reglas de tiempo puras, sin base de datos ni interfaz.

Por estar aislado así se puede probar fácilmente, y en la Fase 2 es justo
la lógica que se traslada al servidor (Cloudflare Worker con Cron Trigger).
"""
from __future__ import annotations

import calendar
from datetime import datetime, timedelta


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
