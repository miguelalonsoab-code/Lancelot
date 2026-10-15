"""
La cara del asistente: un círculo flotante, siempre encima de las demás ventanas,
con dos ojos animados. Se dibuja 100 % con código (QPainter), sin imágenes.

Estados (los decide el núcleo, aquí solo se dibujan):
    tranquilo  -> anillo turquesa, parpadea y mira alrededor
    estudio    -> anillo violeta que se vacía con el tiempo, mirada concentrada
    descanso   -> anillo verde agua con el tiempo de descanso
    esperando  -> anillo violeta latiendo lento: "¿seguimos?"
    sospecha   -> ojos entrecerrados mirando de reojo: detectó una distracción
    escuchando -> anillo celeste y barritas de sonido: esperando lo que le digas
    pendiente  -> anillo ámbar, hay tareas para hoy (el número abajo dice cuántas)
    alerta     -> anillo naranja que late, ojos grandes: algo venció
    feliz      -> ojos "^ ^" un par de segundos al completar o agregar una tarea
    dormido    -> ojos cerrados y "z" flotando (de noche, sin pendientes)

Interacción:
    clic izquierdo  -> abre/cierra el panel de tareas
    arrastrar       -> mueve la cara (la posición se guarda)
    clic derecho    -> menú
"""
from __future__ import annotations

import math
import random
import time

from PySide6.QtCore import QPoint, QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import (QColor, QCursor, QFont, QPainter, QPainterPath, QPen, QPixmap,
                           QRadialGradient)
from PySide6.QtWidgets import QWidget

from config import COLORES, FPS_ANIMACION, TAMANO_CARA

MARGEN = 14            # espacio transparente alrededor para el brillo del anillo
DURACION_FELIZ = 2.5   # segundos


