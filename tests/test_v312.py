"""
v3.12: horario fijo de la semana y horas libres.

    python -m unittest tests.test_v312 -v
"""
import os
import sys
import tempfile
import unittest
from datetime import date, datetime, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from nucleo.almacen import Almacen                                        # noqa: E402
from nucleo.horario import (Bloque, describir_dias, describir_libre, hablar_duracion,   # noqa: E402
                            huecos, interpretar_bloque)

try:
    from PySide6.QtWidgets import QApplication
except ImportError:
    QApplication = None

MARTES = date(2026, 10, 20)


def bloque(texto):
    b = interpretar_bloque(texto)
    assert isinstance(b, Bloque), b
    return b


class TestInterpretarBloque(unittest.TestCase):
    def test_frases(self):
        casos = {
            "de lunes a viernes de 9am a 6pm trabajo": ((0, 1, 2, 3, 4), "09:00", "18:00", "Trabajo"),
            "martes y jueves de 7 a 10 de la noche clase de redes": ((1, 3), "19:00", "22:00", "Clase de redes"),
            "sábados de 8 a 12 inglés": ((5,), "08:00", "12:00", "Inglés"),
            "lunes, miércoles y viernes de 2 a 4 gimnasio": ((0, 2, 4), "14:00", "16:00", "Gimnasio"),
            "todos los días de 13:00 a 14:00 almuerzo": (tuple(range(7)), "13:00", "14:00", "Almuerzo"),
            "fines de semana de 10 a 1 fútbol": ((5, 6), "10:00", "13:00", "Fútbol"),
            "de lunes a viernes 8:30-17:30 Trabajo en Sanna": ((0, 1, 2, 3, 4), "08:30", "17:30", "Trabajo en Sanna"),
            "miércoles de 6 a 8 de la tarde taller": ((2,), "18:00", "20:00", "Taller"),
            "lunes de 10pm a 12am turno": ((0,), "22:00", "23:59", "Turno"),
            "los domingos de 9 a 11": ((6,), "09:00", "11:00", "Ocupado"),
        }
        for texto, (dias, ini, fin, titulo) in casos.items():
            b = bloque(texto)
            self.assertEqual((b.dias, f"{b.inicio:%H:%M}", f"{b.fin:%H:%M}", b.titulo), (dias, ini, fin, titulo), texto)

    def test_lo_que_falta_se_explica(self):
        self.assertIn("¿Qué días?", interpretar_bloque("trabajo de 9 a 6"))
        self.assertIn("horas", interpretar_bloque("lunes almuerzo"))
        self.assertIn("medianoche", interpretar_bloque("lunes de 22 a 2 turno noche"))

    def test_describir(self):
        self.assertEqual(describir_dias((0, 1, 2, 3, 4)), "lun a vie")
        self.assertEqual(describir_dias((1, 3)), "mar y jue")
        self.assertEqual(describir_dias((0, 2, 4)), "lun, mié y vie")
        self.assertEqual(hablar_duracion(90), "una hora y media")
        self.assertEqual(hablar_duracion(30), "media hora")
        self.assertEqual(hablar_duracion(135), "2 horas y 15 minutos")


