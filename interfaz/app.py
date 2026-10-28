"""
Controlador principal: crea las piezas y las conecta. Es el "director de orquesta".

    app.py            ← tú estás aquí: tareas, comandos, estado de la cara, ventanas, menú
    avisos.py         qué muestra la burbuja y en qué orden (tareas, mensajes)
    asistente_voz.py  oír, hablar, diálogo, abrir apps y páginas, apodos
    estudio.py        modo estudio (pomodoros, aliento, distracciones)

Ninguna de esas piezas conoce SQLite ni dibuja la cara por su cuenta: piden cosas
a través del asistente (self.a en cada una).

Modos:
  - estudio  : sesión de pomodoros. Se activa y se termina.
  - silencio : sin sonidos, voz ni notificaciones de Windows; los avisos siguen en la cara.
  Pueden estar los dos activos a la vez (estudiar en la biblioteca, por ejemplo).

Cada día, la primera vez que te ve frente a la laptop, te saluda con tus pendientes
(ver saludar()). Mientras el saludo está en pantalla, los avisos de tareas esperan.

Actualizaciones (solo con Lancelot.exe y REPO_ACTUALIZACIONES configurado): al minuto de abrir
y cada pocas horas pregunta a GitHub si hay una versión nueva; si la hay, te ofrece instalarla.

Sincronización con el celular (si existe nube.json): cada minuto y poco después de cada cambio
(ver sincronizar() y _cambio_local()).

Eventos (v3.10): además del aviso a su hora, avisan con días de anticipación (ver _avisar_eventos_proximos),
y cuando su día pasa se cierran solos (o pasan al próximo año, si se repiten).

Frases (v3.10): si dejas el mouse sobre la cara, te dice una frase (ver decir_frase()); desde la v3.11
también en voz alta. Tus frases viajan al celular junto con la sincronización (ver _preferencias_para_subir).

Perfil (v3.13): tus horas de sueño, tu meta de estudio y tus actividades (ver sección "perfil" abajo
y nucleo/perfil.py). Lo usa todo lo que depende de ti: horas libres, la cara de noche, la meta del gráfico.

Horario (v3.12): tus bloques fijos de la semana y tus horas libres (ver sección "horario" abajo
y nucleo/horario.py). Base para que, más adelante, Lancelot te recomiende qué hacer en ese tiempo.

Aprendizaje (v3.11): si corriges Tarea/Evento en el panel, lo anota y, si se repite, aprende
(ver aprender_correccion() y nucleo/aprendizaje.py).
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import sys
import time
from datetime import date, datetime, time as hora, timedelta

from PySide6.QtCore import QObject, QPoint, QTimer
from PySide6.QtGui import QAction, QGuiApplication, QIcon
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from config import (ATAJO_HABLAR, CARPETA_RESPALDOS, COLORES, HORA_DESPERTAR, HORA_DORMIR,
                    HORA_SALUDO, META_ESTUDIO_DIARIO, NOMBRE_ASISTENTE, NOMBRE_USUARIO, NOMBRES_MODO,
                    RESPALDOS_A_CONSERVAR, RUTA_BD, SALUDO_ACTIVO, SALUDO_HABLADO, SEGUNDOS_ENTRE_REVISIONES,
                    SEGUNDOS_MENSAJE, SEGUNDOS_SALUDO, VERSION, EMPAQUETADO, REPO_ACTUALIZACIONES,
                    HORAS_ENTRE_BUSQUEDAS, BUSCAR_ACTUALIZACIONES_EN_DESARROLLO, NOMBRE_ARCHIVO_NUBE,
                    SEGUNDOS_ENTRE_SINCRONIZACIONES, FRASES_ACTIVAS, SEGUNDOS_MOUSE_PARA_FRASE,
                    SEGUNDOS_ENTRE_FRASES, SEGUNDOS_FRASE, NOMBRE_ARCHIVO_FRASES, HABLAR_RECORDATORIOS,
                    FRASES_HABLADAS, HORA_AVISO_PREVIO, SUGERENCIAS_AL_QUEDAR_LIBRE, MINUTOS_PARA_SUGERIR,
                    MINUTOS_PARA_ARRANCAR, RECHAZOS_PARA_APRENDER, DIAS_QUE_RECUERDA_RECHAZOS,
                    MINUTOS_MAS_TARDE, SUGERENCIAS_EN_CELULAR)
from interfaz.actualizador import Actualizador
from interfaz.asistente_voz import ControladorVoz, NotificadorVoz
from interfaz.avisos import GestorAvisos, NotificadorCara
from interfaz.burbuja import Burbuja
from interfaz.cara import Cara, pixmap_cara
from interfaz.estudio import ModoEstudio
from interfaz.panel import Panel
from interfaz.sincronizador import Resultado, Sincronizador, leer_configuracion
from interfaz.tema import cargar_fuentes
from notificadores.base import Notificador
from notificadores.windows import NotificadorWindows
from nucleo import aprendizaje
from nucleo.almacen import LOTE_SINCRONIZACION, SIN_CAMBIO, Almacen
from nucleo.comandos import Comando, interpretar_comando
from nucleo.estadisticas import ResumenSemana, describir_semana, resumen_semana
from nucleo.frases import (REFLEXIONES, BolsaFrases, crear_archivo_frases, guardar_frase_usuario,
                           leer_frases_usuario)
from nucleo.hablado import hora_hablada
from nucleo.horario import (NOMBRE_CATEGORIA, Bloque, Excepcion, buscar_por_nombre, choque, heredar_categoria, coincide, describir_libre, duracion_minutos, hablar_duracion,
                            huecos, interpretar_bloque, interpretar_excepcion, leer_duracion, minutos, raiz,
                            total_libre)
from nucleo.perfil import Actividad, Perfil, describir_perfil, interpretar_actividad, leer_hora
from nucleo import contexto
from nucleo.agenda import agenda_del_dia, marcas_del_mes
from nucleo.recomendador import (NOMBRE_MOMENTO, Plan, Sugerencia, clave, describir_plan, lunes_de, momento_de,
                                 recomendar)
from nucleo.interprete import describir_faltan, describir_fecha, normalizar, usar_vocabulario
from nucleo.planificador import a_manana, estado_del_dia
from nucleo.respaldo import hacer_respaldo
from nucleo.saludo import armar_saludo, debe_saludar
from nucleo.version import Actualizacion, resumen_notas
from sensores.inactividad import segundos_inactivo

log = logging.getLogger(__name__)

# Confirmaciones habladas cuando un comando llega por voz
_CONFIRMACION_VOZ = {
    "pausa": "Pausado.",
    "seguir": "Seguimos.",
    "silencio": "Modo silencio.",
    "sin_silencio": "Vuelvo a hablar.",
}

SEGUNDOS_PARA_ESTAR_PRESENTE = 120    # si no tocas nada hace más de esto, el saludo espera


class Asistente(QObject):
    def __init__(self, app: QApplication, ruta_bd=None):
        super().__init__()
        self.app = app
        cargar_fuentes(app)                             # v3.24: Manrope y JetBrains Mono (tema Zafiro)
        self.ruta_bd = ruta_bd or RUTA_BD               # las pruebas usan una base temporal
        self.almacen = Almacen(self.ruta_bd)
        self.almacen.reactivar_avisos_pendientes()
        # Tu perfil (lo que nunca dijiste toma los valores de config.py). Se guarda en memoria porque
        # actualizar_estado() lo consulta cada segundo durante el modo estudio.
        self._perfil_defecto = Perfil(hora(HORA_DESPERTAR), hora(min(HORA_DORMIR, 23), 59 if HORA_DORMIR >= 24 else 0),
                                      META_ESTUDIO_DIARIO)
        self.perfil = self.almacen.perfil(self._perfil_defecto)
        self.almacen.limpiar_excepciones(date.today())
        self.silencio = self.almacen.leer_ajuste("silencio") == "1"
        self._avisos_en_pausa_hasta: datetime | None = None   # mientras se muestra el saludo

        # --- Interfaz
        self.cara = Cara()
        self.cara.silencio = self.silencio
        self.burbuja = Burbuja()
        self.panel = Panel()
        self.bandeja = QSystemTrayIcon(QIcon(pixmap_cara(64)))
        self.bandeja.setToolTip(NOMBRE_ASISTENTE)

        # --- Piezas (el orden importa: los avisos y la voz se usan entre sí)
        self.estudio = ModoEstudio(self.almacen)
        self.avisos = GestorAvisos(self)
        self.voz = ControladorVoz(self)
        self.notificador_windows = NotificadorWindows(self.bandeja)
        self.actualizador = Actualizador(REPO_ACTUALIZACIONES, VERSION, self.ruta_bd.parent / "actualizaciones")
        self._actualizacion: Actualizacion | None = None   # la última ofrecida
        nube = leer_configuracion(self.ruta_bd.parent / NOMBRE_ARCHIVO_NUBE)
        self.nube = Sincronizador(*nube, VERSION) if nube else None
        self.estado_nube = ("", False)                     # (texto, ¿es un error?) para el panel
        # Frases al dejar el mouse sobre la cara: las de fábrica + las tuyas (frases.txt)
        self.ruta_frases = self.ruta_bd.parent / NOMBRE_ARCHIVO_FRASES
        try:
            crear_archivo_frases(self.ruta_frases)
        except OSError:
            log.warning("no se pudo crear %s", self.ruta_frases)
        self._frases_leidas = None                         # fecha de modificación de frases.txt ya leída
        self.bolsa_frases = BolsaFrases(REFLEXIONES)
        self._ultima_frase: float | None = None            # time.monotonic() de la última frase dicha
        # Lo aprendido de tus correcciones Tarea/Evento: lo usan el panel, la voz y (sincronizado) el celular
        self.aprendizaje = aprendizaje.cargar(self.almacen.leer_ajuste("aprendizaje"))
        self.vocabulario = aprendizaje.vocabulario(self.aprendizaje)
        usar_vocabulario(self.vocabulario)
        # Con sincronización: los avisos anticipados esperan a la primera sincronización del día,
        # por si el celular ya te lo mostró mientras la laptop estaba apagada
        self._nube_lista = False
        # Canales de aviso de tareas (en la Fase 2 se agrega aquí el del celular)
        self.notificadores: list[Notificador] = [NotificadorCara(self.avisos), self.notificador_windows,
                                                 NotificadorVoz(self.voz)]

        # --- Señales
        self.estudio.aviso.connect(self.avisos.mostrar_mensaje)
        self.estudio.cambio.connect(self.actualizar_estado)
        self.estudio.celebrar.connect(self.cara.celebrar)
        self.cara.clicada.connect(self._alternar_panel)
        self.cara.menu_pedido.connect(self._menu_cara)
        self.cara.movida.connect(self._al_mover_cara)
        self.cara.segundos_reposo = SEGUNDOS_MOUSE_PARA_FRASE
        self.cara.reposo.connect(self.decir_frase)
        self.panel.agregar_pedido.connect(self.agregar)
        self.panel.completar_pedido.connect(self.completar)
        self.panel.eliminar_pedido.connect(self.eliminar)
        self.panel.editar_pedido.connect(self.editar)
        self.panel.comando_pedido.connect(self.ejecutar_comando)
        self.panel.hablar_pedido.connect(self.voz.oido.escuchar_una_orden)
        self.panel.reprogramar_pedido.connect(self.reprogramar)
        self.panel.reprogramar_vencidas_pedido.connect(self.reprogramar_vencidas)
        self.panel.semana_pedida.connect(self.mostrar_semana)
        self.panel.correccion_pedida.connect(self.aprender_correccion)
        self.panel.bloque_agregar_pedido.connect(lambda texto: self.agregar_bloque(texto))
        self.panel.bloque_borrar_pedido.connect(self.borrar_bloque)
        self.panel.bloque_categoria_pedido.connect(self.cambiar_categoria_bloque)       # v3.22
        self.panel.excepcion_borrar_pedido.connect(self.borrar_excepcion)
        self.panel.aprendido_borrar_pedido.connect(self.olvidar_aprendido)
        self.panel.calendario_pedido.connect(self._mostrar_calendario)
        self.panel.calendario_agendar_pedido.connect(self._agendar_dia)
        self.panel.verificar_choque = self.texto_choque
        self.panel.perfil_guardar_pedido.connect(self.guardar_perfil)
        self.panel.actividad_agregar_pedido.connect(lambda texto: self.agregar_actividad(texto))
        self.panel.actividad_borrar_pedido.connect(self.borrar_actividad)
        self.panel.actividad_hecha_pedido.connect(self.alternar_actividad_hoy)
        self.panel.perfil_pedido.connect(lambda: self.decir_perfil())
        self.panel.hora_aviso_previo = HORA_AVISO_PREVIO
        if self.nube:
            self.nube.terminado.connect(self._al_sincronizar)
        self.actualizador.encontrada.connect(self._al_encontrar_actualizacion)
        self.actualizador.sin_novedad.connect(self._al_no_haber_actualizacion)
        self.actualizador.descargada.connect(self._al_descargar_actualizacion)
        self.actualizador.fallo.connect(
            lambda texto: self.avisos.mostrar_mensaje("Actualización", texto, [], COLORES["alerta"], 10, False))

        self._menu_bandeja = QMenu()                 # se guarda para que no se libere
        self._menu_bandeja.aboutToShow.connect(lambda: self._llenar_menu(self._menu_bandeja))
        self.bandeja.setContextMenu(self._menu_bandeja)
        self.bandeja.activated.connect(self._al_activar_bandeja)
        self.bandeja.show()

        # --- Relojes
        self.reloj_revision = QTimer(self)                 # ¿venció algo?
        self.reloj_revision.timeout.connect(self.revisar)
        self.reloj_revision.start(SEGUNDOS_ENTRE_REVISIONES * 1000)
        self.reloj_refresco = QTimer(self)                 # textos como "hoy 20:00" y el saludo
        self.reloj_refresco.timeout.connect(self._cada_minuto)
        self.reloj_refresco.start(60 * 1000)
        self.reloj_respaldo = QTimer(self)                 # por si la laptop queda prendida de un día a otro
        self.reloj_respaldo.timeout.connect(self.respaldar)
        self.reloj_respaldo.start(3 * 60 * 60 * 1000)
        if self.nube:
            self.reloj_nube = QTimer(self)                 # cada minuto
            self.reloj_nube.timeout.connect(self.sincronizar)
            self.reloj_nube.start(SEGUNDOS_ENTRE_SINCRONIZACIONES * 1000)
            self.nube_pronto = QTimer(self, singleShot=True)   # poco después de un cambio tuyo
            self.nube_pronto.timeout.connect(self.sincronizar)
            QTimer.singleShot(2000, self.sincronizar)
            self.estado_nube = ("Conectando con el celular…", False)
        if self.busca_actualizaciones:
            self.actualizador.limpiar_descargas()
            QTimer.singleShot(60 * 1000, self.actualizador.buscar)      # un minuto después de abrir
            self.reloj_actualizacion = QTimer(self)
            self.reloj_actualizacion.timeout.connect(self.actualizador.buscar)
            self.reloj_actualizacion.start(HORAS_ENTRE_BUSQUEDAS * 60 * 60 * 1000)

        if self.almacen.leer_ajuste("escucha") == "1":
            self.voz.poner_escucha(True, avisar=False)

        self._colocar_cara()
        self.cara.show()
        self.refrescar()
        self.respaldar()
        QTimer.singleShot(1500, self._al_arrancar)
        log.info("Lancelot %s iniciado%s", VERSION, " (.exe)" if EMPAQUETADO else "")

    def _al_arrancar(self):
        if getattr(self, "_cerrado", False):               # se cerró antes de terminar de arrancar
            return
        self.saludar()                                     # primero el saludo del día (si toca)
        self.revisar()                                     # luego los avisos atrasados

    def _cada_minuto(self):
        self.refrescar()
        self.saludar()                                     # por si la laptop quedó prendida de un día a otro

    # ================================================================ tareas
    def revisar(self):
        """Se ejecuta cada pocos segundos: ¿llegó la hora de algo?"""
        ahora = datetime.now()
        if self._avisos_en_pausa_hasta and ahora < self._avisos_en_pausa_hasta:
            return                                   # se está mostrando el saludo; avisa en un rato
        cerrados = self.almacen.cerrar_eventos_pasados(ahora)   # eventos de días anteriores
        for id_ in cerrados:
            self.avisos.quitar(id_)
        if cerrados:
            self._cambio_local()
        vencidas = self.almacen.por_avisar(ahora)
        for tarea in vencidas:
            self.almacen.marcar_avisada(tarea.id)
            for canal in self.notificadores:
                if canal.ruidoso and self.silencio:
                    continue
                try:
                    canal.notificar(tarea)
                except Exception:                    # un canal caído no tumba a los demás
                    log.exception("el canal %s falló al avisar", type(canal).__name__)
        self._avisar_eventos_proximos(ahora)
        self._sugerir_al_quedar_libre(ahora)
        contadas, descartadas = self.almacen.repasar_sugeridas(ahora.date())
        for id_ in descartadas:
            self.avisos.quitar(id_)
        if descartadas:
            log.info("descartadas %d tarea(s) sugeridas que no se hicieron", len(descartadas))
            self._cambio_local()                     # que el celular también las borre
        if vencidas or cerrados or contadas or descartadas:
            self.refrescar()

    def _avisar_eventos_proximos(self, ahora: datetime):
        """
        Avisos anticipados ("Aniversario · falta 1 semana"). Si estás estudiando o hablándole,
        esperan a que termines: no son urgentes. Si tocan varios a la vez, van juntos en una burbuja.
        """
        if self.estudio.activo or self.voz.dialogo or self.voz.escuchando_orden:
            return
        if self.nube and not self._nube_lista:
            return                                   # primero saber si el celular ya lo avisó
        tocan = self.almacen.por_avisar_antes(ahora, HORA_AVISO_PREVIO)
        if not tocan:
            return
        for t, _ in tocan:
            self.almacen.marcar_aviso_previo(t.id, ahora)
        self._cambio_local()                         # que el celular sepa que ya lo viste aquí
        lineas = [f"{t.titulo}: {describir_faltan(t.fecha, ahora)} · {describir_fecha(t.fecha, ahora)}"
                  for t, _ in tocan]
        cabecera = "Se acerca" if len(tocan) == 1 else f"Se acercan {len(tocan)} eventos"
        texto = lineas[0] if len(lineas) == 1 else "\n".join(f"• {l}" for l in lineas)
        self.avisos.mostrar_mensaje(cabecera, texto, [("Entendido", "cerrar")], COLORES["evento"], 0, False)
        if not self.silencio:
            self.notificador_windows.mensaje(cabecera, texto)
            if HABLAR_RECORDATORIOS:
                t = tocan[0][0]
                saludo = f"{NOMBRE_USUARIO}, " if NOMBRE_USUARIO else ""
                self.voz.decir(f"{saludo}se acerca {t.titulo}: {describir_faltan(t.fecha, ahora)}.")
        log.info("aviso anticipado de %d evento(s)", len(tocan))

    def agregar(self, titulo: str, fecha: datetime, repeticion, tipo: str = "tarea", anticipacion=None,
                duracion=None):
        t = self.almacen.agregar(titulo, fecha, repeticion, tipo, anticipacion, duracion)
        self._avisar_si_choca(t)
        self._cambio_local()
        self.cara.celebrar()
        self.refrescar()

    def completar(self, tarea_id: int):
        t = self.almacen.obtener(tarea_id)
        self.almacen.completar(tarea_id)
        if t:                                    # "Gimnasio" completada = una vez más para tu meta semanal
            for a in self._actividades_que_nombra(t.titulo):
                self.almacen.marcar_actividad(a.id, date.today())
        self._cambio_local()
        self.avisos.quitar(tarea_id)
        self.cara.celebrar()
        self.refrescar()

    def posponer(self, tarea_id: int, minutos: int):
        self.almacen.posponer(tarea_id, minutos)
        self._cambio_local()
        self.avisos.quitar(tarea_id)
        self.refrescar()

    def editar(self, tarea_id: int, titulo: str, fecha: datetime, repeticion, tipo=SIN_CAMBIO,
               anticipacion=SIN_CAMBIO, duracion=SIN_CAMBIO):
        self.almacen.editar(tarea_id, titulo, fecha, repeticion, tipo, anticipacion, duracion)
        self._avisar_si_choca(self.almacen.obtener(tarea_id))
        self._cambio_local()
        self.avisos.quitar(tarea_id)            # si estaba sonando y la moviste, deja de sonar
        self.cara.celebrar()
        self.refrescar()

    def eliminar(self, tarea_id: int):
        self.almacen.eliminar(tarea_id)
        self._cambio_local()
        self.avisos.quitar(tarea_id)
        self.refrescar()

    def reprogramar(self, tarea_id: int, fecha: datetime):
        self.almacen.reprogramar(tarea_id, fecha)
        self._cambio_local()
        self.avisos.quitar(tarea_id)
        self.cara.celebrar()
        self.refrescar()

    def reprogramar_vencidas(self) -> int:
        """Pasa cada vencida a mañana, a la misma hora. Devuelve cuántas movió."""
        ahora = datetime.now()
        vencidas = self.almacen.vencidas(ahora)
        for t in vencidas:
            self.almacen.reprogramar(t.id, a_manana(t.fecha, ahora))
            self.avisos.quitar(t.id)
        if vencidas:
            self._cambio_local()
            n = len(vencidas)
            self.avisos.mostrar_mensaje("↻ Reprogramadas", f"Pasé {n} tarea{'s' if n > 1 else ''} a mañana, "
                                        "a la misma hora.", [], COLORES["tranquilo"], 6, False)
            self.cara.celebrar()
        self.refrescar()
        return len(vencidas)

    # ======================================================== sincronización
    def _cambio_local(self):
        """Algo cambió aquí: se sube en unos segundos (si haces varios cambios seguidos, va todo junto)."""
        if self.nube:
            self.nube_pronto.start(2500)

    def sincronizar(self):
        if not self.nube or self.nube.ocupado or getattr(self, "_cerrado", False):
            return                                   # _cerrado: un temporizador que llega tras salir()
        desde = int(self.almacen.leer_ajuste("nube_cursor", "0") or 0)
        self.nube.sincronizar(desde, self.almacen.cambios_por_subir(), self._preferencias_para_subir(),
                              self._extra_para_subir())

    # ------------------------------------------------------- contexto del celular (v3.19)
    def contexto_celular(self) -> dict:
        """Lo que el celular necesita para calcular horas libres y sugerencias igual que aquí."""
        hoy = date.today()
        return contexto.armar(
            self.perfil, MINUTOS_PARA_ARRANCAR, self.almacen.horario(), self.almacen.excepciones(hoy),
            self.almacen.actividades_hechas(hoy - timedelta(days=13), hoy),
            {d: m for d, (_, m) in self.almacen.estudio_por_dia(hoy - timedelta(days=6), hoy).items()},
            self.almacen.momentos_a_evitar(hoy - timedelta(days=DIAS_QUE_RECUERDA_RECHAZOS), RECHAZOS_PARA_APRENDER),
            self.almacen.uuids_sugeridas(), self.almacen.leer_ajuste("ultima_sugerencia") or None,
            SUGERENCIAS_EN_CELULAR)

    def _extra_para_subir(self) -> dict | None:
        """El contexto (solo si cambió desde la última subida) y qué acciones del celular ya se aplicaron."""
        extra = {}
        c = self.contexto_celular()
        if contexto.huella(c) != self.almacen.leer_ajuste("contexto_subido"):
            extra["contexto"] = c
        aplicadas = self._acciones_aplicadas()
        if aplicadas:
            extra["acciones_ok"] = aplicadas
        return extra or None

    def _acciones_aplicadas(self) -> list[int]:
        try:
            return [int(x) for x in json.loads(self.almacen.leer_ajuste("acciones_aplicadas") or "[]")]
        except (ValueError, TypeError):
            return []

    def aplicar_acciones(self, acciones: list[dict]) -> int:
        """
        Lo que hiciste en el celular («ya fui al gimnasio», «mañana no trabajo», agendar una sugerencia).
        Cada acción se aplica una sola vez (se recuerda su id hasta que el servidor confirma que la borró).
        Devuelve cuántas se aplicaron ahora.
        """
        aplicadas = self._acciones_aplicadas()
        nuevas, avisos = 0, []
        for a in acciones:
            id_, tipo, d = a.get("id"), a.get("tipo"), a.get("datos") or {}
            if not isinstance(id_, int) or id_ in aplicadas:
                continue
            try:
                if tipo == "hecha":
                    if any(x.id == d["actividad_id"] for x in self.perfil.actividades):
                        self.almacen.marcar_actividad(d["actividad_id"], date.fromisoformat(d["dia"]))
                elif tipo == "excepcion":
                    e = contexto.excepcion_de_dict(d)
                    if not any((x.desde, x.hasta, x.filtro) == (e.desde, e.hasta, e.filtro)
                               for x in self.almacen.excepciones(e.desde)):
                        self.almacen.agregar_excepcion(e)
                        avisos.append(e.describir())
                elif tipo == "quitar_excepcion":
                    for x in self.almacen.excepciones(date(2000, 1, 1)):
                        if (x.desde.isoformat(), x.hasta.isoformat(), x.filtro) == (d["desde"], d["hasta"], d["filtro"]):
                            self.almacen.borrar_excepcion(x.id)
                            avisos.append(f"Quitado: {x.describir()}")
                elif tipo == "actividad":
                    a = contexto.actividad_de_dict({**d, "id": None})
                    if not any(clave(x.nombre) == clave(a.nombre) for x in self.perfil.actividades):
                        self.almacen.agregar_actividad(a)
                        self._recargar_perfil()
                        avisos.append(f"Actividad: {a.describir()}")
                elif tipo == "quitar_actividad":
                    quitada = next((x for x in self.perfil.actividades if x.id == d["id"]), None)
                    if quitada:
                        self.almacen.borrar_actividad(quitada.id)
                        self._recargar_perfil()
                        avisos.append(f"Quitada la actividad: {quitada.nombre}")
                elif tipo == "bloque":
                    b = contexto.bloque_de_dict({**d, "id": None})
                    if not any((x.dias, x.inicio, x.fin, x.titulo) == (b.dias, b.inicio, b.fin, b.titulo)
                               for x in self.almacen.horario()):
                        self.almacen.agregar_bloque(b)
                        avisos.append(f"Horario: {b.describir()}")
                elif tipo == "categoria_bloque":       # v3.23: cambiada desde el celular
                    bloque = next((x for x in self.almacen.horario() if x.id == d["id"]), None)
                    if bloque and bloque.categoria != d["categoria"] and self.almacen.cambiar_categoria(bloque.id, d["categoria"]):
                        avisos.append(f"Categoría: {bloque.titulo} → {NOMBRE_CATEGORIA[d['categoria']]}")
                elif tipo == "quitar_bloque":
                    quitado = next((x for x in self.almacen.horario() if x.id == d["id"]), None)
                    if quitado:
                        self.almacen.borrar_bloque(quitado.id)
                        avisos.append(f"Quitado del horario: {quitado.titulo}")
                elif tipo == "perfil":
                    self.almacen.guardar_perfil(hora.fromisoformat(d["despertar"]) if "despertar" in d else None,
                                                hora.fromisoformat(d["dormir"]) if "dormir" in d else None,
                                                d.get("meta_estudio"))
                    self._recargar_perfil()
                    avisos.append(f"Perfil: despiertas {self.perfil.despertar:%H:%M}, duermes {self.perfil.dormir:%H:%M}, "
                                  f"meta {duracion_minutos(self.perfil.meta_estudio)}")
                elif tipo == "sugerida":
                    local = self.almacen.id_por_uuid(d["tarea"])
                    if local is None:
                        continue                      # la tarea todavía no llegó: se aplica la próxima vez
                    self.almacen.marcar_tarea_sugerida(local, d.get("actividad_id"))
            except (KeyError, ValueError, TypeError):
                log.warning("acción del celular inválida: %s", a)
            aplicadas.append(id_)
            nuevas += 1
        self.almacen.guardar_ajuste("acciones_aplicadas", json.dumps(aplicadas[-500:]))
        if avisos:
            self.avisos.mostrar_mensaje("Desde el celular", "\n".join(f"• {x}" for x in avisos), [],
                                        COLORES["tranquilo"], 8, False)
        return nuevas

    def _preferencias_para_subir(self) -> dict | None:
        """Tus frases y lo aprendido, para el celular. Solo si cambiaron desde la última vez que se subieron."""
        prefs = {"frases": aprendizaje_frases(self.ruta_frases), "vocabulario": self.vocabulario}
        return None if _huella(prefs) == self.almacen.leer_ajuste("preferencias_subidas") else prefs

    def _al_sincronizar(self, r: Resultado):
        self._nube_lista = True                      # (aunque falle: sin internet, la laptop avisa igual)
        if not r.ok:
            self.estado_nube = (f"{r.error}", True)
            self.actualizar_estado()
            return
        if r.preferencias:
            self.almacen.guardar_ajuste("preferencias_subidas", _huella(r.preferencias))
        if r.extra and "contexto" in r.extra:
            self.almacen.guardar_ajuste("contexto_subido", contexto.huella(r.extra["contexto"]))
        if r.extra and r.extra.get("acciones_ok"):            # el servidor ya las borró: se pueden olvidar
            confirmadas = set(r.extra["acciones_ok"])
            self.almacen.guardar_ajuste("acciones_aplicadas", json.dumps(
                [x for x in self._acciones_aplicadas() if x not in confirmadas]))
        self.almacen.confirmar_subidas([(c["id"], c["actualizada"]) for c in r.subidos])
        for x in r.rechazados:
            log.warning("el servidor rechazó la tarea %s: %s", x.get("id"), x.get("error"))
        tocadas = self.almacen.aplicar_remotos(r.cambios)
        self.almacen.guardar_ajuste("nube_cursor", str(r.cursor))
        if self.aplicar_acciones(r.acciones):
            log.info("sincronización: %d acción(es) llegaron del celular", len(r.acciones))
            self.refrescar()
            self._cambio_local()                     # confirmar enseguida y subir el contexto nuevo
        for id_ in tocadas:                                  # completada o borrada en el celular: deja de sonar aquí
            t = self.almacen.obtener(id_)
            if not t or t.estado != "pendiente" or not t.fecha <= datetime.now():
                self.avisos.quitar(id_)
        self.estado_nube = (f"Sincronizado con el celular · {datetime.now():%H:%M}", False)
        if tocadas:
            log.info("sincronización: %d tarea(s) llegaron del celular", len(tocadas))
            self.refrescar()
            self.revisar()
        else:
            self.actualizar_estado()
        if len(r.subidos) >= LOTE_SINCRONIZACION or not r.completo:   # quedó más por subir o bajar
            QTimer.singleShot(500, self.sincronizar)

    # ================================================================ saludo
    def saludar(self, forzado: bool = False) -> bool:
        """
        El saludo del día. Sin 'forzado', solo una vez por día y cuando:
          - ya es más tarde que HORA_SALUDO,
          - estás frente a la laptop (tocaste teclado o mouse hace poco),
          - no hay un aviso de tarea ni una conversación en curso.
        Si algo de eso falla, se vuelve a intentar al minuto siguiente.
        """
        ahora = datetime.now()
        if not forzado:
            if not SALUDO_ACTIVO or not debe_saludar(ahora, self.almacen.leer_ajuste("ultimo_saludo"), HORA_SALUDO):
                return False
            if (self.avisos.cola or self.voz.dialogo or self.voz.escuchando_orden
                    or segundos_inactivo() > SEGUNDOS_PARA_ESTAR_PRESENTE):
                return False
        bloques = self.almacen.horario()
        if self.almacen.repasar_sugeridas(ahora.date())[1]:   # que el saludo no cuente como vencidas las de ayer
            self._cambio_local()
        plan = self.plan_del_dia(ahora.date(), ahora) if bloques else None
        s = armar_saludo(ahora, self.almacen.pendientes(), self.almacen.racha(ahora.date()), NOMBRE_USUARIO,
                         libres=self.horas_libres(ahora.date(), ahora) if bloques else None,
                         sugerencia=plan.sugerencias[0] if plan else None)
        self.almacen.guardar_ajuste("ultimo_saludo", ahora.date().isoformat())
        self._avisos_en_pausa_hasta = ahora + timedelta(seconds=SEGUNDOS_SALUDO)
        self.avisos.mostrar_mensaje(s.titulo, s.texto, [], COLORES["feliz"], SEGUNDOS_SALUDO, False)
        if SALUDO_HABLADO:
            self.voz.decir(s.hablado)
        self.cara.celebrar()
        log.info("saludo del día%s", " (pedido)" if forzado else "")
        return True

    # ================================================================ perfil
    def _responder(self, cabecera: str, texto: str, hablado: str | None, por_voz: bool, segundos: int = 8):
        self.avisos.mostrar_mensaje(cabecera, texto, [], COLORES["tranquilo"], segundos, False)
        if por_voz:
            self.voz.decir(hablado or texto)

    def _recargar_perfil(self):
        self.perfil = self.almacen.perfil(self._perfil_defecto)
        self.refrescar()

    def guardar_perfil(self, despertar: hora | None = None, dormir: hora | None = None, meta: int | None = None):
        self.almacen.guardar_perfil(despertar, dormir, meta)
        self._recargar_perfil()
        self._responder("Perfil", f"Guardado. Despiertas {self.perfil.despertar:%H:%M}, duermes "
                        f"{self.perfil.dormir:%H:%M}, meta de estudio {duracion_minutos(self.perfil.meta_estudio)}.",
                        None, False, 6)

    def agregar_actividad(self, texto: str, por_voz: bool = False) -> bool:
        a = interpretar_actividad(texto)
        if not isinstance(a, Actividad):
            self.avisos.mostrar_mensaje("Actividades", a, [], COLORES["pendiente"], 10, False)
            if por_voz:
                self.voz.decir("No entendí qué actividad. Dime, por ejemplo: gimnasio una hora tres veces por semana.")
            self.panel.actividad_anotada(False)
            return False
        self.almacen.agregar_actividad(a)
        self._responder("Anotado en tu perfil", a.describir(), f"Listo, anoté {a.nombre}.", por_voz)
        self.panel.actividad_anotada(True)
        self._recargar_perfil()
        return True

    def borrar_actividad(self, id_: int):
        self.almacen.borrar_actividad(id_)
        self._recargar_perfil()

    def decir_perfil(self, por_voz: bool = False):
        texto, hablado = describir_perfil(self.perfil, self.almacen.horario())
        self._responder("Lo que sé de ti", texto, hablado, por_voz, SEGUNDOS_MENSAJE)
        if not por_voz:
            self.panel.ver_perfil()

    def _comando_perfil(self, c: Comando, por_voz: bool):
        accion, texto = c.accion, c.texto or ""
        if accion == "perfil":
            self.decir_perfil(por_voz)
        elif accion in ("despertar", "dormir"):
            h = leer_hora(texto, accion)
            if h is None:
                self._responder("Perfil", "No entendí la hora. Por ejemplo: «me despierto a las 6:30».", None, por_voz)
                return
            self.almacen.guardar_perfil(**{"despertar" if accion == "despertar" else "dormir": h})
            self._recargar_perfil()
            verbo = "te despiertas" if accion == "despertar" else "te duermes"
            self._responder("Perfil", f"Anotado: {verbo} a las {h:%H:%M}.", f"Listo, {verbo} a las {h:%H:%M}.", por_voz)
        elif accion == "meta_estudio":
            d = leer_duracion(normalizar(texto))
            numero = re.search(r"\d+", texto)
            meta = d[0] if d else int(numero.group()) if numero else None
            if not meta:
                self._responder("Meta de estudio", "No entendí. Por ejemplo: «meta de estudio 120 minutos».",
                                None, por_voz)
                return
            self.almacen.guardar_perfil(meta_estudio=meta)
            self._recargar_perfil()
            self._responder("Meta de estudio", f"Tu meta diaria ahora es {duracion_minutos(self.perfil.meta_estudio)}.",
                            f"Listo, tu meta es {hablar_duracion(self.perfil.meta_estudio)} al día.", por_voz)
        elif accion == "actividad":
            self.agregar_actividad(texto, por_voz)
        elif accion == "actividades":
            acts = self.perfil.actividades
            lista = "\n".join(f"• {a.describir()}" for a in acts) or "Todavía no me dijiste qué te gusta hacer."
            self._responder("Tus actividades", lista, ("Tus actividades: " + ", ".join(a.nombre for a in acts) + "."
                                                       if acts else None), por_voz, SEGUNDOS_MENSAJE)
        elif accion == "borrar_actividad":
            buscado = normalizar(texto).strip()
            borradas = [a for a in self.perfil.actividades if buscado and buscado in normalizar(a.nombre)]
            for a in borradas:
                self.almacen.borrar_actividad(a.id)
            self._recargar_perfil()
            self._responder("Actividades", "Quité: " + ", ".join(a.nombre for a in borradas) + "." if borradas
                            else f"No encontré «{texto}» en tus actividades.", None, por_voz)
        elif accion == "traslado":
            lugar, d = normalizar(texto).strip(), leer_duracion(normalizar(c.destino or ""))
            bloques = [b for b in self.almacen.horario() if lugar and lugar in normalizar(b.titulo)]
            if not d or not bloques:
                motivo = ("No entendí cuánto tardas. Por ejemplo: «al trabajo tardo 45 minutos»." if not d
                          else f"No tengo «{texto}» en tu horario. Anótalo primero: «horario: …».")
                self._responder("Traslado", motivo, None, por_voz)
                return
            for b in bloques:
                self.almacen.cambiar_traslado(b.id, d[0])
            self.refrescar()
            self._responder("Traslado", f"Anotado: {duracion_minutos(d[0])} para llegar a {bloques[0].titulo} "
                            "(y otro tanto para volver). Ya lo resto de tus horas libres.",
                            "Listo, lo resto de tus horas libres.", por_voz)

    # =============================================================== horario
    def horas_libres(self, dia: date, ahora: datetime | None = None, minimo: int = 30) -> list[tuple[datetime, datetime]]:
        """
        Tus horas libres de ese día (si es hoy, desde ahora): tu horario fijo, sin lo que liberan tus
        excepciones ("el 1 de noviembre no trabajo") y menos tus tareas/eventos con duración ("examen de 8 a 10").
        """
        return huecos(dia, self.almacen.horario(), self.perfil.despertar, self.perfil.dormir, ahora or datetime.now(),
                      minimo, excepciones=self.almacen.excepciones(dia), extras=self._ocupaciones(dia))

    def _ocupaciones(self, dia: date) -> list[tuple[datetime, datetime, str]]:
        """Tareas y eventos pendientes de ese día que tienen duración: [(inicio, fin, título)]."""
        return [(t.fecha, t.fin, t.titulo) for t in self.almacen.pendientes()
                if t.duracion and t.fecha.date() == dia]

    def bloque_que_choca(self, fecha: datetime, duracion: int | None, tipo: str = "tarea") -> Bloque | None:
        """
        El bloque de tu horario que se cruza con eso ese día (respetando tus excepciones), o None.
        Solo cuenta lo que ocupa tiempo: algo con duración o un evento. "Llamar al banco a las 10" (una tarea
        de un momento) no avisa: se puede hacer en el trabajo.
        """
        if not (duracion or tipo == "evento"):
            return None
        return choque(fecha, duracion, self.almacen.horario(), self.almacen.excepciones(fecha.date()))

    def texto_choque(self, fecha: datetime, duracion: int | None, tipo: str = "tarea") -> str | None:
        """Para la vista previa del panel: "Trabajo (08:30–17:30)" o None."""
        b = self.bloque_que_choca(fecha, duracion, tipo)
        return f"{b.titulo} ({b.inicio:%H:%M}–{b.fin:%H:%M})" if b else None

    def _avisar_si_choca(self, t):
        """Después de anotar o editar: si se cruza con tu horario, te lo dice (no lo impide)."""
        if not t or t.estado != "pendiente":
            return
        b = self.bloque_que_choca(t.fecha, t.duracion, t.tipo)
        if b:
            self.avisos.mostrar_mensaje(
                "Se cruza con tu horario",
                f"«{t.titulo}» se cruza con {b.titulo} ({b.inicio:%H:%M}–{b.fin:%H:%M}).\nSi ese día no vas, dime "
                f"«el {t.fecha.day} no voy a {b.titulo.lower()}» y lo quito de tus horas ocupadas.",
                [], COLORES["pendiente"], 12, False)

    # ------------------------------------------------------- calendario (v3.20)
    def _mostrar_calendario(self):
        """La pestaña: marcas del mes a la vista y la agenda (con sugerencias) del día elegido."""
        ahora = datetime.now()
        dia = self.panel.dia_calendario()
        anio, mes = self.panel.mes_calendario()
        primero = date(anio, mes, 1)
        desde, hasta = primero - timedelta(days=7), (primero + timedelta(days=38))
        pendientes = self.almacen.pendientes()
        marcas = marcas_del_mes(desde, hasta, pendientes, self.almacen.excepciones(desde))
        dias = (dia - ahora.date()).days
        titulo = ({0: "Hoy", 1: "Mañana", -1: "Ayer"}.get(dias)
                  or f"{['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo'][dia.weekday()]} "
                     f"{dia.day:02d}/{dia.month:02d}")
        libres = self.horas_libres(dia, ahora) if self.almacen.horario() else []
        agenda = agenda_del_dia(dia, self.almacen.horario(), self.almacen.excepciones(dia), pendientes, libres,
                                self.almacen.ids_sugeridas())
        plan = self.plan_del_dia(dia, ahora) if dias >= 0 else Plan([], [])
        self.panel.mostrar_calendario(marcas, titulo, agenda, plan.sugerencias, plan.sin_lugar)
        if self.panel.modo_semana:                   # v3.21: las 7 columnas de la semana del día elegido
            lunes = dia - timedelta(days=dia.weekday())
            semana = []
            for i in range(7):
                d = lunes + timedelta(days=i)
                libres_d = self.horas_libres(d, datetime.combine(d, hora(0))) if self.almacen.horario() else []
                semana.append((d, agenda_del_dia(d, self.almacen.horario(), self.almacen.excepciones(d), pendientes,
                                                 libres_d, self.almacen.ids_sugeridas())))
            self.panel.mostrar_semana_cal(semana, self.perfil.despertar, self.perfil.dormir, ahora.date())

    def _agendar_dia(self, dia: date):
        self._ultimo_plan = self.plan_del_dia(dia)
        self.agendar_plan()

    def _mostrar_horario(self):
        ahora = datetime.now()
        self.panel.mostrar_horario(self.almacen.horario(), describir_libre(self.horas_libres(ahora.date(), ahora)),
                                   describir_libre(self.horas_libres(ahora.date() + timedelta(days=1), ahora)),
                                   self.almacen.excepciones(ahora.date()),
                                   self.plan_del_dia(ahora.date(), ahora).sugerencias,
                                   self._aprendido())

    def _aprendido(self) -> list[tuple[str, str]]:
        """[(clave, momento)] de lo que ya no te sugiero, ordenado."""
        hoy = date.today()
        evitar = self.almacen.momentos_a_evitar(hoy - timedelta(days=DIAS_QUE_RECUERDA_RECHAZOS),
                                                RECHAZOS_PARA_APRENDER)
        orden = list(NOMBRE_MOMENTO)
        return sorted(((n, m) for n, ms in evitar.items() for m in ms), key=lambda x: (x[0], orden.index(x[1])))

    def olvidar_aprendido(self, nombre: str, momento: str):
        """✕ en «NO TE SUGIERO»: vuelve a sugerirte eso en ese momento del día."""
        self.almacen.olvidar_rechazo(nombre, momento)
        self.refrescar()

    def agregar_bloque(self, texto: str, por_voz: bool = False) -> bool:
        """
        "de lunes a viernes de 9am a 6pm trabajo" -> un bloque fijo. Devuelve si se anotó.
        En el mismo campo del panel también se puede escribir una excepción: "el 1 de noviembre no trabajo".
        """
        c = interpretar_comando(texto)
        if c and c.accion == "excepcion":
            ok = self.agregar_excepcion(c.texto or texto, por_voz)
            self.panel.bloque_anotado(ok)
            return ok
        b = interpretar_bloque(texto)
        if not isinstance(b, Bloque):                  # no se entendió: b es la explicación
            self.avisos.mostrar_mensaje("Horario", b, [], COLORES["pendiente"], 10, False)
            if por_voz:
                self.voz.decir("No entendí los días o las horas. Prueba de nuevo, por ejemplo: "
                               "de lunes a viernes de 9 a 6 trabajo.")
            self.panel.bloque_anotado(False)
            return False
        self.almacen.agregar_bloque(heredar_categoria(b, self.almacen.horario()))       # v3.23
        self.avisos.mostrar_mensaje("Anotado en tu horario", b.describir(), [], COLORES["tranquilo"], 8, False)
        if por_voz:
            self.voz.decir(f"Listo, anoté {b.titulo} en tu horario.")
        self.panel.bloque_anotado(True)
        self.refrescar()
        return True

    def borrar_bloque(self, id_: int):
        self.almacen.borrar_bloque(id_)
        self.refrescar()

    def cambiar_categoria_bloque(self, id_: int, categoria: str):
        """El selector Trabajo · Clase · Otro de la pestaña Horario (v3.22): cambia el color y la categoría del bloque."""
        if self.almacen.cambiar_categoria(id_, categoria):
            self.refrescar()

    def categoria_por_nombre(self, nombre: str, categoria: str, por_voz: bool = False):
        """«computación gráfica es clase» (v3.24): pone esa categoría a todos los bloques con ese nombre."""
        bloques = buscar_por_nombre(nombre, self.almacen.horario())
        for b in bloques:
            self.almacen.cambiar_categoria(b.id, categoria)
        if bloques:
            nombres = list(dict.fromkeys(b.titulo for b in bloques))
            cuantos = f" ({len(bloques)} bloques)" if len(bloques) > 1 else ""
            texto = f"{', '.join(nombres)}{cuantos}: ahora es {NOMBRE_CATEGORIA[categoria].lower()}."
        else:
            texto = f"No encontré «{nombre}» en tu horario. Revisa cómo se llama en la pestaña Horario."
        self._responder("Horario", texto, texto, por_voz)
        self.refrescar()

    def borrar_bloques_por_nombre(self, nombre: str, por_voz: bool = False):
        buscado = normalizar(nombre).strip()
        borrados = [b for b in self.almacen.horario() if buscado and buscado in normalizar(b.titulo)]
        for b in borrados:
            self.almacen.borrar_bloque(b.id)
        texto = ("Quité de tu horario: " + ", ".join(b.titulo for b in borrados) + "." if borrados
                 else f"No encontré «{nombre}» en tu horario. Míralo en el panel, pestaña Horario.")
        self.avisos.mostrar_mensaje("Horario", texto, [], COLORES["tranquilo"], 8, False)
        if por_voz:
            self.voz.decir(texto)
        self.refrescar()

    # ----------------------------------------------------------- excepciones (v3.14)
    def agregar_excepcion(self, texto: str, por_voz: bool = False) -> bool:
        """"el 1 de noviembre no trabajo" / "vacaciones del 20 al 30 de diciembre". Devuelve si se anotó."""
        hoy = date.today()
        e = interpretar_excepcion(texto, hoy)
        bloques = self.almacen.horario()
        if isinstance(e, Excepcion) and e.filtro and bloques and not any(coincide(e.filtro, b.titulo) for b in bloques):
            e = (f"No encontré nada parecido a «{e.titulo.split()[-1]}» en tu horario. Revisa cómo lo llamaste "
                 "en la pestaña Horario, o di «el … tengo libre» para liberar todo el día.")
        if not isinstance(e, Excepcion):
            self._responder("Día libre", e, "No entendí la fecha. " + e.split(". ")[0] + ".", por_voz)
            return False
        e = self.almacen.agregar_excepcion(e)
        afectados = sorted({b.titulo for b in bloques if coincide(e.filtro, b.titulo)})
        que = ("todo tu horario" if not e.filtro else ", ".join(afectados) or "esos bloques")
        dias = "ese día" if e.desde == e.hasta else "esos días"
        self._responder("Anotado", f"{e.describir()}\nNo cuento {que} {dias}: tendrás más horas libres.",
                        f"Listo, {dias} no cuento {que}.", por_voz)
        self.refrescar()
        return True

    def decir_excepciones(self, por_voz: bool = False):
        lista = self.almacen.excepciones(date.today())
        if lista:
            texto = "\n".join(f"• {e.describir()}" for e in lista)
            hablado = "Tus días libres: " + "; ".join(e.titulo for e in lista[:5]) + "."
        else:
            texto = ("No tienes días libres ni excepciones anotadas. Di, por ejemplo, «el 1 de noviembre no trabajo» "
                     "o «vacaciones del 20 al 30 de diciembre».")
            hablado = "No tienes días libres anotados."
        self._responder("Días libres", texto, hablado, por_voz)
        if not por_voz:
            self.panel.ver_horario()

    def borrar_excepcion(self, id_: int):
        self.almacen.borrar_excepcion(id_)
        self.refrescar()

    # ========================================================== sugerencias (v3.15)
    def plan_del_dia(self, dia: date, ahora: datetime | None = None) -> Plan:
        """
        Qué te conviene hacer ese día en tus horas libres (si es hoy, desde ahora).
        - Nada en los primeros MINUTOS_PARA_ARRANCAR después de despertar.
        - Lo que ya agendaste ese día («Gimnasio» o «Estudiar» como tarea) cuenta como planificado:
          no se vuelve a sugerir (y su tiempo ya está restado de tus horas libres).
        - Lo que rechazaste seguido en un momento del día, ahí no se sugiere.
        """
        ahora = ahora or datetime.now()
        hechas = self.almacen.actividades_hechas(lunes_de(dia), dia)
        arranque = datetime.combine(dia, self.perfil.despertar) + timedelta(minutes=MINUTOS_PARA_ARRANCAR)
        libres = [(max(a, arranque), b) for a, b in self.horas_libres(dia, ahora)]
        libres = [(a, b) for a, b in libres if b - a >= timedelta(minutes=15)]
        del_dia = [t for t in self.almacen.pendientes() if t.fecha.date() == dia]
        planificadas = {a.id for t in del_dia for a in self._actividades_que_nombra(t.titulo)}
        estudio_agendado = sum(t.duracion or 0 for t in del_dia if "estudi" in normalizar(t.titulo))
        estudio = (self.almacen.resumen_dia(dia)[1] if dia == ahora.date() else 0) + estudio_agendado
        evitar = self.almacen.momentos_a_evitar(dia - timedelta(days=DIAS_QUE_RECUERDA_RECHAZOS),
                                                RECHAZOS_PARA_APRENDER)
        return recomendar(dia, libres, self.perfil.actividades, {i: len(d) for i, d in hechas.items()},
                          {i for i, d in hechas.items() if dia in d} | planificadas, estudio, self.perfil.meta_estudio,
                          evitar=evitar)

    def sugerir(self, cuando: str | None = None, por_voz: bool = False):
        """«¿Qué hago hoy?» / «recomiéndame algo para mañana»."""
        ahora = datetime.now()
        manana = cuando == "manana"
        dia = ahora.date() + timedelta(days=1 if manana else 0)
        palabra = "mañana" if manana else "hoy"
        if not self.almacen.horario() and not self.perfil.actividades:
            self._responder("Sugerencias", "Para sugerirte algo necesito conocerte un poco: anota tu horario "
                            "(pestaña Horario) y lo que te gusta hacer (pestaña Perfil, por ejemplo «actividad: "
                            "gimnasio 1 hora 3 veces por semana en la tarde»).",
                            "Primero cuéntame tu horario y qué te gusta hacer.", por_voz, 12)
            return
        plan = self.plan_del_dia(dia, ahora)
        self._ultimo_plan = plan
        texto, hablado = describir_plan(plan, palabra)
        if not self.perfil.actividades:
            texto += "\nTip: agrega tus actividades en Perfil y también te las sugiero."
        botones = [("Agendar", "agendar_plan"), ("Cerrar", "cerrar")] if plan else []
        self.avisos.mostrar_mensaje(f"Para {palabra}", texto, botones, COLORES["tranquilo"], SEGUNDOS_MENSAJE, False)
        if por_voz:
            self.voz.decir(hablado + (" Si quieres, dime «agéndalo»." if plan else ""))

    def agendar_plan(self, por_voz: bool = False):
        """
        «Agendar» / «agéndalo»: el último plan que te mostré pasa a ser tareas con su hora y duración
        (te aviso a esa hora; al completarlas cuentan para tu meta). Si no te mostré ninguno, el de hoy.
        """
        ahora = datetime.now()
        plan = getattr(self, "_ultimo_plan", None)
        if plan is None:                              # ojo: un Plan vacío es "falso", por eso 'is None'
            plan = self.plan_del_dia(ahora.date(), ahora)
        self._ultimo_plan = None
        pendientes = self.almacen.pendientes()
        agendadas = []
        for s in plan.sugerencias:
            inicio = s.inicio
            if inicio <= ahora:                       # "ya mismo": desde el próximo múltiplo de 5 min
                inicio = (ahora + timedelta(minutes=5 - ahora.minute % 5)).replace(second=0, microsecond=0)
            if any(t.fecha.date() == inicio.date() and normalizar(t.titulo) == normalizar(s.nombre) for t in pendientes):
                continue                              # ya estaba agendada
            minutos_ = int((s.fin - s.inicio).total_seconds() // 60)
            t = self.almacen.agregar(s.nombre, inicio, None, "tarea", None, minutos_)
            self.almacen.marcar_tarea_sugerida(t.id, s.actividad_id)     # si no se hace, mañana se descarta
            agendadas.append(f"{inicio:%H:%M} {s.nombre} ({duracion_minutos(minutos_)})")
        if agendadas:
            self._cambio_local()
            self.cara.celebrar()
            self._responder("Agendado", "\n".join(f"• {x}" for x in agendadas) + "\nTe aviso a cada hora. "
                            "Si alguna no la haces, mañana la quito sola (no queda vencida).",
                            f"Listo, agendé {len(agendadas)} {'cosa' if len(agendadas) == 1 else 'cosas'}.", por_voz)
        else:
            self._responder("Agendar", "No hay nada nuevo que agendar.", None, por_voz)
        self.refrescar()

    def aceptar_sugerencia(self):
        """«✓ Lo hago» en el aviso de hueco libre: estudiar abre el modo estudio; una actividad cuenta como hecha."""
        s: Sugerencia | None = getattr(self, "_sugerencia_ofrecida", None)
        self._sugerencia_ofrecida = None
        if s is None:
            return
        if s.clase == "estudio":
            self.estudio.iniciar()
            return
        hoy = date.today()
        if s.actividad_id is not None:
            self.almacen.marcar_actividad(s.actividad_id, hoy)
        else:
            for a in self._actividades_que_nombra(s.nombre):
                self.almacen.marcar_actividad(a.id, hoy)
        self.cara.celebrar()
        self.refrescar()
        self.avisos.mostrar_mensaje("¡Vamos!", f"Cuento {s.nombre} como hecho hoy. Si al final no puedes, "
                                    "desmárcalo en Perfil («✓ hoy»).", [], COLORES["feliz"], 10, False)

    def rechazar_sugerencia(self):
        """«Ahora no»: se anota. Si lo rechazas seguido en ese momento del día, dejo de sugerirlo ahí."""
        s: Sugerencia | None = getattr(self, "_sugerencia_ofrecida", None)
        self._sugerencia_ofrecida = None
        if s is None:
            return
        hoy, momento = s.inicio.date(), momento_de(s.inicio)
        self.almacen.rechazar_sugerencia(clave(s.nombre), hoy, momento)
        evitar = self.almacen.momentos_a_evitar(hoy - timedelta(days=DIAS_QUE_RECUERDA_RECHAZOS),
                                                RECHAZOS_PARA_APRENDER)
        if momento in evitar.get(clave(s.nombre), set()):
            self._responder("Aprendido", f"Ya no te sugiero {s.nombre.lower()} en {NOMBRE_MOMENTO[momento]} "
                            f"(por {DIAS_QUE_RECUERDA_RECHAZOS // 7} semanas). Si cambias de idea, di "
                            "«vuelve a sugerirme todo».", None, False, 12)

    def olvidar_rechazos(self, por_voz: bool = False):
        n = self.almacen.olvidar_rechazos()
        self._responder("Sugerencias", "Listo, olvidé lo que rechazaste: vuelvo a sugerirte todo." if n
                        else "No había nada rechazado.", None, por_voz)

    def _sugerir_al_quedar_libre(self, ahora: datetime):
        """
        Al empezar un hueco libre (saliste del trabajo, terminó una clase) te propone lo que toca.
        Una sola vez por hueco, solo si estás frente a la laptop y no está pasando otra cosa.
        No cuenta el hueco de cuando te despiertas (para eso está el saludo).
        Si pulsaste «Más tarde», lo vuelve a proponer pasado MINUTOS_MAS_TARDE (si estás libre)
        o al empezar tu próximo hueco, lo que llegue primero (v3.17).
        """
        if not SUGERENCIAS_AL_QUEDAR_LIBRE or not self.almacen.horario():
            return
        if (self.estudio.activo or self.voz.dialogo or self.voz.escuchando_orden or self.avisos.cola
                or segundos_inactivo() > SEGUNDOS_PARA_ESTAR_PRESENTE):
            return
        dia = ahora.date()
        despertar = datetime.combine(dia, self.perfil.despertar)
        inicio = next((a for a, b in huecos(dia, self.almacen.horario(), self.perfil.despertar, self.perfil.dormir,
                                            None, excepciones=self.almacen.excepciones(dia),
                                            extras=self._ocupaciones(dia))
                       if a > despertar and a <= ahora < a + timedelta(minutes=MINUTOS_PARA_SUGERIR)), None)
        nuevo_hueco = inicio is not None and self.almacen.leer_ajuste("ultima_sugerencia") != f"{inicio:%Y-%m-%d %H:%M}"
        pospuesta = self._sugerencia_pospuesta(dia)
        libre_ahora = any(a <= ahora < b for a, b in self.horas_libres(dia, ahora, minimo=1))
        toca_pospuesta = pospuesta is not None and pospuesta[0] <= ahora and libre_ahora
        if pospuesta is not None and pospuesta[2] and not toca_pospuesta:
            pospuesta = None                         # «a las 8» es a las 8: un hueco anterior no lo adelanta
        if not (nuevo_hueco or toca_pospuesta):
            return
        if nuevo_hueco:
            self.almacen.guardar_ajuste("ultima_sugerencia", f"{inicio:%Y-%m-%d %H:%M}")
        plan = self.plan_del_dia(dia, ahora)
        primera = None
        if pospuesta is not None:
            self.almacen.guardar_ajuste("sugerencia_pospuesta", "")
            primera = (next((s for s in plan.sugerencias if clave(s.nombre) == pospuesta[1]), None)
                       or self._sugerencia_de(pospuesta[1], ahora))
        if primera is None:
            primera = plan.sugerencias[0] if plan else None
            if primera is None or primera.inicio > ahora + timedelta(minutes=30):
                return                               # nada que hacer ya mismo: no molesta
        libre_hasta = next((b for a, b in self.horas_libres(dia, ahora, minimo=1) if a <= primera.inicio < b),
                           primera.fin)
        que = primera.nombre.lower() if primera.clase == "estudio" else primera.nombre
        if primera.inicio <= ahora + timedelta(minutes=5):
            pregunta, hablada = f"Estás libre hasta las {libre_hasta:%H:%M}. ¿Qué tal {que}?", \
                f"Estás libre hasta {hora_hablada(libre_hasta)}. ¿Qué tal {que}?"
        else:
            pregunta, hablada = f"¿{que[:1].upper() + que[1:]} a las {primera.inicio:%H:%M}?", \
                f"¿{que} {hora_hablada(primera.inicio)}?"
        resto = [s for s in plan.sugerencias if s is not primera]
        texto = f"{pregunta} ({primera.motivo})" + (f"\nDespués: {resto[0].describir()}" if resto else "")
        self._sugerencia_ofrecida = primera
        self.avisos.mostrar_mensaje("Tienes un hueco libre", texto,
                                    [("✓ Lo hago", "sugerencia_si"), ("Más tarde", "sugerencia_luego"),
                                     ("Ahora no", "sugerencia_no")], COLORES["tranquilo"], 60, False)
        if not self.silencio and HABLAR_RECORDATORIOS:
            self.voz.decir(hablada)
        log.info("sugerencia al quedar libre: %s%s", primera.nombre, " (pospuesta)" if pospuesta else "")
        self._cambio_local()                         # sube 'hueco_avisado': el celular no repite este aviso

    def _sugerencia_pospuesta(self, dia: date) -> tuple[datetime, str, bool] | None:
        """
        (desde cuándo, clave del nombre, hora fija) de lo que dejaste para más tarde hoy; None si no hay.
        Hora fija = lo pediste «a las 8»: no se adelanta aunque empiece antes otro hueco.
        """
        valor = self.almacen.leer_ajuste("sugerencia_pospuesta") or ""
        cuando, _, resto = valor.partition("|")
        nombre, _, fija = resto.partition("|")
        try:
            desde = datetime.strptime(cuando, "%Y-%m-%d %H:%M")
        except ValueError:
            return None
        return (desde, nombre, fija == "fija") if desde.date() == dia and nombre else None

    def _sugerencia_de(self, nombre: str, ahora: datetime) -> Sugerencia | None:
        """Una sugerencia "a mano" para lo que dejaste para más tarde, aunque el plan de ahora no la traiga."""
        if nombre == clave("Estudiar"):
            falta = max(self.perfil.meta_estudio - self.almacen.resumen_dia(ahora.date())[1], 25)
            return Sugerencia("Estudiar", ahora, ahora + timedelta(minutes=min(falta, 100)),
                              "lo dejaste para esta hora", "estudio")
        a = next((a for a in self.perfil.actividades if clave(a.nombre) == nombre), None)
        return (Sugerencia(a.nombre, ahora, ahora + timedelta(minutes=a.minutos), "lo dejaste para esta hora",
                           "actividad", a.id) if a else None)

    def _ofrecida_vigente(self) -> Sugerencia | None:
        """La última sugerencia que te ofrecí, si es de hoy."""
        s: Sugerencia | None = getattr(self, "_sugerencia_ofrecida", None)
        return s if s is not None and s.inicio.date() == date.today() else None

    def posponer_sugerencia(self, ahora: datetime | None = None):
        """«Más tarde»: no es un rechazo; te lo vuelvo a proponer luego."""
        s = self._ofrecida_vigente()
        self._sugerencia_ofrecida = None
        if s is None:
            return
        cuando = (ahora or datetime.now()).replace(second=0, microsecond=0) + timedelta(minutes=MINUTOS_MAS_TARDE)
        self.almacen.guardar_ajuste("sugerencia_pospuesta", f"{cuando:%Y-%m-%d %H:%M}|{clave(s.nombre)}")
        self._responder("Más tarde", f"Te vuelvo a proponer {s.nombre.lower() if s.clase == 'estudio' else s.nombre} "
                        f"desde las {cuando:%H:%M} si estás libre, o al empezar tu próximo hueco. "
                        "También puedes decirme «más tarde, a las 8».", None, False)

    def posponer_hasta(self, texto: str, por_voz: bool = False, ahora: datetime | None = None):
        """«Más tarde, a las 8»: lo que te ofrecí (o lo que ya habías dejado para luego) a esa hora exacta."""
        ahora = ahora or datetime.now()
        s = self._ofrecida_vigente()
        pospuesta = self._sugerencia_pospuesta(ahora.date())
        nombre = clave(s.nombre) if s else (pospuesta[1] if pospuesta else None)
        if nombre is None:
            self._responder("Más tarde", "No tengo ninguna sugerencia pendiente. Pregúntame «¿qué hago?».",
                            None, por_voz)
            return
        cuando = proxima_hora(texto, ahora)
        if cuando is None:
            self._responder("Más tarde", "No entendí la hora o ya pasó. Prueba: «más tarde, a las 8».", None, por_voz)
            return
        self._sugerencia_ofrecida = None
        self.avisos.ocultar_mensaje()
        self.almacen.guardar_ajuste("sugerencia_pospuesta", f"{cuando:%Y-%m-%d %H:%M}|{nombre}|fija")
        que = "estudiar" if nombre == clave("Estudiar") else nombre[:1].upper() + nombre[1:]
        self._responder("Anotado", f"Te propongo {que} a las {cuando:%H:%M} (si a esa hora estás libre).",
                        f"Listo, te lo propongo {hora_hablada(cuando)}.", por_voz)

    def _actividades_que_nombra(self, texto: str) -> list[Actividad]:
        """Las actividades de tu perfil que aparecen en el texto: «fui al gimnasio» -> Gimnasio."""
        palabras = [raiz(p) for p in normalizar(texto).split() if len(p) >= 4]
        return [a for a in self.perfil.actividades if any(coincide(p, a.nombre) for p in palabras)]

    def actividad_hecha(self, texto: str, por_voz: bool = False):
        """«Ya fui al gimnasio» / «hice yoga»: cuenta para tu meta de la semana."""
        hoy = date.today()
        encontradas = self._actividades_que_nombra(texto)
        if not encontradas:
            self._responder("Actividades", f"«{texto}» no está en tus actividades. Si quieres que lo cuente, "
                            "agrégala en la pestaña Perfil (por ejemplo «actividad: yoga 1 hora 2 veces por semana»).",
                            "Eso no está en tus actividades. Agrégalo en tu perfil.", por_voz, 10)
            return
        for a in encontradas:
            self.almacen.marcar_actividad(a.id, hoy)
        hechas = self.almacen.actividades_hechas(lunes_de(hoy), hoy)
        lineas = []
        for a in encontradas:
            n = len(hechas.get(a.id, []))
            lineas.append(f"{a.nombre}: {n} de {a.veces_semana} esta semana" + (", meta cumplida" if n >= a.veces_semana else "")
                          if a.veces_semana else f"{a.nombre}: anotado hoy")
        self.cara.celebrar()
        self._responder("¡Bien!", "\n".join(lineas), "¡Bien! " + ". ".join(lineas) + ".", por_voz)
        self.refrescar()

    def alternar_actividad_hoy(self, id_: int):
        """El botón ✓ de la pestaña Perfil: marca o desmarca que la hiciste hoy."""
        hoy = date.today()
        if not self.almacen.marcar_actividad(id_, hoy):
            self.almacen.marcar_actividad(id_, hoy, False)
        self.refrescar()

    def decir_horario(self, por_voz: bool = False):
        bloques = self.almacen.horario()
        if not bloques:
            texto = ("Todavía no anotaste tu horario. Escribe, por ejemplo: «horario: de lunes a viernes "
                     "de 9am a 6pm trabajo».")
            hablado = "Todavía no anotaste tu horario."
        else:
            texto = "\n".join(f"• {b.describir()}" for b in bloques)
            hablado = "Tu horario: " + "; ".join(b.titulo for b in bloques[:5]) + "."
        self.avisos.mostrar_mensaje("Tu horario", texto, [], COLORES["tranquilo"], SEGUNDOS_MENSAJE, False)
        if por_voz:
            self.voz.decir(hablado)
        else:
            self.panel.ver_horario()

    def decir_libre(self, manana: bool = False, por_voz: bool = False):
        ahora = datetime.now()
        dia = ahora.date() + timedelta(days=1 if manana else 0)
        cuando = "mañana" if manana else "hoy"
        if not self.almacen.horario():
            texto = ("Para saber cuándo estás libre, primero anota tu horario: «horario: de lunes a viernes "
                     "de 9am a 6pm trabajo».")
            self.avisos.mostrar_mensaje("Tiempo libre", texto, [], COLORES["tranquilo"], 10, False)
            if por_voz:
                self.voz.decir("Primero anota tu horario, así sé cuándo estás ocupado.")
            return
        libres = self.horas_libres(dia, ahora)
        if libres:
            texto = "\n".join(f"• {x}" for x in describir_libre(libres).split(" · ")) + f"\nEn total: {total_libre(libres)}."
            a, b = libres[0]
            hablado = (f"{cuando.capitalize()} tienes {hablar_duracion(minutos(libres))} libre. "
                       f"{'El próximo hueco' if not manana else 'El primero'} empieza {hora_hablada(a)} "
                       f"y dura {hablar_duracion(minutos([(a, b)]))}.")
        else:
            texto = hablado = f"{cuando.capitalize()} no te queda tiempo libre en tu horario."
        self.avisos.mostrar_mensaje(f"Libre {cuando}", texto, [], COLORES["tranquilo"], SEGUNDOS_MENSAJE, False)
        if por_voz:
            self.voz.decir(hablado)

    # ================================================================ frases
    def puede_decir_frase(self) -> bool:
        """Solo si está "libre": sin avisos, sin modo estudio, sin burbuja a la vista, sin conversación."""
        return (FRASES_ACTIVAS and self.cara.isVisible() and not self.avisos.cola and not self.estudio.activo
                and self.burbuja.tipo is None and not self.voz.dialogo and not self.voz.escuchando_orden)

    def decir_frase(self, pedida: bool = False, por_voz: bool = False) -> bool:
        """
        Al dejar el mouse sobre la cara (pedida=False): como mucho una cada SEGUNDOS_ENTRE_FRASES.
        Si la pides ("dime una frase", "motívame"), siempre. Devuelve True si dijo una.
        """
        ahora = time.monotonic()
        if not pedida:
            if not self.puede_decir_frase():
                return False
            if self._ultima_frase is not None and ahora - self._ultima_frase < SEGUNDOS_ENTRE_FRASES:
                return False
        self._leer_frases_si_cambiaron()
        frase = self.bolsa_frases.sacar()
        if not frase:
            return False
        self._ultima_frase = ahora
        self.avisos.mostrar_mensaje(f"{NOMBRE_ASISTENTE}", frase, [], COLORES["feliz"], SEGUNDOS_FRASE, False)
        if FRASES_HABLADAS or por_voz:
            self.voz.decir(frase)                    # en modo silencio, decir() no suena
        return True

    def aprender_correccion(self, titulo: str, detectado: str, elegido: str):
        """Corregiste Tarea/Evento en el panel: se anota y, si se repite, se aprende (nucleo/aprendizaje.py)."""
        if not aprendizaje.registrar_correccion(self.aprendizaje, titulo, detectado, elegido):
            return
        self.almacen.guardar_ajuste("aprendizaje", aprendizaje.guardar(self.aprendizaje))
        nuevo = aprendizaje.vocabulario(self.aprendizaje)
        if nuevo != self.vocabulario:
            log.info("aprendí de tus correcciones: %s", nuevo)
            self.vocabulario = nuevo
            usar_vocabulario(nuevo)
            self._cambio_local()                     # que el celular también lo sepa

    def guardar_frase(self, frase: str, por_voz: bool = False):
        try:
            nueva = guardar_frase_usuario(self.ruta_frases, frase)
        except OSError:
            log.exception("no se pudo guardar la frase")
            self.avisos.mostrar_mensaje("Frases", "No pude guardar la frase (¿frases.txt está abierto?).",
                                        [], COLORES["alerta"], 8, False)
            return
        texto = (f"Guardada: «{frase.strip()}». Te la diré de vez en cuando." if nueva
                 else "Esa frase ya la tenía.")
        self.avisos.mostrar_mensaje("Frases", texto, [], COLORES["feliz"], 8, False)
        if por_voz:
            self.voz.decir("Listo, guardé tu frase." if nueva else "Esa frase ya la tenía.")
        if nueva:
            self.cara.celebrar()

    def _leer_frases_si_cambiaron(self):
        """frases.txt se vuelve a leer solo si lo editaste (así puedes cambiarlo sin cerrar Lancelot)."""
        try:
            modificado = self.ruta_frases.stat().st_mtime_ns
        except OSError:
            modificado = None
        if modificado != self._frases_leidas:
            self._frases_leidas = modificado
            self.bolsa_frases.cambiar_frases(REFLEXIONES + leer_frases_usuario(self.ruta_frases))

    # ======================================================= actualizaciones
    @property
    def busca_actualizaciones(self) -> bool:
        return bool(REPO_ACTUALIZACIONES) and (EMPAQUETADO or BUSCAR_ACTUALIZACIONES_EN_DESARROLLO)

    def buscar_actualizaciones(self):
        """La búsqueda que pides tú ("busca actualizaciones"): siempre responde algo."""
        if not REPO_ACTUALIZACIONES:
            self.avisos.mostrar_mensaje("Versión " + VERSION, "Para buscar versiones nuevas, escribe tu repositorio "
                                        "en config.py (REPO_ACTUALIZACIONES).", [], COLORES["tranquilo"], 8, False)
            return
        self.avisos.mostrar_mensaje("Actualizaciones", f"Tengo la versión {VERSION}. Buscando una más nueva…",
                                    [], COLORES["tranquilo"], 6, False)
        self.actualizador.buscar(manual=True)

    def _al_encontrar_actualizacion(self, act: Actualizacion, manual: bool):
        ya_ofrecida = self._actualizacion and self._actualizacion.version == act.version
        omitida = self.almacen.leer_ajuste("version_omitida") == act.version
        if not manual and (ya_ofrecida or omitida):
            return                                   # no insistir con la misma versión
        if not manual and (self.estudio.activo or self.burbuja.tipo == "tarea"):
            return                                   # no interrumpir: se vuelve a ofrecer en la próxima búsqueda
        self._actualizacion = act
        peso = f" · {act.tamano / 1024 ** 2:.0f} MB" if act.tamano else ""
        novedades = resumen_notas(act.notas)
        self.avisos.mostrar_mensaje(f"{NOMBRE_ASISTENTE} {act.version} disponible{peso}",
                                    novedades or "Hay una versión nueva.",
                                    [("Actualizar", "actualizar"), ("Ahora no", "cerrar"),
                                     ("Omitir", "omitir_version")], COLORES["feliz"], 45, False)
        if manual:
            self.voz.decir(f"Hay una versión nueva: la {act.version}.")

    def _al_no_haber_actualizacion(self, texto: str, manual: bool):
        if manual:                                   # las búsquedas automáticas no molestan
            self.avisos.mostrar_mensaje("Actualizaciones", texto, [], COLORES["tranquilo"], 8, False)
            self.voz.decir(texto)

    def actualizar_ahora(self):
        act = self._actualizacion
        if not act:
            return
        if not EMPAQUETADO:                          # en desarrollo se actualiza con git pull
            from voz import web
            web.abrir_url(act.url_pagina)
            self.avisos.mostrar_mensaje("Modo desarrollo", "Con python main.py se actualiza con «git pull». "
                                        "Te abrí la página de la versión.", [], COLORES["tranquilo"], 8, False)
            return
        self.avisos.mostrar_mensaje("⬇ Descargando", f"Bajando {NOMBRE_ASISTENTE} {act.version}. "
                                    "Te aviso cuando esté listo; puedes seguir usándome.", [], COLORES["tranquilo"], 8, False)
        self.actualizador.descargar(act)

    def omitir_actualizacion(self):
        if self._actualizacion:
            self.almacen.guardar_ajuste("version_omitida", self._actualizacion.version)

    def _al_descargar_actualizacion(self, ruta: str):
        """Descargado y verificado: Lancelot se cierra y el instalador lo vuelve a abrir actualizado."""
        version = self._actualizacion.version if self._actualizacion else ""
        self.avisos.mostrar_mensaje("Instalando", f"Me cierro unos segundos para instalar la {version} "
                                    "y vuelvo solo. Tus tareas no se tocan.", [], COLORES["feliz"], 5, False)
        self.voz.decir("Me actualizo y vuelvo en un momento.")
        log.info("instalando actualización %s", version)

        def instalar_y_salir():
            self.actualizador.instalar(ruta)
            self.salir()
        QTimer.singleShot(4000, instalar_y_salir)    # tiempo para leer el mensaje (y oírlo)

    # ================================================================ semana
    def resumen_de_semana(self, semanas_atras: int = 0) -> ResumenSemana:
        """Los 7 días que terminan hoy (o N semanas antes), con la sesión en curso incluida."""
        ahora = datetime.now()
        hoy = ahora.date()
        fin = hoy - timedelta(weeks=semanas_atras)
        datos = self.almacen.estudio_por_dia(fin - timedelta(days=13), fin)   # + 7 días para comparar
        if self.estudio.activo and semanas_atras == 0:
            pomos, mins = datos.get(hoy, (0, 0))
            p = self.estudio.pomodoro
            datos[hoy] = (pomos + p.completados, mins + p.minutos_enfocados(ahora))
        return resumen_semana(datos, fin, self.perfil.meta_estudio)

    def mostrar_semana(self, semanas_atras: int = 0):
        self.panel.mostrar_semana(self.resumen_de_semana(semanas_atras), date.today())
        self.panel.mostrar_actividades_semana(self.resumen_actividades(semanas_atras))

    def resumen_actividades(self, semanas_atras: int = 0) -> str:
        """'Actividades: Gimnasio 2 de 3 · Leer 5 de 7 · Correr 0' (los mismos 7 días del gráfico)."""
        if not self.perfil.actividades:
            return ""
        fin = date.today() - timedelta(weeks=semanas_atras)
        hechas = self.almacen.actividades_hechas(fin - timedelta(days=6), fin)
        partes = []
        for a in self.perfil.actividades:
            n = len(hechas.get(a.id, []))
            partes.append(f"{a.nombre} {n} de {a.veces_semana}" + (" (meta cumplida)" if n >= a.veces_semana else "")
                          if a.veces_semana else f"{a.nombre} {n}")
        return "Actividades: " + " · ".join(partes) + "".join(f"\n{x}" for x in self.comentario_agendadas(fin))

    def comentario_agendadas(self, fin: date | None = None) -> list[str]:
        """
        Comentario honesto si agendas algo desde las sugerencias y casi nunca lo haces (2+ veces sin hacer
        en esos 7 días y menos hechas que descartadas). No es un reproche: es una pista para ajustar.
        """
        fin = fin or date.today()
        salida = []
        for nombre, (hechas, descartadas) in self.almacen.balance_sugeridas(fin - timedelta(days=6), fin).items():
            if descartadas >= 2 and hechas < descartadas:
                total = hechas + descartadas
                salida.append(f"Agendaste {nombre} {total} veces y lo hiciste {hechas}. Quizá esa hora no te sirve: "
                              "dime «Ahora no» cuando no te convenga (aprendo el momento) o baja la meta en Perfil.")
        return salida

    def respaldar(self):
        try:
            creado = hacer_respaldo(self.ruta_bd, CARPETA_RESPALDOS if self.ruta_bd == RUTA_BD
                                    else self.ruta_bd.parent / "respaldos", date.today(), RESPALDOS_A_CONSERVAR)
            if creado:
                log.info("respaldo creado: %s", creado.name)
        except Exception:
            log.exception("no se pudo crear el respaldo")

    # ============================================================== comandos
    def ejecutar_comando(self, c: Comando, por_voz: bool = False):
        """Punto único para todo comando, venga del panel, del menú o de la voz."""
        log.info("comando: %s%s", c.accion, " (voz)" if por_voz else "")
        if self.voz.ejecutar(c):                     # abrir, buscar, hora, agenda, apodos, escucha
            self.refrescar()
            return
        accion = c.accion
        mensaje = self.avisos.mostrar_mensaje
        if accion == "estudio":
            self.estudio.iniciar(c.minutos)
        elif accion in ("pausa", "seguir", "terminar"):
            if not self.estudio.activo:
                mensaje("Modo estudio", "No hay una sesión activa. Escribe «modo estudio».",
                        [], COLORES["estudio"], 6, False)
            else:
                {"pausa": self.estudio.pausar, "seguir": self.estudio.seguir,
                 "terminar": self.estudio.terminar}[accion]()
        elif accion == "silencio":
            self._poner_silencio(True)
            mensaje(f"{NOMBRES_MODO['silencio']}", "Sin sonidos ni notificaciones. Los avisos siguen apareciendo aquí.",
                    [], COLORES["dormido"], 6, False)
        elif accion == "sin_silencio":
            self._poner_silencio(False)
            mensaje("Sonido activado", "Vuelvo a sonar con los avisos.", [], COLORES["tranquilo"], 5, False)
        elif accion == "normal":
            self._poner_silencio(False)
            if self.estudio.activo:
                self.estudio.terminar()
            else:
                mensaje(NOMBRES_MODO["normal"], "De vuelta al modo normal.", [], COLORES["tranquilo"], 5, False)
        elif accion == "actualizacion":
            self.buscar_actualizaciones()
        elif accion == "saludo":
            self.saludar(forzado=True)
        elif accion in ("perfil", "despertar", "dormir", "meta_estudio", "actividad", "actividades",
                        "borrar_actividad", "traslado"):
            self._comando_perfil(c, por_voz)
        elif accion == "horario_agregar":
            self.agregar_bloque(c.texto or "", por_voz)
        elif accion == "horario_borrar":
            self.borrar_bloques_por_nombre(c.texto or "", por_voz)
        elif accion == "categoria":
            self.categoria_por_nombre(c.texto or "", c.destino or "otro", por_voz)
        elif accion == "horario_ver":
            self.decir_horario(por_voz)
        elif accion == "sugerir":
            self.sugerir(c.texto, por_voz)
        elif accion == "actividad_hecha":
            self.actividad_hecha(c.texto or "", por_voz)
        elif accion == "posponer_hasta":
            self.posponer_hasta(c.texto or "", por_voz)
        elif accion == "agendar_plan":
            self.agendar_plan(por_voz)
        elif accion == "olvidar_rechazos":
            self.olvidar_rechazos(por_voz)
        elif accion == "excepcion":
            self.agregar_excepcion(c.texto or "", por_voz)
        elif accion == "excepciones":
            self.decir_excepciones(por_voz)
        elif accion == "libre":
            self.decir_libre(c.texto == "manana", por_voz)
        elif accion == "frase":
            self.decir_frase(pedida=True, por_voz=por_voz)
        elif accion == "guardar_frase":
            self.guardar_frase(c.texto or "", por_voz)
        elif accion == "semana":
            texto, hablado = describir_semana(self.resumen_de_semana())
            comentarios = self.comentario_agendadas()
            if comentarios:
                texto += "\n" + "\n".join(comentarios)
                hablado += " Ojo: hay cosas que agendas y casi nunca haces. Te dejé el detalle en pantalla."
            mensaje("Tu semana", texto, [], COLORES["estudio"], SEGUNDOS_MENSAJE, False)
            if por_voz:
                self.voz.decir(hablado)
            else:
                self.panel.ver_estudio()
        elif accion == "vencidas_manana":
            n = self.reprogramar_vencidas()
            if not n:
                mensaje("Vencidas", "No tienes tareas vencidas.", [], COLORES["tranquilo"], 5, False)
            if por_voz:
                self.voz.decir(f"Listo, pasé {n} a mañana." if n else "No tienes tareas vencidas.")
        elif accion == "resumen":
            texto = self.estudio.resumen_hoy(datetime.now())
            mensaje("Tu día", texto, [], COLORES["estudio"], SEGUNDOS_MENSAJE, False)
            if por_voz:
                self.voz.decir(texto.replace("Hoy:", "Hoy llevas").replace("pomodoro(s)", "pomodoros")
                               .replace(" · ", ", ").replace(" h ", " horas ").replace(" min", " minutos"))
        if por_voz:
            if accion in _CONFIRMACION_VOZ:
                self.voz.decir(_CONFIRMACION_VOZ[accion])
            elif accion == "estudio":
                self.voz.decir(f"Modo estudio. Bloques de {self.estudio.pomodoro.minutos_enfoque} minutos. Vamos.")
            elif accion == "terminar" and not self.estudio.activo:
                self.voz.decir("Sesión terminada. Buen trabajo.")
        self.refrescar()

    def _poner_silencio(self, activo: bool):
        self.silencio = activo
        self.cara.silencio = activo
        self.almacen.guardar_ajuste("silencio", "1" if activo else "0")

    # ================================================================ estado
    def refrescar(self):
        """Actualización completa (incluye la lista de tareas y, si está a la vista, el gráfico)."""
        self.actualizar_estado()
        self.panel.mostrar_tareas(self.almacen.pendientes(), self.almacen.ids_sugeridas())
        self._mostrar_horario()
        if self.panel.viendo_calendario:
            self._mostrar_calendario()
        hoy = date.today()
        hechas = self.almacen.actividades_hechas(lunes_de(hoy), hoy)
        self.panel.mostrar_perfil(self.perfil, {i: len(d) for i, d in hechas.items()},
                                  {i for i, d in hechas.items() if hoy in d})
        if self.panel.viendo_estudio:
            self.mostrar_semana(self.panel.semanas_atras)

    def actualizar_estado(self):
        """Actualización liviana: cara y modos. El modo estudio la llama cada segundo."""
        ahora = datetime.now()
        pendientes = self.almacen.pendientes()
        self.cara.contador = sum(1 for t in pendientes if t.fecha.date() == ahora.date())

        if self.voz.escuchando_orden:                     # te está escuchando: lo más importante
            estado, progreso, texto = "escuchando", None, None
        elif self.avisos.cola:                            # una tarea vencida manda
            estado, progreso, texto = "alerta", None, None
        elif self.estudio.activo:
            estado, progreso, texto = self.estudio.estado_cara(ahora)
        else:
            estado = estado_del_dia([t.fecha for t in pendientes], False, ahora, self.perfil.dormir.hour,
                                    self.perfil.despertar.hour)
            progreso, texto = None, None
        self.cara.set_estado(estado)
        self.cara.progreso, self.cara.texto = progreso, texto
        self.avisos.cerrar_si_caduco()

        proxima = next((t for t in pendientes if t.fecha >= ahora), None)
        tip = (f"Próxima: {proxima.titulo} ({describir_fecha(proxima.fecha, ahora)})"
               if proxima else "Sin tareas próximas")
        if self.estudio.activo:
            tip = self.estudio.descripcion(ahora) + "\n" + tip
        self.cara.setToolTip(tip)
        self.bandeja.setToolTip(f"{NOMBRE_ASISTENTE} · {tip}")

        if self.panel.isVisible():
            p = self.estudio.pomodoro
            self.panel.mostrar_modos(self.estudio.activo, self.silencio,
                                     self.estudio.descripcion(ahora) if p else "",
                                     bool(p and p.pausado), self.voz.escucha_activa)
            self.panel.mostrar_voz(self.voz.estado)
            self.panel.mostrar_nube(*self.estado_nube)
            self.panel.mostrar_hoy(self.estudio.resumen_hoy(ahora))

    # ============================================================== ventanas
    def _alternar_panel(self):
        if self.panel.isVisible() and self.panel.isActiveWindow():
            self.panel.hide()
        else:
            self.abrir_panel()

    def abrir_panel(self):
        self.panel.abrir()
        self.actualizar_estado()
        if self.panel.viendo_estudio:                # el gráfico pudo quedar viejo mientras estaba oculto
            self.mostrar_semana(self.panel.semanas_atras)

    def _alternar_cara(self):
        if self.cara.isVisible():
            self.cara.hide()
            self.burbuja.hide()
        else:
            self.cara.show()
            self.avisos.mostrar_siguiente()

    def _al_mover_cara(self, pos: QPoint):
        self.almacen.guardar_ajuste("cara_pos", f"{pos.x()},{pos.y()}")
        if self.burbuja.isVisible():
            self.burbuja.reposicionar(self.cara.frameGeometry())

    def _colocar_cara(self):
        guardada = self.almacen.leer_ajuste("cara_pos")
        if guardada:
            x, y = map(int, guardada.split(","))
            # Solo si esa posición sigue existiendo (p. ej. desconectaste un monitor)
            if QGuiApplication.screenAt(QPoint(x + 20, y + 20)):
                self.cara.move(x, y)
                return
        area = QGuiApplication.primaryScreen().availableGeometry()
        self.cara.move(area.right() - self.cara.width() - 30, area.bottom() - self.cara.height() - 30)

    def _al_activar_bandeja(self, motivo):
        if motivo == QSystemTrayIcon.Trigger:        # clic izquierdo en el ícono
            self.abrir_panel()

    # ================================================================= menús
    def _menu_cara(self, pos: QPoint):
        self._ultimo_menu = QMenu()                  # se guarda para que no se libere al mostrarse
        self._llenar_menu(self._ultimo_menu)
        self._ultimo_menu.exec(pos)

    def _llenar_menu(self, menu: QMenu):
        """El menú se arma cada vez que se abre, así siempre refleja el estado actual."""
        menu.clear()
        comando = lambda accion: (lambda: self.ejecutar_comando(Comando(accion)))   # noqa: E731
        opciones = [("Mis tareas", self.abrir_panel), None]
        if self.estudio.activo:
            p = self.estudio.pomodoro
            opciones += [("Seguir" if p.pausado else "Pausar", comando("seguir" if p.pausado else "pausa")),
                         ("Terminar estudio", comando("terminar"))]
        else:
            opciones.append((f"{NOMBRES_MODO['estudio']}", comando("estudio")))
        escucha = self.voz.escucha_activa
        opciones += [
            ("Quitar silencio" if self.silencio else f"{NOMBRES_MODO['silencio']}",
             comando("sin_silencio" if self.silencio else "silencio")),
            ("Resumen de hoy", comando("resumen")),
            ("Mi semana", self.panel.ver_estudio),
            None,
            ("Dejar de escuchar" if escucha else f"Escuchar «{NOMBRE_ASISTENTE}»",
             lambda: self.voz.poner_escucha(not escucha)),
            (f"Hablarle ahora ({ATAJO_HABLAR})", lambda: self.voz.oido.escuchar_una_orden()),
            None,
            ("Mostrar / ocultar cara", self._alternar_cara),
            ("Carpeta de datos", self._abrir_carpeta_datos),
            *([("Sincronizar ahora", self.sincronizar)] if self.nube else []),
            (f"Buscar actualizaciones (v{VERSION})", self.buscar_actualizaciones),
            ("Salir", self.salir),
        ]
        for opcion in opciones:
            if opcion is None:
                menu.addSeparator()
                continue
            accion = QAction(opcion[0], menu)
            accion.triggered.connect(opcion[1])
            menu.addAction(accion)

    def _abrir_carpeta_datos(self):
        """Tareas, respaldos, registro y voces. Con el .exe vive en %LOCALAPPDATA%\\Lancelot."""
        carpeta = self.ruta_bd.parent
        if sys.platform == "win32":
            os.startfile(carpeta)
        else:
            log.info("carpeta de datos: %s", carpeta)

    def salir(self):
        self._cerrado = True
        if self.estudio.activo:
            self.estudio.terminar()                  # guarda la sesión antes de cerrar
        self.voz.detener()
        for reloj in self.findChildren(QTimer):      # ninguno debe dispararse después, con la base ya cerrada
            reloj.stop()
        self.bandeja.hide()
        log.info("Lancelot cerrado")
        self.app.quit()


def aprendizaje_frases(ruta) -> list[str]:
    """Tus frases de frases.txt (como mucho 300) para subirlas al celular."""
    return leer_frases_usuario(ruta)[:300]


def _huella(preferencias: dict) -> str:
    """Para saber si las preferencias cambiaron desde la última vez que se subieron."""
    return hashlib.sha1(json.dumps(preferencias, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def proxima_hora(texto: str, ahora: datetime) -> datetime | None:
    """
    «8» o «8:30» -> la próxima vez que sean las 8 hoy (si ya pasaron las 8 de la mañana, las 8 de la noche).
    Con am/pm o «de la noche» se respeta. None si no se entiende o si esa hora de hoy ya pasó.
    """
    h = leer_hora(texto, "despertar")
    if h is None:
        return None
    cuando = datetime.combine(ahora.date(), h)
    explicita = re.search(r"\b(am|pm|a\.m\.|p\.m\.|manana|tarde|noche)\b", normalizar(texto))
    if cuando <= ahora and not explicita and h.hour < 12:
        cuando += timedelta(hours=12)
    return cuando if cuando > ahora else None