def dibujar_cara(p: QPainter, centro: QPointF, radio: float, estado: str, t: float = 0.0,
                 cierre: float = 0.0, mirada: QPointF = QPointF(0, 0), contador: int = 0,
                 progreso: float | None = None, texto: str | None = None, silencio: bool = False,
                 microfono: bool = False, hablando: bool = False):
    """
    Dibuja la cara completa. Es una función suelta (no un método) para poder
    reutilizarla en el ícono de la bandeja y en las pruebas.
      t        -> segundos transcurridos (para animaciones cíclicas)
      cierre   -> 0 = ojos abiertos, 1 = cerrados (parpadeo)
      mirada   -> desplazamiento de los ojos en píxeles
      contador -> número pequeño abajo (tareas de hoy)
      progreso -> 0..1 tiempo que QUEDA de la fase (el anillo se dibuja como arco)
      texto    -> texto pequeño abajo (p. ej. "18:42"); reemplaza al contador
      silencio -> dibuja una campanita tachada arriba
      microfono-> dibuja un micrófono arriba (escucha continua activada)
      hablando -> los ojos rebotan suavecito mientras habla
    """
    p.setRenderHint(QPainter.Antialiasing)
    color_anillo = QColor(COLORES[estado])
    if estado == "escuchando":
        pulso = (math.sin(t * 5) + 1) / 2
    elif estado in ("alerta", "sospecha"):
        pulso = (math.sin(t * 6) + 1) / 2
    elif estado == "esperando":
        pulso = (math.sin(t * 2.5) + 1) / 2            # latido lento: "¿seguimos?"
    else:
        pulso = 0.0

    # 1) Brillo exterior del anillo
    brillo = QRadialGradient(centro, radio + MARGEN)
    c = QColor(color_anillo)
    c.setAlpha(int(70 + 90 * pulso))
    brillo.setColorAt((radio - 4) / (radio + MARGEN), c)
    c.setAlpha(0)
    brillo.setColorAt(1.0, c)
    p.setPen(Qt.NoPen)
    p.setBrush(brillo)
    p.drawEllipse(centro, radio + MARGEN, radio + MARGEN)

    # 2) Cuerpo (bisel)
    p.setBrush(QColor(COLORES["fondo_bisel"]))
    p.drawEllipse(centro, radio, radio)

    # 3) Anillo de estado (completo, o como arco de tiempo restante)
    p.setBrush(Qt.NoBrush)
    if progreso is None:
        p.setPen(QPen(color_anillo, 3.5 + 2.0 * pulso))
        p.drawEllipse(centro, radio - 7, radio - 7)
    else:
        tenue = QColor(color_anillo)
        tenue.setAlpha(45)
        p.setPen(QPen(tenue, 3.5))
        p.drawEllipse(centro, radio - 7, radio - 7)
        caja = QRectF(centro.x() - (radio - 7), centro.y() - (radio - 7), 2 * (radio - 7), 2 * (radio - 7))
        p.setPen(QPen(color_anillo, 4.5, Qt.SolidLine, Qt.RoundCap))
        # Qt mide los ángulos en 1/16 de grado; 90° = arriba; negativo = sentido horario
        p.drawArc(caja, 90 * 16, int(-360 * 16 * max(0.0, min(1.0, progreso))))

    # 4) Pantalla
    radio_pantalla = radio - 12
    fondo = QRadialGradient(centro + QPointF(0, -radio_pantalla * 0.4), radio_pantalla * 1.3)
    fondo.setColorAt(0, QColor("#11141a"))
    fondo.setColorAt(1, QColor(COLORES["pantalla"]))
    p.setPen(Qt.NoPen)
    p.setBrush(fondo)
    p.drawEllipse(centro, radio_pantalla, radio_pantalla)

    # 5) Ojos
    escala = radio / 75.0                       # todo se diseñó para radio 75
    sep = 28 * escala                           # distancia del centro a cada ojo
    ancho, alto = 32 * escala, 39 * escala
    base = centro + QPointF(0, -4 * escala) + mirada
    color_ojo = QColor(COLORES["ojos"])

    if estado == "alerta":
        ancho, alto = ancho * 1.15, alto * 1.15
        base += QPointF(0, math.sin(t * 12) * 1.5 * escala)    # pequeño salto
    elif estado == "estudio":
        alto *= 0.82                                           # mirada concentrada
    elif estado == "sospecha":
        alto *= 0.42                                           # ojos entrecerrados 🤨
    elif estado == "escuchando":
        ancho, alto = ancho * 1.08, alto * 1.08                # ojos atentos
    if hablando:
        base += QPointF(0, abs(math.sin(t * 9)) * -2.5 * escala)

    for lado in (-1, 1):
        ojo = base + QPointF(lado * sep, 0)
        if estado == "feliz":
            _ojo_feliz(p, ojo, ancho, alto, color_ojo, escala)
        elif estado == "dormido":
            _ojo_dormido(p, ojo, ancho, color_ojo, escala)
        else:
            h = max(alto * (1 - cierre), 3 * escala)
            _ojo_abierto(p, ojo, ancho, h, color_ojo)

    if estado == "dormido":
        _zetas(p, centro, radio_pantalla, t, escala)

    if estado == "escuchando":
        _ondas(p, centro + QPointF(0, radio_pantalla * 0.5), t, escala, color_anillo)

    # 6) Texto inferior: tiempo del pomodoro o contador de tareas de hoy
    if texto is None and contador > 0 and estado not in ("dormido", "feliz", "escuchando"):
        texto = str(contador) if contador < 10 else "9+"
    if texto:
        p.setPen(color_anillo)
        f = QFont("Segoe UI", max(7, int(8 * escala)))
        f.setBold(True)
        p.setFont(f)
        p.drawText(QRectF(centro.x() - 40, centro.y() + radio_pantalla * 0.42, 80, 16 * escala),
                   Qt.AlignCenter, texto)

    # 7) Íconos arriba: micrófono (escucha continua) y campanita tachada (silencio)
    iconos = [f for f, activo in ((_microfono, microfono), (_campana_tachada, silencio)) if activo]
    for i, dibujar in enumerate(iconos):
        dx = (i - (len(iconos) - 1) / 2) * 16 * escala
        dibujar(p, centro + QPointF(dx, -radio_pantalla * 0.68), escala)


