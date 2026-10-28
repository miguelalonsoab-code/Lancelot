"""
v3.17: «Más tarde», ver y borrar lo aprendido uno por uno, y las tareas agendadas desde una sugerencia
que no se hicieron se descartan solas al día siguiente.

    python -m unittest tests.test_v317 -v
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


class TestTareasSugeridas(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.a = Almacen(Path(self.tmp.name) / "t.db")
        self.gim = self.a.agregar_actividad(Actividad("Gimnasio", 60, 3))

    def tearDown(self):
        self.a.con.close()
        self.tmp.cleanup()

    def test_no_hecha_se_descarta_al_dia_siguiente(self):
        t = self.a.agregar("Gimnasio", datetime(2026, 10, 21, 18, 15), None, "tarea", None, 60)
        self.a.marcar_tarea_sugerida(t.id, self.gim.id)
        self.assertEqual(self.a.repasar_sugeridas(date(2026, 10, 21)), ([], []))     # hoy todavía no
        self.assertEqual(self.a.repasar_sugeridas(date(2026, 10, 22)), ([], [t.id]))
        self.assertIsNone(self.a.obtener(t.id))                                       # borrada (se sincroniza)
        self.assertEqual([c["borrada"] for c in self.a.cambios_por_subir()], [True])
        self.assertFalse(self.a.es_sugerida(t.id))

    def test_hecha_en_el_celular_cuenta_la_actividad(self):
        t = self.a.agregar("Gimnasio", datetime(2026, 10, 21, 18, 15), None, "tarea", None, 60)
        self.a.marcar_tarea_sugerida(t.id, self.gim.id)
        self.a.completar(t.id, datetime(2026, 10, 21, 19, 20))                       # como si llegara sincronizada
        hechas, descartadas = self.a.repasar_sugeridas(date(2026, 10, 22))
        self.assertEqual((hechas, descartadas), ([(self.gim.id, date(2026, 10, 21))], []))
        self.assertEqual(self.a.actividades_hechas(date(2026, 10, 19), date(2026, 10, 25)),
                         {self.gim.id: [date(2026, 10, 21)]})

    def test_una_tarea_normal_no_se_toca(self):
        t = self.a.agregar("Pagar la luz", datetime(2026, 10, 20, 9, 0))
        self.assertEqual(self.a.repasar_sugeridas(date(2026, 10, 22)), ([], []))
        self.assertIsNotNone(self.a.obtener(t.id))

    def test_olvidar_un_rechazo(self):
        for d in (20, 21):
            self.a.rechazar_sugerencia("gimnasio", date(2026, 10, d), "tarde")
            self.a.rechazar_sugerencia("gimnasio", date(2026, 10, d), "noche")
        self.assertEqual(self.a.olvidar_rechazo("gimnasio", "tarde"), 2)
        self.assertEqual(self.a.momentos_a_evitar(date(2026, 10, 1)), {"gimnasio": {"noche"}})


@unittest.skipIf(QApplication is None, "PySide6 no está instalado")
class TestAsistenteV317(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setQuitOnLastWindowClosed(False)

    def setUp(self):
        import interfaz.app as modulo
        modulo.segundos_inactivo = lambda: 0
        self.tmp = tempfile.TemporaryDirectory()
        self.a = modulo.Asistente(self.app, ruta_bd=Path(self.tmp.name) / "t.db")
        self.a.voz.habla.decir = lambda *_: None
        self.a._avisos_en_pausa_hasta = None
        self.a.burbuja.ocultar()
        self.a.almacen.guardar_perfil(despertar=time(6), dormir=time(23, 30), meta_estudio=0)
        self.a._recargar_perfil()
        self.a.agregar_actividad("gimnasio 1 hora 3 veces por semana")
        self.a.agregar_actividad("leer 30 min todos los días")
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

    def botones(self):
        return [b.text() for b in self.a.burbuja.findChildren(type(self.a.panel.boton_enviar))]

    def test_mas_tarde_vuelve_a_proponer_lo_mismo(self):
        self.a._sugerir_al_quedar_libre(self.en(17, 5))
        self.assertEqual(self.botones(), ["✓ Lo hago", "Más tarde", "Ahora no"])
        ofrecida = self.a._sugerencia_ofrecida.nombre
        self.a.burbuja.ocultar()
        self.a.posponer_sugerencia(ahora=self.en(17, 6))      # = botón «Más tarde» (sin depender de la hora real)
        self.assertEqual(self.a.burbuja.cabecera.text(), "Más tarde")
        self.assertEqual(self.a.almacen.momentos_a_evitar(self.hoy - timedelta(days=30), 1), {})   # no es rechazo
        pospuesta = self.a._sugerencia_pospuesta(self.hoy)
        self.assertEqual(pospuesta[1], ofrecida.lower())
        self.a.burbuja.ocultar()
        self.a._sugerir_al_quedar_libre(pospuesta[0] - timedelta(minutes=1))   # todavía no
        self.assertFalse(self.a.burbuja.isVisible())
        self.a._sugerir_al_quedar_libre(pospuesta[0] + timedelta(minutes=1))
        self.assertEqual(self.a._sugerencia_ofrecida.nombre, ofrecida)
        self.assertIsNone(self.a._sugerencia_pospuesta(self.hoy))              # se ofrece una sola vez

    def test_mas_tarde_espera_si_estas_ocupado(self):
        self.a._sugerencia_ofrecida = None
        self.a.almacen.guardar_ajuste("sugerencia_pospuesta", f"{self.en(10):%Y-%m-%d %H:%M}|leer")
        self.a._sugerir_al_quedar_libre(self.en(10, 30))                       # en pleno trabajo
        self.assertFalse(self.a.burbuja.isVisible())
        self.assertIsNotNone(self.a._sugerencia_pospuesta(self.hoy))
        self.a._sugerir_al_quedar_libre(self.en(17, 2))                        # al quedar libre: lo pospuesto
        self.assertEqual(self.a._sugerencia_ofrecida.nombre, "Leer")

    def test_lo_aprendido_se_ve_y_se_borra_uno_por_uno(self):
        for d in (1, 2):
            self.a.almacen.rechazar_sugerencia("gimnasio", self.hoy - timedelta(days=d), "tarde")
            self.a.almacen.rechazar_sugerencia("leer", self.hoy - timedelta(days=d), "noche")
        self.a.refrescar()
        lista = self.a.panel.lista_horario
        textos = [lista.item(i).text() for i in range(lista.count())]
        self.assertIn("NO TE SUGIERO · 2", textos)
        self.a.panel.aprendido_borrar_pedido.emit("gimnasio", "tarde")
        self.assertEqual(self.a._aprendido(), [("leer", "noche")])

    def test_agendada_y_no_hecha_se_descarta(self):
        self.a._ultimo_plan = self.a.plan_del_dia(self.hoy + timedelta(days=1))
        self.a.agendar_plan()
        self.assertIn("mañana la quito sola", self.a.burbuja.titulo.text())
        ids = [t.id for t in self.a.almacen.pendientes()]
        self.assertTrue(ids and all(self.a.almacen.es_sugerida(i) for i in ids))
        self.a.almacen.repasar_sugeridas(self.hoy + timedelta(days=2))
        self.assertEqual(self.a.almacen.pendientes(), [])


if __name__ == "__main__":
    unittest.main()
