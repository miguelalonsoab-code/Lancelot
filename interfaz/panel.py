"""
Panel "Mis tareas": modos, tareas y el cuadro donde le "hablas" al asistente.

El cuadro de texto entiende dos cosas:
  - COMANDOS: "modo estudio", "modo estudio 50", "pausa", "terminar", "modo silencio"...
  - TAREAS:   "mañana 8pm pagar la luz", "cada lunes 9am reunión"...
  - EVENTOS:  "el 15 de noviembre aniversario", "examen de cálculo el 20/10" (: avisan días antes)
Primero se revisa si es comando; si no, se interpreta como tarea (o evento: el selector Tarea/Evento
muestra lo que entendió y se puede cambiar).

Pestañas:
  - Tareas:  arriba TAREAS VENCIDAS (siempre a la vista, con ↻ para reprogramar), luego PRÓXIMOS EVENTOS
             y al final las PRÓXIMAS TAREAS.
  - Estudio: gráfico de los últimos 7 días, con ◀ ▶ para ver semanas anteriores.
  - Horario: tus bloques fijos de la semana (trabajo, clases…) y tus horas libres de hoy y mañana.
  - Perfil:  lo que Lancelot sabe de ti: horas de sueño, meta de estudio y actividades que te gustan.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from html import escape

from PySide6.QtCore import QDate, QDateTime, QLocale, QPoint, QSize, Qt, QTime, Signal
from PySide6.QtGui import QAction, QColor, QIcon, QTextCharFormat
from PySide6.QtWidgets import (QGridLayout, QCalendarWidget, QComboBox, QDateTimeEdit, QFormLayout, QFrame, QHBoxLayout, QLabel,
                               QLineEdit, QListWidget, QListWidgetItem, QMenu, QPushButton, QSpinBox, QTabWidget,
                               QTimeEdit, QToolButton, QVBoxLayout, QWidget)

from config import ATAJO_HABLAR, COLORES, VERSION, HORA_POR_DEFECTO, NOMBRE_ASISTENTE, NOMBRES_MODO
from interfaz.grafico import GraficoSemana
from interfaz.iconos import icono, icono_dos_estados, pixmap
from interfaz.tema import ZAFIRO, familia
from interfaz.semana_cal import SemanaCalendario
from nucleo.almacen import Tarea
from nucleo.comandos import Comando, interpretar_comando
from nucleo.estadisticas import ResumenSemana, describir_semana, rango
from nucleo.horario import (CATEGORIAS, ICONO_CATEGORIA, NOMBRE_CATEGORIA, Bloque, Excepcion, coincide, duracion,
                            duracion_minutos)
from nucleo.recomendador import NOMBRE_MOMENTO
from nucleo.perfil import Perfil
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
    "horario_ver": "mostrar tu horario",
    "horario_agregar": "anotar en tu horario: «{texto}»",
    "horario_borrar": "borrar del horario: «{texto}»",
    "categoria": "marcar «{texto}» como {destino}",
    "sugerir": "sugerirte qué hacer en tus horas libres",
    "actividad_hecha": "anotar que hiciste «{texto}» (cuenta para tu meta)",
    "agendar_plan": "agendar las sugerencias como tareas",
    "posponer_hasta": "proponerte la sugerencia a las {texto}",
    "olvidar_rechazos": "olvidar lo que rechazaste y volver a sugerirte todo",
    "excepcion": "anotar un día libre / excepción: «{texto}»",
    "excepciones": "mostrar tus días libres y excepciones",
    "libre": "decirte tus horas libres",
    "perfil": "decirte lo que sé de ti",
    "despertar": "anotar a qué hora te despiertas",
    "dormir": "anotar a qué hora te duermes",
    "meta_estudio": "cambiar tu meta de estudio diaria",
    "actividad": "agregar la actividad «{texto}»",
    "actividades": "decirte tus actividades",
    "borrar_actividad": "borrar la actividad «{texto}»",
    "traslado": "anotar cuánto tardas en llegar a «{texto}»",
}

Z = ZAFIRO
ESTILO = f"""
/* Tema Zafiro del sistema de diseño (v3.24): ver interfaz/tema.py. Una acción primaria por pantalla (#agregar). */
QWidget {{ background: {Z['fondo']}; color: {Z['tinta']}; font-family: {familia()}; font-size: 13px; }}
#titulo {{ font-size: 24px; font-weight: 700; letter-spacing: -0.2px; }}
#vista {{ color: {Z['tinta_suave']}; font-size: 12px; }}
#vista[error="true"] {{ color: {Z['peligro']}; }}
#vista[comando="true"] {{ color: {Z['acento_tinta']}; }}
#vista[editando="true"] {{ color: {Z['acento_tinta']}; }}
QLineEdit, QDateTimeEdit, QComboBox, QTimeEdit, QSpinBox {{
    background: {Z['superficie_alta']}; border: 1px solid {Z['linea_fuerte']}; border-radius: 12px; padding: 8px 12px;
    selection-background-color: {Z['acento_suave']}; selection-color: {Z['tinta']};
}}
QTimeEdit, QSpinBox, QDateTimeEdit {{ font-family: {familia(False)}; }}
QLineEdit:focus, QDateTimeEdit:focus, QComboBox:focus, QTimeEdit:focus, QSpinBox:focus {{ border-color: {Z['acento']}; }}
QComboBox QAbstractItemView {{ background: {Z['superficie_alta']}; border: 1px solid {Z['linea_fuerte']};
                              selection-background-color: {Z['acento_suave']}; selection-color: {Z['acento_tinta']}; }}
QPushButton {{ background: transparent; color: {Z['tinta']}; border: 1px solid {Z['linea_fuerte']}; border-radius: 16px;
              padding: 6px 14px; font-weight: 600; }}
