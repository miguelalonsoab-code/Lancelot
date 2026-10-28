"""
Tema Zafiro (v3.24): los colores y las fuentes del sistema de diseño de Lancelot, dirección B · Zafiro.

    fondo · superficie · superficie_alta      tres niveles: la ventana, lo que se apoya en ella, lo que se pulsa
    linea (decorativa) · linea_fuerte          borde de controles (≥ 3:1)
    tinta · tinta_suave                        texto principal y secundario (≥ 4.5:1 sobre las tres superficies)
    acento · sobre_acento                      la acción primaria (una por pantalla) y el texto encima
    acento_tinta · acento_suave                azul como texto · relleno tenue (chip activo, hueco libre)
    destaque                                   un detalle por zona (subrayado de la pestaña, «hoy»)
    exito · peligro                            «Listo» (verde azulado) · «Vencida» (naranja), siempre con palabra

Los colores de la CARA (config.COLORES: tranquilo, pendiente, alerta…) no cambian: son su ánimo, no la interfaz.

Fuentes: Manrope (texto) y JetBrains Mono (horas, fechas y cifras), licencia SIL OFL 1.1 (interfaz/fuentes/OFL-*.txt).
Van dentro del programa: construir.py las copia al instalador con --add-data.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QFont, QFontDatabase

ZAFIRO = {
    "fondo": "#060d1c",
    "superficie": "#0b172e",
    "superficie_alta": "#112347",
    "linea": "#1b3359",
    "linea_fuerte": "#5a7db2",
    "tinta": "#eaf1ff",
    "tinta_suave": "#a6b9db",
    "acento": "#8fc0ff",
    "sobre_acento": "#07112a",
    "acento_tinta": "#a9d0ff",
    "acento_suave": "#163766",
    "destaque": "#8fc0ff",
    "exito": "#47d9ae",
    "peligro": "#ff9a5c",
}
SANS = "Manrope"
MONO = "JetBrains Mono"
CARPETA_FUENTES = Path(__file__).resolve().parent / "fuentes"
_cargadas: list[str] = []


def cargar_fuentes(app=None) -> list[str]:
    """
    Registra Manrope y JetBrains Mono (una sola vez) y, si se pasa la QApplication, pone Manrope como letra
    de toda la app. Devuelve las familias cargadas; si faltan los archivos, Qt usa la letra del sistema.
    """
    if not _cargadas:
        for archivo in sorted(CARPETA_FUENTES.glob("*.ttf")):
            ident = QFontDatabase.addApplicationFont(str(archivo))
            if ident >= 0:
                _cargadas.extend(f for f in QFontDatabase.applicationFontFamilies(ident) if f not in _cargadas)
    if app is not None and SANS in _cargadas:
        fuente = QFont(SANS)
        fuente.setPixelSize(13)
        app.setFont(fuente)
    return list(_cargadas)


def familia(sans: bool = True) -> str:
    """El nombre para la hoja de estilos, con alternativa si la fuente no está."""
    return f"'{SANS}', 'Segoe UI'" if sans else f"'{MONO}', Consolas"
