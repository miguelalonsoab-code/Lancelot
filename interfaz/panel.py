"""
Panel "Mis tareas": modos, tareas y el cuadro donde le "hablas" al asistente.

El cuadro de texto entiende dos cosas:
  - COMANDOS: "modo estudio", "modo estudio 50", "pausa", "terminar", "modo silencio"...
  - TAREAS:   "mañana 8pm pagar la luz", "cada lunes 9am reunión"...
Primero se revisa si es comando; si no, se interpreta como tarea.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from PySide6.QtCore import QDateTime, Qt, Signal
from PySide6.QtWidgets import (QComboBox, QDateTimeEdit, QFrame, QHBoxLayout, QLabel, QLineEdit,
                               QListWidget, QListWidgetItem, QPushButton, QVBoxLayout, QWidget)

from config import ATAJO_HABLAR, COLORES, NOMBRE_ASISTENTE, NOMBRES_MODO
from nucleo.almacen import Tarea
from nucleo.comandos import Comando, interpretar_comando
from nucleo.interprete import REPETICIONES, describir_fecha, interpretar

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
QListWidget {{ background: transparent; border: none; outline: none; }}
QListWidget::item {{ border-bottom: 1px solid #1d212a; }}
QListWidget::item:selected {{ background: transparent; }}
#fila_titulo {{ font-size: 14px; background: transparent; }}
#fila_fecha {{ color: #8b93a1; font-size: 12px; background: transparent; }}
#fila_fecha[atrasada="true"] {{ color: {COLORES['alerta']}; }}
#fila_fecha[hoy="true"] {{ color: {COLORES['pendiente']}; }}
#mini {{ background: transparent; padding: 4px 8px; font-size: 14px; }}
#mini:hover {{ background: #232731; }}
#pie {{ color: #5d6573; font-size: 11px; }}
"""


