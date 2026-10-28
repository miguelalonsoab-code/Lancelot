"""
v3.24: tema Zafiro completo (colores, fuentes, sin emoji en la interfaz), guiones por sílaba, categoría por
texto o voz y nombres de tareas y eventos dentro de la semana.

    python -m unittest tests.test_v324 -v
"""
import json
import os
import re
import sys
import tempfile
import unittest
from datetime import date, datetime, time, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from nucleo.comandos import interpretar_comando
from nucleo.horario import Bloque, buscar_por_nombre
from nucleo.silabas import GUION_SUAVE, con_guiones, puntos_de_corte, silabas

try:
    from PySide6.QtWidgets import QApplication
except ImportError:
    QApplication = None

EMOJI = re.compile(r"[\U0001F300-\U0001FAFF☀-✒✖-➿⭐⏩-⏿]")


class TestSilabas(unittest.TestCase):
    ESPERADO = {
        "computación": "com-pu-ta-ción", "interacción": "in-te-rac-ción", "gráfica": "grá-fi-ca",
        "trabajo": "tra-ba-jo", "inglés": "in-glés", "construcción": "cons-truc-ción", "química": "quí-mi-ca",
        "guitarra": "gui-ta-rra", "reunión": "reu-nión", "país": "pa-ís", "biología": "bio-lo-gí-a",
        "transporte": "trans-por-te", "inscripción": "ins-crip-ción", "perspectiva": "pers-pec-ti-va",
        "ahorro": "a-ho-rro", "leer": "le-er", "chocolate": "cho-co-la-te", "llave": "lla-ve",
        "averiguéis": "a-ve-ri-guéis", "pingüino": "pin-güi-no", "hoy": "hoy", "leyes": "le-yes",
        "ciudad": "ciu-dad", "examen": "e-xa-men", "obstrucción": "obs-truc-ción", "Sanna": "San-na",
    }

    def test_reglas_del_espanol(self):
        for palabra, esperado in self.ESPERADO.items():
            self.assertEqual("-".join(silabas(palabra)), esperado, palabra)

    def test_no_deja_una_letra_sola_al_partir(self):
        self.assertEqual(puntos_de_corte("universidad"), [3, 6, 8])          # «uni-ver-si-dad», nunca «u-»
        self.assertEqual(puntos_de_corte("día"), [])
        self.assertEqual(puntos_de_corte("UPN"), [])

    def test_guiones_invisibles(self):
        t = con_guiones("Computación Gráfica")
        self.assertEqual(t.replace(GUION_SUAVE, ""), "Computación Gráfica")   # el texto visible no cambia
        self.assertEqual(con_guiones("Trabajo en Sanna", "-"), "Tra-ba-jo en San-na")


class TestCategoriaPorTexto(unittest.TestCase):
    def test_frases_que_cambian_la_categoria(self):
        casos = {"Computación Gráfica es clase": ("computacion grafica", "clase"),
                 "marca inglés como otro": ("ingles", "otro"),
                 "pon Trabajo en Sanna como trabajo": ("trabajo en sanna", "trabajo"),
                 "la categoría de IHC es curso": ("ihc", "clase"),
                 "categoría de inglés: otra cosa": ("ingles", "otro"),
                 "Interacción Humano Computador es un curso": ("interaccion humano computador", "clase")}
        for frase, (texto, categoria) in casos.items():
            c = interpretar_comando(frase)
            self.assertEqual((c.accion, c.texto, c.destino), ("categoria", texto, categoria), frase)

    def test_no_se_confunde_con_otras_frases(self):
        for frase in ("esto es otro tema", "hoy es clase de redes", "mañana es trabajo", "marca la tarea como hecha",
                      "mañana 8pm clase de redes"):
            c = interpretar_comando(frase)
            self.assertTrue(c is None or c.accion != "categoria", frase)
        self.assertEqual(interpretar_comando("el viernes es feriado").accion, "excepcion")

    def test_buscar_por_nombre(self):
        bloques = [Bloque((0,), time(8), time(9), "Clase", 1), Bloque((1,), time(8), time(9), "Clase de redes", 2),
                   Bloque((2,), time(8), time(9), "Computación Gráfica", 3), Bloque((4,), time(8), time(9), "computación gráfica", 4)]
        self.assertEqual([b.id for b in buscar_por_nombre("clase", bloques)], [1])                 # igual gana
        self.assertEqual([b.id for b in buscar_por_nombre("redes", bloques)], [2])                 # si no, contiene
        self.assertEqual([b.id for b in buscar_por_nombre("COMPUTACION  GRAFICA", bloques)], [3, 4])
        self.assertEqual(buscar_por_nombre("  ", bloques), [])


class TestSinEmojiEnTextos(unittest.TestCase):
    def test_saludo_y_perfil(self):
        from nucleo.perfil import Perfil, describir_perfil
        from nucleo.saludo import armar_saludo
        s = armar_saludo(datetime(2026, 10, 28, 7), [], 4, "Miguel")
        self.assertIsNone(EMOJI.search(s.titulo + s.texto), s.titulo + s.texto)
        texto, _ = describir_perfil(Perfil(time(6), time(23), 120, []), [Bloque((0,), time(8), time(9), "Trabajo", 1, 30)])
        self.assertIsNone(EMOJI.search(texto), texto)
        self.assertIn("traslado 30 min", texto)


