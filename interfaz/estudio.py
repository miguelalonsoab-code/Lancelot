"""
Modo estudio: une el Pomodoro (núcleo), las frases de aliento, el sensor de
ventana activa y el registro de sesiones.

No dibuja nada: emite señales y el controlador (app.py) decide cómo mostrarlas.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from PySide6.QtCore import QObject, QTimer, Signal

from config import (CICLOS_PARA_DESCANSO_LARGO, COLORES, DISTRACCIONES, MINUTOS_DESCANSO,
                    MINUTOS_DESCANSO_LARGO, MINUTOS_ENFOQUE, MINUTOS_ENTRE_AVISOS_DISTRACCION,
                    SEGUNDOS_DE_GRACIA, SEGUNDOS_MENSAJE)
from nucleo.almacen import Almacen
from nucleo.distraccion import clave_ventana, detectar_distraccion
from nucleo.frases import SelectorFrases
from nucleo.pomodoro import DESCANSO, DESCANSO_LARGO, ENFOQUE, ESPERANDO, Pomodoro
from sensores.ventana_activa import ventana_activa

NOMBRES_FASE = {ENFOQUE: "Enfoque", DESCANSO: "Descanso",
                DESCANSO_LARGO: "Descanso largo", ESPERANDO: "Esperando"}


class ModoEstudio(QObject):
    # (cabecera, texto, botones[(texto, clave)], color, segundos visibles (0 = fijo), sonar)
    aviso = Signal(str, str, list, str, int, bool)
    cambio = Signal()                     # cambió algo que la cara o el panel deben mostrar
    celebrar = Signal()                   # terminó un pomodoro: ojitos felices

    def __init__(self, almacen: Almacen):
        super().__init__()
        self.almacen = almacen
        self.frases = SelectorFrases()
        self.pomodoro: Pomodoro | None = None
        self.inicio: datetime | None = None
        self.distracciones = 0
        self.sospechando = False

        self._permitidas: set[str] = set()
        self._distraccion_desde: datetime | None = None
        self._ultima_ventana: tuple[str, str] | None = None
        self._ultimo_aviso_distraccion: datetime | None = None
        self._ticks = 0

        self._reloj = QTimer(self)
        self._reloj.timeout.connect(self._tick)

    # ================================================================ estado
    @property
    def activo(self) -> bool:
        return self.pomodoro is not None

    def estado_cara(self, ahora: datetime) -> tuple[str, float | None, str | None]:
        """(estado, progreso del arco, texto pequeño) para dibujar la cara."""
        p = self.pomodoro
        if self.sospechando:
            return "sospecha", 1 - p.progreso(ahora), _mmss(p.restante(ahora))
        if p.fase == ESPERANDO:
            return "esperando", None, "¿seguimos?"
        texto = "pausa" if p.pausado else _mmss(p.restante(ahora))
        estado = "estudio" if p.fase == ENFOQUE else "descanso"
        return estado, 1 - p.progreso(ahora), texto

    def descripcion(self, ahora: datetime) -> str:
        """Línea para el panel: 'Pomodoro 2 · Enfoque · 13:45'."""
        p = self.pomodoro
        numero = p.completados + (1 if p.fase == ENFOQUE else 0)
        partes = [f"Pomodoro {max(numero, 1)}", NOMBRES_FASE[p.fase]]
        if p.fase != ESPERANDO:
            partes.append("en pausa" if p.pausado else _mmss(p.restante(ahora)))
        return " · ".join(partes)

    def resumen_hoy(self, ahora: datetime) -> str:
        pomos, mins = self.almacen.resumen_dia(ahora.date())
        if self.activo:                      # sumar la sesión en curso
            pomos += self.pomodoro.completados
            mins += self.pomodoro.minutos_enfocados(ahora)
        racha = self.almacen.racha(ahora.date())
        texto = f"Hoy: {pomos} pomodoro(s) · {_horas(mins)}"
        if racha >= 2:
            texto += f" · racha de {racha} días 🔥"
        return texto

    # =============================================================== acciones
    def iniciar(self, minutos: int | None = None):
        ahora = datetime.now()
        if self.activo:
            self.terminar()
        enfoque = minutos or MINUTOS_ENFOQUE
        # Para bloques largos, el descanso crece en proporción (50 min -> 10 min)
        descanso = MINUTOS_DESCANSO if enfoque <= MINUTOS_ENFOQUE else round(enfoque / 5)
        self.pomodoro = Pomodoro(enfoque, descanso, MINUTOS_DESCANSO_LARGO, CICLOS_PARA_DESCANSO_LARGO)
        self.pomodoro.iniciar_enfoque(ahora)
        self.inicio = ahora
        self.distracciones = 0
        self._permitidas.clear()
        self._limpiar_sospecha()
        self._reloj.start(1000)

        texto = self.frases.elegir("inicio", mf=enfoque)
        racha = self.almacen.racha(ahora.date())
        if racha >= 2:
            texto += "\n" + self.frases.elegir("racha", racha=racha)
        self.aviso.emit("📚 Modo estudio", texto, [], COLORES["estudio"], 8, False)
        self.cambio.emit()

    def pausar(self):
        if self.activo:
            self.pomodoro.pausar(datetime.now())
            self.cambio.emit()

    def seguir(self):
        if not self.activo:
            return
        ahora = datetime.now()
        if self.pomodoro.pausado:
            self.pomodoro.reanudar(ahora)
        elif self.pomodoro.fase != ENFOQUE:
            self.pomodoro.saltar_descanso(ahora)
        self.cambio.emit()

    def terminar(self):
        if not self.activo:
            return
        ahora = datetime.now()
        p = self.pomodoro
        minutos = p.minutos_enfocados(ahora)
        p.cortar_enfoque(ahora)
        self.almacen.guardar_sesion(self.inicio, ahora, p.completados, minutos, self.distracciones)
        self.pomodoro = None
        self._reloj.stop()
        self._limpiar_sospecha()

        _, hoy = self.almacen.resumen_dia(ahora.date())
        texto = (self.frases.elegir("fin_sesion", n=p.completados, min=minutos, hoy=hoy)
                 if minutos > 0 else "Sesión cerrada. La próxima sale mejor.")
        self.aviso.emit("Sesión terminada", texto, [], COLORES["feliz"], 15, False)
        self.cambio.emit()

    def permitir_ventana_actual(self):
        """Botón 'Es para estudiar': esa ventana deja de contar como distracción."""
        if self._ultima_ventana:
            self._permitidas.add(clave_ventana(*self._ultima_ventana))
        self._limpiar_sospecha()
        self.cambio.emit()

    def volver(self):
        self._limpiar_sospecha()
        self.cambio.emit()

    # ================================================================== reloj
    def _tick(self):
        ahora = datetime.now()
        p = self.pomodoro
        for evento in p.avanzar(ahora):
            datos = dict(n=p.completados, min=p.minutos_enfocados(ahora))
            if evento == "fin_enfoque":
                largo = p.fase == DESCANSO_LARGO
                texto = self.frases.elegir("descanso_largo" if largo else "fin_enfoque", **datos)
                minutos_desc = int(p.duraciones[p.fase].total_seconds() // 60)
                self.aviso.emit(f"✓ Pomodoro {p.completados} · descanso de {minutos_desc} min", texto,
                                [("Saltar descanso", "saltar")], COLORES["descanso"], SEGUNDOS_MENSAJE * 2, True)
                self._limpiar_sospecha()
                self.celebrar.emit()
            elif evento == "fin_descanso":
                self.aviso.emit("Descanso terminado", self.frases.elegir("fin_descanso", **datos),
                                [("▶ Seguir", "seguir"), ("Terminar", "terminar")],
                                COLORES["esperando"], 0, True)

        self._ticks += 1
        if self._ticks % 2 == 0:                          # cada 2 s basta
            self._revisar_distraccion(ahora)
        self.cambio.emit()

    def _revisar_distraccion(self, ahora: datetime):
        p = self.pomodoro
        if p.fase != ENFOQUE or p.pausado:
            self._distraccion_desde = None
            return
        ventana = ventana_activa()
        nombre = detectar_distraccion(*ventana, DISTRACCIONES, self._permitidas) if ventana else None
        if not nombre:
            self._distraccion_desde = None
            if self.sospechando:
                self._limpiar_sospecha()              # volviste: la cara se relaja sola
            return

        self._ultima_ventana = ventana
        if self._distraccion_desde is None:
            self._distraccion_desde = ahora
            return
        lleva = (ahora - self._distraccion_desde).total_seconds()
        reciente = (self._ultimo_aviso_distraccion and
                    ahora - self._ultimo_aviso_distraccion < timedelta(minutes=MINUTOS_ENTRE_AVISOS_DISTRACCION))
        if lleva >= SEGUNDOS_DE_GRACIA and not reciente:
            self.sospechando = True
            self.distracciones += 1
            self._ultimo_aviso_distraccion = ahora
            resta = max(1, int(p.restante(ahora).total_seconds() // 60))
            self.aviso.emit("🤨 ¿Distraído?", self.frases.elegir("distraccion", app=nombre, resta=resta),
                            [("Vuelvo 💪", "volver"), ("Es para estudiar", "permitir")],
                            COLORES["sospecha"], 0, True)

    def _limpiar_sospecha(self):
        self.sospechando = False
        self._distraccion_desde = None


def _mmss(td: timedelta) -> str:
    s = int(td.total_seconds())
    return f"{s // 60:02d}:{s % 60:02d}"


def _horas(minutos: int) -> str:
    return f"{minutos} min" if minutos < 60 else f"{minutos // 60} h {minutos % 60:02d} min"
