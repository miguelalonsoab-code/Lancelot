"""
Controlador de voz: todo lo que Lancelot oye, dice y hace por pedido hablado.

    oído (voz/oido.py) ──texto──► procesar_orden() ──► comando / tarea / diálogo
                                                      └─► responder(): burbuja + voz

También maneja las acciones "de asistente" que sirven igual escritas en el panel:
abrir apps y páginas, buscar, decir la hora o la agenda, y los apodos.
"""
from __future__ import annotations

import logging
import re
import threading
from datetime import datetime
from typing import TYPE_CHECKING

from config import (APPS_EXTRA, ATAJO_HABLAR, CARPETA_RECURSOS, CARPETA_VOCES, CARPETA_VOZ, COLORES, HABLAR_RECORDATORIOS,
                    MODELO_VOSK, NOMBRE_ASISTENTE, NOMBRE_USUARIO, PALABRAS_ACTIVACION,
                    SEGUNDOS_ESPERA_ORDEN, SITIOS_CONOCIDOS, URL_MODELO_VOSK, VOZ_MOTOR, VOZ_VELOCIDAD,
                    VOZ_WINDOWS_PREFERIDA)
from notificadores.base import Notificador
from nucleo.almacen import Tarea
from nucleo.comandos import Comando, interpretar_comando
from nucleo.dialogo import DialogoTarea, Paso
from nucleo.hablado import fecha_hablada, hora_hablada
from nucleo.interprete import describir_avisos, describir_faltan, describir_fecha, interpretar, normalizar
from nucleo.numeros import numeros_a_digitos
from voz.apps import CatalogoApps
from voz.atajo import AtajoTeclado
from voz.habla import Voz
from voz.oido import Oido
from voz import web

if TYPE_CHECKING:
    from interfaz.app import Asistente

log = logging.getLogger(__name__)

# Frases que, dichas por voz, indican que quieres crear una tarea
_PEDIDO_TAREA = re.compile(r"^(?:recuerdame|recordarme|recordar|avisame|anota|anotame|apunta|agrega|"
                           r"nueva tarea|tarea|nuevo evento|evento)\b")

# Acciones que resuelve este controlador (el resto las resuelve app.py)
ACCIONES_DE_VOZ = {"abrir", "abrir_web", "buscar", "hora", "agenda", "vencidas", "apodo", "olvidar_apodo",
                   "apodos", "escucha_on", "escucha_off"}


class NotificadorVoz(Notificador):
    """Dice el recordatorio en voz alta. Es 'ruidoso': en modo silencio se omite."""
    ruidoso = True

    def __init__(self, voz: "ControladorVoz"):
        self.voz = voz

    def notificar(self, tarea: Tarea) -> None:
        if HABLAR_RECORDATORIOS:
            saludo = f"{NOMBRE_USUARIO}, " if NOMBRE_USUARIO else ""
            self.voz.decir(f"{saludo}hoy es: {tarea.titulo}." if tarea.es_evento
                           else f"{saludo}es hora de: {tarea.titulo}.")


