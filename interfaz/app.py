"""
Controlador principal: crea las piezas y las conecta. Es el "director de orquesta".

    app.py            ← tú estás aquí: tareas, comandos, estado de la cara, ventanas, menú
    avisos.py         qué muestra la burbuja y en qué orden (tareas, mensajes)
    asistente_voz.py  oír, hablar, diálogo, abrir apps y páginas, apodos
    estudio.py        modo estudio (pomodoros, aliento, distracciones)

Ninguna de esas piezas conoce SQLite ni dibuja la cara por su cuenta: piden cosas
a través del asistente (self.a en cada una).

Modos:
  - estudio  : sesión de pomodoros. Se activa y se termina.
  - silencio : sin sonidos, voz ni notificaciones de Windows; los avisos siguen en la cara.
  Pueden estar los dos activos a la vez (estudiar en la biblioteca, por ejemplo).
"""
from __future__ import annotations

import logging
from datetime import date, datetime

from PySide6.QtCore import QObject, QPoint, QTimer
from PySide6.QtGui import QAction, QGuiApplication, QIcon
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from config import (ATAJO_HABLAR, CARPETA_RESPALDOS, COLORES, HORA_DESPERTAR, HORA_DORMIR, NOMBRE_ASISTENTE,
                    NOMBRES_MODO, RESPALDOS_A_CONSERVAR, RUTA_BD, SEGUNDOS_ENTRE_REVISIONES, SEGUNDOS_MENSAJE)
from interfaz.asistente_voz import ControladorVoz, NotificadorVoz
from interfaz.avisos import GestorAvisos, NotificadorCara
from interfaz.burbuja import Burbuja
from interfaz.cara import Cara, pixmap_cara
from interfaz.estudio import ModoEstudio
from interfaz.panel import Panel
from notificadores.base import Notificador
from notificadores.windows import NotificadorWindows
from nucleo.almacen import Almacen
from nucleo.comandos import Comando
from nucleo.interprete import describir_fecha
from nucleo.planificador import estado_del_dia
from nucleo.respaldo import hacer_respaldo

log = logging.getLogger(__name__)

# Confirmaciones habladas cuando un comando llega por voz
_CONFIRMACION_VOZ = {
    "pausa": "Pausado.",
    "seguir": "Seguimos.",
    "silencio": "Modo silencio.",
    "sin_silencio": "Vuelvo a hablar.",
}


