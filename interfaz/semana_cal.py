"""
Vista Semana del calendario de la laptop (v3.21): 7 columnas, de que despiertas a que te duermes.

    tu horario fijo con el color de su categoría (azul trabajo · lavanda clase · gris otro; rayado si ese día no va)
    y su nombre adentro · azul tenue = libre · tareas y eventos con borde (sin relleno) y su nombre si cabe
    (v3.23: colores del sistema de diseño; v3.24: tema Zafiro, guiones por sílaba y nombre en tareas/eventos)

Es lo mismo que la vista Semana del celular (movil/publico/calendario.js). Clic en un día = su agenda abajo.
Solo dibuja: los datos (Item de nucleo/agenda.py) los calcula el asistente.
"""
from __future__ import annotations

from datetime import date, time

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import (QAbstractTextDocumentLayout, QBrush, QColor, QFont, QPainter, QPalette, QPen, QTextDocument,
                           QTextOption)
from PySide6.QtWidgets import QSizePolicy, QWidget

from config import COLORES
from interfaz.tema import MONO, ZAFIRO
from nucleo.horario import CATEGORIAS, texto_sobre
from nucleo.silabas import con_guiones

INICIALES = ["L", "M", "M", "J", "V", "S", "D"]
ARRIBA, IZQUIERDA, SEPARACION = 24, 30, 4
Z = {k: QColor(v) for k, v in ZAFIRO.items()}
COLOR = {"libre": Z["acento_suave"], "tarea": Z["linea_fuerte"], "evento": Z["destaque"]}   # tarea/evento: el BORDE
COLOR_BLOQUE = {c: QColor(COLORES[f"bloque_{c}"]) for c in CATEGORIAS}      # v3.22: un color por categoría
ALTO_MINIMO_NOMBRE = 15          # un rectángulo más bajo que esto (en píxeles) no tiene lugar para escribir su nombre
COLUMNA_ANGOSTA = 56             # por debajo de este ancho de columna el nombre baja de 12 a 11 px


def color_texto(categoria: str, liberado: bool = False) -> QColor:
    """El color del nombre: el que mejor se lee sobre el color de su categoría (ver texto_sobre); apagado si no va."""
    if liberado:
        return QColor(Z["tinta_suave"])
    return QColor(texto_sobre(COLOR_BLOQUE.get(categoria, COLOR_BLOQUE["otro"]).name()))


def color_bloque(categoria: str, liberado: bool = False) -> QColor:
    """El color del bloque. Opaco, para que el contraste del nombre sea el calculado; tenue si ese día no va."""
    c = QColor(COLOR_BLOQUE.get(categoria, COLOR_BLOQUE["otro"]))
    c.setAlpha(70 if liberado else 255)
    return c


def tamano_nombre(ancho_columna: float) -> int:
    """Píxeles de la letra del nombre: 12 (el mínimo del sistema de diseño) o 11 si la columna es angosta."""
    return 12 if ancho_columna >= COLUMNA_ANGOSTA else 11


