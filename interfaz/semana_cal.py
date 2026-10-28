"""
Vista Semana del calendario de la laptop (v3.21): 7 columnas, de que despiertas a que te duermes.

    gris = tu horario fijo (rayado si ese día no va) · verde suave = libre · turquesa = tareas · lila = eventos

Es lo mismo que la vista Semana del celular (movil/publico/calendario.js). Clic en un día = su agenda abajo.
Solo dibuja: los datos (Item de nucleo/agenda.py) los calcula el asistente.
"""
from __future__ import annotations

from datetime import date, time

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

from config import COLORES

INICIALES = ["L", "M", "M", "J", "V", "S", "D"]
ARRIBA, IZQUIERDA, SEPARACION = 22, 30, 4
COLOR = {"bloque": QColor("#3b4250"), "libre": QColor(91, 227, 125, 56), "tarea": QColor(COLORES["tranquilo"]),
         "evento": QColor(COLORES["evento"])}


class SemanaCalendario(QWidget):
    dia_elegido = Signal(object)                     # date

    def __init__(self):
        super().__init__()
        self.dias: list[tuple[date, list]] = []      # [(día, [Item])] de lunes a domingo
        self.elegido: date | None = None
        self.hoy: date | None = None
        self.desde, self.hasta = 6 * 60, 23 * 60      # minutos del día que se ven
        self.setMinimumHeight(320)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setCursor(Qt.PointingHandCursor)

    def mostrar(self, dias: list[tuple[date, list]], despertar: time, dormir: time, elegido: date, hoy: date):
        self.dias, self.elegido, self.hoy = dias, elegido, hoy
        self.desde = despertar.hour * 60 + despertar.minute
        fin = dormir.hour * 60 + dormir.minute
        self.hasta = max(self.desde + 60, 24 * 60 if fin <= self.desde else fin)
        self.update()

    # ------------------------------------------------------------ geometría
    def _ancho_columna(self) -> float:
        return (self.width() - IZQUIERDA - SEPARACION * 6) / 7

    def _y(self, minutos: int) -> float:
        alto = self.height() - ARRIBA - 2
        return ARRIBA + (min(max(minutos, self.desde), self.hasta) - self.desde) / (self.hasta - self.desde) * alto

    def mousePressEvent(self, e):
        x = e.position().x() - IZQUIERDA
        if x < 0 or not self.dias:
            return
        i = int(x // (self._ancho_columna() + SEPARACION))
        if 0 <= i < len(self.dias):
            self.dia_elegido.emit(self.dias[i][0])

    # ------------------------------------------------------------ dibujo
    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        tenue = QColor("#8b93a1")
        p.setFont(QFont(self.font().family(), 8))
        p.setPen(tenue)
        for m in range((self.desde // 180 + 1) * 180 if self.desde % 180 else self.desde, self.hasta, 180):
            p.drawText(QRectF(0, self._y(m) - 7, IZQUIERDA - 4, 14), Qt.AlignRight | Qt.AlignVCenter, f"{m // 60}h")
        ancho = self._ancho_columna()
        for i, (dia, items) in enumerate(self.dias):
            x = IZQUIERDA + i * (ancho + SEPARACION)
            fuente = QFont(self.font().family(), 9)
            fuente.setBold(True)
            p.setFont(fuente)
            p.setPen(QColor(COLORES["tranquilo"]) if dia == self.hoy else tenue)
            p.drawText(QRectF(x, 0, ancho, ARRIBA - 4), Qt.AlignCenter, f"{INICIALES[dia.weekday()]} {dia.day}")
            fondo = QRectF(x, ARRIBA, ancho, self.height() - ARRIBA - 2)
            libre_todo = any(it.tipo == "excepcion" for it in items)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor("#16301f") if libre_todo else QColor("#171a21"))
            p.drawRoundedRect(fondo, 6, 6)
            for it in items:
                if it.tipo == "excepcion":
                    continue
                a = it.inicio.hour * 60 + it.inicio.minute
                b = (it.fin.hour * 60 + it.fin.minute if it.fin and it.fin.date() == it.inicio.date()
                     else 24 * 60 if it.fin else a + 30)
                y1, y2 = self._y(a), self._y(b)
                if y2 - y1 < 1:
                    continue
                margen = 5 if it.tipo in ("tarea", "evento") else 2
                rect = QRectF(x + margen, y1, ancho - margen - 2, max(3.0, y2 - y1))
                if it.tipo == "bloque" and it.liberado:
                    p.setBrush(QBrush(QColor("#2a303b"), Qt.BDiagPattern))
                else:
                    p.setBrush(COLOR.get(it.tipo, tenue))
                p.drawRoundedRect(rect, 3, 3)
            if dia == self.elegido:
                p.setBrush(Qt.NoBrush)
                p.setPen(QPen(QColor(COLORES["tranquilo"]), 1.5))
                p.drawRoundedRect(fondo.adjusted(-1, -1, 1, 1), 7, 7)
        p.end()
