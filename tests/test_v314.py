"""
v3.14: duración en tareas y eventos ("examen el viernes de 8 a 10") y excepciones al horario
("el 1 de noviembre no trabajo", "vacaciones del 20 al 30 de diciembre").

    python -m unittest tests.test_v314 -v
"""
import os
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from nucleo.almacen import Almacen                                        # noqa: E402
from nucleo.horario import (Bloque, Excepcion, choque, describir_libre, huecos,   # noqa: E402
                            interpretar_bloque, interpretar_excepcion)
from nucleo.interprete import describir_rango, interpretar                 # noqa: E402

try:
    from PySide6.QtWidgets import QApplication
except ImportError:
    QApplication = None

HOY = date(2026, 10, 21)                     # miércoles
AHORA = datetime(2026, 10, 21, 10, 0)
TRABAJO = interpretar_bloque("de lunes a viernes de 8:30 a 5:30 trabajo en Sanna")
CLASES = interpretar_bloque("martes y jueves de 7 a 10 de la noche clase de redes")


class TestDuracion(unittest.TestCase):
    def test_rangos_y_duraciones(self):
        casos = {
            "examen el viernes de 8 a 10": ("Examen", datetime(2026, 10, 23, 8, 0), 120),
            "reunión mañana de 3 a 4:30 pm": ("Reunión", datetime(2026, 10, 22, 15, 0), 90),
            "cine el sábado 7pm durante 2 horas": ("Cine", datetime(2026, 10, 24, 19, 0), 120),
            "mañana a las 9 pagar la luz": ("Pagar la luz", datetime(2026, 10, 22, 9, 0), None),
        }
        for texto, (titulo, fecha, minutos) in casos.items():
            r = interpretar(texto, AHORA)
            self.assertEqual((r.titulo, r.fecha, r.duracion), (titulo, fecha, minutos), texto)
        self.assertEqual(describir_rango(datetime(2026, 10, 23, 8, 0), 120), "08:00–10:00")

    def test_se_guarda_y_sincroniza(self):
        with tempfile.TemporaryDirectory() as carpeta:
            a = Almacen(Path(carpeta) / "t.db")
            t = a.agregar("Examen", datetime(2026, 10, 23, 8, 0), None, "evento", "7,1", 120)
            self.assertEqual((a.obtener(t.id).duracion, f"{a.obtener(t.id).fin:%H:%M}"), (120, "10:00"))
            [c] = a.cambios_por_subir()
            self.assertEqual(c["duracion"], 120)
            sin_clave = {k: v for k, v in c.items() if k != "duracion"}
            a.aplicar_remotos([{**sin_clave, "titulo": "Examen final", "actualizada": c["actualizada"] + 1000}])
            self.assertEqual((a.obtener(t.id).titulo, a.obtener(t.id).duracion), ("Examen final", 120))  # se conserva
            a.editar(t.id, "Examen final", t.fecha, None, duracion=None)                # se puede quitar
            self.assertIsNone(a.obtener(t.id).duracion)
            a.con.close()


