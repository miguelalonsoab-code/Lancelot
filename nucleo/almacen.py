"""
Almacén de tareas sobre SQLite (viene con Python, no hay que instalar nada).

Esta clase es la "puerta" a los datos: la interfaz nunca escribe SQL.

Sincronización con el celular (etapa 3): cada tarea tiene además
  uuid          identificador que es el mismo en la laptop y en el servidor
  actualizada   milisegundos del último cambio: si laptop y celular cambian lo mismo, gana el más reciente
  borrada       al eliminar se marca (no se borra) para que el celular también se entere
  sincronizada  0 = este cambio todavía no se subió al servidor
"avisada" NO se sincroniza: cada dispositivo lleva su propia cuenta de qué ya avisó.

Eventos (v3.10): además de tareas hay EVENTOS (aniversario, examen, viaje…)
  tipo          'tarea' | 'evento'
  anticipacion  con cuántos días antes avisar: '7,1' = una semana y un día antes (NULL = solo a su hora)
  aviso_previo  cuándo se mandó el último aviso anticipado. Desde la v3.11 SÍ viaja al celular, pero
                aparte de las ediciones: gana el más reciente, sin tocar 'actualizada' (así no pisa tus cambios).
"""
from __future__ import annotations

import re
import sqlite3
import time
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

from nucleo.planificador import HORA_AVISO_PREVIO, aviso_previo_pendiente, siguiente_ocurrencia

FORMATO = "%Y-%m-%d %H:%M"
# Cambios por pedido a /api/sync. El plan gratuito de Cloudflare limita las consultas a la base por pedido
# (unas 50): con lotes chicos, la primera sincronización (todo tu historial) va en varios pedidos seguidos.
LOTE_SINCRONIZACION = 40
TIPOS_VALIDOS = ("tarea", "evento")
_ANTICIPACION = re.compile(r"^\d{1,3}(?:,\d{1,3})*$")
SIN_CAMBIO = object()          # para editar(): "deja el valor que tenía"


def _fecha_valida(texto) -> bool:
    try:
        datetime.strptime(str(texto), FORMATO)
        return True
    except ValueError:
        return False


def limpiar_anticipacion(valor) -> str | None:
    """'7,1' se acepta; cualquier otra cosa (vacío, basura) queda en None = sin avisos previos."""
    texto = str(valor or "").replace(" ", "")
    return texto if _ANTICIPACION.match(texto) else None


def _ms() -> int:
    """Ahora en milisegundos (la misma unidad que usa el servidor)."""
    return int(time.time() * 1000)


