"""
Prueba de integración: el asistente COMPLETO (cara, burbuja, panel, voz, estudio),
pero sin pantalla real, sin micrófono y sin abrir programas de verdad.

Es la red de seguridad para reorganizar el código: si estas pruebas siguen
pasando, Lancelot se comporta igual que antes.

    python -m unittest tests.test_app -v
"""
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")      # sin ventanas reales

try:
    from PySide6.QtWidgets import QApplication
except ImportError:                                         # sin PySide6 no se puede probar la interfaz
    QApplication = None


@unittest.skipIf(QApplication is None, "PySide6 no está instalado")
class TestAsistente(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setQuitOnLastWindowClosed(False)

    def setUp(self):
        import interfaz.app as modulo
        from voz.apps import App
        self.tmp = tempfile.TemporaryDirectory()
        self.a = modulo.Asistente(self.app, ruta_bd=Path(self.tmp.name) / "t.db")
        self.dichos, self.abiertas, self.urls = [], [], []
        ganchos = puntos_de_enganche(self.a, modulo)
        # Lo que diría en voz alta, lo que abriría y lo que escucharía: todo se anota en vez de ocurrir
        ganchos["habla"].decir = self.dichos.append
        ganchos["catalogo"].abrir = lambda app: self.abiertas.append(app.nombre)
        ganchos["oido"].escuchar_una_orden = lambda *_: None
        ganchos["oido"].activar_continuo = lambda *_: None
        ganchos["modulo_web"].abrir_url = lambda url, exe=None: self.urls.append((url, exe)) or True
        ganchos["catalogo"].apps["visual studio code"] = App("Visual Studio Code", "VSCode", "appid")
        self.ganchos = ganchos

    def tearDown(self):
        self.a.salir()
        self.a.almacen.con.close()
        self.tmp.cleanup()

    def decir_por_voz(self, texto):
        self.dichos.clear()
        self.ganchos["procesar_orden"](texto)
        self.app.processEvents()

    def pendientes(self):
        return [(t.titulo, t.fecha.strftime("%H:%M")) for t in self.a.almacen.pendientes()]

    # ---------------------------------------------------------------- tareas
    def test_tarea_vence_avisa_y_se_completa(self):
        self.a.agregar("Pagar la luz", datetime.now() - timedelta(minutes=1), None)
        self.a.revisar()
        self.ganchos["actualizar_estado"]()
        self.assertEqual(self.ganchos["cola"](), [1])
        self.assertEqual(self.a.burbuja.tipo, "tarea")
        self.assertEqual(self.a.cara.estado_base, "alerta")
        self.a.completar(1)
        self.assertEqual(self.ganchos["cola"](), [])
        self.assertEqual(self.a.almacen.pendientes(), [])

    # ------------------------------------------------------------------- voz
    def test_voz_pregunta_lo_que_falta(self):
        self.decir_por_voz("recuérdame comprar pan")
        self.assertTrue(self.dichos and self.dichos[0].startswith("¿Para cuándo"))
        self.decir_por_voz("mañana a las ocho de la noche")
        self.assertEqual(self.pendientes(), [("Comprar pan", "20:00")])
        self.assertIsNone(self.ganchos["dialogo"]())

    def test_apodo_y_abrir(self):
        self.decir_por_voz("cuando diga el código abre visual studio code")
        self.assertEqual(self.a.almacen.apodos(), [("el codigo", "Visual Studio Code")])
        self.decir_por_voz("abre el código")
        self.assertEqual(self.abiertas, ["Visual Studio Code"])

    def test_web_en_navegador(self):
        self.decir_por_voz("abre netflix desde chrome")
        self.assertEqual(self.urls, [("https://www.netflix.com", "chrome.exe")])

    def test_silencio_no_habla(self):
        self.a.ejecutar_comando(self._comando("modo silencio"))
        self.decir_por_voz("qué hora es")
        self.assertEqual(self.dichos, [])
        self.assertTrue(self.a.burbuja.titulo.text().startswith("Son las"))

    # ---------------------------------------------------------------- estudio
    def test_estudio_mensaje_fijo_sobrevive_a_una_tarea(self):
        self.a.ejecutar_comando(self._comando("modo estudio"))
        p = self.a.estudio.pomodoro
        p._fin = datetime.now() - timedelta(seconds=1)
        self.a.estudio._tick()                                   # fin del enfoque
        p._fin = datetime.now() - timedelta(seconds=1)
        self.a.estudio._tick()                                   # fin del descanso: "¿seguimos?"
        self.assertEqual(self.a.burbuja.cabecera.text(), "Descanso terminado")
        self.a.agregar("Llamar al banco", datetime.now() - timedelta(minutes=1), None)
        self.a.revisar()
        self.assertEqual(self.a.burbuja.tipo, "tarea")           # la tarea pasa adelante
        self.a.completar(self.ganchos["cola"]()[0])
        self.assertEqual(self.a.burbuja.cabecera.text(), "Descanso terminado")   # y el mensaje vuelve
        self.a.ejecutar_comando(self._comando("terminar"))
        self.assertEqual(self.a.almacen.resumen_dia(datetime.now().date())[0], 1)

    # ------------------------------------------------------------- v3.6
    def test_saludo_del_dia_pausa_los_avisos(self):
        self.ganchos["config_saludo"](hora=0)                     # que salude a cualquier hora
        self.a.agregar("Pagar la luz", datetime.now() - timedelta(minutes=5), None)
        self.assertTrue(self.a.saludar())
        self.assertIn(", Miguel", self.a.burbuja.cabecera.text())
        self.assertIn("vencida", self.dichos[-1])                  # lo dice en voz alta
        self.a.revisar()
        self.assertEqual(self.ganchos["cola"](), [])               # la tarea espera al saludo
        self.assertFalse(self.a.saludar())                         # solo una vez por día
        self.ganchos["terminar_saludo"]()
        self.a.revisar()
        self.assertEqual(self.ganchos["cola"](), [1])

    def test_vencidas_en_panel_y_todas_a_manana(self):
        ayer = datetime.now().replace(second=0, microsecond=0) - timedelta(days=1)
        self.a.agregar("Pagar la luz", ayer, None)
        self.a.agregar("Examen", datetime.now() + timedelta(days=3), None)
        self.assertEqual(self.a.panel.lista.count(), 4)            # TAREAS VENCIDAS, Pagar la luz, PRÓXIMAS, Examen
        vencida = self.a.almacen.obtener(1)
        self.assertEqual(self.a.panel.opciones_menu_reprogramar(vencida)[-1], ("Elegir fecha y hora…", None))
        self.a.panel.reprogramar_vencidas_pedido.emit()
        self.assertEqual(self.a.almacen.obtener(1).fecha, ayer + timedelta(days=2))   # mañana, misma hora
        # TAREAS VENCIDAS · 0 (sigue a la vista), "Ninguna…", PRÓXIMAS TAREAS · 2, Pagar la luz, Examen
        self.assertEqual(self.a.panel.lista.count(), 5)

    def test_voz_vencidas(self):
        self.a.agregar("Pagar la luz", datetime.now() - timedelta(hours=2), None)
        self.decir_por_voz("qué tengo vencido")
        self.assertEqual(self.dichos, ["Tienes 1 vencida: Pagar la luz."])
        self.decir_por_voz("pasa las vencidas a mañana")
        self.assertEqual(self.dichos, ["Listo, pasé 1 a mañana."])
        self.assertEqual(self.a.almacen.vencidas(datetime.now()), [])

    def test_semana_en_panel(self):
        ahora = datetime.now()
        self.a.almacen.guardar_sesion(ahora.replace(hour=0, minute=0), ahora, 2, 50, 0)
        self.a.ejecutar_comando(self._comando("resumen semanal"))
        self.assertTrue(self.a.panel.viendo_estudio)
        self.assertEqual(self.a.panel.grafico.dias[-1].minutos, 50)
        self.assertEqual(self.a.burbuja.cabecera.text(), "Tu semana")
        self.a.panel._cambiar_semana(+1)                            # ◀ semana anterior
        self.assertEqual(self.a.panel.grafico.dias[-1].fecha, ahora.date() - timedelta(weeks=1))

    # ------------------------------------------------------------- v3.8
    def test_ofrece_actualizacion_y_omitir(self):
        from nucleo.version import Actualizacion
        act = Actualizacion("9.0", "https://github.com/x/Lancelot-setup-9.0.exe", "", "- Novedad", 0, None)
        self.a.actualizador.encontrada.emit(act, False)
        self.app.processEvents()
        self.assertIn("9.0 disponible", self.a.burbuja.cabecera.text())
        self.a.burbuja.accion.emit("omitir_version")
        self.assertEqual(self.a.almacen.leer_ajuste("version_omitida"), "9.0")
        self.a.burbuja.ocultar()
        self.ganchos["olvidar_oferta"]()
        self.a.actualizador.encontrada.emit(act, False)            # la próxima búsqueda automática…
        self.app.processEvents()
        self.assertFalse(self.a.burbuja.isVisible())                # …ya no insiste

    def test_actualizacion_no_interrumpe_el_estudio(self):
        from nucleo.version import Actualizacion
        self.a.ejecutar_comando(self._comando("modo estudio"))
        self.a.burbuja.ocultar()
        self.a.actualizador.encontrada.emit(Actualizacion("9.0", "u", "", "", 0, None), False)
        self.app.processEvents()
        self.assertFalse(self.a.burbuja.isVisible())

    @staticmethod
    def _comando(texto):
        from nucleo.comandos import interpretar_comando
        return interpretar_comando(texto)


def puntos_de_enganche(a, modulo):
    """
    Dónde vive cada pieza dentro del asistente. Si el código se reorganiza,
    solo cambia esta función; las pruebas de arriba quedan idénticas.
    """
    import voz.web
    return {
        "habla": a.voz.habla,
        "oido": a.voz.oido,
        "catalogo": a.voz.catalogo,
        "modulo_web": voz.web,
        "procesar_orden": a.voz.procesar_orden,
        "actualizar_estado": a.actualizar_estado,
        "cola": lambda: a.avisos.cola,
        "dialogo": lambda: a.voz.dialogo,
        "config_saludo": lambda hora: setattr(modulo, "HORA_SALUDO", hora),
        "terminar_saludo": lambda: setattr(a, "_avisos_en_pausa_hasta", None),
        "olvidar_oferta": lambda: setattr(a, "_actualizacion", None),
    }


if __name__ == "__main__":
    unittest.main()
