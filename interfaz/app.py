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
import sys
import time
from datetime import date, datetime, timedelta

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
                    FRASES_HABLADAS, HORA_AVISO_PREVIO)
from interfaz.actualizador import Actualizador
from interfaz.asistente_voz import ControladorVoz, NotificadorVoz
from interfaz.avisos import GestorAvisos, NotificadorCara
from interfaz.burbuja import Burbuja
from interfaz.cara import Cara, pixmap_cara
from interfaz.estudio import ModoEstudio
from interfaz.panel import Panel
from interfaz.sincronizador import Resultado, Sincronizador, leer_configuracion
from notificadores.base import Notificador
from notificadores.windows import NotificadorWindows
from nucleo import aprendizaje
from nucleo.almacen import LOTE_SINCRONIZACION, SIN_CAMBIO, Almacen
from nucleo.comandos import Comando
from nucleo.estadisticas import ResumenSemana, describir_semana, resumen_semana
from nucleo.frases import (REFLEXIONES, BolsaFrases, crear_archivo_frases, guardar_frase_usuario,
                           leer_frases_usuario)
from nucleo.hablado import hora_hablada
from nucleo.horario import (Bloque, describir_libre, hablar_duracion, huecos, interpretar_bloque, minutos,
                            total_libre)
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
        self.ruta_bd = ruta_bd or RUTA_BD               # las pruebas usan una base temporal
        self.almacen = Almacen(self.ruta_bd)
        self.almacen.reactivar_avisos_pendientes()
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
        self.panel.hora_aviso_previo = HORA_AVISO_PREVIO
        if self.nube:
            self.nube.terminado.connect(self._al_sincronizar)
        self.actualizador.encontrada.connect(self._al_encontrar_actualizacion)
        self.actualizador.sin_novedad.connect(self._al_no_haber_actualizacion)
        self.actualizador.descargada.connect(self._al_descargar_actualizacion)
        self.actualizador.fallo.connect(
            lambda texto: self.avisos.mostrar_mensaje("🔄 Actualización", texto, [], COLORES["alerta"], 10, False))

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
            self.estado_nube = ("☁ Conectando con el celular…", False)
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
        if vencidas or cerrados:
            self.refrescar()

    def _avisar_eventos_proximos(self, ahora: datetime):
        """
        Avisos anticipados ("📅 Aniversario · falta 1 semana"). Si estás estudiando o hablándole,
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
        cabecera = "📅 Se acerca" if len(tocan) == 1 else f"📅 Se acercan {len(tocan)} eventos"
        texto = lineas[0] if len(lineas) == 1 else "\n".join(f"• {l}" for l in lineas)
        self.avisos.mostrar_mensaje(cabecera, texto, [("Entendido", "cerrar")], COLORES["evento"], 0, False)
        if not self.silencio:
            self.notificador_windows.mensaje(cabecera, texto)
            if HABLAR_RECORDATORIOS:
                t = tocan[0][0]
                saludo = f"{NOMBRE_USUARIO}, " if NOMBRE_USUARIO else ""
                self.voz.decir(f"{saludo}se acerca {t.titulo}: {describir_faltan(t.fecha, ahora)}.")
        log.info("aviso anticipado de %d evento(s)", len(tocan))

    def agregar(self, titulo: str, fecha: datetime, repeticion, tipo: str = "tarea", anticipacion=None):
        self.almacen.agregar(titulo, fecha, repeticion, tipo, anticipacion)
        self._cambio_local()
        self.cara.celebrar()
        self.refrescar()

    def completar(self, tarea_id: int):
        self.almacen.completar(tarea_id)
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
               anticipacion=SIN_CAMBIO):
        self.almacen.editar(tarea_id, titulo, fecha, repeticion, tipo, anticipacion)
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
        if not self.nube or self.nube.ocupado:
            return
        desde = int(self.almacen.leer_ajuste("nube_cursor", "0") or 0)
        self.nube.sincronizar(desde, self.almacen.cambios_por_subir(), self._preferencias_para_subir())

    def _preferencias_para_subir(self) -> dict | None:
        """Tus frases y lo aprendido, para el celular. Solo si cambiaron desde la última vez que se subieron."""
        prefs = {"frases": aprendizaje_frases(self.ruta_frases), "vocabulario": self.vocabulario}
        return None if _huella(prefs) == self.almacen.leer_ajuste("preferencias_subidas") else prefs

    def _al_sincronizar(self, r: Resultado):
        self._nube_lista = True                      # (aunque falle: sin internet, la laptop avisa igual)
        if not r.ok:
            self.estado_nube = (f"☁ {r.error}", True)
            self.actualizar_estado()
            return
        if r.preferencias:
            self.almacen.guardar_ajuste("preferencias_subidas", _huella(r.preferencias))
        self.almacen.confirmar_subidas([(c["id"], c["actualizada"]) for c in r.subidos])
        for x in r.rechazados:
            log.warning("el servidor rechazó la tarea %s: %s", x.get("id"), x.get("error"))
        tocadas = self.almacen.aplicar_remotos(r.cambios)
        self.almacen.guardar_ajuste("nube_cursor", str(r.cursor))
        for id_ in tocadas:                                  # completada o borrada en el celular: deja de sonar aquí
            t = self.almacen.obtener(id_)
            if not t or t.estado != "pendiente" or not t.fecha <= datetime.now():
                self.avisos.quitar(id_)
        self.estado_nube = (f"☁ Sincronizado con el celular · {datetime.now():%H:%M}", False)
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
        s = armar_saludo(ahora, self.almacen.pendientes(), self.almacen.racha(ahora.date()), NOMBRE_USUARIO,
                         libres=self.horas_libres(ahora.date(), ahora) if bloques else None)
        self.almacen.guardar_ajuste("ultimo_saludo", ahora.date().isoformat())
        self._avisos_en_pausa_hasta = ahora + timedelta(seconds=SEGUNDOS_SALUDO)
        self.avisos.mostrar_mensaje(s.titulo, s.texto, [], COLORES["feliz"], SEGUNDOS_SALUDO, False)
        if SALUDO_HABLADO:
            self.voz.decir(s.hablado)
        self.cara.celebrar()
        log.info("saludo del día%s", " (pedido)" if forzado else "")
        return True

    # =============================================================== horario
    def horas_libres(self, dia: date, ahora: datetime | None = None) -> list[tuple[datetime, datetime]]:
        """Tus horas libres de ese día según tu horario fijo (si es hoy, desde ahora)."""
        return huecos(dia, self.almacen.horario(), HORA_DESPERTAR, HORA_DORMIR, ahora or datetime.now())

    def _mostrar_horario(self):
        ahora = datetime.now()
        self.panel.mostrar_horario(self.almacen.horario(), describir_libre(self.horas_libres(ahora.date(), ahora)),
                                   describir_libre(self.horas_libres(ahora.date() + timedelta(days=1), ahora)))

    def agregar_bloque(self, texto: str, por_voz: bool = False) -> bool:
        """"de lunes a viernes de 9am a 6pm trabajo" -> un bloque fijo. Devuelve si se anotó."""
        b = interpretar_bloque(texto)
        if not isinstance(b, Bloque):                  # no se entendió: b es la explicación
            self.avisos.mostrar_mensaje("🗓 Horario", b, [], COLORES["pendiente"], 10, False)
            if por_voz:
                self.voz.decir("No entendí los días o las horas. Prueba de nuevo, por ejemplo: "
                               "de lunes a viernes de 9 a 6 trabajo.")
            self.panel.bloque_anotado(False)
            return False
        self.almacen.agregar_bloque(b)
        self.avisos.mostrar_mensaje("🗓 Anotado en tu horario", b.describir(), [], COLORES["tranquilo"], 8, False)
        if por_voz:
            self.voz.decir(f"Listo, anoté {b.titulo} en tu horario.")
        self.panel.bloque_anotado(True)
        self.refrescar()
        return True

    def borrar_bloque(self, id_: int):
        self.almacen.borrar_bloque(id_)
        self.refrescar()

    def borrar_bloques_por_nombre(self, nombre: str, por_voz: bool = False):
        buscado = normalizar(nombre).strip()
        borrados = [b for b in self.almacen.horario() if buscado and buscado in normalizar(b.titulo)]
        for b in borrados:
            self.almacen.borrar_bloque(b.id)
        texto = ("Quité de tu horario: " + ", ".join(b.titulo for b in borrados) + "." if borrados
                 else f"No encontré «{nombre}» en tu horario. Míralo en el panel, pestaña 🗓 Horario.")
        self.avisos.mostrar_mensaje("🗓 Horario", texto, [], COLORES["tranquilo"], 8, False)
        if por_voz:
            self.voz.decir(texto.replace("🗓 ", ""))
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
        self.avisos.mostrar_mensaje("🗓 Tu horario", texto, [], COLORES["tranquilo"], SEGUNDOS_MENSAJE, False)
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
            self.avisos.mostrar_mensaje("🕒 Tiempo libre", texto, [], COLORES["tranquilo"], 10, False)
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
        self.avisos.mostrar_mensaje(f"🕒 Libre {cuando}", texto, [], COLORES["tranquilo"], SEGUNDOS_MENSAJE, False)
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
        self.avisos.mostrar_mensaje(f"💬 {NOMBRE_ASISTENTE}", frase, [], COLORES["feliz"], SEGUNDOS_FRASE, False)
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
            self.avisos.mostrar_mensaje("💬 Frases", "No pude guardar la frase (¿frases.txt está abierto?).",
                                        [], COLORES["alerta"], 8, False)
            return
        texto = (f"Guardada: «{frase.strip()}». Te la diré de vez en cuando." if nueva
                 else "Esa frase ya la tenía. 😉")
        self.avisos.mostrar_mensaje("💬 Frases", texto, [], COLORES["feliz"], 8, False)
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
            self.avisos.mostrar_mensaje("🔄 Versión " + VERSION, "Para buscar versiones nuevas, escribe tu repositorio "
                                        "en config.py (REPO_ACTUALIZACIONES).", [], COLORES["tranquilo"], 8, False)
            return
        self.avisos.mostrar_mensaje("🔄 Actualizaciones", f"Tengo la versión {VERSION}. Buscando una más nueva…",
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
        self.avisos.mostrar_mensaje(f"🎁 {NOMBRE_ASISTENTE} {act.version} disponible{peso}",
                                    novedades or "Hay una versión nueva.",
                                    [("Actualizar", "actualizar"), ("Ahora no", "cerrar"),
                                     ("Omitir", "omitir_version")], COLORES["feliz"], 45, False)
        if manual:
            self.voz.decir(f"Hay una versión nueva: la {act.version}.")

    def _al_no_haber_actualizacion(self, texto: str, manual: bool):
        if manual:                                   # las búsquedas automáticas no molestan
            self.avisos.mostrar_mensaje("🔄 Actualizaciones", texto, [], COLORES["tranquilo"], 8, False)
            self.voz.decir(texto)

    def actualizar_ahora(self):
        act = self._actualizacion
        if not act:
            return
        if not EMPAQUETADO:                          # en desarrollo se actualiza con git pull
            from voz import web
            web.abrir_url(act.url_pagina)
            self.avisos.mostrar_mensaje("🔄 Modo desarrollo", "Con python main.py se actualiza con «git pull». "
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
        self.avisos.mostrar_mensaje("🔄 Instalando", f"Me cierro unos segundos para instalar la {version} "
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
        return resumen_semana(datos, fin, META_ESTUDIO_DIARIO)

    def mostrar_semana(self, semanas_atras: int = 0):
        self.panel.mostrar_semana(self.resumen_de_semana(semanas_atras), date.today())

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
            mensaje(f"🔕 {NOMBRES_MODO['silencio']}", "Sin sonidos ni notificaciones. Los avisos siguen apareciendo aquí.",
                    [], COLORES["dormido"], 6, False)
        elif accion == "sin_silencio":
            self._poner_silencio(False)
            mensaje("🔔 Sonido activado", "Vuelvo a sonar con los avisos.", [], COLORES["tranquilo"], 5, False)
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
        elif accion == "horario_agregar":
            self.agregar_bloque(c.texto or "", por_voz)
        elif accion == "horario_borrar":
            self.borrar_bloques_por_nombre(c.texto or "", por_voz)
        elif accion == "horario_ver":
            self.decir_horario(por_voz)
        elif accion == "libre":
            self.decir_libre(c.texto == "manana", por_voz)
        elif accion == "frase":
            self.decir_frase(pedida=True, por_voz=por_voz)
        elif accion == "guardar_frase":
            self.guardar_frase(c.texto or "", por_voz)
        elif accion == "semana":
            texto, hablado = describir_semana(self.resumen_de_semana())
            mensaje("📊 Tu semana", texto, [], COLORES["estudio"], SEGUNDOS_MENSAJE, False)
            if por_voz:
                self.voz.decir(hablado)
            else:
                self.panel.ver_estudio()
        elif accion == "vencidas_manana":
            n = self.reprogramar_vencidas()
            if not n:
                mensaje("↻ Vencidas", "No tienes tareas vencidas. 👌", [], COLORES["tranquilo"], 5, False)
            if por_voz:
                self.voz.decir(f"Listo, pasé {n} a mañana." if n else "No tienes tareas vencidas.")
        elif accion == "resumen":
            texto = self.estudio.resumen_hoy(datetime.now())
            mensaje("📊 Tu día", texto, [], COLORES["estudio"], SEGUNDOS_MENSAJE, False)
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
        self.panel.mostrar_tareas(self.almacen.pendientes())
        self._mostrar_horario()
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
            estado = estado_del_dia([t.fecha for t in pendientes], False, ahora, HORA_DORMIR, HORA_DESPERTAR)
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
            opciones += [("▶ Seguir" if p.pausado else "⏸ Pausar", comando("seguir" if p.pausado else "pausa")),
                         ("⏹ Terminar estudio", comando("terminar"))]
        else:
            opciones.append((f"📚 {NOMBRES_MODO['estudio']}", comando("estudio")))
        escucha = self.voz.escucha_activa
        opciones += [
            ("🔔 Quitar silencio" if self.silencio else f"🔕 {NOMBRES_MODO['silencio']}",
             comando("sin_silencio" if self.silencio else "silencio")),
            ("📊 Resumen de hoy", comando("resumen")),
            ("📈 Mi semana", self.panel.ver_estudio),
            None,
            ("🎙 Dejar de escuchar" if escucha else f"🎙 Escuchar «{NOMBRE_ASISTENTE}»",
             lambda: self.voz.poner_escucha(not escucha)),
            (f"🗣 Hablarle ahora ({ATAJO_HABLAR})", lambda: self.voz.oido.escuchar_una_orden()),
            None,
            ("Mostrar / ocultar cara", self._alternar_cara),
            ("📁 Carpeta de datos", self._abrir_carpeta_datos),
            *([("☁ Sincronizar ahora", self.sincronizar)] if self.nube else []),
            (f"🔄 Buscar actualizaciones (v{VERSION})", self.buscar_actualizaciones),
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
        self.bandeja.hide()
        log.info("Lancelot cerrado")
        self.app.quit()


def aprendizaje_frases(ruta) -> list[str]:
    """Tus frases de frases.txt (como mucho 300) para subirlas al celular."""
    return leer_frases_usuario(ruta)[:300]


def _huella(preferencias: dict) -> str:
    """Para saber si las preferencias cambiaron desde la última vez que se subieron."""
    return hashlib.sha1(json.dumps(preferencias, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
