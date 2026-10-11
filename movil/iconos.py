"""
Dibuja los íconos de la app del celular a partir de la MISMA cara de la laptop (interfaz/cara.py).
Solo hace falta volver a ejecutarlo si cambias el diseño de la cara:

    python movil/iconos.py
"""
import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPointF, QRectF, Qt          # noqa: E402
from PySide6.QtGui import QColor, QGuiApplication, QImage, QPainter   # noqa: E402

from interfaz.cara import dibujar_cara                  # noqa: E402

DESTINO = RAIZ / "movil" / "publico" / "iconos"
FONDO = "#0f1116"


def cara(lado: int, radio_relativo: float, fondo: str | None) -> QImage:
    img = QImage(lado, lado, QImage.Format_ARGB32)
    img.fill(QColor(fondo) if fondo else Qt.transparent)
    p = QPainter(img)
    dibujar_cara(p, QPointF(lado / 2, lado / 2), lado * radio_relativo, "tranquilo")
    p.end()
    return img


def insignia(lado: int) -> QImage:
    """Ícono chico de la barra de notificaciones: Android solo usa la silueta (blanco sobre transparente)."""
    img = QImage(lado, lado, QImage.Format_ARGB32)
    img.fill(Qt.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("white"))
    w, h, sep = lado * 0.24, lado * 0.42, lado * 0.19
    for lado_ojo in (-1, 1):
        cx = lado / 2 + lado_ojo * sep
        p.drawRoundedRect(QRectF(cx - w / 2, lado / 2 - h / 2, w, h), w / 2, w / 2)
    p.end()
    return img


if __name__ == "__main__":
    app = QGuiApplication.instance() or QGuiApplication([])
    DESTINO.mkdir(parents=True, exist_ok=True)
    cara(192, 0.42, None).save(str(DESTINO / "icono-192.png"))
    cara(512, 0.42, None).save(str(DESTINO / "icono-512.png"))
    cara(512, 0.36, FONDO).save(str(DESTINO / "icono-mascara-512.png"))   # dentro de la zona segura de Android
    cara(180, 0.40, FONDO).save(str(DESTINO / "icono-180.png"))
    insignia(96).save(str(DESTINO / "insignia-96.png"))
    print("Íconos listos en", DESTINO.relative_to(RAIZ))
