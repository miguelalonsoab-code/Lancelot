"""
Notificación nativa de Windows 11 (la tarjeta que aparece abajo a la derecha
y queda en el Centro de notificaciones) + un sonido corto.

Se usa el ícono de la bandeja del sistema (QSystemTrayIcon) porque ya viene en
PySide6: no hace falta instalar otra librería solo para esto.
"""
from PySide6.QtWidgets import QSystemTrayIcon

from config import NOMBRE_ASISTENTE
from notificadores.base import Notificador
from nucleo.almacen import Tarea

try:
    import winsound      # solo existe en Windows
except ImportError:      # en otro sistema simplemente no suena
    winsound = None


class NotificadorWindows(Notificador):
    ruidoso = True

    def __init__(self, bandeja: QSystemTrayIcon):
        self.bandeja = bandeja

    def notificar(self, tarea: Tarea) -> None:
        if tarea.es_evento:
            self.mensaje(f"📅 Hoy · {NOMBRE_ASISTENTE}", f"{tarea.titulo}\n{tarea.fecha:%H:%M}")
        else:
            self.mensaje(f"⏰ {NOMBRE_ASISTENTE}", f"{tarea.titulo}\n{tarea.fecha:%H:%M}")

    def mensaje(self, titulo: str, texto: str) -> None:
        """También lo usa el modo estudio (fin de pomodoro, fin de descanso)."""
        self.bandeja.showMessage(titulo, texto, self.bandeja.icon(), 8000)
        if winsound:
            winsound.MessageBeep(winsound.MB_ICONASTERISK)