class Panel(QWidget):
    agregar_pedido = Signal(str, datetime, object)    # titulo, fecha, repeticion (str|None)
    completar_pedido = Signal(int)
    eliminar_pedido = Signal(int)
    editar_pedido = Signal(int, str, datetime, object)  # id, titulo, fecha, repeticion
    comando_pedido = Signal(object)                   # Comando
    hablar_pedido = Signal()                          # botón 🗣: escuchar una orden ahora

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"Mis tareas · {NOMBRE_ASISTENTE}")
        self.setStyleSheet(ESTILO)
        self.resize(430, 620)

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
        self.boton_enviar = QPushButton("Agregar", objectName="agregar", cursor=Qt.PointingHandCursor)
        self.boton_enviar.clicked.connect(self._al_enviar)
        self.boton_cancelar = QPushButton("Cancelar", cursor=Qt.PointingHandCursor)
        self.boton_cancelar.clicked.connect(self._reiniciar_formulario)
        self.boton_cancelar.hide()
        fila_opciones = QHBoxLayout()
        fila_opciones.addWidget(self.selector_fecha, 3)
        fila_opciones.addWidget(self.selector_repeticion, 2)
        fila_opciones.addWidget(self.boton_enviar)
        fila_opciones.addWidget(self.boton_cancelar)

        self.lista = QListWidget()
        self.lista.setSelectionMode(QListWidget.NoSelection)
        self.pie = QLabel(objectName="pie")

        capa = QVBoxLayout(self)
        capa.setContentsMargins(18, 16, 18, 12)
        capa.setSpacing(8)
        capa.addWidget(titulo)
        capa.addLayout(fila_modos)
        capa.addWidget(self.voz)
        capa.addWidget(self.tarjeta)
        capa.addWidget(self.hoy)
        capa.addSpacing(4)
        capa.addWidget(self.entrada)
        capa.addWidget(self.vista)
        capa.addLayout(fila_opciones)
        capa.addSpacing(6)
        capa.addWidget(self.lista, 1)
        capa.addWidget(self.pie)

        self._editando: int | None = None    # id de la tarea que se está editando
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
        self._mostrar_vista("Escribe una tarea y cuándo, o un comando como «modo estudio 50».")

    def empezar_edicion(self, tarea: Tarea):
        """Carga la tarea en el formulario; el botón pasa a decir 'Guardar'."""
        self._editando = None                 # evita que el texto cargado mueva los selectores
        self.entrada.setText(tarea.titulo)
        self.selector_fecha.setDateTime(QDateTime(tarea.fecha))
        self.selector_repeticion.setCurrentIndex(self.selector_repeticion.findData(tarea.repeticion))
        self._editando = tarea.id
        self.boton_enviar.setText("Guardar")
        self._repintar(self.boton_enviar, editando=True)
        self.boton_cancelar.show()
        self._mostrar_vista("✎ Editando. Cambia el texto, la fecha o la repetición y pulsa Guardar.",
                            editando=True)
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
        partes = [f"«{r.titulo or '…'}»",
                  describir_fecha(r.fecha) if r.fecha else "sin hora en el texto → usa el selector"]
        if r.repeticion:
            partes.append("🔁 " + REPETICIONES[r.repeticion].lower())
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
        if fecha <= datetime.now() and not repeticion:
            self._mostrar_vista("Esa fecha ya pasó. Elige una hora futura.", error=True)
            return
        if self._editando is not None:
            self.editar_pedido.emit(self._editando, titulo, fecha, repeticion)
        else:
            self.agregar_pedido.emit(titulo, fecha, repeticion)
        self._reiniciar_formulario()

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

    # ------------------------------------------------------------------ lista
    def mostrar_tareas(self, tareas: list[Tarea]):
        self.lista.clear()
        ahora = datetime.now()
        for t in tareas:
            item = QListWidgetItem(self.lista)
            fila = self._crear_fila(t, ahora)
            item.setSizeHint(fila.sizeHint())
            self.lista.setItemWidget(item, fila)
        hoy = sum(1 for t in tareas if t.fecha.date() == ahora.date())
        self.pie.setText(f"{len(tareas)} pendiente(s) · {hoy} para hoy" if tareas
                         else "Nada pendiente. Escribe arriba para agregar una tarea.")

    def _crear_fila(self, t: Tarea, ahora: datetime) -> QWidget:
        fila = QWidget()
        nombre = QLabel(t.titulo, objectName="fila_titulo", wordWrap=True)
        detalle = describir_fecha(t.fecha, ahora)
        if t.repeticion:
            detalle += "  🔁 " + REPETICIONES[t.repeticion].lower()
        fecha = QLabel(detalle, objectName="fila_fecha")
        fecha.setProperty("atrasada", t.fecha < ahora)
        fecha.setProperty("hoy", t.fecha.date() == ahora.date() and t.fecha >= ahora)

        b_editar = QPushButton("✎", objectName="mini", cursor=Qt.PointingHandCursor, toolTip="Editar")
        b_hecho = QPushButton("✓", objectName="mini", cursor=Qt.PointingHandCursor, toolTip="Hecho")
        b_borrar = QPushButton("✕", objectName="mini", cursor=Qt.PointingHandCursor, toolTip="Eliminar")
        b_editar.clicked.connect(lambda: self.empezar_edicion(t))
        b_hecho.clicked.connect(lambda: self.completar_pedido.emit(t.id))
        b_borrar.clicked.connect(lambda: self.eliminar_pedido.emit(t.id))

        textos = QVBoxLayout()
        textos.setSpacing(1)
        textos.addWidget(nombre)
        textos.addWidget(fecha)
        capa = QHBoxLayout(fila)
        capa.setContentsMargins(4, 8, 4, 8)
        capa.addLayout(textos, 1)
        capa.addWidget(b_editar)
        capa.addWidget(b_hecho)
        capa.addWidget(b_borrar)
        return fila