QPushButton:hover {{ background: {Z['superficie_alta']}; }}
QPushButton:checked {{ background: {Z['acento_suave']}; color: {Z['acento_tinta']}; }}
#agregar {{ background: {Z['acento']}; color: {Z['sobre_acento']}; border: none; font-weight: 700; }}
#agregar:hover {{ background: {Z['acento_tinta']}; }}
#agregar[editando="true"] {{ background: {Z['exito']}; color: {Z['sobre_acento']}; }}
#icono {{ padding: 6px; border-radius: 16px; min-width: 20px; }}
#tarjeta_estudio {{ background: {Z['superficie']}; border: 1px solid {Z['linea']}; border-radius: 18px; }}
#tarjeta_estudio QLabel {{ background: transparent; }}
#estudio_estado {{ color: {Z['tinta']}; font-size: 15px; font-weight: 600; }}
#hoy, #voz, #nube {{ color: {Z['tinta_suave']}; font-size: 12px; }}
#nube[error="true"] {{ color: {Z['peligro']}; }}
QListWidget {{ background: transparent; border: none; outline: none; }}
QListWidget::item {{ border-bottom: 1px solid {Z['linea']}; }}
QListWidget::item:selected {{ background: transparent; }}
#fila_titulo {{ font-size: 15px; font-weight: 600; background: transparent; }}
#fila_fecha {{ color: {Z['tinta_suave']}; font-family: {familia(False)}; font-size: 12px; background: transparent; }}
#fila_fecha[atrasada="true"] {{ color: {Z['peligro']}; }}
#fila_detalle {{ color: {Z['tinta_suave']}; font-size: 12px; background: transparent; }}
#fila_fecha[hoy="true"], #fila_fecha[evento="true"] {{ color: {Z['acento_tinta']}; }}
#mini {{ background: transparent; border: none; border-radius: 16px; padding: 0; }}
#mini:hover {{ background: {Z['superficie_alta']}; }}
#pie {{ color: {Z['tinta_suave']}; font-size: 12px; }}
#seccion {{ color: {Z['tinta_suave']}; font-size: 11px; font-weight: 700; letter-spacing: 1.5px; background: transparent; }}
#seccion[vencidas="true"] {{ color: {Z['peligro']}; }}
#seccion[evento="true"] {{ color: {Z['acento_tinta']}; }}
#enlace {{ background: transparent; border: none; color: {Z['peligro']}; padding: 2px 6px; font-size: 12px; }}
#enlace:hover {{ background: {Z['superficie_alta']}; }}
QTabWidget::pane {{ border: none; }}
QTabBar {{ background: transparent; }}
QTabBar::tab {{ background: transparent; color: {Z['tinta_suave']}; padding: 6px 14px; margin: 4px 4px 4px 0;
               border-radius: 14px; font-weight: 600; }}
QTabBar::tab:selected {{ background: {Z['acento']}; color: {Z['sobre_acento']}; font-weight: 700; }}
QTabBar::tab:hover:!selected {{ color: {Z['tinta']}; background: {Z['superficie']}; }}
#rango {{ font-size: 15px; font-weight: 600; }}
#semana_texto {{ color: {Z['tinta_suave']}; font-size: 13px; }}
#nota {{ color: {Z['tinta_suave']}; font-size: 12px; }}
#libre {{ color: {Z['acento_tinta']}; font-size: 13px; font-weight: 600; }}
QCalendarWidget QWidget#qt_calendar_navigationbar {{ background: {Z['fondo']}; }}
QCalendarWidget QToolButton {{ background: transparent; color: {Z['tinta']}; font-weight: 600; padding: 4px 8px;
                              border: none; border-radius: 14px; }}
QCalendarWidget QToolButton#qt_calendar_prevmonth, QCalendarWidget QToolButton#qt_calendar_nextmonth {{
    font-size: 18px; color: {Z['tinta']}; border: 1px solid {Z['linea_fuerte']}; min-width: 28px; }}
QCalendarWidget QToolButton:hover {{ background: {Z['superficie_alta']}; }}
QCalendarWidget QAbstractItemView {{ background: {Z['superficie']}; color: {Z['tinta']}; font-family: {familia(False)};
                                     selection-background-color: {Z['acento_suave']};
                                     selection-color: {Z['acento_tinta']}; outline: none; }}
QCalendarWidget QAbstractItemView:disabled {{ color: {Z['linea_fuerte']}; }}
#ag_hora {{ color: {Z['tinta_suave']}; font-family: {familia(False)}; font-size: 12px; background: transparent; }}
#ag_hora[tipo="libre"], #fila_titulo[tipo="libre"] {{ color: {Z['acento_tinta']}; }}
#fila_titulo[tipo="bloque"], #fila_titulo[tipo="evento"] {{ color: {Z['tinta']}; }}
QPushButton#categoria {{ background: transparent; color: {Z['tinta_suave']}; border: 1px solid {Z['linea_fuerte']};
                         border-radius: 13px; padding: 3px 10px; font-size: 12px; font-weight: 600; }}
QPushButton#categoria:hover {{ background: {Z['superficie_alta']}; }}
QPushButton#categoria:checked {{ background: {Z['acento_suave']}; color: {Z['acento_tinta']}; font-weight: 700; }}
#chip {{ border: 1px solid {Z['linea_fuerte']}; border-radius: 11px; background: transparent; }}
#chip QLabel, #leyenda QLabel {{ background: transparent; color: {Z['tinta_suave']}; font-size: 12px; }}
#leyenda, #icono_fila {{ background: transparent; }}
#sugerencias_dia {{ background: {Z['superficie']}; border: 1px solid {Z['linea']}; border-radius: 14px; padding: 10px 12px;
                   color: {Z['tinta']}; }}
