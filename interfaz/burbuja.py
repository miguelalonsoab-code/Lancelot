"""
Burbuja que aparece al lado de la cara. Tiene dos usos:

1. Aviso de TAREA: se queda hasta que respondes (Hecho / +10 min / +1 h).
2. MENSAJE (aliento, pomodoro, distracción): botones opcionales y puede
   desaparecer sola después de unos segundos.
"""
from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, Qt, QTimer, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from config import COLORES, MINUTOS_POSPONER, NOMBRE_ASISTENTE
from nucleo.almacen import Tarea

ESTILO_BASE = """
#tarjeta {{
    background: {fondo};
    border: 1px solid {color};
    border-radius: 14px;
}}
QLabel {{ color: #e8ebef; font-family: 'Segoe UI'; background: transparent; }}
#cabecera {{ color: {color}; font-size: 11px; font-weight: 600; }}
#titulo {{ font-size: 14px; font-weight: 600; }}
#extra {{ color: #8b93a1; font-size: 11px; }}
QPushButton {{
    background: #232731; color: #e8ebef; border: none; border-radius: 8px;
    padding: 6px 10px; font-family: 'Segoe UI'; font-size: 12px;
}}
QPushButton:hover {{ background: #2e3340; }}
#principal {{ background: {color}; color: #0b0d12; font-weight: 600; }}
"""


class Burbuja(QWidget):
    hecho = Signal(int)              # id de la tarea
    posponer = Signal(int, int)      # id, minutos
    accion = Signal(str)             # clave del botón de un mensaje

    def __init__(self):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.tarea_id: int | None = None
        self.tipo: str | None = None          # "tarea" | "mensaje" | None

        self._auto_ocultar = QTimer(self, singleShot=True)
        self._auto_ocultar.timeout.connect(self.ocultar)

        tarjeta = QFrame(objectName="tarjeta")
        externo = QVBoxLayout(self)
        externo.setContentsMargins(0, 0, 0, 0)
        externo.addWidget(tarjeta)

        self.cabecera = QLabel(objectName="cabecera")
        self.titulo = QLabel(objectName="titulo", wordWrap=True)
        self.titulo.setMaximumWidth(260)
        self.extra = QLabel(objectName="extra", wordWrap=True)
        self.extra.setMaximumWidth(260)
        self.fila_botones = QHBoxLayout()
        self.fila_botones.setSpacing(6)

        capa = QVBoxLayout(tarjeta)
        capa.setContentsMargins(14, 12, 14, 12)
        capa.setSpacing(6)
        capa.addWidget(self.cabecera)
        capa.addWidget(self.titulo)
        capa.addWidget(self.extra)
        capa.addLayout(self.fila_botones)

    # ------------------------------------------------------------ tareas
    def mostrar_tarea(self, tarea: Tarea, junto_a: QRect, en_cola: int):
        self.tipo, self.tarea_id = "tarea", tarea.id
        self._auto_ocultar.stop()
        self._pintar(COLORES["alerta"],
                     f"⏰ {NOMBRE_ASISTENTE} · {tarea.fecha.strftime('%H:%M')}",
                     tarea.titulo,
                     f"+{en_cola} aviso(s) más esperando" if en_cola else "")
        self._poner_botones([
            ("✓ Hecho", lambda: self.hecho.emit(tarea.id), True),
            (f"+{MINUTOS_POSPONER} min", lambda: self.posponer.emit(tarea.id, MINUTOS_POSPONER), False),
            ("+1 h", lambda: self.posponer.emit(tarea.id, 60), False),
        ])
        self._mostrar_junto_a(junto_a)

    # ----------------------------------------------------------- mensajes
    def mostrar_mensaje(self, cabecera: str, texto: str, botones: list[tuple[str, str]],
                        color: str, segundos: int, junto_a: QRect):
        """botones: [(texto, clave)]. segundos=0 -> se queda hasta que respondas."""
        self.tipo, self.tarea_id = "mensaje", None
        self._pintar(color, cabecera, texto, "")
        self._poner_botones([(t, (lambda c=clave: self.accion.emit(c)), i == 0)
                             for i, (t, clave) in enumerate(botones)])
        self._mostrar_junto_a(junto_a)
        if segundos:
            self._auto_ocultar.start(segundos * 1000)
        else:
            self._auto_ocultar.stop()

    def ocultar(self):
        self._auto_ocultar.stop()
        self.hide()
        self.tipo = None
        self.tarea_id = None

    # ------------------------------------------------------------ privados
    def _pintar(self, color: str, cabecera: str, titulo: str, extra: str):
        self.setStyleSheet(ESTILO_BASE.format(color=color, fondo=COLORES["fondo_bisel"]))
        self.cabecera.setText(cabecera)
        self.titulo.setText(titulo)
        self.extra.setText(extra)
        self.extra.setVisible(bool(extra))

    def _poner_botones(self, botones):
        while self.fila_botones.count():
            w = self.fila_botones.takeAt(0).widget()
            if w:
                w.deleteLater()
        for texto, funcion, principal in botones:
            b = QPushButton(texto, cursor=Qt.PointingHandCursor)
            if principal:
                b.setObjectName("principal")
            b.clicked.connect(funcion)
            self.fila_botones.addWidget(b)

    def _mostrar_junto_a(self, junto_a: QRect):
        self.adjustSize()
        self.reposicionar(junto_a)
        self.show()
        self.raise_()

    def reposicionar(self, junto_a: QRect):
        """A la izquierda de la cara; si no hay espacio, a la derecha."""
        pantalla = QGuiApplication.screenAt(junto_a.center()) or QGuiApplication.primaryScreen()
        area = pantalla.availableGeometry()
        x = junto_a.left() - self.width() - 4
        if x < area.left():
            x = junto_a.right() + 4
        y = junto_a.center().y() - self.height() // 2
        y = max(area.top(), min(y, area.bottom() - self.height()))
        self.move(QPoint(x, y))