def _ondas(p, c: QPointF, t, escala, color):
    """Cinco barritas que suben y bajan, como un ecualizador: 'te estoy escuchando'."""
    p.setPen(Qt.NoPen)
    p.setBrush(color)
    for i in range(5):
        h = (4 + 7 * abs(math.sin(t * 7 + i * 0.9))) * escala
        x = c.x() + (i - 2) * 6 * escala
        p.drawRoundedRect(QRectF(x - 1.5 * escala, c.y() - h / 2, 3 * escala, h), 1.5 * escala, 1.5 * escala)


def _microfono(p, c: QPointF, escala):
    gris = QColor("#8bd3ff")
    p.setPen(QPen(gris, 1.5 * escala, Qt.SolidLine, Qt.RoundCap))
    p.setBrush(Qt.NoBrush)
    p.drawRoundedRect(QRectF(c.x() - 2.5 * escala, c.y() - 6 * escala, 5 * escala, 8 * escala),
                      2.5 * escala, 2.5 * escala)
    arco = QRectF(c.x() - 4.5 * escala, c.y() - 4 * escala, 9 * escala, 8.5 * escala)
    p.drawArc(arco, 200 * 16, 140 * 16)
    p.drawLine(QPointF(c.x(), c.y() + 4.5 * escala), QPointF(c.x(), c.y() + 6.5 * escala))


def _campana_tachada(p, c: QPointF, escala):
    gris = QColor("#8b93a1")
    p.setPen(QPen(gris, 1.6 * escala, Qt.SolidLine, Qt.RoundCap))
    p.setBrush(Qt.NoBrush)
    camino = QPainterPath()
    w, h = 9 * escala, 9 * escala
    camino.moveTo(c.x() - w / 2, c.y() + h / 2)
    camino.quadTo(c.x() - w / 2, c.y() - h / 2, c.x(), c.y() - h / 2)
    camino.quadTo(c.x() + w / 2, c.y() - h / 2, c.x() + w / 2, c.y() + h / 2)
    camino.closeSubpath()
    p.drawPath(camino)
    p.drawLine(QPointF(c.x() - w * 0.7, c.y() - h * 0.7), QPointF(c.x() + w * 0.7, c.y() + h * 0.8))


def _ojo_abierto(p, ojo: QPointF, ancho, alto, color):
    halo = QColor(color)
    halo.setAlpha(28)
    p.setPen(Qt.NoPen)
    p.setBrush(halo)
    p.drawRoundedRect(QRectF(ojo.x() - ancho / 2 - 3, ojo.y() - alto / 2 - 3, ancho + 6, alto + 6),
                      ancho / 2 + 3, ancho / 2 + 3)
    p.setBrush(color)
    radio_borde = min(ancho, alto) / 2
    p.drawRoundedRect(QRectF(ojo.x() - ancho / 2, ojo.y() - alto / 2, ancho, alto),
                      radio_borde, radio_borde)


def _ojo_feliz(p, ojo: QPointF, ancho, alto, color, escala):
    camino = QPainterPath()
    camino.moveTo(ojo.x() - ancho / 2, ojo.y() + alto * 0.15)
    camino.quadTo(ojo.x(), ojo.y() - alto * 0.65, ojo.x() + ancho / 2, ojo.y() + alto * 0.15)
    p.setBrush(Qt.NoBrush)
    p.setPen(QPen(color, 6 * escala, Qt.SolidLine, Qt.RoundCap))
    p.drawPath(camino)


def _ojo_dormido(p, ojo: QPointF, ancho, color, escala):
    camino = QPainterPath()
    camino.moveTo(ojo.x() - ancho / 2, ojo.y())
    camino.quadTo(ojo.x(), ojo.y() + 7 * escala, ojo.x() + ancho / 2, ojo.y())
    c = QColor(color)
    c.setAlpha(170)
    p.setBrush(Qt.NoBrush)
    p.setPen(QPen(c, 4 * escala, Qt.SolidLine, Qt.RoundCap))
    p.drawPath(camino)