@dataclass
class Tarea:
    id: int
    titulo: str
    fecha: datetime
    repeticion: str | None
    estado: str          # "pendiente" | "hecha"
    avisada: bool        # True si ya se mostró el aviso de esta ocurrencia
    tipo: str = "tarea"              # "tarea" | "evento"
    anticipacion: str | None = None  # "7,1": avisar una semana y un día antes

    @property
    def es_evento(self) -> bool:
        return self.tipo == "evento"


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
                completada  TEXT,
                uuid        TEXT,
                actualizada INTEGER NOT NULL DEFAULT 0,
                borrada     INTEGER NOT NULL DEFAULT 0,
                sincronizada INTEGER NOT NULL DEFAULT 0,
                tipo        TEXT    NOT NULL DEFAULT 'tarea',
                anticipacion TEXT,                     -- '7,1' = avisar 7 y 1 días antes
                aviso_previo TEXT                      -- último aviso anticipado (no se sincroniza)
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
        self._migrar_para_sincronizar()
        self.con.commit()

    def _migrar_para_sincronizar(self):
        """
        Bases creadas antes de la v3.9 no tienen las columnas de sincronización (ni las de eventos, de la v3.10):
        se agregan sin perder nada, y cada tarea existente recibe su uuid y queda marcada para subirse al
        servidor la primera vez. Las tareas viejas quedan como 'tarea'.
        """
        columnas = {f["name"] for f in self.con.execute("PRAGMA table_info(tareas)")}
        for nombre, tipo in (("uuid", "TEXT"), ("actualizada", "INTEGER NOT NULL DEFAULT 0"),
                             ("borrada", "INTEGER NOT NULL DEFAULT 0"),
                             ("sincronizada", "INTEGER NOT NULL DEFAULT 0"),
                             ("tipo", "TEXT NOT NULL DEFAULT 'tarea'"),        # v3.10: eventos
                             ("anticipacion", "TEXT"), ("aviso_previo", "TEXT")):
            if nombre not in columnas:
                self.con.execute(f"ALTER TABLE tareas ADD COLUMN {nombre} {tipo}")
        ahora = _ms()
        for (id_,) in self.con.execute("SELECT id FROM tareas WHERE uuid IS NULL").fetchall():
            self.con.execute("UPDATE tareas SET uuid = ?, actualizada = ?, sincronizada = 0 WHERE id = ?",
                             (str(uuid.uuid4()), ahora, id_))
        self.con.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_tareas_uuid ON tareas(uuid)")
        self.con.execute("CREATE INDEX IF NOT EXISTS idx_tareas_subir ON tareas(sincronizada)")

    # ---------------------------------------------------------------- tareas
    def agregar(self, titulo: str, fecha: datetime, repeticion: str | None = None,
                tipo: str = "tarea", anticipacion: str | None = None) -> Tarea:
        cur = self.con.execute(
            "INSERT INTO tareas (titulo, fecha, repeticion, creada, uuid, actualizada, tipo, anticipacion) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (titulo, fecha.strftime(FORMATO), repeticion, datetime.now().strftime(FORMATO), str(uuid.uuid4()), _ms(),
             tipo if tipo in TIPOS_VALIDOS else "tarea", limpiar_anticipacion(anticipacion)),
        )
        self.con.commit()
        return self.obtener(cur.lastrowid)

    def obtener(self, id_: int) -> Tarea | None:
        fila = self.con.execute("SELECT * FROM tareas WHERE id = ? AND borrada = 0", (id_,)).fetchone()
        return self._a_tarea(fila) if fila else None

    def pendientes(self) -> list[Tarea]:
        filas = self.con.execute(
            "SELECT * FROM tareas WHERE estado = 'pendiente' AND borrada = 0 ORDER BY fecha").fetchall()
        return [self._a_tarea(f) for f in filas]

    def por_avisar(self, ahora: datetime) -> list[Tarea]:
        """Tareas cuya hora ya llegó y todavía no se avisaron."""
        filas = self.con.execute(
            "SELECT * FROM tareas WHERE estado = 'pendiente' AND borrada = 0 AND avisada = 0 AND fecha <= ? "
            "ORDER BY fecha", (ahora.strftime(FORMATO),)).fetchall()
        return [self._a_tarea(f) for f in filas]

    def vencidas(self, ahora: datetime) -> list[Tarea]:
        """Tareas pendientes cuya hora ya pasó (se hayan avisado o no). Los eventos no "vencen": se cierran solos."""
        filas = self.con.execute(
            "SELECT * FROM tareas WHERE estado = 'pendiente' AND borrada = 0 AND tipo <> 'evento' AND fecha <= ? "
            "ORDER BY fecha",
            (ahora.strftime(FORMATO),)).fetchall()
        return [self._a_tarea(f) for f in filas]

    def por_avisar_antes(self, ahora: datetime, hora: tuple[int, int] = HORA_AVISO_PREVIO) -> list[tuple[Tarea, int]]:
        """
        Eventos (o tareas con "avísame N días antes") a los que les toca un aviso ANTICIPADO ahora.
        Devuelve [(tarea, días que faltan según el aviso)]. Ver planificador.aviso_previo_pendiente.
        """
        filas = self.con.execute(
            "SELECT * FROM tareas WHERE estado = 'pendiente' AND borrada = 0 AND anticipacion IS NOT NULL "
            "AND anticipacion <> '' AND fecha > ? ORDER BY fecha", (ahora.strftime(FORMATO),)).fetchall()
        tocan = []
        for f in filas:
            desde = datetime.fromtimestamp(f["actualizada"] / 1000) if f["actualizada"] else datetime.min
            if f["aviso_previo"]:
                desde = max(desde, datetime.strptime(f["aviso_previo"], FORMATO))
            tarea = self._a_tarea(f)
            if (n := aviso_previo_pendiente(tarea.fecha, tarea.anticipacion, desde, ahora, hora)) is not None:
                tocan.append((tarea, n))
        return tocan

    def marcar_aviso_previo(self, id_: int, ahora: datetime):
        """
        Anota que ya se avisó con anticipación. No es una edición (no cambia 'actualizada'), pero queda
        para subir: así el celular sabe que ya lo viste aquí y no te lo repite.
        """
        self.con.execute("UPDATE tareas SET aviso_previo = ?, sincronizada = 0 WHERE id = ?",
                         (ahora.strftime(FORMATO), id_))
        self.con.commit()

    def cerrar_eventos_pasados(self, ahora: datetime) -> list[int]:
        """
        Un evento cuyo día ya pasó no es una "tarea vencida": si se repite (cumpleaños) pasa al
        próximo año; si no, queda como hecho. Así no se acumulan en VENCIDAS. Devuelve los id que cambiaron.
        """
        filas = self.con.execute(
            "SELECT * FROM tareas WHERE estado = 'pendiente' AND borrada = 0 AND tipo = 'evento' AND fecha < ?",
            (ahora.strftime("%Y-%m-%d 00:00"),)).fetchall()
        for f in filas:
            t = self._a_tarea(f)
            siguiente = siguiente_ocurrencia(t.fecha, t.repeticion, ahora)
            if siguiente:
                self._cambiar(t.id, "fecha = ?, avisada = 0", siguiente.strftime(FORMATO))
            else:
                self._cambiar(t.id, "estado = 'hecha', completada = ?", ahora.strftime(FORMATO))
        return [f["id"] for f in filas]

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
            self._cambiar(id_, "fecha = ?, avisada = 0", siguiente.strftime(FORMATO))
        else:
            self._cambiar(id_, "estado = 'hecha', completada = ?", ahora.strftime(FORMATO))
        return self.obtener(id_)

    def posponer(self, id_: int, minutos: int, ahora: datetime | None = None):
        nueva = (ahora or datetime.now()).replace(second=0, microsecond=0) + timedelta(minutes=minutos)
        self._cambiar(id_, "fecha = ?, avisada = 0", nueva.strftime(FORMATO))

    def reprogramar(self, id_: int, fecha: datetime):
        """Solo cambia la fecha (título y repetición quedan igual) y vuelve a avisar a esa hora."""
        self._cambiar(id_, "fecha = ?, avisada = 0", fecha.strftime(FORMATO))

    def editar(self, id_: int, titulo: str, fecha: datetime, repeticion: str | None,
               tipo=SIN_CAMBIO, anticipacion=SIN_CAMBIO):
        """
        Cambia título, fecha y repetición (y, si se indican, tipo y anticipación).
        Se reinicia 'avisada' para que la nueva hora vuelva a avisar (si ya había sonado y la moviste).
        """
        asignaciones, valores = "titulo = ?, fecha = ?, repeticion = ?, avisada = 0", [titulo, fecha.strftime(FORMATO),
                                                                                       repeticion]
        if tipo is not SIN_CAMBIO and tipo in TIPOS_VALIDOS:
            asignaciones += ", tipo = ?"
            valores.append(tipo)
        if anticipacion is not SIN_CAMBIO:
            asignaciones += ", anticipacion = ?"
            valores.append(limpiar_anticipacion(anticipacion))
        self._cambiar(id_, asignaciones, *valores)

    def eliminar(self, id_: int):
        """Se marca como borrada (no desaparece de la base) para que el celular también se entere."""
        self._cambiar(id_, "borrada = 1")

    def _cambiar(self, id_: int, asignaciones: str, *valores):
        """UPDATE que además anota cuándo cambió y que falta subirlo al servidor."""
        self.con.execute(f"UPDATE tareas SET {asignaciones}, actualizada = ?, sincronizada = 0 WHERE id = ?",
                         (*valores, _ms(), id_))
        self.con.commit()

    # ------------------------------------------------------------ sincronización
    def cambios_por_subir(self, limite: int = LOTE_SINCRONIZACION) -> list[dict]:
        """Tareas que cambiaron aquí y el servidor todavía no conoce (en el formato de /api/sync)."""
        filas = self.con.execute("SELECT * FROM tareas WHERE sincronizada = 0 ORDER BY actualizada LIMIT ?",
                                 (limite,)).fetchall()
        return [{"id": f["uuid"], "titulo": f["titulo"], "fecha": f["fecha"], "repeticion": f["repeticion"],
                 "estado": f["estado"], "creada": f["creada"], "completada": f["completada"],
                 "actualizada": f["actualizada"], "borrada": bool(f["borrada"]), "tipo": f["tipo"],
                 "anticipacion": f["anticipacion"], "aviso_previo": f["aviso_previo"]} for f in filas]

    def confirmar_subidas(self, subidas: list[tuple[str, int]]):
        """
        (uuid, actualizada) de lo que el servidor ya recibió. Si la tarea volvió a cambiar mientras
        tanto (otra 'actualizada'), queda pendiente para la próxima vez.
        """
        self.con.executemany("UPDATE tareas SET sincronizada = 1 WHERE uuid = ? AND actualizada = ?", subidas)
        self.con.commit()

    def aplicar_remotos(self, cambios: list[dict]) -> list[int]:
        """
        Cambios que vienen del servidor (hechos en el celular). Gana el más reciente: si aquí la tarea
        cambió después, se ignora (y la versión de aquí se sube en la próxima sincronización).
        Devuelve los id locales que cambiaron (para refrescar la cara y la lista).
        """
        tocadas = []
        for c in cambios:
            try:
                datetime.strptime(c["fecha"], FORMATO)
                actualizada = int(c["actualizada"])
            except (KeyError, TypeError, ValueError):
                continue                                     # dato raro: mejor no tocar nada
            estado = "hecha" if c.get("estado") == "hecha" else "pendiente"
            borrada = 1 if c.get("borrada") else 0
            fila = self.con.execute("SELECT * FROM tareas WHERE uuid = ?", (c["id"],)).fetchone()
            previo = c.get("aviso_previo") if _fecha_valida(c.get("aviso_previo")) else None
            if fila and previo and (fila["aviso_previo"] or "") < previo:
                # "ya avisé" del celular: se une siempre (gana el más reciente), aunque la edición de aquí sea más nueva
                self.con.execute("UPDATE tareas SET aviso_previo = ? WHERE id = ?", (previo, fila["id"]))
            if fila and fila["actualizada"] >= actualizada:
                continue
            # Un servidor viejo (sin eventos) no manda tipo ni anticipación: entonces se deja lo que había
            tipo = c.get("tipo") if c.get("tipo") in TIPOS_VALIDOS else (fila["tipo"] if fila else "tarea")
            anticipacion = (limpiar_anticipacion(c.get("anticipacion")) if "anticipacion" in c
                            else (fila["anticipacion"] if fila else None))
            if fila:
                nueva_fecha = fila["fecha"] != c["fecha"]
                self.con.execute(
                    "UPDATE tareas SET titulo = ?, fecha = ?, repeticion = ?, estado = ?, completada = ?, borrada = ?, "
                    "tipo = ?, anticipacion = ?, actualizada = ?, sincronizada = 1, "
                    "avisada = CASE WHEN ? THEN 0 ELSE avisada END WHERE id = ?",
                    (c["titulo"], c["fecha"], c.get("repeticion"), estado, c.get("completada"), borrada,
                     tipo, anticipacion, actualizada, nueva_fecha, fila["id"]))
                tocadas.append(fila["id"])
            elif not borrada:                                 # una borrada que nunca estuvo aquí: nada que hacer
                cur = self.con.execute(
                    "INSERT INTO tareas (uuid, titulo, fecha, repeticion, estado, avisada, creada, completada, "
                    "actualizada, borrada, sincronizada, tipo, anticipacion, aviso_previo) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 1, ?, ?, ?)",
                    (c["id"], c["titulo"], c["fecha"], c.get("repeticion"), estado, int(estado == "hecha"),
                     c.get("creada") or c["fecha"], c.get("completada"), actualizada, tipo, anticipacion, previo))
                tocadas.append(cur.lastrowid)
        self.con.commit()
        return tocadas

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

    def estudio_por_dia(self, desde: date, hasta: date) -> dict[date, tuple[int, int]]:
        """{día: (pomodoros, minutos)} entre dos fechas, ambas incluidas. Los días sin estudio no aparecen."""
        filas = self.con.execute(
            "SELECT substr(inicio, 1, 10) AS dia, SUM(pomodoros), SUM(minutos_enfoque) FROM sesiones "
            "WHERE substr(inicio, 1, 10) BETWEEN ? AND ? GROUP BY dia",
            (desde.isoformat(), hasta.isoformat())).fetchall()
        return {date.fromisoformat(f[0]): (f[1], f[2]) for f in filas}

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
            tipo=fila["tipo"] or "tarea",
            anticipacion=fila["anticipacion"],
        )
