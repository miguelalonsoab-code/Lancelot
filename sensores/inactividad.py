"""
¿Hace cuánto que no tocas el teclado ni el mouse?

Sirve para no saludarte a las 6 de la mañana si dejaste la laptop prendida
y no hay nadie frente a ella: el saludo espera a que vuelvas.
Solo lee un contador de Windows (GetLastInputInfo); no registra qué teclas pulsas.
"""
from __future__ import annotations

import sys


def segundos_inactivo() -> float:
    """En otros sistemas devuelve 0 (se asume que estás presente)."""
    if sys.platform != "win32":
        return 0.0
    import ctypes
    from ctypes import wintypes

    class LASTINPUTINFO(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]

    info = LASTINPUTINFO()
    info.cbSize = ctypes.sizeof(info)
    if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
        return 0.0
    # Ambos contadores son de 32 bits y dan la vuelta cada ~49 días: el & lo corrige
    transcurrido = (ctypes.windll.kernel32.GetTickCount() - info.dwTime) & 0xFFFFFFFF
    return transcurrido / 1000.0