def _zetas(p, centro, radio_pantalla, t, escala):
    """Tres 'z' que suben y se desvanecen en ciclo."""
    for i in range(3):
        fase = ((t * 0.35) + i / 3) % 1.0
        x = centro.x() + radio_pantalla * 0.35 + fase * 14 * escala
        y = centro.y() - radio_pantalla * 0.25 - fase * 30 * escala
        c = QColor(COLORES["ojos"])
        c.setAlpha(int(200 * math.sin(math.pi * fase)))
        p.setPen(c)
        p.setFont(QFont("Segoe UI", int((7 + fase * 5) * escala), QFont.Bold))
        p.drawText(QPointF(x, y), "z")


def pixmap_cara(tamano: int, estado: str = "tranquilo") -> QPixmap:
    """Imagen estática de la cara (para el ícono de la bandeja)."""
    pm = QPixmap(tamano, tamano)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    radio = tamano / 2 - 1
    # Sin margen de brillo: en un ícono pequeño se ve mejor así
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(COLORES["fondo_bisel"]))
    p.drawEllipse(QPointF(tamano / 2, tamano / 2), radio, radio)
    p.setBrush(QColor(COLORES[estado]))
    p.drawEllipse(QPointF(tamano / 2, tamano / 2), radio * 0.88, radio * 0.88)
    p.setBrush(QColor(COLORES["pantalla"]))
    p.drawEllipse(QPointF(tamano / 2, tamano / 2), radio * 0.74, radio * 0.74)
    p.setBrush(QColor(COLORES["ojos"]))
    w, h, sep = radio * 0.26, radio * 0.34, radio * 0.30
    for lado in (-1, 1):
        cx = tamano / 2 + lado * sep
        p.drawRoundedRect(QRectF(cx - w / 2, tamano / 2 - h / 2, w, h), w / 2, w / 2)
    p.end()
    return pm