class TestExcepciones(unittest.TestCase):
    def test_frases(self):
        casos = {
            "el 1 de noviembre no trabajo": ("2026-11-01", "2026-11-01", "traba", "No trabajo"),
            "Vacaciones del 20 al 30 de diciembre": ("2026-12-20", "2026-12-30", "", "Vacaciones"),
            "mañana no tengo clases": ("2026-10-22", "2026-10-22", "clase", "No tengo clases"),
            "el viernes es feriado": ("2026-10-23", "2026-10-23", "", "Feriado"),
            "el 15 tengo libre": ("2026-11-15", "2026-11-15", "", "Día libre"),       # el 15 de octubre ya pasó
            "del 28 de diciembre al 3 de enero son mis vacaciones": ("2026-12-28", "2027-01-03", "", "Vacaciones"),
            "no voy al gimnasio el lunes": ("2026-10-26", "2026-10-26", "gimna", "No voy al gimnasio"),
        }
        for texto, (desde, hasta, filtro, titulo) in casos.items():
            e = interpretar_excepcion(texto, HOY)
            self.assertIsInstance(e, Excepcion, texto)
            self.assertEqual((e.desde.isoformat(), e.hasta.isoformat(), e.filtro, e.titulo),
                             (desde, hasta, filtro, titulo), texto)

    def test_lo_que_falta_se_explica(self):
        self.assertIn("¿Qué día?", interpretar_excepcion("no trabajo", HOY))
        self.assertIn("después del final", interpretar_excepcion("del 5 al 2 de mayo no trabajo", HOY))

    def test_libera_solo_lo_que_dice(self):
        jueves = date(2026, 10, 22)
        no_clases = interpretar_excepcion("mañana no tengo clases", HOY)
        normal = huecos(jueves, [TRABAJO, CLASES], 6, 23)
        con_excepcion = huecos(jueves, [TRABAJO, CLASES], 6, 23, excepciones=[no_clases])
        self.assertEqual(describir_libre(normal), "06:00–08:30 (2 h 30 min) · 17:30–19:00 (1 h 30 min) · "
                                                  "22:00–23:00 (1 h)")
        self.assertEqual(describir_libre(con_excepcion), "06:00–08:30 (2 h 30 min) · 17:30–23:00 (5 h 30 min)")
        feriado = interpretar_excepcion("mañana es feriado", HOY)
        self.assertEqual(describir_libre(huecos(jueves, [TRABAJO, CLASES], 6, 23, excepciones=[feriado])),
                         "06:00–23:00 (17 h)")

    def test_tareas_con_duracion_restan(self):
        sabado = date(2026, 10, 24)
        examen = (datetime(2026, 10, 24, 8, 0), datetime(2026, 10, 24, 10, 0), "Examen")
        otro_dia = (datetime(2026, 10, 25, 8, 0), datetime(2026, 10, 25, 10, 0), "Otro")
        self.assertEqual(describir_libre(huecos(sabado, [TRABAJO], 6, 23, extras=[examen, otro_dia])),
                         "06:00–08:00 (2 h) · 10:00–23:00 (13 h)")

    def test_choque(self):
        viernes = datetime(2026, 10, 23, 8, 0)
        self.assertEqual(choque(viernes, 120, [TRABAJO]).titulo, "Trabajo en Sanna")       # 8–10 vs 8:30–17:30
        self.assertIsNone(choque(viernes, 30, [TRABAJO]))                                  # 8:00–8:30 justo antes
        self.assertIsNone(choque(viernes.replace(hour=12), None, [TRABAJO],
                                 [interpretar_excepcion("el viernes no trabajo", HOY)]))
        self.assertEqual(choque(viernes.replace(hour=12), None, [TRABAJO]).titulo, "Trabajo en Sanna")
        self.assertIsNone(choque(datetime(2026, 10, 24, 9, 0), 60, [TRABAJO]))            # sábado

    def test_se_guardan(self):
        with tempfile.TemporaryDirectory() as carpeta:
            a = Almacen(Path(carpeta) / "t.db")
            vieja = a.agregar_excepcion(Excepcion(date(2026, 8, 1), date(2026, 8, 2), "", "Feriado"))
            nueva = a.agregar_excepcion(interpretar_excepcion("el 1 de noviembre no trabajo", HOY))
            self.assertEqual([e.titulo for e in a.excepciones(HOY)], ["No trabajo"])        # las pasadas no se listan
            self.assertEqual(a.limpiar_excepciones(HOY), 1)                                 # y se borran tras 30 días
            self.assertTrue(a.borrar_excepcion(nueva.id))
            self.assertFalse(a.borrar_excepcion(vieja.id))
            self.assertEqual(a.excepciones(HOY), [])
            a.con.close()


