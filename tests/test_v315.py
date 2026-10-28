"""
v3.15: sugerencias de qué hacer en tus horas libres y conteo de actividades por semana.

    python -m unittest tests.test_v315 -v
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
from nucleo.horario import huecos, interpretar_bloque                     # noqa: E402
from nucleo.perfil import Actividad                                       # noqa: E402
from nucleo.recomendador import describir_plan, lunes_de, recomendar      # noqa: E402

try:
    from PySide6.QtWidgets import QApplication
except ImportError:
    QApplication = None

TRABAJO = interpretar_bloque("de lunes a viernes de 8:30 a 5:30 trabajo, traslado 45 min")
CLASES = interpretar_bloque("martes y jueves de 7 a 10 de la noche clase de redes")
GIMNASIO = Actividad("Gimnasio", 60, 3, "tarde", 1)
LEER = Actividad("Leer", 30, None, "noche", 2)
CORRER = Actividad("Correr", 40, 2, "manana", 3)
SABADO, JUEVES = date(2026, 10, 24), date(2026, 10, 22)


def plan(dia, hechas=None, hoy=(), estudio=0, meta=120, actividades=(GIMNASIO, LEER, CORRER), bloques=(TRABAJO, CLASES)):
    libres = huecos(dia, list(bloques), time(6), time(23))
    return recomendar(dia, libres, list(actividades), hechas or {}, set(hoy), estudio, meta)


def resumen(p):
    return [f"{s.inicio:%H:%M} {s.nombre}" for s in p.sugerencias]


class TestRecomendador(unittest.TestCase):
    def test_dia_libre_respeta_momentos(self):
        p = plan(SABADO, hechas={1: 1}, estudio=20)
        self.assertEqual(resumen(p), ["06:00 Correr", "06:50 Estudiar", "12:00 Gimnasio", "19:00 Leer"])
        self.assertEqual(p.sugerencias[1].motivo, "te faltan 1 h 40 min para tu meta")
        self.assertEqual(p.sugerencias[2].motivo, "llevas 1 de 3 esta semana")
        self.assertEqual(p.sin_lugar, [])

    def test_dia_apretado_prioriza_lo_importante(self):
        p = plan(JUEVES, hechas={1: 1}, estudio=20)        # libre: 6:00–7:45, 18:15–19:00, 22:00–23:00
        self.assertEqual({s.nombre for s in p.sugerencias}, {"Estudiar", "Gimnasio", "Correr"})
        self.assertNotIn("Leer", resumen(p))               # lo menos importante queda afuera
        gimnasio = next(s for s in p.sugerencias if s.nombre == "Gimnasio")
        self.assertIn("no hay hueco en la tarde", gimnasio.motivo)

    def test_meta_cumplida_y_ya_hecho_hoy(self):
        p = plan(SABADO, hechas={1: 3, 3: 1}, hoy={3}, estudio=120)
        self.assertEqual(resumen(p), ["19:00 Leer"])        # gimnasio 3/3, correr ya hoy, estudio al día
        p = plan(SABADO, hechas={1: 3, 3: 2}, estudio=150, actividades=(GIMNASIO, CORRER))
        self.assertEqual(describir_plan(p)[0], "Hoy no tengo nada que sugerirte: vas al día.")

    def test_sin_huecos(self):
        p = recomendar(JUEVES, [], [GIMNASIO], {}, set(), 0, 60)
        self.assertEqual(p.sugerencias, [])
        self.assertEqual(p.sin_lugar, ["Estudiar", "Gimnasio"])
        self.assertIn("No entra: Estudiar, Gimnasio", describir_plan(p)[0])

    def test_estudio_parcial_si_no_entra_entero(self):
        libres = [(datetime(2026, 10, 22, 18, 0), datetime(2026, 10, 22, 18, 40))]
        p = recomendar(JUEVES, libres, [], {}, set(), 0, 120)
        self.assertEqual([(s.nombre, f"{s.inicio:%H:%M}", f"{s.fin:%H:%M}") for s in p.sugerencias],
                         [("Estudiar", "18:00", "18:40")])

    def test_urgencia_crece_al_final_de_la_semana(self):
        # Domingo, te faltan 2 de 2 de correr y 1 de 3 de gimnasio: correr es más urgente
        domingo = date(2026, 10, 25)
        libres = [(datetime(2026, 10, 25, 18, 0), datetime(2026, 10, 25, 19, 0))]
        p = recomendar(domingo, libres, [Actividad("Gimnasio", 60, 3, None, 1), Actividad("Correr", 60, 2, None, 3)],
                       {1: 2}, set(), 0, 0)
        self.assertEqual(resumen(p), ["18:00 Correr"])

    def test_texto_hablado(self):
        p = plan(SABADO, hechas={1: 1}, estudio=20)
        texto, hablado = describir_plan(p)
        self.assertTrue(texto.startswith("• 06:00–06:40 · Correr (llevas 0 de 2 esta semana)"))
        self.assertEqual(hablado, "Te sugiero Correr a las 6 de la mañana, estudiar a las 6 y 50 de la mañana "
                                  "y Gimnasio a las 12 del mediodía.")
        self.assertEqual(lunes_de(SABADO), date(2026, 10, 19))


class TestActividadesHechas(unittest.TestCase):
    def test_se_cuentan_por_dia(self):
        with tempfile.TemporaryDirectory() as carpeta:
            a = Almacen(Path(carpeta) / "t.db")
            g = a.agregar_actividad(Actividad("Gimnasio", 60, 3))
            self.assertTrue(a.marcar_actividad(g.id, date(2026, 10, 20)))
            self.assertFalse(a.marcar_actividad(g.id, date(2026, 10, 20)))        # una vez por día
            a.marcar_actividad(g.id, date(2026, 10, 22))
            a.marcar_actividad(g.id, date(2026, 10, 12))                          # semana pasada
            self.assertEqual(a.actividades_hechas(date(2026, 10, 19), date(2026, 10, 25)),
                             {g.id: [date(2026, 10, 20), date(2026, 10, 22)]})
            self.assertTrue(a.marcar_actividad(g.id, date(2026, 10, 22), False))
            a.borrar_actividad(g.id)
            self.assertEqual(a.actividades_hechas(date(2026, 1, 1), date(2026, 12, 31)), {})
            a.con.close()


@unittest.skipIf(QApplication is None, "PySide6 no está instalado")
class TestAsistenteV315(unittest.TestCase):
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

    def tearDown(self):
        self.a.salir()
        self.a.almacen.con.close()
        self.tmp.cleanup()

    def comando(self, texto, por_voz=False):
        from nucleo.comandos import interpretar_comando
        self.dichos.clear()
        self.a.burbuja.ocultar()
        self.a.ejecutar_comando(interpretar_comando(texto), por_voz=por_voz)

    def test_sin_datos_pide_conocerte(self):
        self.comando("¿qué hago hoy?", por_voz=True)
        self.assertIn("necesito conocerte", self.a.burbuja.titulo.text())
        self.assertEqual(self.dichos, ["Primero cuéntame tu horario y qué te gusta hacer."])

    def test_sugerir_y_contar_actividad(self):
        self.a.agregar_actividad("gimnasio 1 hora 3 veces por semana")
        self.comando("recomiéndame algo para mañana")
        self.assertEqual(self.a.burbuja.cabecera.text(), "Para mañana")
        self.assertIn("Gimnasio (llevas 0 de 3 esta semana)", self.a.burbuja.titulo.text())
        self.comando("ya fui al gimnasio", por_voz=True)
        self.assertEqual(self.a.burbuja.titulo.text(), "Gimnasio: 1 de 3 esta semana")
        self.assertEqual(self.dichos, ["¡Bien! Gimnasio: 1 de 3 esta semana."])
        self.comando("¿qué hago hoy?")
        self.assertNotIn("Gimnasio", self.a.burbuja.titulo.text())          # ya lo hiciste hoy
        self.comando("hice natación")
        self.assertIn("no está en tus actividades", self.a.burbuja.titulo.text())

    def test_boton_y_tarea_completada_cuentan(self):
        self.a.agregar_actividad("leer 30 min 5 veces por semana")
        [leer] = self.a.perfil.actividades
        hoy = date.today()
        self.a.panel.actividad_hecha_pedido.emit(leer.id)
        self.assertEqual(self.a.almacen.actividades_hechas(hoy, hoy), {leer.id: [hoy]})
        self.a.panel.actividad_hecha_pedido.emit(leer.id)                      # desmarcar
        self.assertEqual(self.a.almacen.actividades_hechas(hoy, hoy), {})
        t = self.a.almacen.agregar("Leer el libro de redes", datetime.now() + timedelta(hours=1))
        self.a.completar(t.id)
        self.assertEqual(self.a.almacen.actividades_hechas(hoy, hoy), {leer.id: [hoy]})

    def test_aviso_al_quedar_libre_una_sola_vez(self):
        self.modulo.segundos_inactivo = lambda: 0
        self.a.agregar_actividad("gimnasio 1 hora 3 veces por semana")
        dia = date.today()
        todos = tuple(range(7))
        from nucleo.horario import Bloque
        self.a.almacen.agregar_bloque(Bloque(todos, time(9), time(17), "Trabajo"))
        salida = datetime.combine(dia, time(17, 5))
        self.a._sugerir_al_quedar_libre(salida)
        self.assertEqual(self.a.burbuja.cabecera.text(), "Tienes un hueco libre")
        texto = self.a.burbuja.titulo.text()
        self.assertTrue(texto.startswith("Estás libre hasta las "), texto)
        self.assertIn("¿Qué tal ", texto)
        self.assertIn("Gimnasio", texto)                                        # ahora o "Después:"
        self.a.burbuja.ocultar()
        self.a.avisos.cola.clear()
        self.a._sugerir_al_quedar_libre(salida + timedelta(minutes=1))          # el mismo hueco: no repite
        self.assertFalse(self.a.burbuja.isVisible())
        self.a._sugerir_al_quedar_libre(datetime.combine(dia, time(12, 0)))     # en pleno trabajo: nada
        self.assertFalse(self.a.burbuja.isVisible())

    def test_saludo_y_panel_muestran_la_sugerencia(self):
        from nucleo.horario import Bloque
        self.a.agregar_actividad("gimnasio 1 hora 3 veces por semana")
        self.a.almacen.agregar_bloque(Bloque((6,), time(3), time(4), "Algo los domingos de madrugada"))
        self.a.saludar(forzado=True)
        texto = self.a.burbuja.titulo.text()
        if self.a.plan_del_dia(date.today()):                                 # si a esta hora queda hueco
            self.assertIn("Te sugiero:", texto)
            self.assertTrue(self.a.panel.sugerencias_hoy.text().startswith("Te sugiero:"))


if __name__ == "__main__":
    unittest.main()