class ControladorVoz:
    def __init__(self, asistente: "Asistente"):
        self.a = asistente
        self.dialogo: DialogoTarea | None = None     # conversación a medias ("¿para cuándo?")
        self._escuchar_al_terminar = False           # abrir el micrófono cuando termine de hablar
        self.escuchando_orden = False                # True mientras espera lo que vas a decir
        self.escucha_activa = False                  # escucha continua ("Lancelot…") encendida
        self.estado = f"🎙 Pulsa {ATAJO_HABLAR} y habla, o activa la escucha para llamarme por mi nombre."

        # Apps: menú Inicio + Steam + escritorio (en segundo plano) + apodos guardados
        self.catalogo = CatalogoApps(APPS_EXTRA)
        for apodo, destino in asistente.almacen.apodos():
            self.catalogo.agregar_alias(apodo, destino)
        threading.Thread(target=self._cargar_apps, daemon=True, name="catalogo").start()

        recursos = CARPETA_RECURSOS                    # None con "python main.py"
        self.habla = Voz(VOZ_MOTOR, CARPETA_VOCES, VOZ_WINDOWS_PREFERIDA, VOZ_VELOCIDAD,
                         recursos / "voces" if recursos else None)
        self.oido = Oido(CARPETA_VOZ, MODELO_VOSK, URL_MODELO_VOSK, PALABRAS_ACTIVACION, SEGUNDOS_ESPERA_ORDEN,
                         recursos / "voz" if recursos else None)
        self.atajo = AtajoTeclado()

        self.habla.empezo.connect(self._al_empezar_a_hablar)
        self.habla.termino.connect(self._al_terminar_de_hablar)
        self.habla.estado.connect(lambda texto: log.info("voz: %s", texto))
        self.oido.orden.connect(self.procesar_orden)
        self.oido.llamado.connect(lambda: self.decir("¿Sí?"))
        self.oido.escuchando.connect(self._al_escuchar)
        self.oido.estado.connect(self._al_estado_oido)
        self.oido.oido.connect(lambda texto: log.debug("oído reconoció: %s", texto))
        self.atajo.pulsado.connect(self.oido.escuchar_una_orden)
        self.habla.iniciar()

    def _cargar_apps(self):
        n = self.catalogo.cargar_de_windows()
        log.info("catálogo de apps cargado: %d encontradas", n)

    # ================================================================ hablar
    def decir(self, texto: str):
        if not self.a.silencio:
            self.habla.decir(texto)

    def responder(self, texto_burbuja: str, texto_voz: str | None = None):
        self.a.avisos.mostrar_mensaje(f"🗣 {NOMBRE_ASISTENTE}", texto_burbuja, [], COLORES["escuchando"], 8, False)
        self.decir(texto_voz or texto_burbuja)

    # ======================================================= lo que dijiste
    def procesar_orden(self, texto: str):
        """Lo que dijiste (sin el nombre) pasa por el mismo camino que lo escrito."""
        log.debug("orden de voz: %s", texto)          # solo con NIVEL_REGISTRO = "DEBUG"
        if self.dialogo:                              # es la respuesta a una pregunta suya
            self._continuar_dialogo(self.dialogo.responder(texto))
            return
        texto = numeros_a_digitos(texto)
        if comando := interpretar_comando(texto):
            self.a.ejecutar_comando(comando, por_voz=True)
            return
        r = interpretar(texto)
        # "Lancelot, recuérdame…" o, sin pedirlo así, algo que claramente es un evento con fecha:
        # "Lancelot, el 15 de noviembre es mi aniversario"
        if _PEDIDO_TAREA.match(normalizar(texto)) or (r.tipo == "evento" and r.fecha and r.titulo):
            fecha = r.fecha if r.fecha and (r.fecha > datetime.now() or r.repeticion) else None
            self.dialogo = DialogoTarea(texto, r.titulo, fecha, r.repeticion, tipo=r.tipo,
                                        anticipacion=r.anticipacion)
            self._continuar_dialogo(self.dialogo.siguiente())   # crea ya, o pregunta lo que falta
            return
        self.responder(f"No entendí: «{texto}». Prueba con «abre…», «modo estudio» o «recuérdame…».",
                       "No te entendí. ¿Me lo repites?")

    def ejecutar(self, c: Comando) -> bool:
        """Resuelve las acciones de ACCIONES_DE_VOZ. Devuelve False si no le corresponde."""
        accion = c.accion
        if accion not in ACCIONES_DE_VOZ:
            return False
        if accion == "abrir":
            self._abrir_app(c.texto or "")
        elif accion == "abrir_web":
            self._abrir_web(c.texto or "", c.navegador)
        elif accion == "buscar":
            self._buscar_web(c.texto or "", c.destino or "google", c.navegador)
        elif accion == "hora":
            ahora = datetime.now()
            self.responder(f"Son las {ahora:%H:%M}.", f"Son {hora_hablada(ahora, con_articulo=False)}.")
        elif accion == "agenda":
            self._decir_agenda()
        elif accion == "vencidas":
            self._decir_vencidas()
        elif accion == "apodo":
            self._aprender_apodo(c.texto or "", c.destino or "")
        elif accion == "olvidar_apodo":
            self._olvidar_apodo(c.texto or "")
        elif accion == "apodos":
            self._decir_apodos()
        elif accion in ("escucha_on", "escucha_off"):
            self.poner_escucha(accion == "escucha_on")
        return True

    # ============================================================ diálogo
    def _continuar_dialogo(self, paso: Paso):
        """Hace lo que diga el diálogo: preguntar de nuevo, crear la tarea, cancelar o rendirse."""
        if paso.tipo == "preguntar":
            self.a.avisos.mostrar_mensaje(f"🗣 {NOMBRE_ASISTENTE}", paso.texto,
                                          [("Cancelar", "cancelar_dialogo")], COLORES["escuchando"], 0, False)
            self._escuchar_respuesta(paso.texto)
            return
        dialogo, self.dialogo = self.dialogo, None
        self.a.avisos.ocultar_mensaje()
        if paso.tipo == "crear":
            ahora = datetime.now()
            self.a.agregar(paso.titulo, paso.fecha, paso.repeticion, paso.clase, paso.avisos)
            if paso.clase == "evento":
                avisos = describir_avisos(paso.avisos).replace("avisa ", "")
                extra = f" Te aviso {avisos} y ese día." if avisos else ""
                self.responder(f"📅 Evento: «{paso.titulo}», {describir_fecha(paso.fecha, ahora)} "
                               f"({describir_faltan(paso.fecha, ahora)}).{extra}",
                               f"Listo, anoté el evento {paso.titulo}, {fecha_hablada(paso.fecha, ahora)}.{extra}")
            else:
                self.responder(f"Listo: «{paso.titulo}», {describir_fecha(paso.fecha, ahora)}.",
                               f"Listo. Te aviso {fecha_hablada(paso.fecha, ahora)}: {paso.titulo}.")
        elif paso.tipo == "cancelar":
            self.responder(paso.texto)
        elif paso.tipo == "rendirse":
            self.a.panel.abrir()
            self.a.panel.entrada.setText(dialogo.texto_original if dialogo else "")
            self.responder(paso.texto)

    def cancelar_dialogo(self):
        self._continuar_dialogo(Paso("cancelar", "Listo, no lo anoto."))

    def _escuchar_respuesta(self, pregunta: str):
        """Pregunta en voz alta y, cuando termina de hablar, abre el micrófono para la respuesta."""
        if self.a.silencio:                  # en silencio no habla: escucha de inmediato
            self.oido.escuchar_una_orden()
        else:
            self._escuchar_al_terminar = True
            self.habla.decir(pregunta)

    # ========================================================= apps y web
    def _abrir_app(self, nombre: str):
        app = self.catalogo.buscar(nombre)
        if not app and normalizar(nombre) in {normalizar(k) for k in SITIOS_CONOCIDOS}:
            self._abrir_web(nombre, None)          # "abre netflix" sin app instalada -> la página
            return
        if not app:
            self.responder(f"No encontré «{nombre}» en tu menú Inicio.",
                           f"No encontré {nombre}. Si es una página, agrégala en la configuración.")
            return
        try:
            self.catalogo.abrir(app)
            self.responder(f"Abriendo {app.nombre}…", f"Abriendo {app.nombre}.")
        except Exception as e:
            log.exception("no se pudo abrir %s", app.nombre)
            self.responder(f"No pude abrir {app.nombre}: {e}", f"No pude abrir {app.nombre}.")

    @staticmethod
    def _sitios() -> dict[str, str]:
        """Tus páginas de APPS_EXTRA tienen prioridad sobre las conocidas."""
        tuyas = {k: v for k, v in APPS_EXTRA.items() if v.startswith(("http://", "https://"))}
        return {**SITIOS_CONOCIDOS, **tuyas}

    def _abrir_web(self, sitio: str, navegador: str | None):
        nombre, url, conocido = web.resolver_sitio(sitio, self._sitios())
        if not conocido:
            log.info("página desconocida «%s»: se busca en Google (agrégala a SITIOS_CONOCIDOS)", sitio)
        self._abrir_en_navegador(url, navegador, nombre if conocido else f"la búsqueda de «{sitio}» en Google")

    def _buscar_web(self, consulta: str, buscador: str, navegador: str | None):
        self._abrir_en_navegador(web.url_busqueda(buscador, consulta), navegador,
                                 f"«{consulta}» en {buscador.title()}")

    def _abrir_en_navegador(self, url: str, navegador: str | None, que: str):
        exe = web.navegador_exe(navegador)
        en = f" en {web.NOMBRE_NAVEGADOR[exe]}" if exe else ""
        try:
            pedido_ok = web.abrir_url(url, exe)
            if exe and not pedido_ok:
                self.responder(f"No encontré {navegador}; abrí {que} en tu navegador predeterminado.")
            else:
                self.responder(f"Abriendo {que}{en}…", f"Abriendo {que}{en}.")
        except Exception as e:
            log.exception("no se pudo abrir %s", url)
            self.responder(f"No pude abrir {que}: {e}", f"No pude abrir {que}.")

    # ============================================================ apodos
    def _aprender_apodo(self, apodo: str, destino: str):
        """
        "cuando diga el código abre visual studio code"
        Primero se comprueba que la app exista: el reconocedor de voz se equivoca,
        y no queremos guardar apodos que apunten a nada.
        """
        apodo = normalizar(apodo).strip()
        app = self.catalogo.buscar(destino)
        if not apodo or not app:
            self.responder(f"No encontré «{destino}», así que no guardé el apodo.",
                           f"No encontré {destino}, así que no guardé el apodo.")
            return
        # Se guarda el nombre REAL que encontró ("Visual Studio Code"), no lo que oyó
        self.a.almacen.guardar_apodo(apodo, app.nombre)
        self.catalogo.agregar_alias(apodo, app.nombre)
        self.responder(f"Listo: cuando digas «{apodo}», abro {app.nombre}.",
                       f"Listo. Cuando digas {apodo}, abro {app.nombre}.")

    def _olvidar_apodo(self, apodo: str):
        dicho = normalizar(apodo).strip()
        sin_articulo = lambda t: re.sub(r"^(?:el|la|los|las|mi|un|una) ", "", t)   # noqa: E731
        # "olvida el apodo código" debe encontrar "el codigo"
        apodo = next((a for a, _ in self.a.almacen.apodos() if sin_articulo(a) == sin_articulo(dicho)), dicho)
        if self.a.almacen.borrar_apodo(apodo):
            self.catalogo.quitar_alias(apodo)
            self.responder(f"Olvidé el apodo «{apodo}».")
        else:
            self.responder(f"No tengo ningún apodo «{apodo}».")

    def _decir_apodos(self):
        apodos = self.a.almacen.apodos()
        if not apodos:
            self.responder("Aún no tienes apodos. Di: «cuando diga el código abre Visual Studio Code».",
                           "Aún no tienes apodos.")
            return
        lineas = "\n".join(f"• {a} → {d}" for a, d in apodos)
        hablado = "; ".join(f"{a}, {d}" for a, d in apodos[:6])
        self.responder(f"Tus apodos:\n{lineas}", f"Tus apodos son: {hablado}.")

    def _decir_agenda(self):
        ahora = datetime.now()
        pendientes = self.a.almacen.pendientes()
        hoy = [t for t in pendientes if t.fecha > ahora and t.fecha.date() == ahora.date()]
        vencidas = [t for t in pendientes if t.fecha <= ahora]
        if hoy:
            n = len(hoy)
            lineas = "\n".join(f"• {t.fecha:%H:%M} {t.titulo}" for t in hoy[:6])
            hablado = "; ".join(f"{t.titulo}, {hora_hablada(t.fecha)}" for t in hoy[:5])
            texto, voz = f"Hoy tienes {n}:\n{lineas}", f"Hoy tienes {n} pendiente{'s' if n > 1 else ''}: {hablado}."
        else:
            texto = voz = "No tienes nada más para hoy."
        if vencidas:
            n = len(vencidas)
            texto += f"\n⚠ Y {n} vencida{'s' if n > 1 else ''}. Di «vencidas» para escucharlas."
            voz += f" Además tienes {n} vencida{'s' if n > 1 else ''}."
        pronto = [t for t in pendientes if t.es_evento and 1 <= (t.fecha.date() - ahora.date()).days <= 7]
        if pronto:
            texto += "\n📅 Se acerca: " + ", ".join(f"{t.titulo} ({describir_faltan(t.fecha, ahora)})" for t in pronto[:3])
            voz += " Se acerca " + " y ".join(f"{t.titulo}, {describir_faltan(t.fecha, ahora)}" for t in pronto[:2]) + "."
        self.responder(texto, voz)

    def _decir_vencidas(self):
        vencidas = self.a.almacen.vencidas(datetime.now())
        if not vencidas:
            self.responder("No tienes tareas vencidas. 👌", "No tienes tareas vencidas.")
            return
        n = len(vencidas)
        lineas = "\n".join(f"• {t.titulo} ({describir_fecha(t.fecha).replace('atrasada · ', '')})"
                           for t in vencidas[:6])
        hablado = "; ".join(t.titulo for t in vencidas[:5])
        self.responder(f"Vencidas ({n}):\n{lineas}\nDi «pasa las vencidas a mañana» para moverlas.",
                       f"Tienes {n} vencida{'s' if n > 1 else ''}: {hablado}.")

    # ======================================================= escuchar
    def poner_escucha(self, activo: bool, avisar: bool = True):
        self.escucha_activa = activo
        self.a.cara.microfono = activo
        self.oido.activar_continuo(activo)
        self.a.almacen.guardar_ajuste("escucha", "1" if activo else "0")
        if avisar:
            if activo:
                self.a.avisos.mostrar_mensaje("🎙 Escucha activada",
                                              f"Di «{NOMBRE_ASISTENTE}» y lo que necesites. "
                                              "Todo se procesa en tu laptop; nada sale a internet.",
                                              [], COLORES["escuchando"], 8, False)
            else:
                self.a.avisos.mostrar_mensaje("🎙 Escucha desactivada",
                                              f"Ya no te escucho. Puedes hablarme con {ATAJO_HABLAR}.",
                                              [], COLORES["dormido"], 6, False)
        self.a.actualizar_estado()

    def _al_escuchar(self, si: bool):
        self.escuchando_orden = si
        self.a.actualizar_estado()

    def _al_empezar_a_hablar(self):
        self.oido.silenciar(True)
        self.a.cara.hablando = True

    def _al_terminar_de_hablar(self):
        self.oido.silenciar(False)
        self.a.cara.hablando = False
        if self._escuchar_al_terminar:        # acaba de preguntar algo: escuchar la respuesta
            self._escuchar_al_terminar = False
            self.oido.escuchar_una_orden()

    def _al_estado_oido(self, tipo: str, detalle: str):
        avisos = self.a.avisos
        if tipo == "descargando":
            self.estado = f"⬇ Descargando el modelo de voz (39 MB, solo la primera vez)… {detalle}"
            if detalle == "0 %":
                avisos.mostrar_mensaje("🎙 Preparando la voz", "Descargo el modelo de voz (39 MB). "
                                       "Es solo la primera vez; tarda un poco.", [], COLORES["escuchando"], 10, False)
        elif tipo == "preparando":
            self.estado = "⏳ " + detalle
        elif tipo == "listo":
            log.info("reconocimiento de voz listo")
            self.estado = (f"🎙 Di «{NOMBRE_ASISTENTE}…»" if self.escucha_activa else "🎙 Voz lista.") + \
                          f" También puedes pulsar {ATAJO_HABLAR}."
        elif tipo == "error":
            log.error("voz: %s", detalle)
            self.estado = "⚠ " + detalle
            self.escucha_activa = False
            self.a.cara.microfono = False
            avisos.mostrar_mensaje("🎙 Problema con la voz", detalle, [], COLORES["alerta"], 15, False)
        elif tipo == "sin_orden":
            if self.dialogo:                  # no respondió la pregunta: no perder la tarea
                self._continuar_dialogo(Paso("rendirse", "No te escuché. Te dejé la tarea en el panel."))
            else:
                avisos.mostrar_mensaje(f"🗣 {NOMBRE_ASISTENTE}", "No te escuché. Inténtalo de nuevo.",
                                       [], COLORES["dormido"], 4, False)
        self.a.actualizar_estado()

    def detener(self):
        self.oido.detener()