class Asistente(QObject):
    def __init__(self, app: QApplication, ruta_bd=None):
        super().__init__()
        self.app = app
        self.ruta_bd = ruta_bd or RUTA_BD               # las pruebas usan una base temporal
        self.almacen = Almacen(self.ruta_bd)
        self.almacen.reactivar_avisos_pendientes()
        self.silencio = self.almacen.leer_ajuste("silencio") == "1"

        # --- Interfaz
        self.cara = Cara()
        self.cara.silencio = self.silencio
        self.burbuja = Burbuja()
        self.panel = Panel()
        self.bandeja = QSystemTrayIcon(QIcon(pixmap_cara(64)))
        self.bandeja.setToolTip(NOMBRE_ASISTENTE)

        # --- Piezas (el orden importa: los avisos y la voz se usan entre sí)
        self.estudio = ModoEstudio(self.almacen)
        self.avisos = GestorAvisos(self)
        self.voz = ControladorVoz(self)
        self.notificador_windows = NotificadorWindows(self.bandeja)
        # Canales de aviso de tareas (en la Fase 2 se agrega aquí el del celular)
        self.notificadores: list[Notificador] = [NotificadorCara(self.avisos), self.notificador_windows,
                                                 NotificadorVoz(self.voz)]

        # --- Señales
        self.estudio.aviso.connect(self.avisos.mostrar_mensaje)
        self.estudio.cambio.connect(self.actualizar_estado)
        self.estudio.celebrar.connect(self.cara.celebrar)
        self.cara.clicada.connect(self._alternar_panel)
        self.cara.menu_pedido.connect(self._menu_cara)
        self.cara.movida.connect(self._al_mover_cara)
        self.panel.agregar_pedido.connect(self.agregar)
        self.panel.completar_pedido.connect(self.completar)
        self.panel.eliminar_pedido.connect(self.eliminar)
        self.panel.editar_pedido.connect(self.editar)
        self.panel.comando_pedido.connect(self.ejecutar_comando)
        self.panel.hablar_pedido.connect(self.voz.oido.escuchar_una_orden)

        self._menu_bandeja = QMenu()                 # se guarda para que no se libere
        self._menu_bandeja.aboutToShow.connect(lambda: self._llenar_menu(self._menu_bandeja))
        self.bandeja.setContextMenu(self._menu_bandeja)
        self.bandeja.activated.connect(self._al_activar_bandeja)
        self.bandeja.show()

        # --- Relojes
        self.reloj_revision = QTimer(self)                 # ¿venció algo?
        self.reloj_revision.timeout.connect(self.revisar)
        self.reloj_revision.start(SEGUNDOS_ENTRE_REVISIONES * 1000)
        self.reloj_refresco = QTimer(self)                 # textos como "hoy 20:00"
        self.reloj_refresco.timeout.connect(self.refrescar)
        self.reloj_refresco.start(60 * 1000)
        self.reloj_respaldo = QTimer(self)                 # por si la laptop queda prendida de un día a otro
        self.reloj_respaldo.timeout.connect(self.respaldar)
        self.reloj_respaldo.start(3 * 60 * 60 * 1000)

        if self.almacen.leer_ajuste("escucha") == "1":
            self.voz.poner_escucha(True, avisar=False)

        self._colocar_cara()
        self.cara.show()
        self.refrescar()
        self.respaldar()
        QTimer.singleShot(1500, self.revisar)              # avisos atrasados al abrir
        log.info("Lancelot iniciado")

    # ================================================================ tareas
    def revisar(self):
        """Se ejecuta cada pocos segundos: ¿llegó la hora de algo?"""
        vencidas = self.almacen.por_avisar(datetime.now())
        for tarea in vencidas:
            self.almacen.marcar_avisada(tarea.id)
            for canal in self.notificadores:
                if canal.ruidoso and self.silencio:
                    continue
                try:
                    canal.notificar(tarea)
                except Exception:                    # un canal caído no tumba a los demás
                    log.exception("el canal %s falló al avisar", type(canal).__name__)
        if vencidas:
            self.refrescar()

    def agregar(self, titulo: str, fecha: datetime, repeticion):
        self.almacen.agregar(titulo, fecha, repeticion)
        self.cara.celebrar()
        self.refrescar()

    def completar(self, tarea_id: int):
        self.almacen.completar(tarea_id)
        self.avisos.quitar(tarea_id)
        self.cara.celebrar()
        self.refrescar()

    def posponer(self, tarea_id: int, minutos: int):
        self.almacen.posponer(tarea_id, minutos)
        self.avisos.quitar(tarea_id)
        self.refrescar()

    def editar(self, tarea_id: int, titulo: str, fecha: datetime, repeticion):
        self.almacen.editar(tarea_id, titulo, fecha, repeticion)
        self.avisos.quitar(tarea_id)            # si estaba sonando y la moviste, deja de sonar
        self.cara.celebrar()
        self.refrescar()

    def eliminar(self, tarea_id: int):
        self.almacen.eliminar(tarea_id)
        self.avisos.quitar(tarea_id)
        self.refrescar()

    def respaldar(self):
        try:
            creado = hacer_respaldo(self.ruta_bd, CARPETA_RESPALDOS if self.ruta_bd == RUTA_BD
                                    else self.ruta_bd.parent / "respaldos", date.today(), RESPALDOS_A_CONSERVAR)
            if creado:
                log.info("respaldo creado: %s", creado.name)
        except Exception:
            log.exception("no se pudo crear el respaldo")

    # ============================================================== comandos
    def ejecutar_comando(self, c: Comando, por_voz: bool = False):
        """Punto único para todo comando, venga del panel, del menú o de la voz."""
        log.info("comando: %s%s", c.accion, " (voz)" if por_voz else "")
        if self.voz.ejecutar(c):                     # abrir, buscar, hora, agenda, apodos, escucha
            self.refrescar()
            return
        accion = c.accion
        mensaje = self.avisos.mostrar_mensaje
        if accion == "estudio":
            self.estudio.iniciar(c.minutos)
        elif accion in ("pausa", "seguir", "terminar"):
            if not self.estudio.activo:
                mensaje("Modo estudio", "No hay una sesión activa. Escribe «modo estudio».",
                        [], COLORES["estudio"], 6, False)
            else:
                {"pausa": self.estudio.pausar, "seguir": self.estudio.seguir,
                 "terminar": self.estudio.terminar}[accion]()
        elif accion == "silencio":
            self._poner_silencio(True)
            mensaje(f"🔕 {NOMBRES_MODO['silencio']}", "Sin sonidos ni notificaciones. Los avisos siguen apareciendo aquí.",
                    [], COLORES["dormido"], 6, False)
        elif accion == "sin_silencio":
            self._poner_silencio(False)
            mensaje("🔔 Sonido activado", "Vuelvo a sonar con los avisos.", [], COLORES["tranquilo"], 5, False)
        elif accion == "normal":
            self._poner_silencio(False)
            if self.estudio.activo:
                self.estudio.terminar()
            else:
                mensaje(NOMBRES_MODO["normal"], "De vuelta al modo normal.", [], COLORES["tranquilo"], 5, False)
        elif accion == "resumen":
            texto = self.estudio.resumen_hoy(datetime.now())
            mensaje("📊 Tu día", texto, [], COLORES["estudio"], SEGUNDOS_MENSAJE, False)
            if por_voz:
                self.voz.decir(texto.replace("Hoy:", "Hoy llevas").replace("pomodoro(s)", "pomodoros")
                               .replace(" · ", ", ").replace(" h ", " horas ").replace(" min", " minutos"))
        if por_voz:
            if accion in _CONFIRMACION_VOZ:
                self.voz.decir(_CONFIRMACION_VOZ[accion])
            elif accion == "estudio":
                self.voz.decir(f"Modo estudio. Bloques de {self.estudio.pomodoro.minutos_enfoque} minutos. Vamos.")
            elif accion == "terminar" and not self.estudio.activo:
                self.voz.decir("Sesión terminada. Buen trabajo.")
        self.refrescar()

    def _poner_silencio(self, activo: bool):
        self.silencio = activo
        self.cara.silencio = activo
        self.almacen.guardar_ajuste("silencio", "1" if activo else "0")

    # ================================================================ estado
    def refrescar(self):
        """Actualización completa (incluye la lista de tareas)."""
        self.actualizar_estado()
        self.panel.mostrar_tareas(self.almacen.pendientes())

    def actualizar_estado(self):
        """Actualización liviana: cara y modos. El modo estudio la llama cada segundo."""
        ahora = datetime.now()
        pendientes = self.almacen.pendientes()
        self.cara.contador = sum(1 for t in pendientes if t.fecha.date() == ahora.date())

        if self.voz.escuchando_orden:                     # te está escuchando: lo más importante
            estado, progreso, texto = "escuchando", None, None
        elif self.avisos.cola:                            # una tarea vencida manda
            estado, progreso, texto = "alerta", None, None
        elif self.estudio.activo:
            estado, progreso, texto = self.estudio.estado_cara(ahora)
        else:
            estado = estado_del_dia([t.fecha for t in pendientes], False, ahora, HORA_DORMIR, HORA_DESPERTAR)
            progreso, texto = None, None
        self.cara.set_estado(estado)
        self.cara.progreso, self.cara.texto = progreso, texto
        self.avisos.cerrar_si_caduco()

        proxima = next((t for t in pendientes if t.fecha >= ahora), None)
        tip = (f"Próxima: {proxima.titulo} ({describir_fecha(proxima.fecha, ahora)})"
               if proxima else "Sin tareas próximas")
        if self.estudio.activo:
            tip = self.estudio.descripcion(ahora) + "\n" + tip
        self.cara.setToolTip(tip)
        self.bandeja.setToolTip(f"{NOMBRE_ASISTENTE} · {tip}")

        if self.panel.isVisible():
            p = self.estudio.pomodoro
            self.panel.mostrar_modos(self.estudio.activo, self.silencio,
                                     self.estudio.descripcion(ahora) if p else "",
                                     bool(p and p.pausado), self.voz.escucha_activa)
            self.panel.mostrar_voz(self.voz.estado)
            self.panel.mostrar_hoy(self.estudio.resumen_hoy(ahora))

    # ============================================================== ventanas
    def _alternar_panel(self):
        if self.panel.isVisible() and self.panel.isActiveWindow():
            self.panel.hide()
        else:
            self.abrir_panel()

    def abrir_panel(self):
        self.panel.abrir()
        self.actualizar_estado()

    def _alternar_cara(self):
        if self.cara.isVisible():
            self.cara.hide()
            self.burbuja.hide()
        else:
            self.cara.show()
            self.avisos.mostrar_siguiente()

    def _al_mover_cara(self, pos: QPoint):
        self.almacen.guardar_ajuste("cara_pos", f"{pos.x()},{pos.y()}")
        if self.burbuja.isVisible():
            self.burbuja.reposicionar(self.cara.frameGeometry())

    def _colocar_cara(self):
        guardada = self.almacen.leer_ajuste("cara_pos")
        if guardada:
            x, y = map(int, guardada.split(","))
            # Solo si esa posición sigue existiendo (p. ej. desconectaste un monitor)
            if QGuiApplication.screenAt(QPoint(x + 20, y + 20)):
                self.cara.move(x, y)
                return
        area = QGuiApplication.primaryScreen().availableGeometry()
        self.cara.move(area.right() - self.cara.width() - 30, area.bottom() - self.cara.height() - 30)

    def _al_activar_bandeja(self, motivo):
        if motivo == QSystemTrayIcon.Trigger:        # clic izquierdo en el ícono
            self.abrir_panel()

    # ================================================================= menús
    def _menu_cara(self, pos: QPoint):
        self._ultimo_menu = QMenu()                  # se guarda para que no se libere al mostrarse
        self._llenar_menu(self._ultimo_menu)
        self._ultimo_menu.exec(pos)

    def _llenar_menu(self, menu: QMenu):
        """El menú se arma cada vez que se abre, así siempre refleja el estado actual."""
        menu.clear()
        comando = lambda accion: (lambda: self.ejecutar_comando(Comando(accion)))   # noqa: E731
        opciones = [("Mis tareas", self.abrir_panel), None]
        if self.estudio.activo:
            p = self.estudio.pomodoro
            opciones += [("▶ Seguir" if p.pausado else "⏸ Pausar", comando("seguir" if p.pausado else "pausa")),
                         ("⏹ Terminar estudio", comando("terminar"))]
        else:
            opciones.append((f"📚 {NOMBRES_MODO['estudio']}", comando("estudio")))
        escucha = self.voz.escucha_activa
        opciones += [
            ("🔔 Quitar silencio" if self.silencio else f"🔕 {NOMBRES_MODO['silencio']}",
             comando("sin_silencio" if self.silencio else "silencio")),
            ("📊 Resumen de hoy", comando("resumen")),
            None,
            ("🎙 Dejar de escuchar" if escucha else f"🎙 Escuchar «{NOMBRE_ASISTENTE}»",
             lambda: self.voz.poner_escucha(not escucha)),
            (f"🗣 Hablarle ahora ({ATAJO_HABLAR})", lambda: self.voz.oido.escuchar_una_orden()),
            None,
            ("Mostrar / ocultar cara", self._alternar_cara),
            ("Salir", self.salir),
        ]
        for opcion in opciones:
            if opcion is None:
                menu.addSeparator()
                continue
            accion = QAction(opcion[0], menu)
            accion.triggered.connect(opcion[1])
            menu.addAction(accion)

    def salir(self):
        if self.estudio.activo:
            self.estudio.terminar()                  # guarda la sesión antes de cerrar
        self.voz.detener()
        self.bandeja.hide()
        log.info("Lancelot cerrado")
        self.app.quit()
