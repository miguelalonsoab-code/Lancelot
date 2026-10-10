"""
Copia de seguridad diaria de la base de datos (tareas, sesiones de estudio, apodos).

    datos/respaldos/tareas-2026-10-09.db
    datos/respaldos/tareas-2026-10-08.db
    ...                                  (se conservan las últimas 7)

Se usa la función backup() de SQLite y no una simple copia del archivo: así la copia
sale consistente aunque Lancelot esté escribiendo en ese momento.

Para restaurar: cierra Lancelot, copia el respaldo que quieras sobre datos/tareas.db
(renómbralo a tareas.db) y vuelve a abrirlo.
"""
from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path


def hacer_respaldo(ruta_bd: Path, carpeta: Path, hoy: date, conservar: int = 7) -> Path | None:
    """
    Crea el respaldo de hoy si todavía no existe y borra los más viejos.
    Devuelve la ruta del respaldo creado, o None si ya había uno de hoy (o no hay base).
    """
    if not ruta_bd.exists():
        return None
    carpeta.mkdir(parents=True, exist_ok=True)
    destino = carpeta / f"{ruta_bd.stem}-{hoy.isoformat()}.db"
    creado = None
    if not destino.exists():
        origen = sqlite3.connect(ruta_bd)
        copia = sqlite3.connect(destino)
        try:
            origen.backup(copia)
        finally:
            copia.close()
            origen.close()
        creado = destino
    # El nombre lleva la fecha AAAA-MM-DD, así que el orden alfabético es el orden por fecha
    respaldos = sorted(carpeta.glob(f"{ruta_bd.stem}-*.db"))
    for viejo in respaldos[:-conservar]:
        viejo.unlink()
    return creado
