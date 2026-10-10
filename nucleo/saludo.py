"""
Saludo del día: lo primero que te dice Lancelot cada día.

    ☀️ Buenos días, Miguel
    Hoy tienes 3 pendientes:
    • 09:00 Clase de redes
    • 14:30 Llamar al banco
    • 20:00 Pagar la luz
    ⚠ 1 vencida sin resolver
    🔥 Racha de estudio: 4 días. ¡Que no se corte!

Lógica pura: no sabe de SQLite ni de ventanas, solo arma los textos.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from nucleo.almacen import Tarea
from nucleo.hablado import hora_hablada


@dataclass
class Saludo:
    titulo: str      # cabecera de la burbuja
    texto: str       # cuerpo de la burbuja
    hablado: str     # lo que dice en voz alta (sin emojis ni listas)


def momento_del_dia(hora: int) -> tuple[str, str]:
    """(saludo, emoji) según la hora."""
    if 5 <= hora < 12:
        return "Buenos días", "☀️"
    if 12 <= hora < 19:
        return "Buenas tardes", "🌤"
    return "Buenas noches", "🌙"


def debe_saludar(ahora: datetime, ultimo_saludo: str | None, desde_hora: int) -> bool:
    """Una vez por día, y no antes de 'desde_hora' (si dejaste la laptop prendida de noche)."""
    return ahora.hour >= desde_hora and ultimo_saludo != ahora.date().isoformat()


def armar_saludo(ahora: datetime, pendientes: list[Tarea], racha: int, nombre: str,
                 max_lista: int = 4) -> Saludo:
    saludo, emoji = momento_del_dia(ahora.hour)
    vencidas = [t for t in pendientes if t.fecha <= ahora]
    hoy = [t for t in pendientes if t.fecha > ahora and t.fecha.date() == ahora.date()]

    lineas, frases = [], [f"{saludo}, {nombre}."]
    if hoy:
        n = len(hoy)
        lineas.append(f"Hoy tienes {n} pendiente{'s' if n > 1 else ''}:")
        lineas += [f"• {t.fecha:%H:%M} {t.titulo}" for t in hoy[:max_lista]]
        if n > max_lista:
            lineas.append(f"  … y {n - max_lista} más")
        primera = hoy[0]
        frases.append(f"Hoy tienes {_cantidad(n, 'pendiente')}. "
                      f"{'La primera es' if n > 1 else 'Es'} {primera.titulo}, {hora_hablada(primera.fecha)}.")
    else:
        lineas.append("Hoy no tienes nada agendado.")
        frases.append("Hoy no tienes nada agendado.")
    if vencidas:
        n = len(vencidas)
        lineas.append(f"⚠ {n} vencida{'s' if n > 1 else ''} sin resolver")
        frases.append(f"Además tienes {_cantidad(n, 'tarea vencida', 'tareas vencidas')}.")
    if racha >= 2:
        lineas.append(f"🔥 Racha de estudio: {racha} días. ¡Que no se corte!")
        frases.append(f"Llevas {racha} días seguidos estudiando. ¡Que no se corte!")
    return Saludo(f"{emoji} {saludo}, {nombre}", "\n".join(lineas), " ".join(frases))


def _cantidad(n: int, singular: str, plural: str | None = None) -> str:
    if n == 1:
        return f"una {singular}" if singular.startswith("tarea") else f"un {singular}"
    return f"{n} {plural or singular + 's'}"
