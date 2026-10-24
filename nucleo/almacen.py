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
  duracion      minutos que ocupa (v3.14): "de 8 a 10" = 120. NULL = no se dijo (no resta horas libres)
  aviso_previo  cuándo se mandó el último aviso anticipado. Desde la v3.11 SÍ viaja al celular, pero
                aparte de las ediciones: gana el más reciente, sin tocar 'actualizada' (así no pisa tus cambios).
"""
from __future__ import annotations

import re
import sqlite3
import time
import uuid
from dataclasses import dataclass
from datetime import date, datetime, time as hora, timedelta
from pathlib import Path

from nucleo.horario import Bloque, Excepcion
from nucleo.perfil import Actividad, Perfil
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


def limpiar_duracion(valor) -> int | None:
    """Minutos entre 1 y 24 h; cualquier otra cosa queda en None (= no se sabe cuánto dura)."""
    try:
        minutos = int(valor)
    except (TypeError, ValueError):
        return None
    return minutos if 0 < minutos <= 24 * 60 else None


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
    duracion: int | None = None      # minutos que ocupa ("de 8 a 10" = 120)

    @property
    def fin(self) -> datetime | None:
        return self.fecha + timedelta(minutes=self.duracion) if self.duracion else None

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
                duracion    INTEGER,                   -- minutos que ocupa (v3.14)
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

            -- Horario fijo de la semana (v3.12): "lun a vie 09:00-18:00 Trabajo"
            CREATE TABLE IF NOT EXISTS horario (
                id      INTEGER PRIMARY KEY AUTOINCREMENT,
                dias    TEXT NOT NULL,                 -- '0,1,2,3,4' (0 = lunes)
                inicio  TEXT NOT NULL,                 -- 'HH:MM'
                fin     TEXT NOT NULL,
                titulo  TEXT NOT NULL,
                traslado INTEGER NOT NULL DEFAULT 0    -- minutos de viaje antes y después (v3.13)
            );

            -- Excepciones al horario (v3.14): "el 1 de noviembre no trabajo", "vacaciones del 20 al 30 de diciembre"
            CREATE TABLE IF NOT EXISTS excepciones (
                id      INTEGER PRIMARY KEY AUTOINCREMENT,
                desde   TEXT NOT NULL,                 -- 'YYYY-MM-DD'
                hasta   TEXT NOT NULL,                 -- inclusive
                filtro  TEXT NOT NULL DEFAULT '',      -- 'traba' = solo esos bloques; '' = todos
                titulo  TEXT NOT NULL
            );

            -- Actividades de tu perfil (v3.13): "gimnasio 1 h, 3 veces por semana, en la tarde"
            CREATE TABLE IF NOT EXISTS actividades (
                id      INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre  TEXT NOT NULL,
                minutos INTEGER NOT NULL DEFAULT 60,
                veces_semana INTEGER,                  -- NULL = sin meta
                momento TEXT                           -- manana | tarde | noche | NULL
            );

            -- Veces que hiciste una actividad (v3.15): una fila por actividad y día
            CREATE TABLE IF NOT EXISTS actividades_hechas (
                actividad_id INTEGER NOT NULL,
                dia          TEXT NOT NULL,            -- 'YYYY-MM-DD'
                PRIMARY KEY (actividad_id, dia)
            );

            -- Sugerencias que rechazaste ("Ahora no", v3.16): para aprender en qué momento no te sirven
            CREATE TABLE IF NOT EXISTS sugerencias_rechazadas (
                nombre  TEXT NOT NULL,                 -- clave: 'gimnasio', 'estudiar'
                dia     TEXT NOT NULL,                 -- 'YYYY-MM-DD'
                momento TEXT NOT NULL                  -- manana | tarde | noche
            );

            -- Tareas que salieron de una sugerencia («📌 Agendar», v3.17): si no se hacen, se descartan
            -- solas al día siguiente (no quedan vencidas). Solo en la laptop.
            CREATE TABLE IF NOT EXISTS tareas_sugeridas (
                tarea_id     INTEGER PRIMARY KEY,
                actividad_id INTEGER                   -- NULL = estudiar
            );

            -- En qué quedó cada tarea agendada desde una sugerencia (v3.18): para el resumen de la semana
            CREATE TABLE IF NOT EXISTS historial_sugeridas (
                nombre    TEXT NOT NULL,               -- título de la tarea: 'Gimnasio'
                dia       TEXT NOT NULL,               -- 'YYYY-MM-DD' (día para el que estaba agendada)
                resultado TEXT NOT NULL                -- 'hecha' | 'descartada'
            );

            -- Ajustes sueltos (posición de la cara, etc.)
            CREATE TABLE IF NOT EXISTS ajustes (
                clave TEXT PRIMARY KEY,
                valor TEXT
            );
        """)
        self._migrar_para_sincronizar()
        if "traslado" not in {f["name"] for f in self.con.execute("PRAGMA table_info(horario)")}:
            self.con.execute("ALTER TABLE horario ADD COLUMN traslado INTEGER NOT NULL DEFAULT 0")   # v3.13
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
                             ("anticipacion", "TEXT"), ("aviso_previo", "TEXT"),
                             ("duracion", "INTEGER")):
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
                tipo: str = "tarea", anticipacion: str | None = None, duracion: int | None = None) -> Tarea:
        cur = self.con.execute(
            "INSERT INTO tareas (titulo, fecha, repeticion, creada, uuid, actualizada, tipo, anticipacion, duracion) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (titulo, fecha.strftime(FORMATO), repeticion, datetime.now().strftime(FORMATO), str(uuid.uuid4()), _ms(),
             tipo if tipo in TIPOS_VALIDOS else "tarea", limpiar_anticipacion(anticipacion), limpiar_duracion(duracion)),
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
            "AND id NOT IN (SELECT tarea_id FROM tareas_sugeridas) ORDER BY fecha",   # las sugeridas no "vencen"
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
               tipo=SIN_CAMBIO, anticipacion=SIN_CAMBIO, duracion=SIN_CAMBIO):
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
        if duracion is not SIN_CAMBIO:
            asignaciones += ", duracion = ?"
            valores.append(limpiar_duracion(duracion))
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
                 "anticipacion": f["anticipacion"], "aviso_previo": f["aviso_previo"], "duracion": f["duracion"]}
                for f in filas]

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
            duracion = (limpiar_duracion(c.get("duracion")) if "duracion" in c
                        else (fila["duracion"] if fila else None))
            if fila:
                nueva_fecha = fila["fecha"] != c["fecha"]
                self.con.execute(
                    "UPDATE tareas SET titulo = ?, fecha = ?, repeticion = ?, estado = ?, completada = ?, borrada = ?, "
                    "tipo = ?, anticipacion = ?, duracion = ?, actualizada = ?, sincronizada = 1, "
                    "avisada = CASE WHEN ? THEN 0 ELSE avisada END WHERE id = ?",
                    (c["titulo"], c["fecha"], c.get("repeticion"), estado, c.get("completada"), borrada,
                     tipo, anticipacion, duracion, actualizada, nueva_fecha, fila["id"]))
                tocadas.append(fila["id"])
            elif not borrada:                                 # una borrada que nunca estuvo aquí: nada que hacer
                cur = self.con.execute(
                    "INSERT INTO tareas (uuid, titulo, fecha, repeticion, estado, avisada, creada, completada, "
                    "actualizada, borrada, sincronizada, tipo, anticipacion, aviso_previo, duracion) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 1, ?, ?, ?, ?)",
                    (c["id"], c["titulo"], c["fecha"], c.get("repeticion"), estado, int(estado == "hecha"),
                     c.get("creada") or c["fecha"], c.get("completada"), actualizada, tipo, anticipacion, previo,
                     duracion))
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

    # --------------------------------------------------------------- horario
    def agregar_bloque(self, b: "Bloque") -> "Bloque":
        cur = self.con.execute("INSERT INTO horario (dias, inicio, fin, titulo, traslado) VALUES (?, ?, ?, ?, ?)",
                               (",".join(map(str, b.dias)), f"{b.inicio:%H:%M}", f"{b.fin:%H:%M}", b.titulo,
                                b.traslado))
        self.con.commit()
        return Bloque(b.dias, b.inicio, b.fin, b.titulo, cur.lastrowid, b.traslado)

    def cambiar_traslado(self, id_: int, minutos: int):
        self.con.execute("UPDATE horario SET traslado = ? WHERE id = ?", (max(0, int(minutos)), id_))
        self.con.commit()

    def horario(self) -> list["Bloque"]:
        """Tus bloques fijos, ordenados por primer día y hora."""
        bloques = [Bloque(tuple(int(d) for d in f["dias"].split(",")), hora.fromisoformat(f["inicio"]),
                          hora.fromisoformat(f["fin"]), f["titulo"], f["id"], f["traslado"])
                   for f in self.con.execute("SELECT * FROM horario").fetchall()]
        return sorted(bloques, key=lambda b: (min(b.dias), b.inicio))

    def borrar_bloque(self, id_: int) -> bool:
        cur = self.con.execute("DELETE FROM horario WHERE id = ?", (id_,))
        self.con.commit()
        return cur.rowcount > 0

    def agregar_excepcion(self, e: "Excepcion") -> "Excepcion":
        cur = self.con.execute("INSERT INTO excepciones (desde, hasta, filtro, titulo) VALUES (?, ?, ?, ?)",
                               (e.desde.isoformat(), e.hasta.isoformat(), e.filtro, e.titulo))
        self.con.commit()
        return Excepcion(e.desde, e.hasta, e.filtro, e.titulo, cur.lastrowid)

    def excepciones(self, desde: date | None = None) -> list["Excepcion"]:
        """Las excepciones que todavía no terminaron (hasta >= 'desde', hoy si no se dice), por fecha."""
        desde = desde or date.today()
        filas = self.con.execute("SELECT * FROM excepciones WHERE hasta >= ? ORDER BY desde, id",
                                 (desde.isoformat(),)).fetchall()
        return [Excepcion(date.fromisoformat(f["desde"]), date.fromisoformat(f["hasta"]), f["filtro"], f["titulo"],
                          f["id"]) for f in filas]

    def borrar_excepcion(self, id_: int) -> bool:
        cur = self.con.execute("DELETE FROM excepciones WHERE id = ?", (id_,))
        self.con.commit()
        return cur.rowcount > 0

    def limpiar_excepciones(self, hoy: date) -> int:
        """Borra las que ya pasaron hace más de 30 días (no sirven y la lista no crece para siempre)."""
        cur = self.con.execute("DELETE FROM excepciones WHERE hasta < ?", ((hoy - timedelta(days=30)).isoformat(),))
        self.con.commit()
        return cur.rowcount

    # ---------------------------------------------------------------- perfil
    def perfil(self, por_defecto: Perfil | None = None) -> Perfil:
        """Tu perfil guardado; lo que nunca dijiste toma el valor de 'por_defecto' (config.py)."""
        base = por_defecto or Perfil()
        leer = lambda clave, defecto: self.leer_ajuste(clave) or defecto      # noqa: E731
        try:
            despertar = hora.fromisoformat(leer("perfil_despertar", f"{base.despertar:%H:%M}"))
            dormir = hora.fromisoformat(leer("perfil_dormir", f"{base.dormir:%H:%M}"))
            meta = int(leer("perfil_meta_estudio", str(base.meta_estudio)))
        except ValueError:
            despertar, dormir, meta = base.despertar, base.dormir, base.meta_estudio
        return Perfil(despertar, dormir, meta, self.actividades())

    def guardar_perfil(self, despertar: hora | None = None, dormir: hora | None = None, meta_estudio: int | None = None):
        if despertar is not None:
            self.guardar_ajuste("perfil_despertar", f"{despertar:%H:%M}")
        if dormir is not None:
            self.guardar_ajuste("perfil_dormir", f"{dormir:%H:%M}")
        if meta_estudio is not None:
            self.guardar_ajuste("perfil_meta_estudio", str(max(10, min(int(meta_estudio), 720))))

    def agregar_actividad(self, a: Actividad) -> Actividad:
        cur = self.con.execute("INSERT INTO actividades (nombre, minutos, veces_semana, momento) VALUES (?, ?, ?, ?)",
                               (a.nombre, a.minutos, a.veces_semana, a.momento))
        self.con.commit()
        return Actividad(a.nombre, a.minutos, a.veces_semana, a.momento, cur.lastrowid)

    def actividades(self) -> list[Actividad]:
        return [Actividad(f["nombre"], f["minutos"], f["veces_semana"], f["momento"], f["id"])
                for f in self.con.execute("SELECT * FROM actividades ORDER BY id").fetchall()]

    def borrar_actividad(self, id_: int) -> bool:
        cur = self.con.execute("DELETE FROM actividades WHERE id = ?", (id_,))
        self.con.execute("DELETE FROM actividades_hechas WHERE actividad_id = ?", (id_,))
        self.con.commit()
        return cur.rowcount > 0

    def marcar_actividad(self, id_: int, dia: date, hecha: bool = True) -> bool:
        """Anota (o quita) que hiciste esa actividad ese día. Devuelve si cambió algo."""
        if hecha:
            cur = self.con.execute("INSERT OR IGNORE INTO actividades_hechas (actividad_id, dia) VALUES (?, ?)",
                                   (id_, dia.isoformat()))
        else:
            cur = self.con.execute("DELETE FROM actividades_hechas WHERE actividad_id = ? AND dia = ?",
                                   (id_, dia.isoformat()))
        self.con.commit()
        return cur.rowcount > 0

    def rechazar_sugerencia(self, nombre: str, dia: date, momento: str):
        self.con.execute("INSERT INTO sugerencias_rechazadas (nombre, dia, momento) VALUES (?, ?, ?)",
                         (nombre, dia.isoformat(), momento))
        self.con.commit()

    def momentos_a_evitar(self, desde: date, veces: int = 2) -> dict[str, set[str]]:
        """{nombre: {momentos}} que rechazaste al menos 'veces' veces desde esa fecha."""
        salida: dict[str, set[str]] = {}
        for f in self.con.execute("SELECT nombre, momento FROM sugerencias_rechazadas WHERE dia >= ? "
                                  "GROUP BY nombre, momento HAVING COUNT(*) >= ?", (desde.isoformat(), veces)):
            salida.setdefault(f["nombre"], set()).add(f["momento"])
        return salida

    def marcar_tarea_sugerida(self, tarea_id: int, actividad_id: int | None):
        self.con.execute("INSERT OR REPLACE INTO tareas_sugeridas (tarea_id, actividad_id) VALUES (?, ?)",
                         (tarea_id, actividad_id))
        self.con.commit()

    def es_sugerida(self, tarea_id: int) -> bool:
        return self.con.execute("SELECT 1 FROM tareas_sugeridas WHERE tarea_id = ?", (tarea_id,)).fetchone() is not None

    def repasar_sugeridas(self, hoy: date) -> tuple[list[tuple[int, date]], list[int]]:
        """
        Revisa las tareas que vinieron de una sugerencia:
          - completada (aquí o en el celular) -> cuenta su actividad ese día y deja de seguirla;
          - pendiente de un día anterior      -> se borra (no queda vencida) y se sincroniza el borrado;
          - borrada o inexistente             -> deja de seguirla.
        Devuelve ([(actividad_id, día hecha)], [ids descartados]).
        """
        hechas, descartadas, olvidar = [], [], []
        filas = self.con.execute(
            "SELECT s.tarea_id, s.actividad_id, t.titulo, t.estado, t.fecha, t.completada, t.borrada "
            "FROM tareas_sugeridas s LEFT JOIN tareas t ON t.id = s.tarea_id").fetchall()
        for f in filas:
            if f["estado"] is None or f["borrada"]:
                olvidar.append(f["tarea_id"])
            elif f["estado"] == "hecha":
                self._anotar_historial(f["titulo"], f["fecha"], "hecha")
                if f["actividad_id"] is not None:
                    hechas.append((f["actividad_id"], datetime.strptime(f["completada"] or f["fecha"], FORMATO).date()))
                olvidar.append(f["tarea_id"])
            elif datetime.strptime(f["fecha"], FORMATO).date() < hoy:
                self._anotar_historial(f["titulo"], f["fecha"], "descartada")
                self.eliminar(f["tarea_id"])
                descartadas.append(f["tarea_id"])
                olvidar.append(f["tarea_id"])
        for id_ in olvidar:
            self.con.execute("DELETE FROM tareas_sugeridas WHERE tarea_id = ?", (id_,))
        for actividad_id, dia in hechas:
            self.marcar_actividad(actividad_id, dia)
        self.con.commit()
        return hechas, descartadas

    def _anotar_historial(self, titulo: str, fecha: str, resultado: str):
        self.con.execute("INSERT INTO historial_sugeridas (nombre, dia, resultado) VALUES (?, ?, ?)",
                         (titulo, fecha[:10], resultado))

    def balance_sugeridas(self, desde: date, hasta: date) -> dict[str, tuple[int, int]]:
        """{nombre: (hechas, descartadas)} de lo agendado desde sugerencias entre esas fechas."""
        salida: dict[str, tuple[int, int]] = {}
        for f in self.con.execute(
                "SELECT nombre, SUM(resultado = 'hecha') AS h, SUM(resultado = 'descartada') AS d "
                "FROM historial_sugeridas WHERE dia BETWEEN ? AND ? GROUP BY nombre ORDER BY nombre",
                (desde.isoformat(), hasta.isoformat())):
            salida[f["nombre"]] = (f["h"], f["d"])
        return salida

    def uuids_sugeridas(self) -> list[str]:
        """Los ids compartidos (uuid) de las tareas sugeridas pendientes: el celular tampoco las da por vencidas."""
        return [f[0] for f in self.con.execute(
            "SELECT t.uuid FROM tareas_sugeridas s JOIN tareas t ON t.id = s.tarea_id "
            "WHERE t.estado = 'pendiente' AND t.borrada = 0 ORDER BY t.uuid")]

    def id_por_uuid(self, uuid_: str) -> int | None:
        fila = self.con.execute("SELECT id FROM tareas WHERE uuid = ? AND borrada = 0", (uuid_,)).fetchone()
        return fila[0] if fila else None

    def ids_sugeridas(self) -> set[int]:
        return {f[0] for f in self.con.execute("SELECT tarea_id FROM tareas_sugeridas")}

    def olvidar_rechazo(self, nombre: str, momento: str) -> int:
        """Olvida solo eso: «gimnasio en la tarde» (el ✕ de la pestaña Horario)."""
        cur = self.con.execute("DELETE FROM sugerencias_rechazadas WHERE nombre = ? AND momento = ?", (nombre, momento))
        self.con.commit()
        return cur.rowcount

    def olvidar_rechazos(self) -> int:
        cur = self.con.execute("DELETE FROM sugerencias_rechazadas")
        self.con.commit()
        return cur.rowcount

    def actividades_hechas(self, desde: date, hasta: date) -> dict[int, list[date]]:
        """{id de actividad: [días en que la hiciste]} entre dos fechas (ambas incluidas)."""
        salida: dict[int, list[date]] = {}
        for f in self.con.execute("SELECT actividad_id, dia FROM actividades_hechas WHERE dia BETWEEN ? AND ? "
                                  "ORDER BY dia", (desde.isoformat(), hasta.isoformat())):
            salida.setdefault(f["actividad_id"], []).append(date.fromisoformat(f["dia"]))
        return salida

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
            duracion=fila["duracion"],
        )
