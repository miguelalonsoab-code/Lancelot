"""
v3.11: frases habladas, hora de avisos configurable, "ya avisé" sincronizado, secciones de la lista
y aprender de las correcciones Tarea/Evento.

    python -m unittest tests.test_v311 -v
"""
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from nucleo import aprendizaje                                            # noqa: E402
from nucleo.almacen import Almacen                                        # noqa: E402
from nucleo.frases import REFLEXIONES                                     # noqa: E402
from nucleo.interprete import interpretar                                 # noqa: E402

try:
    from PySide6.QtWidgets import QApplication
except ImportError:
    QApplication = None


def ms(fecha: datetime) -> int:
    return int(fecha.timestamp() * 1000)


class TestAprendizaje(unittest.TestCase):
    def corregir(self, contadores, titulo, elegido, veces=2):
        for _ in range(veces):
            detectado = interpretar(titulo, vocabulario=aprendizaje.vocabulario(contadores)).tipo
            aprendizaje.registrar_correccion(contadores, titulo, detectado, elegido)

    def test_aprende_despues_de_dos_correcciones(self):
        c = aprendizaje.cargar(None)
        self.corregir(c, "Cita con el banco", "tarea", veces=1)
        self.assertEqual(aprendizaje.vocabulario(c)["no_evento"], [])       # una sola vez: todavía no
        self.corregir(c, "Cita con el banco", "tarea", veces=1)
        self.assertEqual(aprendizaje.vocabulario(c)["no_evento"], ["cita"])
        self.corregir(c, "Taller de pintura", "evento")
        self.corregir(c, "Ir al concierto", "evento")
        v = aprendizaje.vocabulario(c)
        self.assertEqual(v, {"evento": ["taller"], "no_evento": ["cita"], "verbos": ["ir"]})
        self.assertEqual(interpretar("cita con el contador mañana", vocabulario=v).tipo, "tarea")
        self.assertEqual(interpretar("taller de cerámica el sábado", vocabulario=v).tipo, "evento")
        self.assertEqual(interpretar("ir a comprar pan", vocabulario=v).tipo, "tarea")

    def test_desaprender_y_guardar(self):
        c = aprendizaje.cargar(None)
        self.corregir(c, "Cita con el banco", "tarea")
        self.corregir(c, "Cita con el dentista", "evento", veces=1)          # al revés: baja el contador
        self.assertEqual(aprendizaje.vocabulario(c)["no_evento"], [])
        self.assertEqual(aprendizaje.cargar(aprendizaje.guardar(c)), c)
        self.assertEqual(aprendizaje.cargar("esto no es json"), {"evento": {}, "no_evento": {}, "verbos": {}})

    def test_sin_correccion_no_anota(self):
        c = aprendizaje.cargar(None)
        self.assertFalse(aprendizaje.registrar_correccion(c, "Examen", "evento", "evento"))
        self.assertFalse(aprendizaje.registrar_correccion(c, "Llamar a mamá", "tarea", "evento"))   # nada que aprender


