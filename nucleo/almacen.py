"""
Almacén de tareas sobre SQLite (viene con Python, no hay que instalar nada).

Esta clase es la "puerta" a los datos: la interfaz nunca escribe SQL.
En la Fase 2 se puede crear un AlmacenRemoto con los MISMOS métodos que
hable con tu Worker por HTTP, y el resto del programa no se entera del cambio.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

from nucleo.planificador import siguiente_ocurrencia

FORMATO = "%Y-%m-%d %H:%M"


@dataclass
class Tarea:
    id: int
    titulo: str
    fecha: datetime
    repeticion: str | None
    estado: str          # "pendiente" | "hecha"
    avisada: bool        # True si ya se mostró el aviso de esta ocurrencia


class Almacen:
    def __init__(self, ruta: Path):
        ruta.parent.mkdir(parents=True, exist_ok=True)
        self.con = sqlite3.connect(ruta)
        self.con.row_factory = sqlite3.Row
        self._crear_tablas()

    def _crear_tablas(self):
        self.con.executescript("""
            CREATE TABLE IF NOT EXISTS tareas (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                titulo      TEXT    NOT NULL,
                fecha       TEXT    NOT NULL,          -- 'AAAA-MM-DD HH:MM'
                repeticion  TEXT,                      -- diaria|laborables|semanal|mensual|NULL
                estado      TEXT    NOT NULL DEFAULT 'pendiente',
                avisada     INTEGER NOT NULL DEFAULT 0,
                creada      TEXT    NOT NULL,
                completada  TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_tareas_pend ON tareas(estado, fecha);

            -- Sesiones del modo estudio (para el resumen y la racha)
            CREATE TABLE IF NOT EXISTS sesiones (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                inicio          TEXT    NOT NULL,
                fin             TEXT    NOT NULL,
                pomodoros       INTEGER NOT NULL,
                minutos_enfoque INTEGER NOT NULL,
                distracciones   INTEGER NOT NULL DEFAULT 0
            );

            -- Apodos de apps aprendidos por voz: "el codigo" -> "Visual Studio Code"
            CREATE TABLE IF NOT EXISTS apodos (
                apodo   TEXT PRIMARY KEY,
                destino TEXT NOT NULL
            );

            -- Ajustes sueltos (posición de la cara, etc.)
            CREATE TABLE IF NOT EXISTS ajustes (
                clave TEXT PRIMARY KEY,
                valor TEXT
            );
        """)
        self.con.commit()

    # ---------------------------------------------------------------- tareas
    def agregar(self, titulo: str, fecha: datetime, repeticion: str | None = None) -> Tarea:
        cur = self.con.execute(
            "INSERT INTO tareas (titulo, fecha, repeticion, creada) VALUES (?, ?, ?, ?)",
            (titulo, fecha.strftime(FORMATO), repeticion, datetime.now().strftime(FORMATO)),
        )
        self.con.commit()
        return self.obtener(cur.lastrowid)

    def obtener(self, id_: int) -> Tarea | None:
        fila = self.con.execute("SELECT * FROM tareas WHERE id = ?", (id_,)).fetchone()
        return self._a_tarea(fila) if fila else None

    def pendientes(self) -> list[Tarea]:
        filas = self.con.execute(
            "SELECT * FROM tareas WHERE estado = 'pendiente' ORDER BY fecha").fetchall()
        return [self._a_tarea(f) for f in filas]

    def por_avisar(self, ahora: datetime) -> list[Tarea]:
        """Tareas cuya hora ya llegó y todavía no se avisaron."""
        filas = self.con.execute(
            "SELECT * FROM tareas WHERE estado = 'pendiente' AND avisada = 0 AND fecha <= ? "
            "ORDER BY fecha", (ahora.strftime(FORMATO),)).fetchall()
        return [self._a_tarea(f) for f in filas]

    def marcar_avisada(self, id_: int):
        self.con.execute("UPDATE tareas SET avisada = 1 WHERE id = ?", (id_,))
        self.con.commit()

    def completar(self, id_: int, ahora: datetime | None = None) -> Tarea | None:
        """
        Si la tarea se repite, se reprograma a su siguiente ocurrencia.
        Si no, queda como 'hecha' (no se borra: sirve de historial).
        Devuelve la tarea tal como quedó.
        """
        ahora = ahora or datetime.now()
        tarea = self.obtener(id_)
        if not tarea:
            return None
        siguiente = siguiente_ocurrencia(tarea.fecha, tarea.repeticion, ahora)
        if siguiente:
            self.con.execute("UPDATE tareas SET fecha = ?, avisada = 0 WHERE id = ?",
                             (siguiente.strftime(FORMATO), id_))
        else:
            self.con.execute("UPDATE tareas SET estado = 'hecha', completada = ? WHERE id = ?",
                             (ahora.strftime(FORMATO), id_))
        self.con.commit()
        return self.obtener(id_)

    def posponer(self, id_: int, minutos: int, ahora: datetime | None = None):
        nueva = (ahora or datetime.now()).replace(second=0, microsecond=0) + timedelta(minutes=minutos)
        self.con.execute("UPDATE tareas SET fecha = ?, avisada = 0 WHERE id = ?",
                         (nueva.strftime(FORMATO), id_))
        self.con.commit()

    def editar(self, id_: int, titulo: str, fecha: datetime, repeticion: str | None):
        """
        Cambia título, fecha y repetición. Se reinicia 'avisada' para que la
        nueva hora vuelva a avisar (si ya había sonado y la moviste a más tarde).
        """
        self.con.execute(
            "UPDATE tareas SET titulo = ?, fecha = ?, repeticion = ?, avisada = 0 WHERE id = ?",
            (titulo, fecha.strftime(FORMATO), repeticion, id_))
        self.con.commit()

    def eliminar(self, id_: int):
        self.con.execute("DELETE FROM tareas WHERE id = ?", (id_,))
        self.con.commit()

    def reactivar_avisos_pendientes(self):
        """
        Al abrir el programa: si quedó algún aviso mostrado pero sin responder
        (cerraste el programa con la burbuja abierta), se vuelve a avisar.
        """
        self.con.execute("UPDATE tareas SET avisada = 0 WHERE estado = 'pendiente' AND avisada = 1")
        self.con.commit()

    # -------------------------------------------------------------- sesiones
    def guardar_sesion(self, inicio: datetime, fin: datetime, pomodoros: int,
                       minutos_enfoque: int, distracciones: int):
        if minutos_enfoque <= 0:
            return                      # una sesión de 0 minutos no aporta nada
        self.con.execute(
            "INSERT INTO sesiones (inicio, fin, pomodoros, minutos_enfoque, distracciones) "
            "VALUES (?, ?, ?, ?, ?)",
            (inicio.strftime(FORMATO), fin.strftime(FORMATO), pomodoros, minutos_enfoque, distracciones))
        self.con.commit()

    def resumen_dia(self, dia: date) -> tuple[int, int]:
        """(pomodoros, minutos de enfoque) de un día."""
        fila = self.con.execute(
            "SELECT COALESCE(SUM(pomodoros), 0), COALESCE(SUM(minutos_enfoque), 0) "
            "FROM sesiones WHERE substr(inicio, 1, 10) = ?", (dia.isoformat(),)).fetchone()
        return fila[0], fila[1]

    def racha(self, hoy: date) -> int:
        """
        Días seguidos con al menos una sesión, contando hacia atrás desde hoy.
        Si hoy aún no estudiaste, la racha de ayer sigue viva.
        """
        dias = {f[0] for f in self.con.execute(
            "SELECT DISTINCT substr(inicio, 1, 10) FROM sesiones").fetchall()}
        dia = hoy if hoy.isoformat() in dias else hoy - timedelta(days=1)
        cuenta = 0
        while dia.isoformat() in dias:
            cuenta += 1
            dia -= timedelta(days=1)
        return cuenta

    # ---------------------------------------------------------------- apodos
    def guardar_apodo(self, apodo: str, destino: str):
        """Si el apodo ya existía, se actualiza a qué app apunta."""
        self.con.execute("INSERT INTO apodos (apodo, destino) VALUES (?, ?) "
                         "ON CONFLICT(apodo) DO UPDATE SET destino = excluded.destino", (apodo, destino))
        self.con.commit()

    def apodos(self) -> list[tuple[str, str]]:
        return [(f["apodo"], f["destino"]) for f in
                self.con.execute("SELECT apodo, destino FROM apodos ORDER BY apodo").fetchall()]

    def borrar_apodo(self, apodo: str) -> bool:
        """Devuelve True si existía."""
        cur = self.con.execute("DELETE FROM apodos WHERE apodo = ?", (apodo,))
        self.con.commit()
        return cur.rowcount > 0

    # --------------------------------------------------------------- ajustes
    def leer_ajuste(self, clave: str, defecto: str | None = None) -> str | None:
        fila = self.con.execute("SELECT valor FROM ajustes WHERE clave = ?", (clave,)).fetchone()
        return fila["valor"] if fila else defecto

    def guardar_ajuste(self, clave: str, valor: str):
        self.con.execute("INSERT INTO ajustes (clave, valor) VALUES (?, ?) "
                         "ON CONFLICT(clave) DO UPDATE SET valor = excluded.valor", (clave, valor))
        self.con.commit()

    # ------------------------------------------------------------- privados
    @staticmethod
    def _a_tarea(fila: sqlite3.Row) -> Tarea:
        return Tarea(
            id=fila["id"],
            titulo=fila["titulo"],
            fecha=datetime.strptime(fila["fecha"], FORMATO),
            repeticion=fila["repeticion"],
            estado=fila["estado"],
            avisada=bool(fila["avisada"]),
        )
