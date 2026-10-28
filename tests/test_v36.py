"""
Pruebas de la versión 3.6: saludo del día, tareas vencidas y semana de estudio.
Lógica pura con fechas fijas (sábado 10/10/2026) para que siempre den igual.

    python -m unittest tests.test_v36 -v
"""
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from nucleo.almacen import Almacen, Tarea                                    # noqa: E402
from nucleo.comandos import interpretar_comando                              # noqa: E402
from nucleo.estadisticas import describir_semana, rango, resumen_semana, variacion  # noqa: E402
from nucleo.interprete import describir_atraso                               # noqa: E402
from nucleo.planificador import a_manana, opciones_reprogramar               # noqa: E402
from nucleo.saludo import armar_saludo, debe_saludar, momento_del_dia        # noqa: E402

AHORA = datetime(2026, 10, 10, 10, 0)     # sábado 10:00


def tarea(id_, titulo, fecha, repeticion=None):
    return Tarea(id_, titulo, fecha, repeticion, "pendiente", False)


class TestVencidas(unittest.TestCase):
    def test_opciones_de_tarea_vencida_ayer_en_la_noche(self):
        opciones = opciones_reprogramar(datetime(2026, 10, 9, 20, 0), AHORA)
        self.assertEqual(opciones, [
            ("En 1 hora", datetime(2026, 10, 10, 11, 0)),
            ("Hoy a las 20:00", datetime(2026, 10, 10, 20, 0)),     # "esta noche" sería igual: se quita
            ("Mañana a las 20:00", datetime(2026, 10, 11, 20, 0)),
            ("Mañana a las 09:00", datetime(2026, 10, 11, 9, 0)),
        ])

    def test_opciones_de_noche_sin_esta_noche(self):
        tarde = datetime(2026, 10, 10, 19, 30)
        etiquetas = [e for e, _ in opciones_reprogramar(datetime(2026, 10, 10, 9, 0), tarde)]
        self.assertEqual(etiquetas, ["En 1 hora", "Mañana a las 09:00"])   # 9:00 mañana sale una sola vez

    def test_a_manana_misma_hora(self):
        self.assertEqual(a_manana(datetime(2026, 10, 3, 7, 15), AHORA), datetime(2026, 10, 11, 7, 15))

    def test_describir_atraso(self):
        self.assertEqual(describir_atraso(AHORA - timedelta(minutes=12), AHORA), "venció hace 12 min")
        self.assertEqual(describir_atraso(datetime(2026, 10, 10, 8, 0), AHORA), "venció hoy 08:00")
        self.assertEqual(describir_atraso(datetime(2026, 10, 9, 20, 0), AHORA), "venció ayer 20:00")
        self.assertEqual(describir_atraso(datetime(2026, 10, 7, 9, 0), AHORA), "venció hace 3 días (mié 07/10)")

    def test_almacen_vencidas_y_reprogramar(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = Almacen(Path(tmp) / "t.db")
            vieja = a.agregar("Pagar la luz", datetime(2026, 10, 9, 20, 0))
            a.agregar("Clase", datetime(2026, 10, 10, 15, 0))
            a.marcar_avisada(vieja.id)
            self.assertEqual([t.titulo for t in a.vencidas(AHORA)], ["Pagar la luz"])
            a.reprogramar(vieja.id, datetime(2026, 10, 11, 20, 0))
            movida = a.obtener(vieja.id)
            self.assertEqual((movida.titulo, movida.fecha, movida.avisada),
                             ("Pagar la luz", datetime(2026, 10, 11, 20, 0), False))
            self.assertEqual(a.vencidas(AHORA), [])
            a.con.close()

    def test_comandos(self):
        casos = {"qué tengo vencido": "vencidas", "pasa las vencidas a mañana": "vencidas_manana",
                 "mueve todas las tareas vencidas para mañana": "vencidas_manana",
                 "buenos días": "saludo", "hola": "saludo", "resumen semanal": "semana",
                 "cómo voy esta semana": "semana", "resumen": "resumen"}
        for texto, accion in casos.items():
            with self.subTest(texto=texto):
                self.assertEqual(interpretar_comando(texto).accion, accion)
        self.assertIsNone(interpretar_comando("mañana 8pm pagar las vencidas"))   # eso es una tarea


class TestSaludo(unittest.TestCase):
    def test_una_vez_por_dia_y_no_de_madrugada(self):
        self.assertTrue(debe_saludar(AHORA, "2026-10-09", 6))
        self.assertFalse(debe_saludar(AHORA, "2026-10-10", 6))              # ya saludó hoy
        self.assertFalse(debe_saludar(datetime(2026, 10, 10, 4, 0), None, 6))
        self.assertTrue(debe_saludar(AHORA, None, 6))                       # primera vez

    def test_momento(self):
        self.assertEqual(momento_del_dia(8), "Buenos días")
        self.assertEqual(momento_del_dia(15), "Buenas tardes")
        self.assertEqual(momento_del_dia(21), "Buenas noches")

    def test_saludo_completo(self):
        pendientes = [tarea(1, "Pagar la luz", datetime(2026, 10, 9, 20, 0)),     # vencida
                      tarea(2, "Llamar al banco", datetime(2026, 10, 10, 14, 30)),
                      tarea(3, "Clase de redes", datetime(2026, 10, 10, 18, 0)),
                      tarea(4, "Examen", datetime(2026, 10, 12, 8, 0))]           # otro día: no sale
        s = armar_saludo(AHORA, pendientes, racha=4, nombre="Miguel")
        self.assertEqual(s.titulo, "Buenos días, Miguel")
        self.assertEqual(s.texto, "Hoy tienes 2 pendientes:\n• 14:30 Llamar al banco\n• 18:00 Clase de redes\n"
                                  "1 vencida sin resolver\nRacha de estudio: 4 días. ¡Que no se corte!")
        self.assertEqual(s.hablado, "Buenos días, Miguel. Hoy tienes 2 pendientes. La primera es Llamar al banco, "
                                    "a las 2 y media de la tarde. Además tienes una tarea vencida. "
                                    "Llevas 4 días seguidos estudiando. ¡Que no se corte!")

    def test_saludo_dia_libre(self):
        s = armar_saludo(datetime(2026, 10, 10, 20, 0), [], racha=1, nombre="Miguel")
        self.assertEqual((s.titulo, s.texto), ("Buenas noches, Miguel", "Hoy no tienes nada agendado."))


class TestSemana(unittest.TestCase):
    HOY = date(2026, 10, 10)

    def test_resumen(self):
        datos = {date(2026, 10, 10): (2, 50), date(2026, 10, 8): (4, 110), date(2026, 10, 4): (1, 25),
                 date(2026, 10, 1): (3, 75), date(2026, 10, 3): (1, 25)}   # los dos últimos: semana anterior
        r = resumen_semana(datos, self.HOY, meta=100)
        self.assertEqual([d.fecha for d in r.dias][0], date(2026, 10, 4))
        self.assertEqual([d.minutos for d in r.dias], [25, 0, 0, 0, 110, 0, 50])
        self.assertEqual((r.total, r.total_anterior, r.promedio, r.dias_con_estudio, r.dias_meta),
                         (185, 100, 26, 3, 1))
        self.assertEqual(r.mejor.fecha, date(2026, 10, 8))
        self.assertEqual(variacion(r), "+85 % que la semana anterior")
        self.assertEqual(rango(r), "4 – 10 oct")
        texto, hablado = describir_semana(r)
        self.assertIn("Mejor día: jueves (1 h 50)", texto)
        self.assertTrue(hablado.startswith("En los últimos 7 días estudiaste 3 horas y 5 minutos, 3 de 7 días"))

    def test_semana_vacia_y_cambio_de_mes(self):
        r = resumen_semana({}, date(2026, 10, 2))
        self.assertEqual(rango(r), "26 sep – 2 oct")
        self.assertEqual(describir_semana(r)[0], "Sin sesiones de estudio en estos 7 días.")
        self.assertIsNone(r.mejor)

    def test_almacen_agrupa_por_dia(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = Almacen(Path(tmp) / "t.db")
            a.guardar_sesion(datetime(2026, 10, 9, 8), datetime(2026, 10, 9, 9), 2, 50, 0)
            a.guardar_sesion(datetime(2026, 10, 9, 20), datetime(2026, 10, 9, 21), 1, 25, 0)
            a.guardar_sesion(datetime(2026, 9, 1, 8), datetime(2026, 9, 1, 9), 2, 50, 0)     # fuera del rango
            self.assertEqual(a.estudio_por_dia(date(2026, 9, 27), self.HOY), {date(2026, 10, 9): (3, 75)})
            a.con.close()


if __name__ == "__main__":
    unittest.main()
