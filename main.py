"""
Punto de entrada. Ejecuta:   python main.py
(o pythonw main.py para que no se abra la ventana negra de consola)
"""
import sys

from PySide6.QtCore import QLocale
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication

from config import APP_ID_WINDOWS, MUTEX_WINDOWS, NIVEL_REGISTRO, NOMBRE_ASISTENTE, RUTA_REGISTRO, VERSION
from registro import configurar_registro

NOMBRE_CANAL = APP_ID_WINDOWS     # "dirección" para que dos copias se encuentren
_mutex = None                     # se guarda aquí para que viva mientras viva el programa


def ya_esta_abierto() -> bool:
    """
    Instancia única: intenta hablar con una copia que ya esté corriendo.
    Si la encuentra, le pide que muestre el panel y devuelve True.
    """
    socket = QLocalSocket()
    socket.connectToServer(NOMBRE_CANAL)
    if socket.waitForConnected(300):
        socket.write(b"mostrar")
        socket.flush()
        socket.waitForBytesWritten(300)
        socket.disconnectFromServer()
        return True
    return False


def main():
    configurar_registro(RUTA_REGISTRO, NIVEL_REGISTRO)   # lo primero: así se registra cualquier fallo
    # En Windows, esto hace que las notificaciones y la barra de tareas muestren
    # el nombre del asistente en vez de "Python".
    if sys.platform == "win32":
        import ctypes
        global _mutex
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID_WINDOWS)
        # "Cartel" de Windows que dice "Lancelot está abierto". El instalador y el desinstalador
        # lo buscan (AppMutex) para pedirte que lo cierres antes de tocar sus archivos.
        _mutex = ctypes.windll.kernel32.CreateMutexW(None, False, MUTEX_WINDOWS)

    QLocale.setDefault(QLocale(QLocale.Spanish, QLocale.Peru))   # fechas en español
    app = QApplication(sys.argv)
    app.setApplicationName(NOMBRE_ASISTENTE)
    app.setApplicationVersion(VERSION)
    app.setQuitOnLastWindowClosed(False)   # cerrar el panel no cierra el asistente

    if ya_esta_abierto():                  # doble clic en iniciar.bat: no abre otra cara
        sys.exit(0)

    from interfaz.app import Asistente    # se importa después de crear QApplication
    asistente = Asistente(app)

    # Escuchar a futuras copias que intenten abrirse
    QLocalServer.removeServer(NOMBRE_CANAL)          # limpia restos si se cerró mal
    servidor = QLocalServer()
    servidor.listen(NOMBRE_CANAL)
    servidor.newConnection.connect(
        lambda: (servidor.nextPendingConnection(), asistente.abrir_panel()))

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
