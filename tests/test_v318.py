"""
v3.18: «más tarde, a las 8», comentario honesto en la semana si agendas y no haces, y lo agendado desde
una sugerencia no aparece en vencidas (sale con 💡 en próximas tareas hasta que se quita solo).

    python -m unittest tests.test_v318 -v
"""
import os
import sys
import tempfile
import unittest
from datetime import date, datetime, time, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from nucleo.almacen import Almacen                                        # noqa: E402
from nucleo.horario import Bloque                                         # noqa: E402
from nucleo.perfil import Actividad                                       # noqa: E402

try:
    from PySide6.QtWidgets import QApplication
except ImportError:
    QApplication = None


class TestProximaHora(unittest.TestCase):
    def test_elige_la_proxima(self):
        from interfaz.app import proxima_hora
        ahora = datetime(2026, 10, 21, 17, 10)
        casos = {"8": "20:00", "8:30": "20:30", "6 de la tarde": "18:00", "9pm": "21:00", "11": "23:00",
                 "18:00": "18:00"}
        for texto, esperado in casos.items():
            self.assertEqual(f"{proxima_hora(texto, ahora):%H:%M}", esperado, texto)
        self.assertIsNone(proxima_hora("8 de la mañana", ahora))            # ya pasó
        self.assertIsNone(proxima_hora("5pm", ahora))
        self.assertEqual(f"{proxima_hora('8', datetime(2026, 10, 21, 7, 0)):%H:%M}", "08:00")


class TestHistorialSugeridas(unittest.TestCase):
    def test_balance_y_vencidas(self):
        with tempfile.TemporaryDirectory() as carpeta:
            a = Almacen(Path(carpeta) / "t.db")
            g = a.agregar_actividad(Actividad("Gimnasio", 60, 3))
            for dia in (19, 20, 21):
                t = a.agregar("Gimnasio", datetime(2026, 10, dia, 18, 0), None, "tarea", None, 60)
                a.marcar_tarea_sugerida(t.id, g.id)
                if dia == 21:
                    a.completar(t.id, datetime(2026, 10, 21, 19, 0))
            normal = a.agregar("Pagar la luz", datetime(2026, 10, 21, 9, 0))
            sugerida = a.agregar("Leer", datetime(2026, 10, 22, 9, 0), None, "tarea", None, 30)
            a.marcar_tarea_sugerida(sugerida.id, None)
            ahora = datetime(2026, 10, 22, 12, 0)
            a.repasar_sugeridas(ahora.date())
            self.assertEqual(a.balance_sugeridas(date(2026, 10, 16), date(2026, 10, 22)), {"Gimnasio": (1, 2)})
            self.assertEqual([t.id for t in a.vencidas(ahora)], [normal.id])          # «Leer» no vence
            self.assertEqual(a.ids_sugeridas(), {sugerida.id})
            a.con.close()


@unittest.skipIf(QApplication is None, "PySide6 no está instalado")
class TestAsistenteV318(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setQuitOnLastWindowClosed(False)

    def setUp(self):
        import interfaz.app as modulo
        modulo.segundos_inactivo = lambda: 0
        self.tmp = tempfile.TemporaryDirectory()
        self.a = modulo.Asistente(self.app, ruta_bd=Path(self.tmp.name) / "t.db")
        self.dichos = []
        self.a.voz.habla.decir = self.dichos.append
        self.a._avisos_en_pausa_hasta = None
        self.a.almacen.guardar_perfil(despertar=time(6), dormir=time(23, 30), meta_estudio=0)
        self.a._recargar_perfil()
        self.a.agregar_actividad("gimnasio 1 hora 3 veces por semana")
        self.a.almacen.agregar_bloque(Bloque(tuple(range(7)), time(9), time(17), "Trabajo"))
        self.hoy = date.today()
        self.a.burbuja.ocultar()
        self.a.avisos.cola.clear()

    def tearDown(self):
        self.a.salir()
        self.a.almacen.con.close()
        self.tmp.cleanup()

    def en(self, h, m=0):
        return datetime.combine(self.hoy, time(h, m))

    def test_mas_tarde_a_una_hora_fija(self):
        from nucleo.comandos import interpretar_comando
        self.a._sugerir_al_quedar_libre(self.en(17, 5))
        self.assertEqual(self.a._sugerencia_ofrecida.nombre, "Gimnasio")
        c = interpretar_comando("más tarde, a las 11:10 de la noche")
        self.assertEqual((c.accion, c.texto), ("posponer_hasta", "11:10 de la noche"))
        self.a.posponer_hasta(c.texto, ahora=self.en(17, 6))                # (a una hora fija: la prueba no
                                                                             # depende de la hora real)
        self.assertEqual(self.a.almacen.leer_ajuste("sugerencia_pospuesta"),
                         f"{self.en(23, 10):%Y-%m-%d %H:%M}|gimnasio|fija")
        # Un hueco nuevo antes de esa hora NO la adelanta
        self.a.almacen.agregar("Cena", self.en(19), None, "tarea", None, 60)
        self.a.burbuja.ocultar()
        self.a._sugerir_al_quedar_libre(self.en(20, 2))
        self.assertIsNotNone(self.a._sugerencia_pospuesta(self.hoy))
        # A su hora sí, aunque el plan ya no la traiga (no entra 1 h antes de dormir): se ofrece igual
        self.a.burbuja.ocultar()
        self.a.avisos.cola.clear()
        self.a._sugerir_al_quedar_libre(self.en(23, 11))
        self.assertTrue(self.a.burbuja.isVisible())
        self.assertEqual(self.a._sugerencia_ofrecida.nombre, "Gimnasio")
        self.assertIn("lo dejaste para esta hora", self.a.burbuja.titulo.text())

    def test_mas_tarde_sin_nada_pendiente(self):
        from nucleo.comandos import interpretar_comando
        self.a.ejecutar_comando(interpretar_comando("luego a las 9pm"))
        self.assertIn("No tengo ninguna sugerencia pendiente", self.a.burbuja.titulo.text())

    def test_comentario_honesto_en_la_semana(self):
        for d in (1, 2):
            self.a.almacen._anotar_historial("Gimnasio", f"{self.hoy - timedelta(days=d):%Y-%m-%d} 18:00", "descartada")
        self.assertEqual(len(self.a.comentario_agendadas()), 1)
        self.assertIn("Agendaste Gimnasio 2 veces y lo hiciste 0", self.a.resumen_actividades())
        from nucleo.comandos import interpretar_comando
        self.dichos.clear()
        self.a.ejecutar_comando(interpretar_comando("resumen semanal"), por_voz=True)
        self.assertIn("📌 Agendaste Gimnasio", self.a.burbuja.titulo.text())
        self.assertTrue(self.dichos[0].endswith("Te dejé el detalle en pantalla."))

    def test_sugerida_pasada_no_sale_en_vencidas(self):
        from PySide6.QtWidgets import QLabel
        t = self.a.almacen.agregar("Gimnasio", datetime.now() - timedelta(minutes=30), None, "tarea", None, 60)
        self.a.almacen.marcar_tarea_sugerida(t.id, None)
        self.a.refrescar()
        lista = self.a.panel.lista
        filas = [" ".join(l.text() for l in lista.itemWidget(lista.item(i)).findChildren(QLabel))
                 for i in range(lista.count())]
        self.assertTrue(filas[0].startswith("⚠ TAREAS VENCIDAS · 0"))
        self.assertTrue(any("💡 Gimnasio" in f and "mañana se quita sola" in f for f in filas))


if __name__ == "__main__":
    unittest.main()