@unittest.skipIf(QApplication is None, "PySide6 no está instalado")
class TestAsistenteV324(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setQuitOnLastWindowClosed(False)

    def setUp(self):
        import interfaz.app as modulo
        from tests.test_v319 import ServidorConAcciones
        self.tmp = tempfile.TemporaryDirectory()
        carpeta = Path(self.tmp.name)
        (carpeta / "nube.json").write_text(json.dumps({"url": "https://lancelot.prueba.workers.dev", "clave": "x"}))
        self.a = modulo.Asistente(self.app, ruta_bd=carpeta / "t.db")
        self.a.voz.habla.decir = lambda *_: None
        self.servidor = ServidorConAcciones()
        self.a.nube.pedir = self.servidor.sync
        self.a.agregar_bloque("de lunes a viernes de 8:30 a 5:30 trabajo en Sanna, traslado 45 min")
        self.a.agregar_bloque("miércoles de 7:30 pm a 10:40 pm Computación Gráfica")
        self.a.agregar_bloque("viernes de 9:10 pm a 10:40 pm Computación Gráfica")

    def tearDown(self):
        self.a.salir()
        self.a.almacen.con.close()
        self.tmp.cleanup()

    def categorias(self):
        return sorted((b.titulo, b.categoria) for b in self.a.almacen.horario())

    def test_fuentes_del_tema(self):
        from interfaz.tema import MONO, SANS, cargar_fuentes
        familias = cargar_fuentes()
        self.assertIn(SANS, familias)
        self.assertIn(MONO, familias)
        self.assertEqual(self.app.font().family(), SANS)

    def test_categoria_por_texto_en_la_laptop(self):
        self.a.ejecutar_comando(interpretar_comando("computación gráfica es clase"))
        self.assertEqual(self.categorias(), [("Computación Gráfica", "clase"), ("Computación Gráfica", "clase"),
                                             ("Trabajo en Sanna", "trabajo")])
        self.assertIn("(2 bloques): ahora es clase", self.a.burbuja.titulo.text() + self.a.burbuja.extra.text())
        self.a.ejecutar_comando(interpretar_comando("marca natación como otro"))
        self.assertIn("No encontré «natacion»", self.a.burbuja.titulo.text() + self.a.burbuja.extra.text())

    def test_nombres_de_tareas_y_eventos_en_la_semana(self):
        p = self.a.panel
        hoy = date.today()
        lunes = hoy - timedelta(days=hoy.weekday())
        self.a.agregar("Examen de redes", datetime.combine(lunes + timedelta(days=12), time(10)), None, "evento", "7,1", 120)
        self.a.agregar("Entregar informe", datetime.combine(lunes + timedelta(days=8), time(19)), None, "tarea", None, 60)
        self.a.agregar("Pagar la luz", datetime.combine(lunes + timedelta(days=9), time(20)), None, "tarea", None, None)
        p.ver_calendario(lunes + timedelta(days=8))
        p.b_semana.click()
        self.a.refrescar()
        p.semana_cal.resize(460, 420)
        p.semana_cal.grab()                                                      # dibuja
        escritos = p.semana_cal.nombres_escritos
        self.assertIn("Examen de redes", escritos)                               # evento de 2 horas: cabe
        self.assertIn("Entregar informe", escritos)                              # tarea de 1 hora: cabe
        self.assertNotIn("Pagar la luz", escritos)                               # sin duración (30 min): muy baja
        self.assertIn("Trabajo en Sanna", escritos)

    def test_sin_emoji_en_el_panel(self):
        from PySide6.QtWidgets import QAbstractButton, QLabel
        p = self.a.panel
        self.a.agregar("Examen", datetime.combine(date.today() + timedelta(days=1), time(19)), None, "evento", "7,1", 120)
        for i in range(p.pestanas.count()):
            p.pestanas.setCurrentIndex(i)
            self.a.refrescar()
            self.app.processEvents()
            self.assertIsNone(EMOJI.search(p.pestanas.tabText(i)), p.pestanas.tabText(i))
        textos = [w.text() for w in p.findChildren(QLabel) + p.findChildren(QAbstractButton)]
        con_emoji = [t for t in textos if EMOJI.search(t or "")]
        self.assertEqual(con_emoji, [])

    def test_botones_con_icono_y_nombre_accesible(self):
        from PySide6.QtWidgets import QPushButton
        p = self.a.panel
        for b in (p.b_estudio, p.b_silencio, p.b_escucha):
            self.assertFalse(b.icon().isNull(), b.text())
        solo_icono = [b for b in p.findChildren(QPushButton) if not b.text()]
        self.assertTrue(solo_icono)
        for b in solo_icono:                                                     # todo botón sin texto dice qué hace
            self.assertTrue(b.accessibleName() or b.toolTip(), b)
            self.assertFalse(b.icon().isNull(), b.toolTip())

    def test_burbuja_con_el_tema(self):
        from interfaz.tema import ZAFIRO
        self.a.avisos.mostrar_mensaje("Prueba", "Hola", [], "#4fd1c5", 5, False)
        self.assertIn(ZAFIRO["superficie"], self.a.burbuja.styleSheet())
        self.assertIn("#4fd1c5", self.a.burbuja.styleSheet())                    # el borde sigue el ánimo de la cara


if __name__ == "__main__":
    unittest.main()
