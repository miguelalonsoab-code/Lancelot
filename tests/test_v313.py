"""
v3.13: tiempo de traslado y perfil (sueño, meta de estudio, actividades).

    python -m unittest tests.test_v313 -v
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
from nucleo.horario import Bloque, describir_libre, huecos, interpretar_bloque, leer_duracion   # noqa: E402
from nucleo.perfil import Actividad, Perfil, describir_perfil, interpretar_actividad, leer_hora  # noqa: E402
from nucleo.planificador import estado_del_dia                            # noqa: E402

try:
    from PySide6.QtWidgets import QApplication
except ImportError:
    QApplication = None

MARTES = date(2026, 10, 20)


class TestTraslado(unittest.TestCase):
    def test_se_lee_en_el_bloque(self):
        casos = {
            "de lunes a viernes de 8:30am a 5:30pm trabajo, traslado 45 min": ("Trabajo", 45),
            "de lunes a viernes de 8:30am a 5:30pm trabajo con 1 hora de viaje": ("Trabajo", 60),
            "martes y jueves de 7 a 10 de la noche clases, traslado media hora": ("Clases", 30),
            "lunes de 9 a 11 viaje a cusco": ("Viaje a cusco", 0),             # "viaje" como título, no traslado
        }
        for texto, (titulo, traslado) in casos.items():
            b = interpretar_bloque(texto)
            self.assertIsInstance(b, Bloque, texto)
            self.assertEqual((b.titulo, b.traslado), (titulo, traslado), texto)

    def test_resta_antes_y_despues(self):
        b = interpretar_bloque("de lunes a viernes de 8:30am a 5:30pm trabajo, traslado 45 min")
        libres = huecos(MARTES, [b], time(6, 30), time(23, 0))
        self.assertEqual(describir_libre(libres), "06:30–07:45 (1 h 15 min) · 18:15–23:00 (4 h 45 min)")

    def test_duraciones(self):
        for texto, minutos in {"45 min": 45, "1 hora": 60, "una hora y media": 90, "media hora": 30,
                               "2 horas y 15 minutos": 135, "1h30min": 90}.items():
            self.assertEqual(leer_duracion(texto)[0], minutos, texto)
        self.assertEqual(leer_duracion("1 hora 3 veces por semana")[0], 60)     # el 3 no son minutos


class TestPerfil(unittest.TestCase):
    def test_horas_de_sueno(self):
        self.assertEqual(leer_hora("a las 6:30", "despertar"), time(6, 30))
        self.assertEqual(leer_hora("a las 11", "dormir"), time(23, 0))
        self.assertEqual(leer_hora("las 11 de la noche", "dormir"), time(23, 0))
        self.assertEqual(leer_hora("a la 1", "dormir"), time(1, 0))
        self.assertIsNone(leer_hora("temprano", "despertar"))

    def test_actividades(self):
        a = interpretar_actividad("gimnasio 1 hora 3 veces por semana en la tarde")
        self.assertEqual((a.nombre, a.minutos, a.veces_semana, a.momento), ("Gimnasio", 60, 3, "tarde"))
        a = interpretar_actividad("ir a correr 45 minutos dos veces por semana por la mañana")
        self.assertEqual((a.nombre, a.minutos, a.veces_semana, a.momento), ("Correr", 45, 2, "manana"))
        a = interpretar_actividad("leer 30 min todos los días")
        self.assertEqual(a.describir(), "Leer · 30 min · todos los días · cuando puedas")
        self.assertIsInstance(interpretar_actividad("1 hora 3 veces por semana"), str)

    def test_se_guarda(self):
        with tempfile.TemporaryDirectory() as carpeta:
            a = Almacen(Path(carpeta) / "t.db")
            defecto = Perfil(time(6), time(23), 100)
            self.assertEqual(a.perfil(defecto).despertar, time(6))
            a.guardar_perfil(despertar=time(6, 30), meta_estudio=120)
            a.agregar_actividad(Actividad("Gimnasio", 60, 3, "tarde"))
            p = a.perfil(defecto)
            self.assertEqual((p.despertar, p.dormir, p.meta_estudio), (time(6, 30), time(23), 120))
            self.assertEqual([x.nombre for x in p.actividades], ["Gimnasio"])
            self.assertTrue(a.borrar_actividad(p.actividades[0].id))
            a.con.close()

    def test_que_sabes_de_mi(self):
        p = Perfil(time(6, 30), time(23), 120, [Actividad("Gimnasio", 60, 3, "tarde")])
        texto, hablado = describir_perfil(p, [interpretar_bloque("de lunes a viernes de 9 a 6 trabajo")])
        self.assertIn("😴 Duermes de 23:00 a 06:30", texto)
        self.assertIn("lun a vie 09:00–18:00 · Trabajo", texto)
        self.assertIn("Gimnasio · 1 h · 3 veces por semana · en la tarde", texto)
        self.assertIn("estudiar 2 horas al día", hablado)

    def test_cara_dormida_si_duermes_pasada_la_medianoche(self):
        self.assertEqual(estado_del_dia([], False, datetime(2026, 10, 20, 0, 30), 1, 7), "tranquilo")
        self.assertEqual(estado_del_dia([], False, datetime(2026, 10, 20, 3), 1, 7), "dormido")
        self.assertEqual(estado_del_dia([], False, datetime(2026, 10, 20, 23, 30), 23, 6), "dormido")


@unittest.skipIf(QApplication is None, "PySide6 no está instalado")
class TestAsistentePerfil(unittest.TestCase):
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

    def test_perfil_por_comandos(self):
        self.comando("me despierto a las 6:30", por_voz=True)
        self.assertEqual(self.dichos, ["Listo, te despiertas a las 06:30."])
        self.comando("me duermo a las 11 de la noche")
        self.comando("meta de estudio 2 horas")
        self.comando("actividad: gimnasio 1 hora 3 veces por semana en la tarde")
        p = self.a.perfil
        self.assertEqual((p.despertar, p.dormir, p.meta_estudio, [x.nombre for x in p.actividades]),
                         (time(6, 30), time(23), 120, ["Gimnasio"]))
        self.assertEqual(self.a.resumen_de_semana().meta, 120)                 # el gráfico usa tu meta
        self.comando("¿qué sabes de mí?")
        self.assertEqual(self.a.burbuja.cabecera.text(), "🙂 Lo que sé de ti")
        self.assertTrue(self.a.panel.viendo_estudio is False and self.a.panel.pestanas.currentIndex() == 3)
        self.comando("borra la actividad gimnasio")
        self.assertEqual(self.a.perfil.actividades, [])

    def test_traslado_por_comando_y_horas_libres(self):
        self.comando("horario: de lunes a viernes de 8:30am a 5:30pm trabajo")
        self.comando("al trabajo tardo 45 minutos")
        self.assertIn("Anotado: 45 min para llegar a Trabajo", self.a.burbuja.titulo.text())
        [b] = self.a.almacen.horario()
        self.assertEqual(b.traslado, 45)
        self.comando("me despierto a las 6:30")
        libres = self.a.horas_libres(MARTES, datetime(2026, 10, 20, 0, 0))
        self.assertEqual(describir_libre(libres), "06:30–07:45 (1 h 15 min) · 18:15–23:00 (4 h 45 min)")
        self.comando("a la universidad tardo 20 minutos")
        self.assertIn("No tengo «universidad» en tu horario", self.a.burbuja.titulo.text())

    def test_panel_perfil(self):
        from PySide6.QtCore import QTime
        p = self.a.panel
        p.campo_despertar.setTime(QTime(7, 0))
        p.campo_meta.setValue(90)
        p.perfil_guardar_pedido.emit(p.campo_despertar.time().toPython(), p.campo_dormir.time().toPython(),
                                     p.campo_meta.value())
        self.assertEqual((self.a.perfil.despertar, self.a.perfil.meta_estudio), (time(7, 0), 90))
        p.entrada_actividad.setText("leer 30 min todos los días en la noche")
        p._al_agregar_actividad()
        self.assertEqual(p.entrada_actividad.text(), "")
        self.assertEqual(p.lista_actividades.count(), 1)


if __name__ == "__main__":
    unittest.main()
