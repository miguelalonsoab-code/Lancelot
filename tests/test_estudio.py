"""
Pruebas del modo estudio (sin interfaz):
    python -m unittest discover tests -v
"""
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from nucleo.almacen import Almacen                                   # noqa: E402
from nucleo.comandos import interpretar_comando                       # noqa: E402
from nucleo.distraccion import clave_ventana, detectar_distraccion    # noqa: E402
from nucleo.frases import SelectorFrases                              # noqa: E402
from nucleo.pomodoro import DESCANSO, DESCANSO_LARGO, ENFOQUE, ESPERANDO, Pomodoro  # noqa: E402

T0 = datetime(2026, 10, 8, 19, 0)


def minutos(n):
    return T0 + timedelta(minutes=n)


class TestPomodoro(unittest.TestCase):
    def test_ciclo_normal(self):
        p = Pomodoro(25, 5, 15, 4)
        p.iniciar_enfoque(T0)
        self.assertEqual(p.fase, ENFOQUE)
        self.assertEqual(p.avanzar(minutos(24)), [])
        self.assertEqual(p.avanzar(minutos(25)), ["fin_enfoque"])
        self.assertEqual(p.fase, DESCANSO)
        self.assertEqual(p.avanzar(minutos(30)), ["fin_descanso"])
        self.assertEqual(p.fase, ESPERANDO)            # espera confirmación
        self.assertEqual(p.avanzar(minutos(60)), [])   # no arranca solo

    def test_descanso_largo_cada_4(self):
        p = Pomodoro(25, 5, 15, 4)
        t = T0
        for _ in range(3):
            p.iniciar_enfoque(t)
            p.avanzar(t + timedelta(minutes=25))
            p.avanzar(t + timedelta(minutes=30))
            t += timedelta(minutes=30)
        p.iniciar_enfoque(t)
        p.avanzar(t + timedelta(minutes=25))
        self.assertEqual(p.fase, DESCANSO_LARGO)
        self.assertEqual(p.completados, 4)

    def test_pausa_congela_el_tiempo(self):
        p = Pomodoro(25, 5)
        p.iniciar_enfoque(T0)
        p.pausar(minutos(10))
        self.assertEqual(p.restante(minutos(40)), timedelta(minutes=15))
        self.assertEqual(p.avanzar(minutos(40)), [])
        p.reanudar(minutos(40))
        self.assertEqual(p.avanzar(minutos(55)), ["fin_enfoque"])

    def test_minutos_enfocados_cuenta_parcial(self):
        p = Pomodoro(25, 5)
        p.iniciar_enfoque(T0)
        p.avanzar(minutos(25))
        p.saltar_descanso(minutos(26))
        p.cortar_enfoque(minutos(36))                  # 10 min del segundo
        self.assertEqual(p.minutos_enfocados(minutos(36)), 35)


class TestComandos(unittest.TestCase):
    def test_comandos(self):
        casos = {
            "modo estudio": ("estudio", None),
            "Ponte en modo estudio": ("estudio", None),
            "modo estudio 50": ("estudio", 50),
            "modo estudio de 45 minutos": ("estudio", 45),
            "pomodoro": ("estudio", None),
            "a estudiar!": ("estudio", None),
            "pausa": ("pausa", None),
            "seguir": ("seguir", None),
            "terminar": ("terminar", None),
            "modo silencio": ("silencio", None),
            "no molestar": ("silencio", None),
            "modo normal": ("normal", None),
            "¿cuánto estudié hoy?": ("resumen", None),
        }
        for texto, (accion, mins) in casos.items():
            with self.subTest(texto=texto):
                c = interpretar_comando(texto)
                self.assertIsNotNone(c)
                self.assertEqual((c.accion, c.minutos), (accion, mins))

    def test_tareas_no_son_comandos(self):
        for texto in ["estudiar para el examen mañana 8pm", "pausa activa a las 4",
                      "terminar el informe", "comprar pan"]:
            with self.subTest(texto=texto):
                self.assertIsNone(interpretar_comando(texto))


class TestDistraccion(unittest.TestCase):
    LISTA = {"youtube": "YouTube", "steam.exe": "Steam"}

    def test_detecta(self):
        self.assertEqual(detectar_distraccion("(3) Gatitos - YouTube - Google Chrome",
                                              "chrome.exe", self.LISTA, set()), "YouTube")
        self.assertEqual(detectar_distraccion("Steam", "steam.exe", self.LISTA, set()), "Steam")
        self.assertIsNone(detectar_distraccion("cara.py - VS Code", "code.exe", self.LISTA, set()))

    def test_permitida(self):
        titulo = "(3) Clase SQL - YouTube - Google Chrome"
        permitidas = {clave_ventana(titulo, "chrome.exe")}
        otra_vez = "(5) Clase SQL - YouTube - Google Chrome"   # cambió el contador
        self.assertIsNone(detectar_distraccion(otra_vez, "chrome.exe", self.LISTA, permitidas))


class TestFrasesYSesiones(unittest.TestCase):
    def test_frase_con_datos(self):
        s = SelectorFrases({"x": ["Llevas {n} pomodoros"]})
        self.assertEqual(s.elegir("x", n=3), "Llevas 3 pomodoros")

    def test_no_repite_la_ultima(self):
        s = SelectorFrases({"x": ["a", "b"]})
        anteriores = [s.elegir("x") for _ in range(10)]
        self.assertTrue(all(a != b for a, b in zip(anteriores, anteriores[1:])))

    def test_resumen_y_racha(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = Almacen(Path(tmp) / "t.db")
            hoy = date(2026, 10, 8)
            for dias_atras in (0, 1, 2, 4):          # el día 3 falta: rompe la racha
                d = datetime.combine(hoy - timedelta(days=dias_atras), datetime.min.time()).replace(hour=19)
                a.guardar_sesion(d, d + timedelta(minutes=50), 2, 50, 0)
            self.assertEqual(a.resumen_dia(hoy), (2, 50))
            self.assertEqual(a.racha(hoy), 3)
            self.assertEqual(a.racha(hoy + timedelta(days=1)), 3)   # mañana sin estudiar aún
            a.con.close()


if __name__ == "__main__":
    unittest.main()
