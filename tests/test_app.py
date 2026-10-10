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
    }


if __name__ == "__main__":
    unittest.main()