class TestHuecos(unittest.TestCase):
    def setUp(self):
        self.bloques = [bloque("de lunes a viernes de 9am a 6pm trabajo"),
                        bloque("martes y jueves de 7 a 10 de la noche clase de redes"),
                        bloque("todos los días de 13:00 a 14:00 almuerzo")]           # dentro del trabajo

    def test_dia_completo(self):
        libres = huecos(MARTES, self.bloques, 6, 23)
        self.assertEqual(describir_libre(libres), "06:00–09:00 (3 h) · 18:00–19:00 (1 h) · 22:00–23:00 (1 h)")

    def test_hoy_desde_ahora_y_minimo(self):
        libres = huecos(MARTES, self.bloques, 6, 23, ahora=datetime(2026, 10, 20, 18, 40))
        self.assertEqual(describir_libre(libres), "22:00–23:00 (1 h)")             # 18:40-19:00 es muy corto

    def test_fin_de_semana_y_sin_horario(self):
        self.assertEqual(describir_libre(huecos(date(2026, 10, 24), self.bloques, 6, 23)),
                         "06:00–13:00 (7 h) · 14:00–23:00 (9 h)")
        self.assertEqual(huecos(MARTES, [], 6, 23), [(datetime.combine(MARTES, time(6)),
                                                       datetime.combine(MARTES, time(23)))])

    def test_se_guarda_en_la_base(self):
        with tempfile.TemporaryDirectory() as carpeta:
            a = Almacen(Path(carpeta) / "t.db")
            for b in self.bloques:
                a.agregar_bloque(b)
            guardados = a.horario()
            self.assertEqual([b.titulo for b in guardados], ["Trabajo", "Almuerzo", "Clase de redes"])
            self.assertTrue(a.borrar_bloque(guardados[0].id))
            self.assertEqual(len(a.horario()), 2)
            a.con.close()


@unittest.skipIf(QApplication is None, "PySide6 no está instalado")
class TestAsistenteHorario(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setQuitOnLastWindowClosed(False)

    def setUp(self):
        import interfaz.app as modulo
        self.tmp = tempfile.TemporaryDirectory()
        self.a = modulo.Asistente(self.app, ruta_bd=Path(self.tmp.name) / "t.db")
        self.dichos = []
        self.a.voz.habla.decir = self.dichos.append
        self.a.burbuja.ocultar()

    def tearDown(self):
        self.a.salir()
        self.a.almacen.con.close()
        self.tmp.cleanup()

    def comando(self, texto, por_voz=False):
        from nucleo.comandos import interpretar_comando
        self.dichos.clear()
        self.a.ejecutar_comando(interpretar_comando(texto), por_voz=por_voz)

    def test_anotar_ver_y_borrar_por_comando(self):
        self.comando("tiempo libre")
        self.assertIn("primero anota tu horario", self.a.burbuja.titulo.text())
        self.comando("horario: de lunes a viernes de 9am a 6pm Trabajo", por_voz=True)
        self.assertEqual(self.a.burbuja.cabecera.text(), "Anotado en tu horario")
        self.assertEqual(self.dichos, ["Listo, anoté Trabajo en tu horario."])
        self.comando("estoy ocupado martes y jueves de 7 a 10 de la noche clase de Redes")
        self.comando("mi horario")
        self.assertIn("mar y jue 19:00–22:00 · Clase de Redes", self.a.burbuja.titulo.text())
        self.comando("¿cuándo estoy libre mañana?", por_voz=True)
        self.assertTrue(self.a.burbuja.cabecera.text().startswith("Libre mañana"))
        self.assertTrue(self.dichos[0].startswith("Mañana tienes"))
        self.comando("borra el horario de trabajo")
        self.assertEqual([b.titulo for b in self.a.almacen.horario()], ["Clase de Redes"])

    def test_panel_y_saludo(self):
        p = self.a.panel
        p.entrada_bloque.setText("de lunes a viernes de 9 a 6")                       # sin título: "Ocupado"
        p._al_agregar_bloque()
        self.assertEqual(p.entrada_bloque.text(), "")
        self.assertEqual(p.lista_horario.count(), 1)
        self.assertTrue(p.libre_hoy.text().startswith("Libre hoy:"))
        p.entrada_bloque.setText("gimnasio de 7 a 8")                                 # faltan los días
        p._al_agregar_bloque()
        self.assertEqual(p.entrada_bloque.text(), "gimnasio de 7 a 8")                # no se borra: hay que corregir
        self.assertIn("¿Qué días?", self.a.burbuja.titulo.text())
        self.a.saludar(forzado=True)
        self.assertIn("Libre hoy:", self.a.burbuja.titulo.text())


if __name__ == "__main__":
    unittest.main()