@unittest.skipIf(QApplication is None, "PySide6 no está instalado")
class TestAsistenteV314(unittest.TestCase):
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
        self.a._avisos_en_pausa_hasta = None
        self.a.burbuja.ocultar()
        self.a.almacen.agregar_bloque(Bloque(tuple(range(7)), TRABAJO.inicio, TRABAJO.fin, "Trabajo en Sanna"))
        self.manana = date.today() + timedelta(days=1)

    def tearDown(self):
        self.a.salir()
        self.a.almacen.con.close()
        self.tmp.cleanup()

    def comando(self, texto, por_voz=False):
        from nucleo.comandos import interpretar_comando
        self.dichos.clear()
        self.a.burbuja.ocultar()
        self.a.ejecutar_comando(interpretar_comando(texto), por_voz=por_voz)

    def test_evento_que_se_cruza_avisa(self):
        inicio = datetime.combine(self.manana, TRABAJO.inicio) + timedelta(hours=1)
        self.a.agregar("Examen", inicio, None, "evento", "7,1", 120)
        self.assertEqual(self.a.burbuja.cabecera.text(), "⚠ Se cruza con tu horario")
        self.assertIn("«Examen» se cruza con Trabajo en Sanna (08:30–17:30)", self.a.burbuja.titulo.text())
        self.a.burbuja.ocultar()
        self.a.agregar("Llamar al banco", inicio, None)                         # tarea de un momento: no avisa
        self.assertFalse(self.a.burbuja.isVisible())
        self.assertIsNone(self.a.texto_choque(inicio, None, "tarea"))
        self.assertEqual(self.a.texto_choque(inicio, 60, "tarea"), "Trabajo en Sanna (08:30–17:30)")

    def test_excepcion_por_comando_libera_y_se_lista(self):
        dia = self.manana.day
        antes = describir_libre(self.a.horas_libres(self.manana))
        self.comando(f"el {dia} no voy a trabajo en sanna", por_voz=True)
        self.assertEqual(self.a.burbuja.cabecera.text(), "🏖 Anotado")
        self.assertEqual(self.dichos, ["Listo, ese día no cuento Trabajo en Sanna."])
        despues = describir_libre(self.a.horas_libres(self.manana))
        self.assertNotEqual(antes, despues)
        self.assertNotIn("17:30", despues)
        # y ya no avisa de choque ese día
        self.assertIsNone(self.a.texto_choque(datetime.combine(self.manana, TRABAJO.inicio), 60, "evento"))
        self.comando("mis días libres")
        self.assertIn("No voy a trabajo", self.a.burbuja.titulo.text())
        textos = [self.a.panel.lista_horario.item(i).text() for i in range(self.a.panel.lista_horario.count())]
        self.assertTrue(any(t.startswith("🏖 DÍAS LIBRES") for t in textos))

    def test_filtro_que_no_existe_no_se_guarda(self):
        self.comando("mañana no voy al gimnasio")
        self.assertIn("No encontré nada parecido a «gimnasio»", self.a.burbuja.titulo.text())
        self.assertEqual(self.a.almacen.excepciones(), [])

    def test_campo_del_horario_acepta_excepciones_y_tareas_restan(self):
        p = self.a.panel
        p.entrada_bloque.setText("mañana es feriado")
        p._al_agregar_bloque()
        self.assertEqual(p.entrada_bloque.text(), "")
        self.assertEqual([e.titulo for e in self.a.almacen.excepciones()], ["Feriado"])
        completo = self.a.horas_libres(self.manana)
        self.a.agregar("Cine", datetime.combine(self.manana, TRABAJO.inicio), None, "evento", None, 120)
        con_cine = self.a.horas_libres(self.manana)
        self.assertEqual(sum((b - a for a, b in completo), timedelta()) - sum((b - a for a, b in con_cine),
                                                                                  timedelta()), timedelta(hours=2))

    def test_vista_previa_del_panel(self):
        p = self.a.panel
        dia = self.manana
        p.entrada.setText(f"examen el {dia.day}/{dia.month} de 9 a 11")
        self.assertIn("09:00–11:00", p.vista.text())
        self.assertIn("⚠ se cruza con Trabajo en Sanna", p.vista.text())


if __name__ == "__main__":
    unittest.main()