class SemanaCalendario(QWidget):
    dia_elegido = Signal(object)                     # date

    def __init__(self):
        super().__init__()
        self.dias: list[tuple[date, list]] = []      # [(día, [Item])] de lunes a domingo
        self.elegido: date | None = None
        self.hoy: date | None = None
        self.desde, self.hasta = 6 * 60, 23 * 60      # minutos del día que se ven
        self.nombres_escritos: list[str] = []         # lo último que se escribió dentro de los rectángulos (pruebas)
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
    def _escribir_nombre(self, p: QPainter, rect: QRectF, titulo: str, color: QColor, tachado: bool = False):
        """
        Un nombre dentro de su rectángulo, en letra chica y cortado en el borde; tachado si ese día no va.
        Se usa un QTextDocument porque deja partir una palabra larga («Computación») cuando no entra en la columna:
        con drawText y TextWordWrap la palabra se cortaría de golpe en el borde. v3.24: con guiones suaves en cada
        sílaba (nucleo/silabas.py), así se parte «Com-pu-ta-ción» con guion y no «Computa|ción».
        """
        fuente = QFont(self.font().family())
        fuente.setPixelSize(tamano_nombre(self._ancho_columna()))
        fuente.setBold(True)
        fuente.setStrikeOut(tachado)
        opciones = QTextOption()
        opciones.setWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere)
        doc = QTextDocument()
        doc.setDocumentMargin(0)
        doc.setDefaultFont(fuente)
        doc.setDefaultTextOption(opciones)
        doc.setTextWidth(max(10.0, rect.width() - 5))
        doc.setPlainText(con_guiones(titulo))
        contexto = QAbstractTextDocumentLayout.PaintContext()
        contexto.palette.setColor(QPalette.Text, color)
        p.save()
        p.setClipRect(rect)
        p.translate(rect.left() + 3, rect.top() + 2)
        doc.documentLayout().draw(p, contexto)
        p.restore()
        self.nombres_escritos.append(titulo)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        self.nombres_escritos = []
        mono = QFont(MONO)
        mono.setPixelSize(11)
        p.setFont(mono)
        p.setPen(Z["tinta_suave"])
        for m in range((self.desde // 180 + 1) * 180 if self.desde % 180 else self.desde, self.hasta, 180):
            p.drawText(QRectF(0, self._y(m) - 7, IZQUIERDA - 4, 14), Qt.AlignRight | Qt.AlignVCenter, f"{m // 60}h")
        ancho = self._ancho_columna()
        for i, (dia, items) in enumerate(self.dias):
            x = IZQUIERDA + i * (ancho + SEPARACION)
            self._cabecera(p, dia, QRectF(x, 0, ancho, ARRIBA - 4))
            fondo = QRectF(x, ARRIBA, ancho, self.height() - ARRIBA - 2)
            libre_todo = any(it.tipo == "excepcion" for it in items)
            p.setPen(Qt.NoPen)
            p.setBrush(Z["acento_suave"] if libre_todo else Z["superficie"])
            p.drawRoundedRect(fondo, 8, 8)
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
                if it.tipo == "bloque":
                    p.setBrush(QBrush(color_bloque(it.categoria, True), Qt.BDiagPattern) if it.liberado
                               else color_bloque(it.categoria))
                    p.drawRoundedRect(rect, 4, 4)
                    if rect.height() >= ALTO_MINIMO_NOMBRE:
                        self._escribir_nombre(p, rect, it.titulo, color_texto(it.categoria, it.liberado), it.liberado)
                elif it.tipo in ("tarea", "evento"):
                    # v3.23: con borde y sin relleno, para no confundirse con los bloques rellenos del horario
                    p.setBrush(Z["superficie_alta"])
                    p.setPen(QPen(COLOR[it.tipo], 1.5))
                    p.drawRoundedRect(rect.adjusted(0.75, 0.75, -0.75, -0.75), 4, 4)
                    p.setPen(Qt.NoPen)
                    if rect.height() >= ALTO_MINIMO_NOMBRE:             # v3.24: también llevan su nombre
                        self._escribir_nombre(p, rect, it.titulo, Z["tinta"])
                else:
                    p.setBrush(COLOR.get(it.tipo, Z["linea"]))
                    p.drawRoundedRect(rect, 4, 4)
            if dia == self.elegido:
                p.setBrush(Qt.NoBrush)
                p.setPen(QPen(Z["acento"], 2))
                p.drawRoundedRect(fondo.adjusted(-1, -1, 1, 1), 9, 9)
        p.end()

    def _cabecera(self, p: QPainter, dia: date, caja: QRectF):
        """«M 28»: el día elegido en una píldora azul tenue; hoy subrayado con el color de destaque."""
        fuente = QFont(self.font().family())
        fuente.setPixelSize(12)
        fuente.setBold(True)
        p.setFont(fuente)
        texto = f"{INICIALES[dia.weekday()]} {dia.day}"
        if dia == self.elegido:
            p.setPen(Qt.NoPen)
            p.setBrush(Z["acento_suave"])
            p.drawRoundedRect(caja.adjusted(2, 1, -2, -1), caja.height() / 2, caja.height() / 2)
            p.setPen(Z["acento_tinta"])
        else:
            p.setPen(Z["tinta"] if dia == self.hoy else Z["tinta_suave"])
        p.drawText(caja, Qt.AlignCenter, texto)
        if dia == self.hoy:
            ancho = p.fontMetrics().horizontalAdvance(texto)
            p.fillRect(QRectF(caja.center().x() - ancho / 2, caja.bottom() - 1, ancho, 2), Z["destaque"])