class Cara(QWidget):
    clicada = Signal()
    menu_pedido = Signal(QPoint)
    movida = Signal(QPoint)
    reposo = Signal()                  # el mouse se quedó encima un rato (sin hacer clic)

    def __init__(self):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(TAMANO_CARA + 2 * MARGEN, TAMANO_CARA + 2 * MARGEN)

        self.estado_base = "tranquilo"     # el que decide el núcleo
        self.feliz_hasta = 0.0
        self.contador = 0
        self.progreso: float | None = None # arco de tiempo (modo estudio)
        self.texto: str | None = None      # "18:42", "pausa", etc.
        self.silencio = False
        self.microfono = False             # escucha continua activada
        self.hablando = False

        # Estado de la animación
        self.t = 0.0
        self._ultimo = time.monotonic()
        self.cierre = 0.0
        self._inicio_parpadeo = -1.0
        self._proximo_parpadeo = 2.0
        self.mirada = QPointF(0, 0)
        self._objetivo_mirada = QPointF(0, 0)
        self._proximo_vistazo = 1.0

        # Arrastre
        self._pos_presion = None
        self._pos_ventana = None
        self._arrastrando = False

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(int(1000 / FPS_ANIMACION))

        # Mouse encima sin hacer clic -> señal 'reposo' (Lancelot dice una frase)
        self.segundos_reposo = 1.5
        self._reloj_reposo = QTimer(self, singleShot=True)
        self._reloj_reposo.timeout.connect(self._al_reposar)

    # ------------------------------------------------------------ API pública
    @property
    def estado(self) -> str:
        if self.estado_base == "escuchando":            # escuchar le gana a todo
            return "escuchando"
        return "feliz" if self.t < self.feliz_hasta else self.estado_base

    def set_estado(self, estado: str):
        self.estado_base = estado

    def celebrar(self):
        self.feliz_hasta = self.t + DURACION_FELIZ

    # ------------------------------------------------------------- animación
    def _tick(self):
        ahora = time.monotonic()
        dt = min(ahora - self._ultimo, 0.1)
        self._ultimo = ahora
        self.t += dt

        # Parpadeo: cada 2.5–6 s, a veces doble
        if self.t >= self._proximo_parpadeo and self.estado in (
                "tranquilo", "pendiente", "alerta", "estudio", "descanso", "esperando", "escuchando"):
            self._inicio_parpadeo = self.t
            doble = random.random() < 0.2
            self._proximo_parpadeo = self.t + (0.3 if doble else random.uniform(2.5, 6.0))
        fase = (self.t - self._inicio_parpadeo) / 0.18
        self.cierre = math.sin(math.pi * fase) if 0 <= fase <= 1 else 0.0

        # Mirada: sigue al mouse si está cerca; si no, mira a lados al azar
        self._actualizar_objetivo_mirada()
        k = min(1.0, dt * 8)
        self.mirada += (self._objetivo_mirada - self.mirada) * k

        self.update()

    def _actualizar_objetivo_mirada(self):
        escala = TAMANO_CARA / 150
        centro = self.mapToGlobal(self.rect().center())
        d = QCursor.pos() - centro
        dist = math.hypot(d.x(), d.y())
        if self.estado == "dormido":
            self._objetivo_mirada = QPointF(0, 0)
        elif self.estado == "estudio":
            self._objetivo_mirada = QPointF(0, 4 * escala)        # "leyendo", mirando abajo
        elif self.estado == "sospecha":
            self._objetivo_mirada = QPointF(9 * escala, -1 * escala)   # mirada de reojo
        elif self.estado == "escuchando":
            self._objetivo_mirada = QPointF(0, -2 * escala)            # te mira de frente
        elif 1 < dist < 500:
            fuerza = min(dist / 250, 1.0)
            self._objetivo_mirada = QPointF(d.x() / dist * 9 * escala * fuerza,
                                            d.y() / dist * 6 * escala * fuerza)
        elif self.t >= self._proximo_vistazo:
            self._proximo_vistazo = self.t + random.uniform(1.5, 4.5)
            if random.random() < 0.4:
                self._objetivo_mirada = QPointF(0, 0)
            else:
                self._objetivo_mirada = QPointF(random.uniform(-8, 8) * escala,
                                                random.uniform(-4, 4) * escala)

    def paintEvent(self, _):
        p = QPainter(self)
        dibujar_cara(p, QPointF(self.width() / 2, self.height() / 2), TAMANO_CARA / 2,
                     self.estado, self.t, self.cierre, self.mirada, self.contador,
                     self.progreso, self.texto, self.silencio, self.microfono, self.hablando)
        p.end()

    # ------------------------------------------------------------------ mouse
    def enterEvent(self, e):
        self._reloj_reposo.start(int(self.segundos_reposo * 1000))
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._reloj_reposo.stop()
        super().leaveEvent(e)

    def _al_reposar(self):
        if self.underMouse() and self._pos_presion is None:     # sigue encima y no lo está arrastrando
            self.reposo.emit()

    def mousePressEvent(self, e):
        self._reloj_reposo.stop()                  # un clic es otra cosa: abre el panel o el menú
        if e.button() == Qt.LeftButton:
            self._pos_presion = e.globalPosition().toPoint()
            self._pos_ventana = self.pos()
            self._arrastrando = False
        elif e.button() == Qt.RightButton:
            self.menu_pedido.emit(e.globalPosition().toPoint())

    def mouseMoveEvent(self, e):
        if self._pos_presion is None:
            return
        delta = e.globalPosition().toPoint() - self._pos_presion
        if self._arrastrando or delta.manhattanLength() > 4:
            self._arrastrando = True
            self.move(self._pos_ventana + delta)

    def mouseReleaseEvent(self, e):
        if e.button() != Qt.LeftButton or self._pos_presion is None:
            return
        if self._arrastrando:
            self.movida.emit(self.pos())
        else:
            self.clicada.emit()
        self._pos_presion = None
        self._arrastrando = False