class TestAvisoPrevioSincronizado(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.a = Almacen(Path(self.tmp.name) / "t.db")

    def tearDown(self):
        self.a.con.close()
        self.tmp.cleanup()

    def test_hora_configurable(self):
        t = self.a.agregar("Viaje", datetime(2026, 11, 15, 9, 0), None, "evento", "7")
        self.a.con.execute("UPDATE tareas SET actualizada = ? WHERE id = ?", (ms(datetime(2026, 10, 1)), t.id))
        self.assertEqual(len(self.a.por_avisar_antes(datetime(2026, 11, 8, 9, 0))), 1)
        self.assertEqual(self.a.por_avisar_antes(datetime(2026, 11, 8, 9, 0), (20, 0)), [])
        self.assertEqual(len(self.a.por_avisar_antes(datetime(2026, 11, 8, 20, 0), (20, 0))), 1)

    def test_ya_aviso_el_celular(self):
        t = self.a.agregar("Aniversario", datetime(2026, 11, 15, 9, 0), "anual", "evento", "7,1")
        self.a.con.execute("UPDATE tareas SET actualizada = ? WHERE id = ?", (ms(datetime(2026, 10, 1)), t.id))
        [c] = self.a.cambios_por_subir()
        self.a.confirmar_subidas([(c["id"], c["actualizada"])])
        # Mientras tanto la editaste aquí (más nuevo que lo del celular)…
        self.a.editar(t.id, "Nuestro aniversario", t.fecha, "anual")
        # …y llega del servidor la versión vieja, pero con "ya avisé el 8 a las 9:05" del celular
        self.a.aplicar_remotos([{**c, "aviso_previo": "2026-11-08 09:05"}])
        self.assertEqual(self.a.obtener(t.id).titulo, "Nuestro aniversario")          # tu edición gana…
        self.assertEqual(self.a.por_avisar_antes(datetime(2026, 11, 8, 10, 0)), [])   # …y no repite el aviso

    def test_llega_nueva_con_aviso_hecho(self):
        self.a.aplicar_remotos([{"id": "abc-123-xyz", "titulo": "Boda", "fecha": "2026-11-15 18:00", "repeticion": None,
                                 "estado": "pendiente", "creada": "2026-10-01 10:00", "completada": None,
                                 "actualizada": ms(datetime(2026, 10, 1)), "borrada": False, "tipo": "evento",
                                 "anticipacion": "7,1", "aviso_previo": "2026-11-08 09:05"}])
        self.assertEqual(self.a.por_avisar_antes(datetime(2026, 11, 8, 12, 0)), [])
        self.assertEqual(len(self.a.por_avisar_antes(datetime(2026, 11, 14, 9, 0))), 1)

    def test_vencidas_no_incluye_eventos(self):
        self.a.agregar("Pagar la luz", datetime(2026, 10, 7, 6, 0))
        self.a.agregar("Examen", datetime(2026, 10, 7, 6, 0), None, "evento", "7,1")
        self.assertEqual([t.titulo for t in self.a.vencidas(datetime(2026, 10, 7, 8, 0))], ["Pagar la luz"])


@unittest.skipIf(QApplication is None, "PySide6 no está instalado")
class TestAsistenteV311(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setQuitOnLastWindowClosed(False)

    def setUp(self, con_nube=False):
        import interfaz.app as modulo
        from tests.test_v39 import ServidorFalso
        self.tmp = tempfile.TemporaryDirectory()
        carpeta = Path(self.tmp.name)
        if con_nube:
            (carpeta / "nube.json").write_text(json.dumps({"url": "https://lancelot.prueba.workers.dev", "clave": "x"}))
        self.a = modulo.Asistente(self.app, ruta_bd=carpeta / "t.db")
        self.dichos = []
        self.a.voz.habla.decir = self.dichos.append
        self.a._avisos_en_pausa_hasta = None
        self.a.burbuja.ocultar()
        if con_nube:
            self.servidor, self.pedidos = ServidorFalso(), []
            self.a.nube.pedir = lambda cuerpo: (self.pedidos.append(cuerpo), self.servidor.sync(cuerpo))[1]

    def tearDown(self):
        self.a.salir()
        self.a.almacen.con.close()
        self.tmp.cleanup()

    def sincronizar(self):
        desde = int(self.a.almacen.leer_ajuste("nube_cursor", "0"))
        self.a.nube._trabajar(desde, self.a.almacen.cambios_por_subir(), self.a._preferencias_para_subir())
        self.app.processEvents()

    def test_la_frase_se_dice_en_voz_alta(self):
        self.a.cara.reposo.emit()
        frase = self.a.burbuja.titulo.text()
        self.assertIn(frase, REFLEXIONES)
        self.assertEqual(self.dichos, [frase])
        self.a.burbuja.ocultar()
        self.a._ultima_frase = None
        self.a.ejecutar_comando(self._comando("modo silencio"))
        self.a.burbuja.ocultar()
        self.dichos.clear()
        self.a.cara.reposo.emit()
        self.assertTrue(self.a.burbuja.isVisible())                 # en silencio se muestra…
        self.assertEqual(self.dichos, [])                           # …pero no suena

    def test_secciones_del_panel(self):
        ahora = datetime.now()
        self.a.agregar("Aniversario", ahora + timedelta(days=5), "anual", "evento", "7,1")
        self.a.agregar("Limpiar la sala", ahora + timedelta(hours=2), None)
        textos = [self._texto_fila(i) for i in range(self.a.panel.lista.count())]
        self.assertTrue(textos[0].startswith("TAREAS VENCIDAS · 0"))
        self.assertIn("Ninguna", textos[1])
        self.assertTrue(textos[2].startswith("PRÓXIMOS EVENTOS · 1"))
        self.assertIn("Aniversario", textos[3])
        self.assertTrue(textos[4].startswith("PRÓXIMAS TAREAS · 1"))
        self.assertIn("Limpiar la sala", textos[5])

    def test_aprende_de_las_correcciones_del_panel_y_lo_sube(self):
        self.tearDown()
        self.setUp(con_nube=True)
        p = self.a.panel
        for dia in (20, 21):
            p.entrada.setText(f"cita con el banco el {dia}/12 a las 10am")
            self.assertEqual(p.selector_tipo.currentData(), "evento")
            p.selector_tipo.setCurrentIndex(p.selector_tipo.findData("tarea"))
            p._al_enviar()
        self.assertEqual(self.a.vocabulario["no_evento"], ["cita"])
        p.entrada.setText("cita con el contador el 22/12 a las 10am")
        self.assertEqual(p.selector_tipo.currentData(), "tarea")    # ya aprendió
        self.sincronizar()
        self.assertEqual(self.pedidos[-1]["preferencias"]["vocabulario"]["no_evento"], ["cita"])
        self.sincronizar()
        self.assertNotIn("preferencias", self.pedidos[-1])           # sin cambios: no se vuelve a subir

    def test_con_nube_el_aviso_anticipado_espera_la_primera_sincronizacion(self):
        self.tearDown()
        self.setUp(con_nube=True)
        t = self.a.almacen.agregar("Aniversario", datetime.now() + timedelta(days=7), "anual", "evento", "7,1")
        self.a.almacen.por_avisar_antes = lambda *_: [(self.a.almacen.obtener(t.id), 7)]
        self.a.revisar()
        self.assertFalse(self.a.burbuja.isVisible())               # todavía no sabe qué avisó el celular
        self.sincronizar()
        self.a.revisar()
        self.assertEqual(self.a.burbuja.cabecera.text(), "Se acerca")

    def _texto_fila(self, i):
        from PySide6.QtWidgets import QLabel
        fila = self.a.panel.lista.itemWidget(self.a.panel.lista.item(i))
        return " ".join(l.text() for l in fila.findChildren(QLabel))

    @staticmethod
    def _comando(texto):
        from nucleo.comandos import interpretar_comando
        return interpretar_comando(texto)


if __name__ == "__main__":
    unittest.main()


class TestLotes(unittest.TestCase):
    def test_primera_sincronizacion_en_lotes(self):
        from nucleo.almacen import LOTE_SINCRONIZACION
        with tempfile.TemporaryDirectory() as carpeta:
            a = Almacen(Path(carpeta) / "t.db")
            for i in range(LOTE_SINCRONIZACION + 5):
                a.agregar(f"Tarea {i}", datetime(2026, 12, 1, 9, 0))
            lote = a.cambios_por_subir()
            self.assertEqual(len(lote), LOTE_SINCRONIZACION)
            a.confirmar_subidas([(c["id"], c["actualizada"]) for c in lote])
            self.assertEqual(len(a.cambios_por_subir()), 5)
            a.con.close()
