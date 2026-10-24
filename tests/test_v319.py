"""
v3.19: el celular conoce tu horario y tus actividades (contexto que sube la laptop) y lo que haces en el
celular («ya fui al gimnasio», «mañana no trabajo», agendar una sugerencia) llega a la laptop.

    python -m unittest tests.test_v319 -v
"""
import json
import os
import sys
import tempfile
import unittest
from datetime import date, time, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from nucleo import contexto                                               # noqa: E402
from nucleo.horario import Bloque, Excepcion                              # noqa: E402
from nucleo.perfil import Actividad, Perfil                               # noqa: E402

try:
    from PySide6.QtWidgets import QApplication
except ImportError:
    QApplication = None


class TestContexto(unittest.TestCase):
    def test_ida_y_vuelta(self):
        b = Bloque((0, 1, 2, 3, 4), time(8, 30), time(17, 30), "Trabajo", traslado=45)
        e = Excepcion(date(2026, 11, 1), date(2026, 11, 1), "traba", "No trabajo")
        a = Actividad("Gimnasio", 60, 3, "tarde", 7)
        self.assertEqual(contexto.bloque_de_dict(contexto.bloque_a_dict(b)), b)
        self.assertEqual(contexto.excepcion_de_dict(contexto.excepcion_a_dict(e)), e)
        self.assertEqual(contexto.actividad_de_dict(contexto.actividad_a_dict(a)), a)

    def test_armar_y_huella(self):
        p = Perfil(time(6), time(23), 100, [Actividad("Gimnasio", 60, 3, "tarde", 7)])
        c = contexto.armar(p, 30, [], [], {7: [date(2026, 10, 21), date(2026, 10, 20)]}, {date(2026, 10, 21): 40},
                           {"leer": {"noche", "manana"}}, ["b-uuid", "a-uuid"])
        self.assertEqual(c["perfil"], {"despertar": "06:00", "dormir": "23:00", "meta_estudio": 100, "avisar_huecos": True,
                                       "minutos_para_arrancar": 30})
        self.assertEqual(c["hechas"], {"7": ["2026-10-20", "2026-10-21"]})
        self.assertEqual(c["evitar"], {"leer": ["manana", "noche"]})
        self.assertEqual(c["sugeridas"], ["a-uuid", "b-uuid"])
        self.assertEqual(json.loads(json.dumps(c)), c)                       # se puede mandar como JSON
        self.assertEqual(contexto.huella(c), contexto.huella(json.loads(json.dumps(c))))


class ServidorConAcciones:
    """El ServidorFalso de v3.9, más el contexto y las acciones del celular (como src/index.js)."""

    def __init__(self):
        from tests.test_v39 import ServidorFalso
        self.base = ServidorFalso()
        self.contexto, self.acciones, self.siguiente, self.pedidos = None, [], 1, []

    def del_celular(self, tipo, datos):
        self.acciones.append({"id": self.siguiente, "tipo": tipo, "datos": datos})
        self.siguiente += 1

    def sync(self, cuerpo):
        self.pedidos.append(cuerpo)
        if "contexto" in cuerpo:
            self.contexto = cuerpo["contexto"]
        ok = set(cuerpo.get("acciones_ok", []))
        self.acciones = [a for a in self.acciones if a["id"] not in ok]
        return {**self.base.sync(cuerpo), "acciones": list(self.acciones)}


@unittest.skipIf(QApplication is None, "PySide6 no está instalado")
class TestAsistenteV319(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setQuitOnLastWindowClosed(False)

    def setUp(self):
        import interfaz.app as modulo
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

    def test_sube_el_contexto_solo_si_cambio(self):
        self.sincronizar()
        c = self.servidor.contexto
        self.assertEqual(c["horario"][0]["titulo"], "Trabajo")
        self.assertEqual(c["actividades"][0]["nombre"], "Gimnasio")
        self.sincronizar()
        self.assertNotIn("contexto", self.servidor.pedidos[-1])               # sin cambios: no se repite
        self.a.agregar_excepcion("el 1 de noviembre no trabajo")
        self.sincronizar()
        self.assertEqual(self.servidor.pedidos[-1]["contexto"]["excepciones"][0]["titulo"], "No trabajo")

    def test_aplica_las_acciones_del_celular_una_sola_vez(self):
        gim = self.a.perfil.actividades[0]
        manana = self.hoy + timedelta(days=1)
        self.servidor.del_celular("hecha", {"actividad_id": gim.id, "dia": self.hoy.isoformat()})
        self.servidor.del_celular("excepcion", {"desde": manana.isoformat(), "hasta": manana.isoformat(),
                                                "filtro": "traba", "titulo": "No trabajo"})
        self.servidor.del_celular("hecha", {"actividad_id": 999, "dia": self.hoy.isoformat()})   # ya no existe
        self.sincronizar()
        self.assertEqual(self.a.almacen.actividades_hechas(self.hoy, self.hoy), {gim.id: [self.hoy]})
        self.assertEqual([e.titulo for e in self.a.almacen.excepciones()], ["No trabajo"])
        self.assertEqual(self.a.burbuja.cabecera.text(), "📱 Desde el celular")
        self.assertEqual(self.a._acciones_aplicadas(), [1, 2, 3])
        # La siguiente sincronización confirma (el servidor las borra) y sube el contexto con lo nuevo
        self.sincronizar()
        enviado = self.servidor.pedidos[-1]
        self.assertEqual(enviado["acciones_ok"], [1, 2, 3])
        self.assertEqual(enviado["contexto"]["hechas"], {str(gim.id): [self.hoy.isoformat()]})
        self.assertEqual(self.servidor.acciones, [])
        self.assertEqual(self.a._acciones_aplicadas(), [])
        self.assertEqual(len(self.a.almacen.excepciones()), 1)                 # no se duplicó

    def test_sugerida_desde_el_celular(self):
        uuid_ = "uuid-del-celular-123"
        self.servidor.base.desde_el_celular(id=uuid_, titulo="Gimnasio", fecha=f"{self.hoy + timedelta(days=1)} 18:15",
                                            tipo="tarea", duracion=60)
        self.servidor.del_celular("sugerida", {"tarea": uuid_, "actividad_id": self.a.perfil.actividades[0].id})
        self.sincronizar()
        local = self.a.almacen.id_por_uuid(uuid_)
        self.assertTrue(self.a.almacen.es_sugerida(local))
        self.sincronizar()
        self.assertEqual(self.servidor.pedidos[-1]["contexto"]["sugeridas"], [uuid_])

    def test_sugerida_que_todavia_no_llego_espera(self):
        self.servidor.del_celular("sugerida", {"tarea": "uuid-que-no-llego", "actividad_id": None})
        self.sincronizar()
        self.assertEqual(self.a._acciones_aplicadas(), [])                     # no se confirma: se reintenta
        self.assertEqual(len(self.servidor.acciones), 1)


if __name__ == "__main__":
    unittest.main()
