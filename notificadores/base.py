"""
Contrato que cumple cualquier canal de aviso.

Hoy hay dos: la cara (burbuja en pantalla) y la notificación de Windows.
En la Fase 2 se agrega, por ejemplo, un NotificadorNtfy o NotificadorTelegram
que envíe el aviso al celular: basta con crear una clase nueva que herede de esta
y registrarla en interfaz/app.py. Nada más del programa tiene que cambiar.
"""
from abc import ABC, abstractmethod

from nucleo.almacen import Tarea


class Notificador(ABC):
    # True si el canal hace ruido o salta fuera de la cara (sonido, notificación de Windows).
    # En "modo silencio" el asistente se salta los canales ruidosos.
    ruidoso: bool = False

    @abstractmethod
    def notificar(self, tarea: Tarea) -> None:
        """Avisar al usuario que llegó la hora de una tarea."""
