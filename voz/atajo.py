"""
Atajo de teclado global (funciona aunque estés en otra app): Ctrl + Alt + Espacio.

Cómo: cada 60 ms se pregunta a Windows si esas tres teclas están presionadas
(GetAsyncKeyState). Cuando pasan de "sueltas" a "presionadas", se emite 'pulsado'.
Es más simple que registrar un atajo con mensajes de Windows y no necesita permisos.
"""
from __future__ import annotations

import sys

from PySide6.QtCore import QObject, QTimer, Signal

_CTRL, _ALT, _ESPACIO = 0x11, 0x12, 0x20


class AtajoTeclado(QObject):
    pulsado = Signal()

    def __init__(self):
        super().__init__()
        self._antes = False
        if sys.platform != "win32":
            return
        import ctypes
        self._estado_tecla = ctypes.windll.user32.GetAsyncKeyState
        self._estado_tecla.restype = ctypes.c_short
        self._reloj = QTimer(self)
        self._reloj.timeout.connect(self._revisar)
        self._reloj.start(60)

    def _revisar(self):
        ahora = all(self._estado_tecla(t) & 0x8000 for t in (_CTRL, _ALT, _ESPACIO))
        if ahora and not self._antes:
            self.pulsado.emit()
        self._antes = ahora