QMenu {{ background: {Z['superficie']}; border: 1px solid {Z['linea']}; padding: 4px; }}
QMenu::item {{ padding: 6px 18px; border-radius: 8px; }}
QMenu::item:selected {{ background: {Z['superficie_alta']}; }}
QToolTip {{ background: {Z['superficie_alta']}; color: {Z['tinta']}; border: 1px solid {Z['linea_fuerte']}; padding: 4px 8px; }}
QScrollBar:vertical {{ background: transparent; width: 8px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {Z['linea_fuerte']}; border-radius: 4px; min-height: 24px; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical, QScrollBar::add-page:vertical,
QScrollBar::sub-page:vertical {{ background: none; height: 0; }}
"""


def _boton_icono(nombre: str, ayuda: str, color: str | None = None) -> QPushButton:
    """Botón chico solo con icono (v3.24: antes ✎ ✓ ✕ ↻). El nombre accesible y la ayuda dicen qué hace."""
    b = QPushButton("", objectName="mini", cursor=Qt.PointingHandCursor, toolTip=ayuda)
    b.setIcon(icono(nombre, color or ZAFIRO["tinta_suave"], 16))
    b.setAccessibleName(ayuda)
    b.setFixedSize(32, 32)
    return b


def _con_icono(etiqueta: QLabel, nombre: str | None, color: str) -> QLabel | QHBoxLayout:
    """
    v3.24: un icono de línea delante del texto (calendario = evento, bombilla = sugerida, reloj = libre), en lugar
    del emoji que antes iba dentro del texto. Sin icono devuelve la misma etiqueta.
    """
    if not nombre:
        return etiqueta
    dibujo = QLabel(objectName="icono_fila")
    dibujo.setPixmap(pixmap(nombre, color, 16))
    dibujo.setFixedWidth(18)
    fila = QHBoxLayout()
    fila.setSpacing(6)
    fila.addWidget(dibujo, 0, Qt.AlignTop)
    fila.addWidget(etiqueta, 1)
    return fila


def _agregar(caja, cosa):
    """Agrega un widget o un layout (lo que devuelva _con_icono)."""
    (caja.addLayout if isinstance(cosa, QHBoxLayout) else caja.addWidget)(cosa)


def _punto(categoria: str) -> str:
    """El puntito de color de una categoría del horario, en HTML para un QLabel (v3.22)."""
    return f'<span style="color:{COLORES.get("bloque_" + categoria, COLORES["bloque_otro"])}">●</span>'


class Panel(QWidget):
    agregar_pedido = Signal(str, datetime, object, str, object, object)  # titulo, fecha, repeticion, tipo,
    #                                                                       anticipacion, duracion (min o None)
    completar_pedido = Signal(int)
    eliminar_pedido = Signal(int)
    editar_pedido = Signal(int, str, datetime, object, str, object, object)  # id + lo mismo
    comando_pedido = Signal(object)                   # Comando
    hablar_pedido = Signal()                          # botón: escuchar una orden ahora
    reprogramar_pedido = Signal(int, datetime)        # id, nueva fecha (atajos de ↻)
    reprogramar_vencidas_pedido = Signal()            # "Todas a mañana"
    semana_pedida = Signal(int)                       # semanas hacia atrás (0 = últimos 7 días)
    correccion_pedida = Signal(str, str, str)         # título, lo que entendió, lo que elegiste (tarea/evento)
    bloque_agregar_pedido = Signal(str)               # "de lunes a viernes de 9am a 6pm trabajo"
    bloque_borrar_pedido = Signal(int)                # id del bloque
    bloque_categoria_pedido = Signal(int, str)        # id del bloque, categoría nueva (v3.22)
    excepcion_borrar_pedido = Signal(int)             # id de la excepción (v3.14)
    aprendido_borrar_pedido = Signal(str, str)        # (nombre, momento) que ya no se sugiere (v3.17)
    perfil_guardar_pedido = Signal(object, object, int)  # despertar (time), dormir (time), meta de estudio (min)
    actividad_agregar_pedido = Signal(str)            # "gimnasio 1 hora 3 veces por semana en la tarde"
    actividad_borrar_pedido = Signal(int)
    actividad_hecha_pedido = Signal(int)              # ✓ hoy (v3.15): marca o desmarca
    perfil_pedido = Signal()                          # "¿Qué sabe Lancelot de mí?"
    calendario_pedido = Signal()                      # cambió el día o el mes a la vista (v3.20)
    calendario_agendar_pedido = Signal(object)        # agendar las sugerencias de ese día (date)

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"Mis tareas · {NOMBRE_ASISTENTE} {VERSION}")
        self.setStyleSheet(ESTILO)
        self.resize(520, 660)

        titulo = QLabel("Mis tareas", objectName="titulo")

        # --- Barra de modos
        self.b_estudio = QPushButton(f"{NOMBRES_MODO['estudio']}", checkable=True,
                                     cursor=Qt.PointingHandCursor)
        self.b_silencio = QPushButton(f"{NOMBRES_MODO['silencio']}", checkable=True,
                                      cursor=Qt.PointingHandCursor)
        self.b_estudio.clicked.connect(
            lambda marcado: self.comando_pedido.emit(Comando("estudio" if marcado else "terminar")))
        self.b_silencio.clicked.connect(
            lambda marcado: self.comando_pedido.emit(Comando("silencio" if marcado else "sin_silencio")))
        self.b_escucha = QPushButton("Escucha", checkable=True, cursor=Qt.PointingHandCursor,
                                     toolTip=f"Escuchar siempre, esperando que digas «{NOMBRE_ASISTENTE}»")
        self.b_escucha.clicked.connect(
            lambda marcado: self.comando_pedido.emit(Comando("escucha_on" if marcado else "escucha_off")))
        b_hablar = QPushButton("", objectName="icono", cursor=Qt.PointingHandCursor,
                               toolTip=f"Hablarle ahora (igual que {ATAJO_HABLAR})")
        b_hablar.setAccessibleName("Hablarle ahora")
        # v3.24: iconos de línea en vez de emoji (el texto dice qué hace; el icono solo ayuda a reconocerlo)
        for boton, nombre_icono in ((self.b_estudio, "libro"), (self.b_silencio, "campana_off"),
                                    (self.b_escucha, "oreja"), (b_hablar, "microfono")):
            boton.setIcon(icono_dos_estados(nombre_icono, ZAFIRO["tinta_suave"], ZAFIRO["acento_tinta"], 16))
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
        self.b_pausa = QPushButton("Pausa", cursor=Qt.PointingHandCursor)
        self.b_pausa.setIcon(icono("pausa", ZAFIRO["tinta"], 14))
        self.b_pausa.clicked.connect(lambda: self.comando_pedido.emit(
            Comando("seguir" if self.b_pausa.text() == "Seguir" else "pausa")))
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
        self.selector_tipo.setMinimumWidth(118)              # que "Evento" no se corte (con el padding del estilo)
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
        self.actividades_semana = QLabel(objectName="semana_texto", wordWrap=True)   # (v3.16)
        nota = QLabel("La línea punteada es tu meta diaria (cámbiala en la pestaña Perfil). "
                      "Las barras verdes la cumplieron. También puedes preguntar «resumen semanal».",
                      objectName="nota", wordWrap=True)
        pestana_estudio = QWidget()
        capa_estudio = QVBoxLayout(pestana_estudio)
        capa_estudio.setContentsMargins(0, 10, 0, 0)
        capa_estudio.setSpacing(10)
        capa_estudio.addLayout(fila_rango)
        capa_estudio.addWidget(self.grafico)
        capa_estudio.addWidget(self.semana_texto)
        capa_estudio.addWidget(self.actividades_semana)
        capa_estudio.addStretch()
        capa_estudio.addWidget(nota)

        # --- Pestaña "Horario": bloques fijos y horas libres
        self.libre_hoy = QLabel(objectName="libre", wordWrap=True)
        self.libre_manana = QLabel(objectName="semana_texto", wordWrap=True)
        self.sugerencias_hoy = QLabel(objectName="semana_texto", wordWrap=True)      # (v3.15)
        self.entrada_bloque = QLineEdit(placeholderText="de lunes a viernes de 9am a 6pm trabajo, traslado 45 min")
        self.entrada_bloque.returnPressed.connect(self._al_agregar_bloque)
        b_bloque = QPushButton("Anotar", objectName="agregar", cursor=Qt.PointingHandCursor)
        b_bloque.clicked.connect(self._al_agregar_bloque)
        fila_bloque = QHBoxLayout()
        fila_bloque.addWidget(self.entrada_bloque, 1)
        fila_bloque.addWidget(b_bloque)
        self.lista_horario = QListWidget()
        self.lista_horario.setSelectionMode(QListWidget.NoSelection)
        self.lista_horario.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        nota_horario = QLabel("Lo que te ocupa cada semana (trabajo, clases, gimnasio…). Con esto Lancelot sabe "
                              "cuándo estás libre. Para un día que no se cumple escribe aquí mismo «el 1 de noviembre "
                              "no trabajo» o «vacaciones del 20 al 30 de diciembre». También puedes preguntar "
                              "«¿cuándo estoy libre?».", objectName="nota", wordWrap=True)
        pestana_horario = QWidget()
        capa_horario = QVBoxLayout(pestana_horario)
        capa_horario.setContentsMargins(0, 10, 0, 0)
        capa_horario.setSpacing(8)
        capa_horario.addWidget(self.libre_hoy)
        capa_horario.addWidget(self.libre_manana)
        capa_horario.addWidget(self.sugerencias_hoy)
        capa_horario.addLayout(fila_bloque)
        capa_horario.addWidget(self.lista_horario, 1)
        capa_horario.addWidget(nota_horario)

        self.pestanas = QTabWidget()
        self.pestanas.addTab(pestana_tareas, "Tareas")
        self.pestanas.addTab(pestana_estudio, "Estudio")
        self.pestanas.addTab(pestana_horario, "Horario")

        # --- Pestaña "Perfil": lo que Lancelot sabe de ti
        self.campo_despertar = QTimeEdit(displayFormat="HH:mm")
        self.campo_dormir = QTimeEdit(displayFormat="HH:mm")
        self.campo_meta = QSpinBox(minimum=10, maximum=720, singleStep=10, suffix=" min al día")
        b_guardar_perfil = QPushButton("Guardar", objectName="agregar", cursor=Qt.PointingHandCursor)
        b_guardar_perfil.clicked.connect(lambda: self.perfil_guardar_pedido.emit(
            self.campo_despertar.time().toPython(), self.campo_dormir.time().toPython(), self.campo_meta.value()))
        formulario = QFormLayout()
        formulario.addRow("Me despierto", self.campo_despertar)
        formulario.addRow("Me duermo", self.campo_dormir)
        formulario.addRow("Meta de estudio", self.campo_meta)
        formulario.addRow("", b_guardar_perfil)
        self.entrada_actividad = QLineEdit(placeholderText="gimnasio 1 hora 3 veces por semana en la tarde")
        self.entrada_actividad.returnPressed.connect(self._al_agregar_actividad)
        b_actividad = QPushButton("Agregar", objectName="agregar", cursor=Qt.PointingHandCursor)
        b_actividad.clicked.connect(self._al_agregar_actividad)
        fila_actividad = QHBoxLayout()
        fila_actividad.addWidget(self.entrada_actividad, 1)
        fila_actividad.addWidget(b_actividad)
        self.lista_actividades = QListWidget()
        self.lista_actividades.setSelectionMode(QListWidget.NoSelection)
        self.lista_actividades.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        b_que_sabes = QPushButton("¿Qué sabes de mí?", cursor=Qt.PointingHandCursor)
        b_que_sabes.clicked.connect(self.perfil_pedido.emit)
        pestana_perfil = QWidget()
        capa_perfil = QVBoxLayout(pestana_perfil)
        capa_perfil.setContentsMargins(0, 10, 0, 0)
        capa_perfil.setSpacing(8)
        capa_perfil.addLayout(formulario)
        capa_perfil.addWidget(QLabel("ACTIVIDADES QUE TE GUSTAN", objectName="seccion"))
        capa_perfil.addLayout(fila_actividad)
        capa_perfil.addWidget(self.lista_actividades, 1)
        capa_perfil.addWidget(b_que_sabes)
        capa_perfil.addWidget(QLabel("Con tu horario, tus horas de sueño y tus actividades, Lancelot sabe cuándo "
                                     "estás libre y te sugiere qué hacer («¿qué hago hoy?»). Marca «○ hoy» o di "
                                     "«ya fui al gimnasio» para que cuente en tu meta de la semana.",
                                     objectName="nota", wordWrap=True))
        self.pestanas.addTab(pestana_perfil, "Perfil")

        # --- Pestaña "Calendario" (v3.20): el mes y la agenda del día elegido
        self.calendario = QCalendarWidget()
        self.calendario.setLocale(QLocale(QLocale.Spanish, QLocale.Peru))
        self.calendario.setFirstDayOfWeek(Qt.Monday)
        self.calendario.setVerticalHeaderFormat(QCalendarWidget.NoVerticalHeader)
        self.calendario.setGridVisible(False)
        normal = QTextCharFormat()
        normal.setForeground(QColor("#e8ebef"))
        for d in (Qt.Saturday, Qt.Sunday):                       # sin el rojo de fin de semana de Qt
            self.calendario.setWeekdayTextFormat(d, normal)
        cabecera = QTextCharFormat()                              # "lun mar mié…" sobre fondo oscuro
        cabecera.setForeground(QColor(ZAFIRO["tinta_suave"]))
        cabecera.setBackground(QColor(ZAFIRO["fondo"]))
        self.calendario.setHeaderTextFormat(cabecera)
        for nombre, texto in (("qt_calendar_prevmonth", "‹"), ("qt_calendar_nextmonth", "›")):
            boton = self.calendario.findChild(QToolButton, nombre)     # las flechas de Qt casi no se ven en oscuro
            if boton:
                boton.setIcon(QIcon())
                boton.setText(texto)
                boton.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self.calendario.selectionChanged.connect(self.calendario_pedido.emit)
        self.calendario.currentPageChanged.connect(lambda *_: self.calendario_pedido.emit())
        # Mes / Semana (v3.21)
        self.b_mes = QPushButton("Mes", checkable=True, checked=True, cursor=Qt.PointingHandCursor)
        self.b_semana = QPushButton("Semana", checkable=True, cursor=Qt.PointingHandCursor)
        self.b_mes.clicked.connect(lambda: self._modo_calendario(False))
        self.b_semana.clicked.connect(lambda: self._modo_calendario(True))
        self.b_sem_antes = QPushButton("‹", objectName="mini", cursor=Qt.PointingHandCursor, toolTip="Semana anterior")
        self.b_sem_despues = QPushButton("›", objectName="mini", cursor=Qt.PointingHandCursor, toolTip="Semana siguiente")
        self.b_sem_antes.clicked.connect(self.semana_anterior)
        self.b_sem_despues.clicked.connect(self.semana_siguiente)
        self.rango_semana = QLabel(objectName="rango", alignment=Qt.AlignCenter)
        fila_modo = QHBoxLayout()
        fila_modo.addWidget(self.b_mes)
        fila_modo.addWidget(self.b_semana)
        fila_modo.addStretch()
        fila_modo.addWidget(self.b_sem_antes)
        fila_modo.addWidget(self.rango_semana)
        fila_modo.addWidget(self.b_sem_despues)
        self.semana_cal = SemanaCalendario()
        self.semana_cal.dia_elegido.connect(lambda d: self.calendario.setSelectedDate(QDate(d.year, d.month, d.day)))
        self.semana_cal.hide()
        self.leyenda_semana = self._leyenda_semana()                       # v3.23
        self.leyenda_semana.hide()
        for w in (self.b_sem_antes, self.b_sem_despues, self.rango_semana):
            w.hide()
        self.agenda_titulo = QLabel(objectName="rango")
        self.lista_agenda = QListWidget()
        self.lista_agenda.setSelectionMode(QListWidget.NoSelection)
        self.lista_agenda.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.sugerencias_dia = QLabel(objectName="sugerencias_dia", wordWrap=True)
        self.b_agendar_dia = QPushButton("Agendar", objectName="agregar", cursor=Qt.PointingHandCursor)
        self.b_agendar_dia.clicked.connect(lambda: self.calendario_agendar_pedido.emit(self.dia_calendario()))
        fila_sug = QHBoxLayout()
        fila_sug.addWidget(self.sugerencias_dia, 1)
        fila_sug.addWidget(self.b_agendar_dia, 0, Qt.AlignTop)
        pestana_calendario = QWidget()
        capa_cal = QVBoxLayout(pestana_calendario)
        capa_cal.setContentsMargins(0, 10, 0, 0)
        capa_cal.setSpacing(8)
        capa_cal.addLayout(fila_modo)
        capa_cal.addWidget(self.calendario)
        capa_cal.addWidget(self.semana_cal, 2)
        capa_cal.addWidget(self.leyenda_semana)
        capa_cal.addWidget(self.agenda_titulo)
        capa_cal.addWidget(self.lista_agenda, 1)
        capa_cal.addLayout(fila_sug)
        self.pestanas.addTab(pestana_calendario, "Calendario")
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

        self.hora_aviso_previo = (9, 0)       # la pone el asistente (config.HORA_AVISO_PREVIO)
        # El asistente pone aquí una función (fecha, duración) -> "Trabajo (08:30–17:30)" si se cruza con tu horario
        self.verificar_choque = lambda fecha, duracion, tipo: None
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
            self.b_pausa.setText("Seguir" if pausado else "Pausa")
            self.b_pausa.setIcon(icono("play" if pausado else "pausa", ZAFIRO["tinta"], 14))

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
        self._mostrar_vista("Editando. Cambia el texto, la fecha o la repetición y pulsa Guardar.",
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
            self._mostrar_vista(f"Comando: {desc} (Enter)", comando=True)
            return
        r = interpretar(texto)
        if r.fecha:
            self.selector_fecha.setDateTime(QDateTime(r.fecha))
        self.selector_repeticion.setCurrentIndex(self.selector_repeticion.findData(r.repeticion))
        self.selector_tipo.setCurrentIndex(self.selector_tipo.findData(r.tipo))
        partes = [f"{'evento ' if r.tipo == 'evento' else ''}«{r.titulo or '…'}»",
                  describir_fecha(r.fecha) if r.fecha else "sin hora en el texto → usa el selector"]
        if r.repeticion:
            partes.append("se repite: " + REPETICIONES[r.repeticion].lower())
        if r.avisos:
            partes.append(describir_avisos(r.avisos))
        if r.fecha and r.duracion:
            partes[1] = f"{describir_fecha(r.fecha)}–{r.fecha + timedelta(minutes=r.duracion):%H:%M}"
        choque = self.verificar_choque(r.fecha, r.duracion, r.tipo) if r.fecha else None
        if choque:
            partes.append(f"se cruza con {choque}")
        self._mostrar_vista("Entendí: " + " · ".join(partes), error=bool(choque))

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
        if tipo != r.tipo:                    # lo corregiste a mano: que Lancelot aprenda
            self.correccion_pedida.emit(titulo, r.tipo, tipo)
        # Duración: la del texto ("de 8 a 10"); si editas sin escribir una nueva, se queda la que tenía
        duracion = r.duracion or (self._tarea_editada.duracion if self._tarea_editada else None)
        if self._editando is not None:
            self.editar_pedido.emit(self._editando, titulo, fecha, repeticion, tipo, anticipacion, duracion)
        else:
            self.agregar_pedido.emit(titulo, fecha, repeticion, tipo, anticipacion, duracion)
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

    # ---------------------------------------------------------------- horario
    def ver_horario(self):
        self.pestanas.setCurrentIndex(2)
        self.abrir()

    def _al_agregar_bloque(self):
        texto = self.entrada_bloque.text().strip()
        if texto:
            self.bloque_agregar_pedido.emit(texto)

    def bloque_anotado(self, ok: bool):
        """El asistente avisa si se pudo: así el texto no se borra cuando hay que corregirlo."""
        if ok:
            self.entrada_bloque.clear()

    # ----------------------------------------------------------------- perfil
    def ver_perfil(self):
        self.pestanas.setCurrentIndex(3)
        self.abrir()

    def _al_agregar_actividad(self):
        texto = self.entrada_actividad.text().strip()
        if texto:
            self.actividad_agregar_pedido.emit(texto)

    def actividad_anotada(self, ok: bool):
        if ok:
            self.entrada_actividad.clear()

    def mostrar_perfil(self, p: Perfil, hechas_semana: dict[int, int] | None = None, hechas_hoy: set[int] = frozenset()):
        for campo, valor in ((self.campo_despertar, p.despertar), (self.campo_dormir, p.dormir)):
            if not campo.hasFocus():                   # no pisar lo que estás escribiendo
                campo.setTime(QTime(valor.hour, valor.minute))
        if not self.campo_meta.hasFocus():
            self.campo_meta.setValue(p.meta_estudio)
        self.lista_actividades.clear()
        for a in p.actividades:
            fila = QWidget()
            nombre = QLabel(a.nombre, objectName="fila_titulo", wordWrap=True)
            n = (hechas_semana or {}).get(a.id, 0)
            semana = (f" · esta semana {n}/{a.veces_semana}" + (" · meta cumplida" if n >= a.veces_semana else "")
                      if a.veces_semana else (f" · esta semana {n}" if n else ""))
            detalle = QLabel(a.describir().split(" · ", 1)[1] + semana, objectName="fila_fecha", wordWrap=True)
            hecha = a.id in hechas_hoy
            b_hecha = QPushButton("✓ hoy" if hecha else "○ hoy", objectName="mini", cursor=Qt.PointingHandCursor,
                                  toolTip="Desmarcar: hoy no la hice" if hecha else "Marcar que la hiciste hoy")
            b_hecha.clicked.connect(lambda _=False, i=a.id: self.actividad_hecha_pedido.emit(i))
            b_borrar = _boton_icono("x", "Quitar")
            b_borrar.clicked.connect(lambda _=False, i=a.id: self.actividad_borrar_pedido.emit(i))
            textos = QVBoxLayout()
            textos.setSpacing(1)
            textos.addWidget(nombre)
            textos.addWidget(detalle)
            capa = QHBoxLayout(fila)
            capa.setContentsMargins(4, 8, 4, 8)
            capa.addLayout(textos, 1)
            capa.addWidget(b_hecha)
            capa.addWidget(b_borrar)
            item = QListWidgetItem(self.lista_actividades)
            item.setSizeHint(QSize(0, fila.sizeHint().height()))
            self.lista_actividades.setItemWidget(item, fila)
        if not p.actividades:
            vacio = QListWidgetItem("Cuéntale qué te gusta hacer: gimnasio, leer, salir a correr…", self.lista_actividades)
            vacio.setFlags(Qt.NoItemFlags)

    def mostrar_horario(self, bloques: list[Bloque], libre_hoy: str, libre_manana: str,
                        excepciones: list[Excepcion] = (), sugerencias: list = (),
                        aprendido: list[tuple[str, str]] = ()):
        self.libre_hoy.setText(f"Libre hoy: {libre_hoy}")
        self.libre_manana.setText(f"Mañana: {libre_manana}")
        self.sugerencias_hoy.setText("Te sugiero: " + " · ".join(f"{s.inicio:%H:%M} {s.nombre}" for s in sugerencias))
        self.sugerencias_hoy.setVisible(bool(sugerencias))
        self.lista_horario.clear()
        for b in bloques:
            self._fila_horario(b.titulo, b.cuando + (f" · traslado de {duracion_minutos(b.traslado)} antes y después"
                                                     if b.traslado else ""),
                               "Quitar del horario", lambda _=False, i=b.id: self.bloque_borrar_pedido.emit(i),
                               categoria=b.categoria,
                               al_categoria=lambda c, i=b.id: self.bloque_categoria_pedido.emit(i, c))
        if not bloques:
            vacio = QListWidgetItem("Todavía no anotaste tu horario. Escríbelo arriba.", self.lista_horario)
            vacio.setFlags(Qt.NoItemFlags)
        if excepciones:
            cabecera = QListWidgetItem(f"DÍAS LIBRES Y EXCEPCIONES · {len(excepciones)}", self.lista_horario)
            cabecera.setFlags(Qt.NoItemFlags)
        for e in excepciones:
            cuando = e.describir().rsplit(" · ", 1)[0]
            afectados = ", ".join(dict.fromkeys(b.titulo for b in bloques if coincide(e.filtro, b.titulo)))
            self._fila_horario(e.titulo, f"{cuando} · " + (f"sin {afectados}" if e.filtro else "todo tu horario libre"),
                               "Quitar la excepción", lambda _=False, i=e.id: self.excepcion_borrar_pedido.emit(i))
        if aprendido:
            cabecera = QListWidgetItem(f"NO TE SUGIERO · {len(aprendido)}", self.lista_horario)
            cabecera.setFlags(Qt.NoItemFlags)
        for nombre, momento in aprendido:
            self._fila_horario(nombre[:1].upper() + nombre[1:],
                               f"en {NOMBRE_MOMENTO[momento]} · dijiste «Ahora no» varias veces",
                               "Volver a sugerirlo en ese momento",
                               lambda _=False, n=nombre, m=momento: self.aprendido_borrar_pedido.emit(n, m))

    def _fila_horario(self, titulo: str, detalle: str, ayuda: str, al_borrar, categoria: str | None = None,
                      al_categoria=None):
        """
        Una fila de la lista. Con 'categoria' (solo los bloques) lleva su punto de color y, debajo, el selector
        Trabajo · Clase · Otro (v3.23; antes era un botón que daba la vuelta). al_categoria(categoria) se llama al
        tocar una opción.
        """
        fila = QWidget()
        nombre = QLabel(titulo, objectName="fila_titulo", wordWrap=True)
        if categoria:
            nombre.setTextFormat(Qt.RichText)
            nombre.setText(f'{_punto(categoria)} {escape(titulo)}')
        abajo = QLabel(detalle, objectName="fila_fecha", wordWrap=True)
        b_borrar = _boton_icono("x", ayuda)
        b_borrar.clicked.connect(al_borrar)
        textos = QVBoxLayout()
        textos.setSpacing(1)
        textos.addWidget(nombre)
        textos.addWidget(abajo)
        if categoria and al_categoria:
            textos.addSpacing(4)
            textos.addLayout(self._selector_categoria(categoria, al_categoria))
        capa = QHBoxLayout(fila)
        capa.setContentsMargins(4, 8, 4, 8)
        capa.addLayout(textos, 1)
        capa.addWidget(b_borrar, 0, Qt.AlignTop)
        item = QListWidgetItem(self.lista_horario)
        item.setSizeHint(QSize(0, fila.sizeHint().height()))
        self.lista_horario.setItemWidget(item, fila)

    @staticmethod
    def _selector_categoria(actual: str, al_elegir) -> QHBoxLayout:
        """Los tres botones Trabajo · Clase · Otro con su icono; el de la categoría actual, marcado."""
        fila = QHBoxLayout()
        fila.setSpacing(6)
        for c in CATEGORIAS:
            b = QPushButton(NOMBRE_CATEGORIA[c], objectName="categoria", checkable=True, checked=c == actual,
                            cursor=Qt.PointingHandCursor, toolTip=f"Categoría: {NOMBRE_CATEGORIA[c]}")
            b.setIcon(icono_dos_estados(ICONO_CATEGORIA[c], ZAFIRO["tinta_suave"], ZAFIRO["acento_tinta"], 14))
            b.setAccessibleName(f"Categoría {NOMBRE_CATEGORIA[c]}")
            b.clicked.connect(lambda _=False, c=c: al_elegir(c))
            fila.addWidget(b)
        fila.addStretch()
        return fila

    @staticmethod
    def _chip_categoria(categoria: str) -> QWidget:
        """Etiqueta de la agenda: cuadradito de color + icono + palabra («Clase»). El estado nunca va solo en color."""
        chip = QWidget(objectName="chip")
        capa = QHBoxLayout(chip)
        capa.setContentsMargins(8, 2, 10, 2)
        capa.setSpacing(5)
        muestra = QLabel()
        muestra.setFixedSize(10, 10)
        muestra.setStyleSheet(f"background: {COLORES['bloque_' + categoria]}; border-radius: 3px;")
        dibujo = QLabel()
        dibujo.setPixmap(pixmap(ICONO_CATEGORIA[categoria], ZAFIRO["tinta_suave"], 14))
        capa.addWidget(muestra)
        capa.addWidget(dibujo)
        capa.addWidget(QLabel(NOMBRE_CATEGORIA[categoria]))
        return chip

    @staticmethod
    def _leyenda_semana() -> QWidget:
        """Qué significa cada color de la vista Semana (v3.23), en dos filas para que entre en el panel."""
        caja = QWidget(objectName="leyenda")
        capa = QGridLayout(caja)
        capa.setContentsMargins(4, 0, 4, 0)
        capa.setHorizontalSpacing(14)
        capa.setVerticalSpacing(4)
        muestras = [(NOMBRE_CATEGORIA[c], f"background: {COLORES['bloque_' + c]};") for c in CATEGORIAS] + [
            ("Libre", f"background: {ZAFIRO['acento_suave']}; border: 1px solid {ZAFIRO['linea_fuerte']};"),
            ("No va ese día", f"background: transparent; border: 1px dashed {ZAFIRO['linea_fuerte']};"),
            ("Tarea", f"background: {ZAFIRO['superficie_alta']}; border: 2px solid {ZAFIRO['linea_fuerte']};"),
            ("Evento", f"background: {ZAFIRO['superficie_alta']}; border: 2px solid {ZAFIRO['destaque']};")]
        for n, (texto, estilo) in enumerate(muestras):
            muestra = QLabel()
            muestra.setFixedSize(12, 12)
            muestra.setStyleSheet(estilo + " border-radius: 3px;")
            par = QHBoxLayout()
            par.setSpacing(5)
            par.addWidget(muestra)
            par.addWidget(QLabel(texto))
            par.addStretch()
            capa.addLayout(par, n // 4, n % 4)
        return caja

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
        if indice == 4:
            self.calendario_pedido.emit()

    # ------------------------------------------------------------ calendario (v3.20)
    @property
    def viendo_calendario(self) -> bool:
        return self.isVisible() and self.pestanas.currentIndex() == 4

    @property
    def modo_semana(self) -> bool:
        return self.b_semana.isChecked()

    def _modo_calendario(self, semana: bool):
        self.b_semana.setChecked(semana)
        self.b_mes.setChecked(not semana)
        self.calendario.setVisible(not semana)
        for w in (self.semana_cal, self.leyenda_semana, self.b_sem_antes, self.b_sem_despues, self.rango_semana):
            w.setVisible(semana)
        self.calendario_pedido.emit()

    def semana_anterior(self):
        self.calendario.setSelectedDate(self.calendario.selectedDate().addDays(-7))

    def semana_siguiente(self):
        self.calendario.setSelectedDate(self.calendario.selectedDate().addDays(7))

    def mostrar_semana_cal(self, dias: list, despertar, dormir, hoy: date):
        self.semana_cal.mostrar(dias, despertar, dormir, self.dia_calendario(), hoy)
        a, b = dias[0][0], dias[-1][0]
        meses = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
        self.rango_semana.setText(f"{a.day} {meses[a.month - 1]} – {b.day} {meses[b.month - 1]}")

    def ver_calendario(self, dia: date | None = None):
        if dia:
            self.calendario.setSelectedDate(QDate(dia.year, dia.month, dia.day))
        self.pestanas.setCurrentIndex(4)
        self.abrir()

    def dia_calendario(self) -> date:
        q = self.calendario.selectedDate()
        return date(q.year(), q.month(), q.day())

    def mes_calendario(self) -> tuple[int, int]:
        return self.calendario.yearShown(), self.calendario.monthShown()

    def mostrar_calendario(self, marcas: dict, titulo: str, agenda: list, sugerencias: list, sin_lugar: list):
        """marcas: {date: (tareas, eventos, libre)}; agenda: [Item] de nucleo/agenda.py; sugerencias del día."""
        self.calendario.setDateTextFormat(QDate(), QTextCharFormat())          # borra las marcas anteriores
        for d, (tareas, eventos, libre) in marcas.items():
            f = QTextCharFormat()
            if tareas or eventos:
                f.setFontWeight(700)
                f.setForeground(QColor(ZAFIRO["destaque"] if eventos else ZAFIRO["acento_tinta"]))
            if libre:
                f.setBackground(QColor(ZAFIRO["acento_suave"]))
            self.calendario.setDateTextFormat(QDate(d.year, d.month, d.day), f)
        self.agenda_titulo.setText(titulo)
        self.lista_agenda.clear()
        for i in agenda:
            self._fila_agenda(i)
        if not agenda:
            vacio = QListWidgetItem("Nada anotado.", self.lista_agenda)
            vacio.setFlags(Qt.NoItemFlags)
        texto = ""
        if sugerencias:
            texto = "Te sugiero:\n" + "\n".join(f"• {s.describir()}" for s in sugerencias)
        if sin_lugar:
            texto += ("\n" if texto else "") + "No entra: " + ", ".join(sin_lugar) + "."
        self.sugerencias_dia.setText(texto)
        self.sugerencias_dia.setVisible(bool(texto))
        self.b_agendar_dia.setVisible(bool(sugerencias))

    def _fila_agenda(self, i):
        fila = QWidget()
        if i.tipo == "excepcion":
            hora = "Todo el día"
        elif i.fin and i.tipo in ("bloque", "libre"):
            hora = f"{i.inicio:%H:%M}–{i.fin:%H:%M}"
        else:
            hora = f"{i.inicio:%H:%M}"
        titulo = {"libre": f"Libre · {duracion(i.inicio, i.fin) if i.fin else ''}",
                  "evento": i.titulo}.get(i.tipo, i.titulo)
        detalle = i.detalle or (f"Hasta las {i.fin:%H:%M}" if i.fin and i.tipo in ("tarea", "evento") else "")
        l_hora = QLabel(hora, objectName="ag_hora")
        l_hora.setFixedWidth(92)
        l_hora.setProperty("tipo", i.tipo)
        nombre = QLabel(titulo, objectName="fila_titulo", wordWrap=True)
        nombre.setProperty("tipo", i.tipo)
        if i.liberado:
            fuente = nombre.font()
            fuente.setStrikeOut(True)
            nombre.setFont(fuente)
        textos = QVBoxLayout()
        textos.setSpacing(1)
        dibujo = {"libre": "reloj", "evento": "calendario"}.get(i.tipo) or ("bombilla" if i.sugerida else None)
        _agregar(textos, _con_icono(nombre, dibujo, ZAFIRO["destaque"] if i.tipo == "evento" else ZAFIRO["acento_tinta"]))
        if detalle:
            textos.addWidget(QLabel(detalle, objectName="fila_detalle", wordWrap=True))   # texto, no fecha: Manrope
        capa = QHBoxLayout(fila)
        capa.setContentsMargins(4, 6, 4, 6)
        capa.addWidget(l_hora)
        capa.addLayout(textos, 1)
        if i.tipo == "bloque" and i.categoria:
            capa.addWidget(self._chip_categoria(i.categoria), 0, Qt.AlignVCenter)
        if i.tarea is not None:
            b = _boton_icono("lapiz", "Editar")
            b.clicked.connect(lambda _=False, t=i.tarea: self.empezar_edicion(t))
            capa.addWidget(b)
        item = QListWidgetItem(self.lista_agenda)
        item.setSizeHint(QSize(0, fila.sizeHint().height()))
        self.lista_agenda.setItemWidget(item, fila)

    def _cambiar_semana(self, paso: int):
        self.semanas_atras = max(0, self.semanas_atras + paso)
        self.semana_pedida.emit(self.semanas_atras)

    def mostrar_semana(self, r: ResumenSemana, hoy):
        """Lo llama el asistente con los datos ya calculados."""
        self.rango.setText(("Últimos 7 días · " if self.semanas_atras == 0 else "") + rango(r))
        self.b_despues.setEnabled(self.semanas_atras > 0)
        self.grafico.mostrar(r.dias, r.meta, hoy)
        self.semana_texto.setText(describir_semana(r)[0])

    def mostrar_actividades_semana(self, texto: str):
        self.actividades_semana.setText(texto)
        self.actividades_semana.setVisible(bool(texto))

    # ------------------------------------------------------------------ lista
    def mostrar_tareas(self, tareas: list[Tarea], sugeridas: set[int] = frozenset()):
        """
        Tres secciones: TAREAS VENCIDAS (siempre, aunque no haya), PRÓXIMOS EVENTOS y PRÓXIMAS TAREAS.
        Un evento nunca es "vencido": el de hoy sigue en eventos hasta que termina el día.
        Lo agendado desde una sugerencia (ids en 'sugeridas', con el icono de bombilla) tampoco vence: sigue en próximas tareas
        hasta el final del día y mañana se quita solo.
        """
        self.lista.clear()
        self._sugeridas = sugeridas
        ahora = datetime.now()
        vencidas = [t for t in tareas if not t.es_evento and t.fecha <= ahora and t.id not in sugeridas]
        eventos = [t for t in tareas if t.es_evento]
        proximas = [t for t in tareas if not t.es_evento and (t.fecha > ahora or t.id in sugeridas)]
        self._agregar_fila(self._crear_seccion(f"TAREAS VENCIDAS · {len(vencidas)}", vencidas=bool(vencidas)))
        for t in vencidas:
            self._agregar_fila(self._crear_fila(t, ahora, vencida=True))
        if not vencidas:
            self._agregar_fila(self._crear_vacio("Ninguna. Vas al día."))
        if eventos:
            self._agregar_fila(self._crear_seccion(f"PRÓXIMOS EVENTOS · {len(eventos)}", evento=True))
            for t in eventos:
                self._agregar_fila(self._crear_fila(t, ahora))
        self._agregar_fila(self._crear_seccion(f"PRÓXIMAS TAREAS · {len(proximas)}"))
        for t in proximas:
            self._agregar_fila(self._crear_fila(t, ahora))
        if not proximas:
            self._agregar_fila(self._crear_vacio("Escribe arriba para agregar una tarea."))
        hoy = sum(1 for t in proximas + eventos if t.fecha > ahora and t.fecha.date() == ahora.date())
        partes = [f"{len(tareas)} pendiente(s)", f"{hoy} más para hoy"]
        if vencidas:
            partes.append(f"{len(vencidas)} vencida(s)")
        self.pie.setText(" · ".join(partes) if tareas
                         else "Nada pendiente. Escribe arriba para agregar una tarea.")

    def _agregar_fila(self, fila: QWidget):
        item = QListWidgetItem(self.lista)
        item.setSizeHint(QSize(0, fila.sizeHint().height()))   # ancho 0: que tome el de la lista
        self.lista.setItemWidget(item, fila)

    def _crear_seccion(self, texto: str, vencidas: bool = False, evento: bool = False) -> QWidget:
        fila = QWidget()
        etiqueta = QLabel(texto, objectName="seccion")
        etiqueta.setProperty("vencidas", vencidas)
        etiqueta.setProperty("evento", evento)
        capa = QHBoxLayout(fila)
        capa.setContentsMargins(4, 10, 4, 2)
        capa.addWidget(etiqueta, 1)
        if vencidas:
            b_todas = QPushButton("Todas a mañana →", objectName="enlace", cursor=Qt.PointingHandCursor,
                                  toolTip="Mueve cada vencida a mañana, a la misma hora")
            b_todas.clicked.connect(self.reprogramar_vencidas_pedido.emit)
            capa.addWidget(b_todas)
        return fila

    def _crear_vacio(self, texto: str) -> QWidget:
        fila = QWidget()
        capa = QHBoxLayout(fila)
        capa.setContentsMargins(4, 4, 4, 8)
        capa.addWidget(QLabel(texto, objectName="fila_fecha"))
        return fila

    def _crear_fila(self, t: Tarea, ahora: datetime, vencida: bool = False) -> QWidget:
        fila = QWidget()
        sugerida = t.id in getattr(self, "_sugeridas", ())
        nombre = QLabel(t.titulo, objectName="fila_titulo", wordWrap=True)
        if sugerida and t.fecha <= ahora:
            detalle = f"era a las {t.fecha:%H:%M} · si no la haces, mañana se quita sola"
        elif vencida:
            detalle = describir_atraso(t.fecha, ahora)
        elif t.es_evento and t.fecha <= ahora:
            detalle = f"hoy {t.fecha:%H:%M} · es hoy"              # ya fue su hora, pero el día sigue
        else:
            detalle = describir_fecha(t.fecha, ahora)
        if t.duracion and not vencida and not (sugerida and t.fecha <= ahora):
            detalle += f"–{t.fin:%H:%M}"                         # "sáb 17/10 08:00–10:00"
        if t.es_evento and not vencida and t.fecha.date() > ahora.date():
            detalle += f" · {describir_faltan(t.fecha, ahora)}"
        if t.repeticion:
            detalle += " · se repite: " + REPETICIONES[t.repeticion].lower()
        fecha = QLabel(detalle, objectName="fila_fecha")
        if t.anticipacion:
            h, m = self.hora_aviso_previo
            fecha.setToolTip(describir_avisos(t.anticipacion).capitalize() + f" (a las {h}:{m:02d}) y a su hora.")
        fecha.setProperty("atrasada", vencida)
        fecha.setProperty("hoy", t.fecha.date() == ahora.date() and not vencida)
        fecha.setProperty("evento", t.es_evento and not vencida and t.fecha.date() != ahora.date())

        if vencida:   # en vez de editar, el menú de reprogramar (que también trae "Elegir fecha…")
            b_primero = _boton_icono("repetir", "Reprogramar")
            b_primero.clicked.connect(lambda: self._abrir_menu_reprogramar(t, b_primero))
        else:
            b_primero = _boton_icono("lapiz", "Editar")
            b_primero.clicked.connect(lambda: self.empezar_edicion(t))
        b_hecho = _boton_icono("check", "Hecho", ZAFIRO["exito"])
        b_borrar = _boton_icono("x", "Eliminar")
        b_hecho.clicked.connect(lambda: self.completar_pedido.emit(t.id))
        b_borrar.clicked.connect(lambda: self.eliminar_pedido.emit(t.id))

        textos = QVBoxLayout()
        textos.setSpacing(1)
        dibujo = "calendario" if t.es_evento else "bombilla" if sugerida else None
        _agregar(textos, _con_icono(nombre, dibujo, ZAFIRO["destaque"] if t.es_evento else ZAFIRO["acento_tinta"]))
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
