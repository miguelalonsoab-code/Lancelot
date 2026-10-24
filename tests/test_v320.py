"""
v3.20: calendario en la laptop, días libres y actividades editables desde el celular, aviso de hueco libre
en el celular (el servidor no repite lo que la laptop ya dijo) y semana en el celular.

    python -m unittest tests.test_v320 -v
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

from nucleo.agenda import agenda_del_dia, marcas_del_mes, tareas_del_dia   # noqa: E402
from nucleo.almacen import Tarea                                           # noqa: E402
from nucleo.horario import Bloque, Excepcion                              # noqa: E402

try:
    from PySide6.QtWidgets import QApplication
except ImportError:
    QApplication = None

JUEVES = date(2026, 10, 22)
TRABAJO = Bloque((0, 1, 2, 3, 4), time(8, 30), time(17, 30), "Trabajo en Sanna", traslado=45)


def tarea(id_, titulo, fecha, tipo="tarea", duracion=None, repeticion=None):
    return Tarea(id_, titulo, datetime.strptime(fecha, "%Y-%m-%d %H:%M"), repeticion, "pendiente", False, tipo, None, duracion)


TAREAS = [tarea(1, "Examen de redes", "2026-10-23 19:00", "evento", 120), tarea(2, "Pagar la luz", "2026-10-22 09:00"),
          tarea(3, "Regar plantas", "2026-10-20 07:00", repeticion="diaria")]


class TestAgenda(unittest.TestCase):
    """Lo mismo que prueba pruebas/contexto.test.mjs para el celular."""

    def test_tareas_del_dia_con_repeticiones(self):
        self.assertEqual([(t.id, f"{f:%H:%M}") for t, f in tareas_del_dia(TAREAS, JUEVES)], [(3, "07:00"), (2, "09:00")])
        self.assertEqual(tareas_del_dia(TAREAS, date(2026, 10, 19)), [])

    def test_agenda_y_marcas(self):
        viernes = date(2026, 10, 23)
        libres = [(datetime(2026, 10, 23, 6), datetime(2026, 10, 23, 7, 45)),
                  (datetime(2026, 10, 23, 18, 15), datetime(2026, 10, 23, 19))]
        agenda = agenda_del_dia(viernes, [TRABAJO], [], TAREAS, libres, {3})
        self.assertEqual([(i.tipo, f"{i.inicio:%H:%M}", i.titulo, i.sugerida) for i in agenda], [
            ("libre", "06:00", "Libre", False), ("tarea", "07:00", "Regar plantas", True),
            ("bloque", "08:30", "Trabajo en Sanna", False), ("libre", "18:15", "Libre", False),
            ("evento", "19:00", "Examen de redes", False)])
        self.assertEqual(f"{agenda[-1].fin:%H:%M}", "21:00")
        libre = [Excepcion(date(2026, 11, 2), date(2026, 11, 2), "traba", "No trabajo")]
        otra = agenda_del_dia(date(2026, 11, 2), [TRABAJO], libre, [], [])
        self.assertEqual([(i.tipo, i.liberado) for i in otra], [("excepcion", False), ("bloque", True)])
        marcas = marcas_del_mes(date(2026, 10, 21), date(2026, 11, 2), TAREAS, libre)
        self.assertEqual(marcas[date(2026, 10, 23)], (1, 1, False))
        self.assertEqual(marcas[date(2026, 11, 2)], (1, 0, True))


@unittest.skipIf(QApplication is None, "PySide6 no está instalado")
class TestAsistenteV320(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setQuitOnLastWindowClosed(False)

    def setUp(self):
        import interfaz.app as modulo
        from tests.test_v319 import ServidorConAcciones
        self.modulo = modulo
        self.tmp = tempfile.TemporaryDirectory()
        carpeta = Path(self.tmp.name)
        (carpeta / "nube.json").write_text(json.dumps({"url": "https://lancelot.prueba.workers.dev", "clave": "x"}))
        self.a = modulo.Asistente(self.app, ruta_bd=carpeta / "t.db")
        self.a.voz.habla.decir = lambda *_: None
        self.servidor = ServidorConAcciones()
        self.a.nube.pedir = self.servidor.sync
        self.a.agregar_actividad("gimnasio 1 hora 3 veces por semana en la tarde")
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

    def test_editar_desde_el_celular(self):
        gim = self.a.perfil.actividades[0]
        self.a.agregar_excepcion("el 1 de noviembre no trabajo")
        self.servidor.del_celular("actividad", {"nombre": "Yoga", "minutos": 45, "veces_semana": 2, "momento": None})
        self.servidor.del_celular("actividad", {"nombre": "gimnasio", "minutos": 30, "veces_semana": 1, "momento": None})
        self.servidor.del_celular("quitar_actividad", {"id": gim.id})
        self.servidor.del_celular("quitar_excepcion", {"desde": "2026-11-01", "hasta": "2026-11-01", "filtro": "traba"})
        self.sincronizar()
        self.assertEqual([a.nombre for a in self.a.perfil.actividades], ["Yoga"])
        self.assertEqual(self.a.almacen.excepciones(date(2026, 1, 1)), [])
        self.assertEqual(self.a.burbuja.cabecera.text(), "📱 Desde el celular")
        self.assertIn("Actividad: Yoga", self.a.burbuja.titulo.text())
        self.sincronizar()
        self.assertEqual([a["nombre"] for a in self.servidor.pedidos[-1]["contexto"]["actividades"]], ["Yoga"])

    def test_el_contexto_dice_que_hueco_ya_aviso_la_laptop(self):
        self.modulo.segundos_inactivo = lambda: 0
        self.a.almacen.agregar_bloque(Bloque(tuple(range(7)), time(9), time(17), "Clases"))
        despertar = datetime.combine(self.hoy, self.a.perfil.despertar)
        inicio = next(a for a, _ in self.a.horas_libres(self.hoy, datetime.combine(self.hoy, time(0, 1))) if a > despertar)
        self.a._sugerir_al_quedar_libre(inicio + timedelta(minutes=5))     # 17:00 el finde, 18:15 entre semana
        c = self.a.contexto_celular()
        self.assertEqual(c["hueco_avisado"], f"{inicio:%Y-%m-%d %H:%M}")
        self.assertTrue(c["perfil"]["avisar_huecos"])

    def test_pestana_calendario(self):
        p = self.a.panel
        manana = self.hoy + timedelta(days=1)
        self.a.agregar("Examen", datetime.combine(manana, time(19)), None, "evento", "7,1", 120)
        p.ver_calendario(manana)
        self.a.refrescar()
        self.assertTrue(p.viendo_calendario)
        self.assertEqual(p.agenda_titulo.text(), "Mañana")
        from PySide6.QtWidgets import QLabel
        textos = [" ".join(l.text() for l in p.lista_agenda.itemWidget(p.lista_agenda.item(i)).findChildren(QLabel))
                  for i in range(p.lista_agenda.count())]
        self.assertTrue(any("📅 Examen" in t and "Hasta las 21:00" in t for t in textos))
        self.assertEqual(manana.weekday() < 5, any("Trabajo" in t for t in textos))
        self.assertTrue(p.sugerencias_dia.text().startswith("💡 Te sugiero:"))
        p.b_agendar_dia.click()
        self.assertTrue(any(self.a.almacen.es_sugerida(t.id) for t in self.a.almacen.pendientes()))


if __name__ == "__main__":
    unittest.main()
