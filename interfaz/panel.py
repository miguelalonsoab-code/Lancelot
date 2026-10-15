"""
Panel "Mis tareas": modos, tareas y el cuadro donde le "hablas" al asistente.

El cuadro de texto entiende dos cosas:
  - COMANDOS: "modo estudio", "modo estudio 50", "pausa", "terminar", "modo silencio"...
  - TAREAS:   "mañana 8pm pagar la luz", "cada lunes 9am reunión"...
  - EVENTOS:  "el 15 de noviembre aniversario", "examen de cálculo el 20/10" (📅: avisan días antes)
Primero se revisa si es comando; si no, se interpreta como tarea (o evento: el selector Tarea/Evento
muestra lo que entendió y se puede cambiar).

Pestañas:
  - Tareas:  arriba las VENCIDAS (con ↻ para reprogramar), luego las próximas.
  - Estudio: gráfico de los últimos 7 días, con ◀ ▶ para ver semanas anteriores.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from PySide6.QtCore import QDateTime, QPoint, QSize, Qt, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (QComboBox, QDateTimeEdit, QFrame, QHBoxLayout, QLabel, QLineEdit,
                               QListWidget, QListWidgetItem, QMenu, QPushButton, QTabWidget, QVBoxLayout,
                               QWidget)

from config import ATAJO_HABLAR, COLORES, VERSION, HORA_POR_DEFECTO, META_ESTUDIO_DIARIO, NOMBRE_ASISTENTE, NOMBRES_MODO
from interfaz.grafico import GraficoSemana
from nucleo.almacen import Tarea
from nucleo.comandos import Comando, interpretar_comando
from nucleo.estadisticas import ResumenSemana, describir_semana, rango
from nucleo.interprete import (REPETICIONES, TIPOS, avisos_previos, describir_atraso, describir_avisos,
                               describir_faltan, describir_fecha, interpretar)
from nucleo.planificador import opciones_reprogramar

DESCRIPCION_COMANDO = {
    "estudio": "activar {modo}",
    "pausa": "pausar el pomodoro",
    "seguir": "seguir con el pomodoro",
    "terminar": "terminar la sesión de estudio",
    "silencio": "activar {silencio}",
    "normal": "volver al modo normal",
    "resumen": "mostrar cuánto estudiaste hoy",
    "abrir": "abrir «{texto}»",
    "hora": "decir la hora",
    "agenda": "decir tus pendientes de hoy",
    "escucha_on": "activar la escucha por voz",
    "escucha_off": "desactivar la escucha por voz",
    "apodo": "guardar el apodo «{texto}» → «{destino}»",
    "olvidar_apodo": "olvidar el apodo «{texto}»",
    "apodos": "mostrar tus apodos",
    "abrir_web": "abrir «{texto}»{en}",
    "buscar": "buscar «{texto}» en {destino}{en}",
    "saludo": "saludarte con el resumen del día",
    "semana": "mostrar cuánto estudiaste esta semana",
    "vencidas": "decir tus tareas vencidas",
    "vencidas_manana": "pasar todas las vencidas a mañana (misma hora)",
    "actualizacion": "buscar una versión nueva de Lancelot",
    "frase": "decirte una frase",
    "guardar_frase": "guardar la frase «{texto}»",
}

ESTILO = f"""
QWidget {{ background: #0f1116; color: #e8ebef; font-family: 'Segoe UI'; font-size: 13px; }}
#titulo {{ font-size: 20px; font-weight: 700; }}
#vista {{ color: #8b93a1; font-size: 12px; }}
#vista[error="true"] {{ color: {COLORES['alerta']}; }}
#vista[comando="true"] {{ color: {COLORES['estudio']}; }}
QLineEdit, QDateTimeEdit, QComboBox {{
    background: #1a1d24; border: 1px solid #2a2f3a; border-radius: 8px; padding: 7px 9px;
}}
QLineEdit:focus {{ border-color: {COLORES['tranquilo']}; }}
QPushButton {{ background: #232731; border: none; border-radius: 8px; padding: 7px 12px; }}
QPushButton:hover {{ background: #2e3340; }}
QPushButton:checked {{ background: #3a3550; color: #d9d3ff; }}
#agregar {{ background: {COLORES['tranquilo']}; color: #06201d; font-weight: 600; }}
#agregar:hover {{ background: #6fe3d8; }}
#agregar[editando="true"] {{ background: {COLORES['pendiente']}; color: #2a1f00; }}
#vista[editando="true"] {{ color: {COLORES['pendiente']}; }}
#tarjeta_estudio {{ background: #171428; border: 1px solid #3a3268; border-radius: 12px; }}
#tarjeta_estudio QLabel {{ background: transparent; }}
#estudio_estado {{ color: #cfc8ff; font-size: 15px; font-weight: 600; }}
#hoy {{ color: #8b93a1; font-size: 12px; }}
#voz {{ color: #6fb8e0; font-size: 11px; }}
#nube {{ color: #8b93a1; font-size: 11px; }}
#nube[error="true"] {{ color: {COLORES['pendiente']}; }}
QListWidget {{ background: transparent; border: none; outline: none; }}
QListWidget::item {{ border-bottom: 1px solid #1d212a; }}
QListWidget::item:selected {{ background: transparent; }}
#fila_titulo {{ font-size: 14px; background: transparent; }}
#fila_fecha {{ color: #8b93a1; font-size: 12px; background: transparent; }}
#fila_fecha[atrasada="true"] {{ color: {COLORES['alerta']}; }}
#fila_fecha[hoy="true"] {{ color: {COLORES['pendiente']}; }}
#fila_fecha[evento="true"] {{ color: {COLORES['evento']}; }}
#mini {{ background: transparent; padding: 4px 8px; font-size: 14px; }}
#mini:hover {{ background: #232731; }}
#pie {{ color: #5d6573; font-size: 11px; }}
#seccion {{ color: #8b93a1; font-size: 11px; font-weight: 700; letter-spacing: 1px; background: transparent; }}
#seccion[vencidas="true"] {{ color: {COLORES['alerta']}; }}
#enlace {{ background: transparent; color: {COLORES['alerta']}; padding: 2px 6px; font-size: 12px; }}
#enlace:hover {{ background: #2a1d1d; }}
QTabWidget::pane {{ border: none; }}
QTabBar::tab {{ background: transparent; color: #8b93a1; padding: 6px 14px; margin-right: 4px;
               border-bottom: 2px solid transparent; }}
QTabBar::tab:selected {{ color: #e8ebef; border-bottom-color: {COLORES['tranquilo']}; }}
QTabBar::tab:hover {{ color: #e8ebef; }}
#rango {{ font-size: 14px; font-weight: 600; }}
#semana_texto {{ color: #c3c8d1; font-size: 12px; }}
#nota {{ color: #5d6573; font-size: 11px; }}
QMenu {{ background: #1a1d24; border: 1px solid #2a2f3a; padding: 4px; }}
QMenu::item {{ padding: 6px 18px; border-radius: 6px; }}
QMenu::item:selected {{ background: #2e3340; }}
"""


class Panel(QWidget):
    agregar_pedido = Signal(str, datetime, object, str, object)  # titulo, fecha, repeticion, tipo, anticipacion
    completar_pedido = Signal(int)
    eliminar_pedido = Signal(int)
    editar_pedido = Signal(int, str, datetime, object, str, object)  # id + lo mismo
    comando_pedido = Signal(object)                   # Comando
    hablar_pedido = Signal()                          # botón 🗣: escuchar una orden ahora
    reprogramar_pedido = Signal(int, datetime)        # id, nueva fecha (atajos de ↻)
    reprogramar_vencidas_pedido = Signal()            # "Todas a mañana"
    semana_pedida = Signal(int)                       # semanas hacia atrás (0 = últimos 7 días)

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"Mis tareas · {NOMBRE_ASISTENTE} {VERSION}")
        self.setStyleSheet(ESTILO)
        self.resize(520, 660)

        titulo = QLabel("Mis tareas", objectName="titulo")

        # --- Barra de modos
        self.b_estudio = QPushButton(f"📚 {NOMBRES_MODO['estudio']}", checkable=True,
                                     cursor=Qt.PointingHandCursor)
        self.b_silencio = QPushButton(f"🔕 {NOMBRES_MODO['silencio']}", checkable=True,
                                      cursor=Qt.PointingHandCursor)
        self.b_estudio.clicked.connect(
            lambda marcado: self.comando_pedido.emit(Comando("estudio" if marcado else "terminar")))
        self.b_silencio.clicked.connect(
            lambda marcado: self.comando_pedido.emit(Comando("silencio" if marcado else "sin_silencio")))
        self.b_escucha = QPushButton("🎙 Escucha", checkable=True, cursor=Qt.PointingHandCursor,
                                     toolTip=f"Escuchar siempre, esperando que digas «{NOMBRE_ASISTENTE}»")
        self.b_escucha.clicked.connect(
            lambda marcado: self.comando_pedido.emit(Comando("escucha_on" if marcado else "escucha_off")))
        b_hablar = QPushButton("🗣", cursor=Qt.PointingHandCursor,
                               toolTip=f"Hablarle ahora (igual que {ATAJO_HABLAR})")
        b_hablar.clicked.connect(self.hablar_pedido.emit)
        fila_modos = QHBoxLayout()
        fila_modos.addWidget(self.b_estudio)
        fila_modos.addWidget(self.b_silencio)
        fila_modos.addWidget(self.b_escucha)
        fila_modos.addStretch()
        fila_modos.addWidget(b_hablar)
        self.voz = QLabel(objectName="voz", wordWrap=True)
        self.nube = QLabel(objectName="nube", wordWrap=True)
        self.nube.hide()                                  # solo si la sincronización está configurada

        # --- Tarjeta del modo estudio (solo visible durante una sesión)
        self.tarjeta = QFrame(objectName="tarjeta_estudio")
        self.estudio_estado = QLabel(objectName="estudio_estado")
        self.b_pausa = QPushButton("⏸ Pausa", cursor=Qt.PointingHandCursor)
        self.b_pausa.clicked.connect(lambda: self.comando_pedido.emit(
            Comando("seguir" if self.b_pausa.text().startswith("▶") else "pausa")))
        b_terminar = QPushButton("Terminar", cursor=Qt.PointingHandCursor)
        b_terminar.clicked.connect(lambda: self.comando_pedido.emit(Comando("terminar")))
        fila_t = QHBoxLayout()
        fila_t.addStretch()
        fila_t.addWidget(self.b_pausa)
        fila_t.addWidget(b_terminar)
        capa_t = QVBoxLayout(self.tarjeta)
        capa_t.setContentsMargins(12, 10, 12, 10)
        capa_t.addWidget(self.estudio_estado)
        capa_t.addLayout(fila_t)
        self.tarjeta.hide()

        self.hoy = QLabel(objectName="hoy")

        # --- Entrada de tareas / comandos
        self.entrada = QLineEdit(placeholderText="Tarea o comando: «mañana 8pm pagar la luz», «modo estudio»")
        self.entrada.textChanged.connect(self._al_escribir)
        self.entrada.returnPressed.connect(self._al_enviar)
        self.vista = QLabel(objectName="vista", wordWrap=True)

        self.selector_fecha = QDateTimeEdit(calendarPopup=True)
        self.selector_fecha.setDisplayFormat("ddd dd/MM/yyyy  HH:mm")
        self.selector_repeticion = QComboBox()
        for clave, texto in REPETICIONES.items():
            self.selector_repeticion.addItem(texto, clave)
        self.selector_tipo = QComboBox(toolTip="Un evento (aniversario, examen, viaje…) avisa además "
                                               "una semana y un día antes")
        for clave, texto in TIPOS.items():
            self.selector_tipo.addItem(texto, clave)
        self.selector_tipo.setMinimumWidth(118)              # que "📅 Evento" no se corte (con el padding del estilo)
        self.boton_enviar = QPushButton("Agregar", objectName="agregar", cursor=Qt.PointingHandCursor)
        self.boton_enviar.clicked.connect(self._al_enviar)
        self.boton_cancelar = QPushButton("Cancelar", cursor=Qt.PointingHandCursor)
        self.boton_cancelar.clicked.connect(self._reiniciar_formulario)
        self.boton_cancelar.hide()
        fila_opciones = QHBoxLayout()
        fila_opciones.addWidget(self.selector_fecha, 3)
        fila_opciones.addWidget(self.selector_repeticion, 2)
        fila_opciones.addWidget(self.selector_tipo)
        fila_opciones.addWidget(self.boton_enviar)
        fila_opciones.addWidget(self.boton_cancelar)

        self.lista = QListWidget()
        self.lista.setSelectionMode(QListWidget.NoSelection)
        self.lista.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)   # las filas se ajustan al ancho
        self.pie = QLabel(objectName="pie")

        # --- Pestaña "Tareas"
        pestana_tareas = QWidget()
        capa_tareas = QVBoxLayout(pestana_tareas)
        capa_tareas.setContentsMargins(0, 8, 0, 0)
        capa_tareas.setSpacing(8)
        capa_tareas.addWidget(self.entrada)
        capa_tareas.addWidget(self.vista)
        capa_tareas.addLayout(fila_opciones)
        capa_tareas.addSpacing(4)
        capa_tareas.addWidget(self.lista, 1)
        capa_tareas.addWidget(self.pie)

        # --- Pestaña "Estudio": la semana en un gráfico
        self.semanas_atras = 0
        b_antes = QPushButton("◀", objectName="mini", cursor=Qt.PointingHandCursor, toolTip="Semana anterior")
        self.b_despues = QPushButton("▶", objectName="mini", cursor=Qt.PointingHandCursor,
                                     toolTip="Semana siguiente")
        b_antes.clicked.connect(lambda: self._cambiar_semana(+1))
        self.b_despues.clicked.connect(lambda: self._cambiar_semana(-1))
        self.rango = QLabel(objectName="rango", alignment=Qt.AlignCenter)
        fila_rango = QHBoxLayout()
        fila_rango.addWidget(b_antes)
        fila_rango.addWidget(self.rango, 1)
        fila_rango.addWidget(self.b_despues)
        self.grafico = GraficoSemana()
        self.semana_texto = QLabel(objectName="semana_texto", wordWrap=True)
        nota = QLabel(f"La línea punteada es tu meta diaria ({META_ESTUDIO_DIARIO} min, en config.py). "
                      "Las barras verdes la cumplieron. También puedes preguntar «resumen semanal».",
                      objectName="nota", wordWrap=True)
        pestana_estudio = QWidget()
        capa_estudio = QVBoxLayout(pestana_estudio)
        capa_estudio.setContentsMargins(0, 10, 0, 0)
        capa_estudio.setSpacing(10)
        capa_estudio.addLayout(fila_rango)
        capa_estudio.addWidget(self.grafico)
        capa_estudio.addWidget(self.semana_texto)
        capa_estudio.addStretch()
        capa_estudio.addWidget(nota)

        self.pestanas = QTabWidget()
        self.pestanas.addTab(pestana_tareas, "Tareas")
        self.pestanas.addTab(pestana_estudio, "📊 Estudio")
        self.pestanas.currentChanged.connect(self._al_cambiar_pestana)

        capa = QVBoxLayout(self)
        capa.setContentsMargins(18, 16, 18, 12)
        capa.setSpacing(8)
        capa.addWidget(titulo)
        capa.addLayout(fila_modos)
        capa.addWidget(self.voz)
        capa.addWidget(self.nube)
        capa.addWidget(self.tarjeta)
        capa.addWidget(self.hoy)
        capa.addWidget(self.pestanas, 1)

        self._editando: int | None = None    # id de la tarea que se está editando
        self._tarea_editada: Tarea | None = None
        self._menu_reprogramar: QMenu | None = None
        self._reiniciar_formulario()

    # ---------------------------------------------------------------- abrir
    def abrir(self):
        self.show()
        self.raise_()
        self.activateWindow()
        self.entrada.setFocus()

    def closeEvent(self, e):
        e.ignore()          # cerrar el panel solo lo oculta: el asistente sigue en la cara
        self.hide()

    # --------------------------------------------------------- modos/estudio
    def mostrar_modos(self, estudiando: bool, silencio: bool, descripcion: str = "",
                      pausado: bool = False, escucha: bool = False):
        self.b_estudio.setChecked(estudiando)
        self.b_silencio.setChecked(silencio)
        self.b_escucha.setChecked(escucha)
        self.tarjeta.setVisible(estudiando)
        if estudiando:
            self.estudio_estado.setText(descripcion)
            self.b_pausa.setText("▶ Seguir" if pausado else "⏸ Pausa")

    def mostrar_hoy(self, texto: str):
        self.hoy.setText(texto)

    def mostrar_voz(self, texto: str):
        self.voz.setText(texto)

    def mostrar_nube(self, texto: str, error: bool = False):
        self.nube.setVisible(bool(texto))
        self.nube.setText(texto)
        self._repintar(self.nube, error=error)

    # ------------------------------------------------------------- formulario
    def _reiniciar_formulario(self):
        self._editando = None
        self.boton_enviar.setText("Agregar")
        self._repintar(self.boton_enviar, editando=False)
        self.boton_cancelar.hide()
        self.entrada.clear()
        sugerida = (datetime.now() + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
        self.selector_fecha.setDateTime(QDateTime(sugerida))
        self.selector_repeticion.setCurrentIndex(0)
        self.selector_tipo.setCurrentIndex(0)
        self._tarea_editada = None
        self._mostrar_vista("Escribe una tarea y cuándo, o un comando como «modo estudio 50».")

    def empezar_edicion(self, tarea: Tarea):
        """Carga la tarea en el formulario; el botón pasa a decir 'Guardar'."""
        self._editando = None                 # evita que el texto cargado mueva los selectores
        self.entrada.setText(tarea.titulo)
        self.selector_fecha.setDateTime(QDateTime(tarea.fecha))
        self.selector_repeticion.setCurrentIndex(self.selector_repeticion.findData(tarea.repeticion))
        self.selector_tipo.setCurrentIndex(self.selector_tipo.findData(tarea.tipo))
        self._editando = tarea.id
        self._tarea_editada = tarea
        self.boton_enviar.setText("Guardar")
        self._repintar(self.boton_enviar, editando=True)
        self.boton_cancelar.show()
        self._mostrar_vista("✎ Editando. Cambia el texto, la fecha o la repetición y pulsa Guardar.",
                            editando=True)
        self.pestanas.setCurrentIndex(0)
        self.abrir()
        self.entrada.selectAll()

    def _al_escribir(self, texto: str):
        if self._editando is not None:
            # En edición no se buscan comandos; si escribes una fecha nueva, se aplica
            r = interpretar(texto)
            if r.fecha:
                self.selector_fecha.setDateTime(QDateTime(r.fecha))
            if r.repeticion:
                self.selector_repeticion.setCurrentIndex(self.selector_repeticion.findData(r.repeticion))
            if r.tipo == "evento":
                self.selector_tipo.setCurrentIndex(self.selector_tipo.findData("evento"))
            return
        if not texto.strip():
            self._mostrar_vista("Escribe una tarea y cuándo, o un comando como «modo estudio 50».")
            return
        comando = interpretar_comando(texto)
        if comando:
            desc = DESCRIPCION_COMANDO[comando.accion].format(
                modo=NOMBRES_MODO["estudio"].lower(), silencio=NOMBRES_MODO["silencio"].lower(),
                texto=comando.texto or "", destino=comando.destino or "",
                en=f" en {comando.navegador}" if comando.navegador else "")
            if comando.minutos:
                desc += f" con bloques de {comando.minutos} min"
            self._mostrar_vista(f"⚡ Comando: {desc} (Enter)", comando=True)
            return
        r = interpretar(texto)
        if r.fecha:
            self.selector_fecha.setDateTime(QDateTime(r.fecha))
        self.selector_repeticion.setCurrentIndex(self.selector_repeticion.findData(r.repeticion))
        self.selector_tipo.setCurrentIndex(self.selector_tipo.findData(r.tipo))
        partes = [f"{'📅 ' if r.tipo == 'evento' else ''}«{r.titulo or '…'}»",
                  describir_fecha(r.fecha) if r.fecha else "sin hora en el texto → usa el selector"]
        if r.repeticion:
            partes.append("🔁 " + REPETICIONES[r.repeticion].lower())
        if r.avisos:
            partes.append(describir_avisos(r.avisos))
        self._mostrar_vista("Entendí: " + " · ".join(partes))

    def _al_enviar(self):
        texto = self.entrada.text().strip()
        if not texto:
            return
        if self._editando is None and (comando := interpretar_comando(texto)):
            self.comando_pedido.emit(comando)
            self._reiniciar_formulario()
            return
        r = interpretar(texto)
        titulo = r.titulo or texto
        fecha = self.selector_fecha.dateTime().toPython().replace(second=0, microsecond=0)
        repeticion = self.selector_repeticion.currentData()
        tipo = self.selector_tipo.currentData()
        if fecha <= datetime.now() and not repeticion:
            self._mostrar_vista("Esa fecha ya pasó. Elige una hora futura.", error=True)
            return
        anticipacion = self._anticipacion(r.anticipacion, tipo, repeticion)
        if self._editando is not None:
            self.editar_pedido.emit(self._editando, titulo, fecha, repeticion, tipo, anticipacion)
        else:
            self.agregar_pedido.emit(titulo, fecha, repeticion, tipo, anticipacion)
        self._reiniciar_formulario()

    def _anticipacion(self, pedida: str | None, tipo: str, repeticion: str | None) -> str | None:
        """
        Con cuántos días avisar antes: lo que escribiste ("avísame 3 días antes") manda; si editas sin
        cambiar el tipo, se conserva la que tenía; si no, la de siempre para ese tipo (evento: 7 y 1 días).
        """
        t = self._tarea_editada
        if not pedida and t is not None and t.tipo == tipo:
            return t.anticipacion
        return avisos_previos(tipo, repeticion, pedida)

    def _mostrar_vista(self, texto: str, error: bool = False, comando: bool = False,
                       editando: bool = False):
        self.vista.setText(texto)
        self._repintar(self.vista, error=error, comando=comando, editando=editando)

    @staticmethod
    def _repintar(widget, **propiedades):
        """Cambia propiedades usadas en el estilo (p. ej. [editando="true"]) y lo reaplica."""
        for nombre, valor in propiedades.items():
            widget.setProperty(nombre, valor)
        widget.style().unpolish(widget)
        widget.style().polish(widget)

    # ---------------------------------------------------------------- estudio
    @property
    def viendo_estudio(self) -> bool:
        return self.isVisible() and self.pestanas.currentIndex() == 1

    def ver_estudio(self):
        self.pestanas.setCurrentIndex(1)
        self.abrir()
        self.semana_pedida.emit(self.semanas_atras)

    def _al_cambiar_pestana(self, indice: int):
        if indice == 1:
            self.semana_pedida.emit(self.semanas_atras)

    def _cambiar_semana(self, paso: int):
        self.semanas_atras = max(0, self.semanas_atras + paso)
        self.semana_pedida.emit(self.semanas_atras)

    def mostrar_semana(self, r: ResumenSemana, hoy):
        """Lo llama el asistente con los datos ya calculados."""
        self.rango.setText(("Últimos 7 días · " if self.semanas_atras == 0 else "") + rango(r))
        self.b_despues.setEnabled(self.semanas_atras > 0)
        self.grafico.mostrar(r.dias, r.meta, hoy)
        self.semana_texto.setText(describir_semana(r)[0])

    # ------------------------------------------------------------------ lista
    def mostrar_tareas(self, tareas: list[Tarea]):
        self.lista.clear()
        ahora = datetime.now()
        vencidas = [t for t in tareas if t.fecha <= ahora]
        proximas = [t for t in tareas if t.fecha > ahora]
        if vencidas:
            self._agregar_fila(self._crear_seccion(f"⚠ VENCIDAS · {len(vencidas)}", vencidas=True))
            for t in vencidas:
                self._agregar_fila(self._crear_fila(t, ahora, vencida=True))
            if proximas:
                self._agregar_fila(self._crear_seccion("PRÓXIMAS"))
        for t in proximas:
            self._agregar_fila(self._crear_fila(t, ahora))
        hoy = sum(1 for t in proximas if t.fecha.date() == ahora.date())
        partes = [f"{len(tareas)} pendiente(s)", f"{hoy} más para hoy"]
        if vencidas:
            partes.append(f"{len(vencidas)} vencida(s)")
        self.pie.setText(" · ".join(partes) if tareas
                         else "Nada pendiente. Escribe arriba para agregar una tarea.")

    def _agregar_fila(self, fila: QWidget):
        item = QListWidgetItem(self.lista)
        item.setSizeHint(QSize(0, fila.sizeHint().height()))   # ancho 0: que tome el de la lista
        self.lista.setItemWidget(item, fila)

    def _crear_seccion(self, texto: str, vencidas: bool = False) -> QWidget:
        fila = QWidget()
        etiqueta = QLabel(texto, objectName="seccion")
        etiqueta.setProperty("vencidas", vencidas)
        capa = QHBoxLayout(fila)
        capa.setContentsMargins(4, 10, 4, 2)
        capa.addWidget(etiqueta, 1)
        if vencidas:
            b_todas = QPushButton("Todas a mañana →", objectName="enlace", cursor=Qt.PointingHandCursor,
                                  toolTip="Mueve cada vencida a mañana, a la misma hora")
            b_todas.clicked.connect(self.reprogramar_vencidas_pedido.emit)
            capa.addWidget(b_todas)
        return fila

    def _crear_fila(self, t: Tarea, ahora: datetime, vencida: bool = False) -> QWidget:
        fila = QWidget()
        nombre = QLabel(("📅 " if t.es_evento else "") + t.titulo, objectName="fila_titulo", wordWrap=True)
        detalle = describir_atraso(t.fecha, ahora) if vencida else describir_fecha(t.fecha, ahora)
        if t.es_evento and not vencida and t.fecha.date() > ahora.date():
            detalle += f" · {describir_faltan(t.fecha, ahora)}"
        if t.repeticion:
            detalle += "  🔁 " + REPETICIONES[t.repeticion].lower()
        fecha = QLabel(detalle, objectName="fila_fecha")
        if t.anticipacion:
            fecha.setToolTip(describir_avisos(t.anticipacion).capitalize() + " (a las 9:00) y a su hora.")
        fecha.setProperty("atrasada", vencida)
        fecha.setProperty("hoy", t.fecha.date() == ahora.date() and not vencida)
        fecha.setProperty("evento", t.es_evento and not vencida and t.fecha.date() != ahora.date())

        if vencida:   # en vez de ✎, el menú de reprogramar (que también trae "Elegir fecha…")
            b_primero = QPushButton("↻", objectName="mini", cursor=Qt.PointingHandCursor, toolTip="Reprogramar")
            b_primero.clicked.connect(lambda: self._abrir_menu_reprogramar(t, b_primero))
        else:
            b_primero = QPushButton("✎", objectName="mini", cursor=Qt.PointingHandCursor, toolTip="Editar")
            b_primero.clicked.connect(lambda: self.empezar_edicion(t))
        b_hecho = QPushButton("✓", objectName="mini", cursor=Qt.PointingHandCursor, toolTip="Hecho")
        b_borrar = QPushButton("✕", objectName="mini", cursor=Qt.PointingHandCursor, toolTip="Eliminar")
        b_hecho.clicked.connect(lambda: self.completar_pedido.emit(t.id))
        b_borrar.clicked.connect(lambda: self.eliminar_pedido.emit(t.id))

        textos = QVBoxLayout()
        textos.setSpacing(1)
        textos.addWidget(nombre)
        textos.addWidget(fecha)
        capa = QHBoxLayout(fila)
        capa.setContentsMargins(4, 8, 4, 8)
        capa.addLayout(textos, 1)
        capa.addWidget(b_primero)
        capa.addWidget(b_hecho)
        capa.addWidget(b_borrar)
        return fila

    def opciones_menu_reprogramar(self, t: Tarea) -> list[tuple[str, datetime | None]]:
        """Los atajos del menú ↻. None = "Elegir fecha…" (abre la edición)."""
        return opciones_reprogramar(t.fecha, datetime.now(), HORA_POR_DEFECTO) + [("Elegir fecha y hora…", None)]

    def _abrir_menu_reprogramar(self, t: Tarea, boton: QPushButton):
        menu = QMenu(self)
        for etiqueta, cuando in self.opciones_menu_reprogramar(t):
            if cuando is None:
                menu.addSeparator()
            accion = QAction(etiqueta, menu)
            if cuando is None:
                accion.triggered.connect(lambda: self.empezar_edicion(t))
            else:
                accion.triggered.connect(lambda _=False, c=cuando: self.reprogramar_pedido.emit(t.id, c))
            menu.addAction(accion)
        self._menu_reprogramar = menu                   # que no se libere mientras está abierto
        menu.popup(boton.mapToGlobal(QPoint(0, boton.height())))
