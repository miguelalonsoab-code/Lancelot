"""
v3.21: horario fijo y perfil editables desde el celular (la laptop los aplica), y vista Semana en la laptop.

    python -m unittest tests.test_v321 -v
"""
import json
import os
import sys
import tempfile
import unittest
from datetime import date, datetime, time, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication
except ImportError:
    QApplication = None


@unittest.skipIf(QApplication is None, "PySide6 no está instalado")
class TestAsistenteV321(unittest.TestCase):
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
        self.a.agregar_bloque("de lunes a viernes de 8:30 a 5:30 trabajo, traslado 45 min")
        self.hoy = date.today()

    def tearDown(self):
        self.a.salir()
        self.a.almacen.con.close()
        self.tmp.cleanup()

    def sincronizar(self):
        desde = int(self.a.almacen.leer_ajuste("nube_cursor", "0"))
        self.a.nube._trabajar(desde, self.a.almacen.cambios_por_subir(), self.a._preferencias_para_subir(),
                              self.a._extra_para_subir())
        self.app.processEvents()

    def test_horario_y_perfil_desde_el_celular(self):
        self.sincronizar()
        [trabajo] = self.servidor.contexto["horario"]
        self.assertIsNotNone(trabajo["id"])                                    # el celular necesita el id para quitarlo
        clase = {"dias": [2], "inicio": "19:30", "fin": "22:40", "titulo": "Computación Gráfica", "traslado": 0}
        self.servidor.del_celular("bloque", clase)
        self.servidor.del_celular("bloque", clase)                              # repetido: no se duplica
        self.servidor.del_celular("quitar_bloque", {"id": trabajo["id"]})
        self.servidor.del_celular("perfil", {"dormir": "23:30", "meta_estudio": 60})
        self.sincronizar()
        self.assertEqual([b.describir() for b in self.a.almacen.horario()], ["mié 19:30–22:40 · Computación Gráfica"])
        self.assertEqual((f"{self.a.perfil.dormir:%H:%M}", self.a.perfil.meta_estudio), ("23:30", 60))
        self.assertEqual(f"{self.a.perfil.despertar:%H:%M}", "06:00")           # lo que no se mandó, no cambia
        self.assertIn("Horario: mié 19:30–22:40 · Computación Gráfica", self.a.burbuja.titulo.text())
        self.sincronizar()
        self.assertEqual(self.servidor.pedidos[-1]["contexto"]["perfil"]["dormir"], "23:30")

    def test_vista_semana(self):
        p = self.a.panel
        lunes = self.hoy - timedelta(days=self.hoy.weekday())
        self.a.agregar("Examen", datetime.combine(lunes + timedelta(days=8), time(19)), None, "evento", "7,1", 120)
        p.ver_calendario(lunes + timedelta(days=8))
        p.b_semana.click()
        self.a.refrescar()
        self.assertTrue(p.semana_cal.isVisible())
        self.assertFalse(p.calendario.isVisible())
        dias = p.semana_cal.dias
        self.assertEqual([d for d, _ in dias][0], lunes + timedelta(days=7))
        martes = dict(dias)[lunes + timedelta(days=8)]
        self.assertEqual({i.tipo for i in martes}, {"bloque", "libre", "evento"})
        self.assertIn("–", p.agenda_titulo.text() + p.rango_semana.text())
        p.semana_siguiente()
        self.assertEqual(p.dia_calendario(), lunes + timedelta(days=15))
        p.b_mes.click()
        self.assertTrue(p.calendario.isVisible())


if __name__ == "__main__":
    unittest.main()
