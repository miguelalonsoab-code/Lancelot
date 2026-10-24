"""
v3.16: mejoras de las sugerencias — botones «✓ Lo hago» / «Ahora no» (y aprende de los rechazos),
«📌 Agendar», margen al despertar y resumen semanal de actividades.

    python -m unittest tests.test_v316 -v
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
from nucleo.recomendador import momento_de, recomendar                    # noqa: E402

try:
    from PySide6.QtWidgets import QApplication
except ImportError:
    QApplication = None

SABADO = date(2026, 10, 24)


def libre(h1, h2, dia=SABADO):
    return (datetime.combine(dia, time(h1)), datetime.combine(dia, time(h2)))


class TestAprenderRechazos(unittest.TestCase):
    def test_evita_el_momento_rechazado(self):
        gimnasio = Actividad("Gimnasio", 60, 3, "tarde", 1)
        libres = [libre(8, 11), libre(14, 18)]
        normal = recomendar(SABADO, libres, [gimnasio], {}, set(), 0, 0)
        self.assertEqual([f"{s.inicio:%H:%M}" for s in normal.sugerencias], ["14:00"])
        aprendido = recomendar(SABADO, libres, [gimnasio], {}, set(), 0, 0, evitar={"gimnasio": {"tarde"}})
        self.assertEqual([(f"{s.inicio:%H:%M}", s.motivo) for s in aprendido.sugerencias],
                         [("08:00", "llevas 0 de 3 esta semana; no hay hueco en la tarde")])
        nunca = recomendar(SABADO, libres, [gimnasio], {}, set(), 0, 0, evitar={"gimnasio": {"tarde", "manana"}})
        self.assertEqual(nunca.sugerencias, [])

    def test_momento_de(self):
        self.assertEqual([momento_de(datetime(2026, 1, 1, h)) for h in (2, 6, 12, 18, 19, 23)],
                         ["noche", "manana", "tarde", "tarde", "noche", "noche"])

    def test_se_guardan_y_se_olvidan(self):
        with tempfile.TemporaryDirectory() as carpeta:
            a = Almacen(Path(carpeta) / "t.db")
            a.rechazar_sugerencia("gimnasio", date(2026, 10, 1), "tarde")       # hace mucho: no cuenta
            a.rechazar_sugerencia("gimnasio", date(2026, 10, 20), "tarde")
            self.assertEqual(a.momentos_a_evitar(date(2026, 10, 3)), {})        # una sola vez reciente
            a.rechazar_sugerencia("gimnasio", date(2026, 10, 21), "tarde")
            a.rechazar_sugerencia("estudiar", date(2026, 10, 21), "noche")
            self.assertEqual(a.momentos_a_evitar(date(2026, 10, 3)), {"gimnasio": {"tarde"}})
            self.assertEqual(a.olvidar_rechazos(), 4)
            self.assertEqual(a.momentos_a_evitar(date(2026, 1, 1)), {})
            a.con.close()


@unittest.skipIf(QApplication is None, "PySide6 no está instalado")
class TestAsistenteV316(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setQuitOnLastWindowClosed(False)

    def setUp(self):
        import interfaz.app as modulo
        self.modulo = modulo
        self.tmp = tempfile.TemporaryDirectory()
        self.a = modulo.Asistente(self.app, ruta_bd=Path(self.tmp.name) / "t.db")
        self.dichos = []
        self.a.voz.habla.decir = self.dichos.append
        self.a._avisos_en_pausa_hasta = None
        self.a.burbuja.ocultar()
        self.manana = date.today() + timedelta(days=1)
        self.a.almacen.guardar_perfil(meta_estudio=0)
        self.a._recargar_perfil()

    def tearDown(self):
        if self.a.estudio.activo:
            self.a.estudio.terminar()
        self.a.salir()
        self.a.almacen.con.close()
        self.tmp.cleanup()

    def comando(self, texto, por_voz=False):
        from nucleo.comandos import interpretar_comando
        self.dichos.clear()
        self.a.burbuja.ocultar()
        self.a.avisos.cola.clear()
        self.a.ejecutar_comando(interpretar_comando(texto), por_voz=por_voz)

    def test_margen_al_despertar(self):
        self.a.agregar_actividad("leer 30 min todos los días")
        plan = self.a.plan_del_dia(self.manana)
        despertar = datetime.combine(self.manana, self.a.perfil.despertar)
        self.assertEqual(plan.sugerencias[0].inicio, despertar + timedelta(minutes=30))

    def test_agendar_el_plan(self):
        self.a.agregar_actividad("gimnasio 1 hora 3 veces por semana")
        self.comando("recomiéndame algo para mañana")
        self.assertIn("📌 Agendar", [b.text() for b in self.a.burbuja.findChildren(type(self.a.panel.boton_enviar))])
        self.comando("agéndalo", por_voz=True)
        [t] = [t for t in self.a.almacen.pendientes() if t.titulo == "Gimnasio"]
        self.assertEqual((t.fecha.date(), t.duracion, t.tipo), (self.manana, 60, "tarea"))
        self.assertEqual(self.dichos, ["Listo, agendé 1 cosa."])
        self.assertEqual(self.a.plan_del_dia(self.manana).sugerencias, [])     # ya está planificado
        self.a._ultimo_plan = self.a.plan_del_dia(self.manana)                 # vacío: ya está todo agendado
        self.comando("agéndalo")
        self.assertEqual(self.a.burbuja.titulo.text(), "No hay nada nuevo que agendar.")
        self.a.completar(t.id)                                                  # completarla cuenta
        self.assertEqual(len(self.a.almacen.actividades_hechas(date.today(), date.today())), 1)

    def _ofrecer(self, nombre="Gimnasio", clase="actividad", hora=18):
        from nucleo.recomendador import Sugerencia
        inicio = datetime.combine(date.today(), time(hora))
        self.a._sugerencia_ofrecida = Sugerencia(nombre, inicio, inicio + timedelta(hours=1), "x", clase)

    def test_lo_hago_y_ahora_no(self):
        self.a.agregar_actividad("gimnasio 1 hora 3 veces por semana")
        self._ofrecer()
        self.a.avisos._al_pulsar_boton("sugerencia_si")
        self.assertEqual(len(self.a.almacen.actividades_hechas(date.today(), date.today())), 1)
        self.assertEqual(self.a.burbuja.cabecera.text(), "💪 ¡Vamos!")
        self._ofrecer()
        self.a.avisos._al_pulsar_boton("sugerencia_no")
        self.assertEqual(self.a.almacen.momentos_a_evitar(date.today() - timedelta(days=1)), {})
        self.a.burbuja.ocultar()
        self._ofrecer()
        self.a.avisos._al_pulsar_boton("sugerencia_no")
        self.assertEqual(self.a.burbuja.cabecera.text(), "💡 Aprendido")
        self.assertIn("Ya no te sugiero gimnasio en la tarde", self.a.burbuja.titulo.text())
        self.comando("vuelve a sugerirme todo")
        self.assertIn("olvidé lo que rechazaste", self.a.burbuja.titulo.text())

    def test_lo_hago_estudiar_abre_el_modo_estudio(self):
        self._ofrecer("Estudiar", "estudio")
        self.a.avisos._al_pulsar_boton("sugerencia_si")
        self.assertTrue(self.a.estudio.activo)

    def test_resumen_de_actividades_en_estudio(self):
        self.assertEqual(self.a.resumen_actividades(), "")
        self.a.agregar_actividad("gimnasio 1 hora 1 vez por semana")
        self.a.agregar_actividad("leer 30 min")
        for a in self.a.perfil.actividades:
            self.a.almacen.marcar_actividad(a.id, date.today())
        self.assertEqual(self.a.resumen_actividades(), "💪 Actividades: Gimnasio 1 de 1 ✅ · Leer 1")
        self.assertEqual(self.a.resumen_actividades(1), "💪 Actividades: Gimnasio 0 de 1 · Leer 0")
        self.a.mostrar_semana(0)
        self.assertTrue(self.a.panel.actividades_semana.text().startswith("💪 Actividades:"))

    def test_hueco_libre_ofrece_botones(self):
        self.modulo.segundos_inactivo = lambda: 0
        self.a.agregar_actividad("gimnasio 1 hora 3 veces por semana")
        self.a.almacen.agregar_bloque(Bloque(tuple(range(7)), time(9), time(17), "Trabajo"))
        self.a._sugerir_al_quedar_libre(datetime.combine(date.today(), time(17, 5)))
        textos = [b.text() for b in self.a.burbuja.findChildren(type(self.a.panel.boton_enviar))]
        self.assertIn("✓ Lo hago", textos)
        self.assertIn("Ahora no", textos)
        self.assertEqual(self.a._sugerencia_ofrecida.nombre, "Gimnasio")


if __name__ == "__main__":
    unittest.main()
