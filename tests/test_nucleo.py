"""
Pruebas del núcleo (sin interfaz). Ejecutar desde la carpeta del proyecto:
    python -m unittest discover tests -v
Usan una fecha fija (miércoles 07/10/2026 06:30) para que siempre den igual.
"""
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from nucleo.almacen import Almacen                       # noqa: E402
from nucleo.interprete import interpretar                 # noqa: E402
from nucleo.planificador import estado_del_dia, siguiente_ocurrencia  # noqa: E402

AHORA = datetime(2026, 10, 7, 6, 30)   # miércoles


class TestInterprete(unittest.TestCase):
    CASOS = [
        # texto,                                         título esperado,      fecha esperada,               repetición
        ("mañana 8pm pagar la luz",                      "Pagar la luz",       datetime(2026, 10, 8, 20, 0),  None),
        ("en 20 minutos estirar la espalda",             "Estirar la espalda", datetime(2026, 10, 7, 6, 50),  None),
        ("en media hora sacar la ropa",                  "Sacar la ropa",      datetime(2026, 10, 7, 7, 0),   None),
        ("el viernes a las 3 llamar al banco",           "Llamar al banco",    datetime(2026, 10, 9, 15, 0),  None),
        ("15/10 10:30 entregar informe",                 "Entregar informe",   datetime(2026, 10, 15, 10, 30), None),
        ("el 20 de octubre cumple de Juan",              "Cumple de Juan",     datetime(2026, 10, 20, 9, 0),  "anual"),  # cumpleaños: cada año
        ("cada lunes 9am reunión de equipo",             "Reunión de equipo",  datetime(2026, 10, 12, 9, 0),  "semanal"),
        ("tomar pastilla todos los días a las 10 de la noche", "Tomar pastilla", datetime(2026, 10, 7, 22, 0), "diaria"),
        ("esta noche a las 8 llamar a mamá",             "Llamar a mamá",      datetime(2026, 10, 7, 20, 0),  None),
        ("recuérdame que mañana por la tarde debo ir al banco", "Debo ir al banco", datetime(2026, 10, 8, 15, 0), None),
        ("a las 8 de la mañana correr",                  "Correr",             datetime(2026, 10, 7, 8, 0),   None),
        ("al mediodía almorzar",                         "Almorzar",           datetime(2026, 10, 7, 12, 0),  None),
        ("a la 1 y media cita",                          "Cita",               datetime(2026, 10, 7, 13, 30), None),
    ]

    def test_casos(self):
        for texto, titulo, fecha, rep in self.CASOS:
            with self.subTest(texto=texto):
                r = interpretar(texto, AHORA)
                self.assertEqual(r.titulo, titulo)
                self.assertEqual(r.fecha, fecha)
                self.assertEqual(r.repeticion, rep)

    def test_numero_suelto_no_es_hora(self):
        r = interpretar("comprar 2 panes", AHORA)
        self.assertEqual(r.titulo, "Comprar 2 panes")
        self.assertIsNone(r.fecha)

    def test_fecha_imposible_no_se_usa(self):
        self.assertIsNone(interpretar("revisar 31/02", AHORA).fecha)


class TestPlanificador(unittest.TestCase):
    def test_laborables_salta_fin_de_semana(self):
        viernes = datetime(2026, 10, 9, 7, 0)
        self.assertEqual(siguiente_ocurrencia(viernes, "laborables", viernes),
                         datetime(2026, 10, 12, 7, 0))      # lunes

    def test_mensual_dia_31(self):
        enero31 = datetime(2027, 1, 31, 9, 0)
        self.assertEqual(siguiente_ocurrencia(enero31, "mensual", enero31),
                         datetime(2027, 2, 28, 9, 0))

    def test_salta_ocurrencias_perdidas(self):
        # Laptop apagada 3 días: no se acumulan avisos, se va a la próxima futura
        hace3 = datetime(2026, 10, 4, 22, 0)
        self.assertEqual(siguiente_ocurrencia(hace3, "diaria", AHORA),
                         datetime(2026, 10, 7, 22, 0))

    def test_estados(self):
        hoy = [datetime(2026, 10, 7, 20, 0)]
        self.assertEqual(estado_del_dia(hoy, True, AHORA, 23, 6), "alerta")
        self.assertEqual(estado_del_dia(hoy, False, AHORA, 23, 6), "pendiente")
        self.assertEqual(estado_del_dia([], False, AHORA, 23, 6), "tranquilo")
        self.assertEqual(estado_del_dia([], False, AHORA.replace(hour=23, minute=40), 23, 6), "dormido")


class TestAlmacen(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.a = Almacen(Path(self.tmp.name) / "t.db")

    def tearDown(self):
        self.a.con.close()
        self.tmp.cleanup()

    def test_ciclo_completo(self):
        t = self.a.agregar("Pagar luz", datetime(2026, 10, 7, 6, 0))
        self.assertEqual([x.id for x in self.a.por_avisar(AHORA)], [t.id])
        self.a.marcar_avisada(t.id)
        self.assertEqual(self.a.por_avisar(AHORA), [])        # no avisa dos veces
        self.a.posponer(t.id, 10, AHORA)
        self.assertEqual(self.a.obtener(t.id).fecha, datetime(2026, 10, 7, 6, 40))
        self.a.completar(t.id, AHORA)
        self.assertEqual(self.a.pendientes(), [])

    def test_editar_reinicia_aviso(self):
        t = self.a.agregar("Pagar luz", datetime(2026, 10, 7, 6, 0))
        self.a.marcar_avisada(t.id)
        self.a.editar(t.id, "Pagar luz y agua", datetime(2026, 10, 7, 9, 0), "mensual")
        e = self.a.obtener(t.id)
        self.assertEqual((e.titulo, e.fecha, e.repeticion, e.avisada),
                         ("Pagar luz y agua", datetime(2026, 10, 7, 9, 0), "mensual", False))

    def test_repetitiva_se_reprograma(self):
        t = self.a.agregar("Agua", datetime(2026, 10, 7, 6, 0), "diaria")
        self.a.completar(t.id, AHORA)
        quedo = self.a.obtener(t.id)
        self.assertEqual(quedo.estado, "pendiente")
        self.assertEqual(quedo.fecha, datetime(2026, 10, 8, 6, 0))


class TestRespaldo(unittest.TestCase):
    def test_respaldo_diario_y_rotacion(self):
        from datetime import date, timedelta
        from nucleo.respaldo import hacer_respaldo
        with tempfile.TemporaryDirectory() as tmp:
            bd = Path(tmp) / "tareas.db"
            a = Almacen(bd)
            a.agregar("Pagar luz", datetime(2026, 10, 9, 20, 0))
            carpeta = Path(tmp) / "respaldos"
            dia = date(2026, 10, 1)
            for i in range(10):                                   # 10 días seguidos
                self.assertIsNotNone(hacer_respaldo(bd, carpeta, dia + timedelta(days=i), conservar=7))
            self.assertIsNone(hacer_respaldo(bd, carpeta, dia + timedelta(days=9)))   # ya existe el de hoy
            nombres = sorted(p.name for p in carpeta.iterdir())
            self.assertEqual(len(nombres), 7)
            self.assertEqual(nombres[0], "tareas-2026-10-04.db")  # se borraron los 3 más viejos
            # La copia es una base válida con los datos
            copia = Almacen(carpeta / nombres[-1])
            self.assertEqual([t.titulo for t in copia.pendientes()], ["Pagar luz"])
            copia.con.close()
            a.con.close()


if __name__ == "__main__":
    unittest.main()
