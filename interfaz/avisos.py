"""
Gestor de avisos: decide QUÉ muestra la burbuja junto a la cara y en qué orden.

Reglas:
1. Las tareas vencidas tienen prioridad. Si hay varias, van en cola, de a una.
2. Los mensajes (aliento, pomodoro, respuestas de voz) se muestran cuando la burbuja
   está libre. Si llega una tarea encima de un mensaje FIJO ("¿Seguimos?"), el mensaje
   se guarda y vuelve cuando la tarea se responde.
3. Un mensaje fijo que ya no tiene sentido se cierra solo (p. ej. "¿Distraído?" si
   volviste por tu cuenta, o "¿Para cuándo?" si cancelaste el diálogo).
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from config import HABLAR_MENSAJES_ESTUDIO
from notificadores.base import Notificador
from nucleo.almacen import Tarea
from nucleo.pomodoro import ESPERANDO

if TYPE_CHECKING:
    from interfaz.app import Asistente


class NotificadorCara(Notificador):
    """La cara también es un canal de aviso: pone la tarea en la cola de la burbuja."""

    def __init__(self, avisos: "GestorAvisos"):
        self.avisos = avisos

    def notificar(self, tarea: Tarea) -> None:
        self.avisos.encolar(tarea.id)


class GestorAvisos:
    def __init__(self, asistente: "Asistente"):
        self.a = asistente
        self.cola: list[int] = []                 # ids de tareas avisadas esperando respuesta
        self._mensaje_actual = None               # mensaje fijo que se está mostrando
        self._mensaje_pendiente = None            # mensaje fijo que espera a que se libere la burbuja

        b = asistente.burbuja
        b.hecho.connect(asistente.completar)
        b.posponer.connect(asistente.posponer)
        b.accion.connect(self._al_pulsar_boton)

    # ================================================================ tareas
    def encolar(self, tarea_id: int):
        if tarea_id not in self.cola:
            self.cola.append(tarea_id)
        self.mostrar_siguiente()

    def quitar(self, tarea_id: int):
        if tarea_id in self.cola:
            self.cola.remove(tarea_id)
        if self.a.burbuja.tarea_id == tarea_id:
            self.a.burbuja.ocultar()
        self.mostrar_siguiente()

    def mostrar_siguiente(self):
        """Las tareas tienen prioridad; los mensajes esperan a que se libere la burbuja."""
        burbuja, cara = self.a.burbuja, self.a.cara
        while self.cola:
            tarea = self.a.almacen.obtener(self.cola[0])
            if tarea and tarea.estado == "pendiente":
                if cara.isVisible():
                    if burbuja.tipo == "mensaje" and self._mensaje_actual:
                        self._mensaje_pendiente = self._mensaje_actual   # no perder "¿seguimos?"
                    burbuja.mostrar_tarea(tarea, cara.frameGeometry(), len(self.cola) - 1)
                return
            self.cola.pop(0)                         # se borró o completó desde el panel
        if burbuja.tipo == "tarea":
            burbuja.ocultar()
        if self._mensaje_pendiente and burbuja.tipo is None:
            pendiente, self._mensaje_pendiente = self._mensaje_pendiente, None
            if self._vigente(pendiente):
                self._pintar(*pendiente)

    # ============================================================== mensajes
    def mostrar_mensaje(self, cabecera: str, texto: str, botones: list, color: str,
                        segundos: int, sonar: bool):
        """
        botones: [(texto, clave)] · segundos: 0 = fijo hasta que respondas
        sonar: además notificación de Windows y voz (salvo modo silencio)
        """
        if sonar and not self.a.silencio:
            self.a.notificador_windows.mensaje(cabecera, texto)
            if HABLAR_MENSAJES_ESTUDIO:
                self.a.voz.decir(texto)
        if self.a.burbuja.tipo == "tarea":
            if segundos == 0:                        # solo vale la pena guardar los fijos
                self._mensaje_pendiente = (cabecera, texto, botones, color, segundos)
            return
        self._pintar(cabecera, texto, botones, color, segundos)

    def ocultar_mensaje(self):
        if self.a.burbuja.tipo == "mensaje":
            self.a.burbuja.ocultar()
            self._mensaje_actual = None

    def cerrar_si_caduco(self):
        """Se llama en cada actualización de estado."""
        if (self.a.burbuja.tipo == "mensaje" and self._mensaje_actual
                and not self._vigente(self._mensaje_actual)):
            self.ocultar_mensaje()

    def _pintar(self, cabecera, texto, botones, color, segundos):
        self._mensaje_actual = (cabecera, texto, botones, color, segundos) if segundos == 0 else None
        if self.a.cara.isVisible():
            self.a.burbuja.mostrar_mensaje(cabecera, texto, botones, color, segundos,
                                           self.a.cara.frameGeometry())

    def _vigente(self, mensaje) -> bool:
        claves = {clave for _, clave in mensaje[2]}
        estudio = self.a.estudio
        if "cancelar_dialogo" in claves:
            return self.a.voz.dialogo is not None
        if "permitir" in claves:
            return estudio.activo and estudio.sospechando
        if "seguir" in claves:
            return estudio.activo and estudio.pomodoro.fase == ESPERANDO
        return True

    def _al_pulsar_boton(self, clave: str):
        self.a.burbuja.ocultar()
        self._mensaje_actual = None
        estudio = self.a.estudio
        acciones = {
            "seguir": estudio.seguir,
            "saltar": estudio.seguir,                # en descanso, "seguir" = empezar ya
            "terminar": estudio.terminar,
            "volver": estudio.volver,
            "permitir": estudio.permitir_ventana_actual,
            "cancelar_dialogo": self.a.voz.cancelar_dialogo,
            "actualizar": self.a.actualizar_ahora,
            "omitir_version": self.a.omitir_actualizacion,
            "agendar_plan": self.a.agendar_plan,          # v3.16: sugerencias
            "sugerencia_si": self.a.aceptar_sugerencia,
            "sugerencia_no": self.a.rechazar_sugerencia,
            "sugerencia_luego": self.a.posponer_sugerencia,
        }
        if clave in acciones:
            acciones[clave]()
        self.mostrar_siguiente()
        self.a.refrescar()
