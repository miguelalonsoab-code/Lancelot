"""
Gráfico de barras de la semana de estudio, dibujado a mano con QPainter
(igual que la cara: sin librerías de gráficos extra).

    1 h 40
     ███        ┄┄┄┄┄┄┄┄┄┄┄┄┄┄ meta
     ███   45   ███
     ███  ███   ███        ███
      L    M     M    J     V    S    D
"""
from __future__ import annotations

from datetime import date

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

from interfaz.tema import ZAFIRO
from nucleo.estadisticas import DIAS_CORTOS, DiaEstudio, horas


class GraficoSemana(QWidget):
    def __init__(self):
        super().__init__()
        self.dias: list[DiaEstudio] = []
        self.meta = 0
        self.hoy: date | None = None
        self.setMinimumHeight(170)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def mostrar(self, dias: list[DiaEstudio], meta: int, hoy: date):
        self.dias, self.meta, self.hoy = dias, meta, hoy
        self.setToolTip("\n".join(f"{d.fecha:%d/%m}: {horas(d.minutos)} · {d.pomodoros} pomodoro(s)"
                                  for d in dias))
        self.update()

    def paintEvent(self, _):
        if not self.dias:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        ancho, alto = self.width(), self.height()
        arriba, abajo = 22, 24                          # espacio para los números y las letras
        alto_util = alto - arriba - abajo
        tope = max(max(d.minutos for d in self.dias), self.meta, 30)   # escala: al menos 30 min
        columna = ancho / len(self.dias)
        barra = min(34.0, columna * 0.56)

        fuente = QFont(self.font())
        fuente.setPointSizeF(8.5)
        p.setFont(fuente)

        # Línea de la meta diaria
        if self.meta:
            y = arriba + alto_util * (1 - self.meta / tope)
            p.setPen(QPen(QColor(ZAFIRO["destaque"]), 1, Qt.DashLine))      # v3.24: «línea de meta» = destaque
            p.drawLine(4, int(y), ancho - 4, int(y))

        for i, d in enumerate(self.dias):
            x = columna * i + (columna - barra) / 2
            es_hoy = d.fecha == self.hoy
            cumplio = self.meta and d.minutos >= self.meta
            # v3.24 (tema Zafiro): meta cumplida = acento; sin cumplir = superficie alta con borde
            color = QColor(ZAFIRO["acento"] if cumplio else ZAFIRO["superficie_alta"])

            if d.minutos:
                h = max(4.0, alto_util * d.minutos / tope)
                y = arriba + alto_util - h
                camino = QPainterPath()
                camino.addRoundedRect(QRectF(x, y, barra, h), 6, 6)
                p.fillPath(camino, color)
                if not cumplio:
                    p.setPen(QPen(QColor(ZAFIRO["linea_fuerte"]), 1))
                    p.drawPath(camino)
                p.setPen(QColor(ZAFIRO["tinta"]))
                p.drawText(QRectF(columna * i, y - 18, columna, 16), Qt.AlignCenter, _corto(d.minutos))
            else:                                       # día sin estudio: una rayita en la base
                p.fillRect(QRectF(x, arriba + alto_util - 2, barra, 2), QColor(ZAFIRO["linea"]))

            p.setPen(QColor(ZAFIRO["tinta"] if es_hoy else ZAFIRO["tinta_suave"]))
            letra = QFont(fuente)
            letra.setBold(es_hoy)
            p.setFont(letra)
            p.drawText(QRectF(columna * i, alto - abajo + 4, columna, abajo - 4), Qt.AlignCenter,
                       "hoy" if es_hoy else DIAS_CORTOS[d.fecha.weekday()])
            p.setFont(fuente)
        p.end()


def _corto(minutos: int) -> str:
    """Etiqueta encima de la barra: '45' o '1h40'."""
    return str(minutos) if minutos < 60 else f"{minutos // 60}h{minutos % 60:02d}"
