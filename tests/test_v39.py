"""
Pruebas de la v3.9: sincronización de la laptop con el servidor (y el celular).

    python -m unittest tests.test_v39 -v
"""
import json
import os
import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from nucleo.almacen import Almacen, _ms   # noqa: E402

F = "%Y-%m-%d %H:%M"


class TestAlmacenSincronizable(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ruta = Path(self.tmp.name) / "t.db"

    def tearDown(self):
        self.tmp.cleanup()

    def abrir(self):
        a = Almacen(self.ruta)
        self.addCleanup(a.con.close)
        return a

    def test_migra_una_base_vieja_sin_perder_nada(self):
        con = sqlite3.connect(self.ruta)                       # así era tareas.db hasta la v3.8
        con.executescript("""
            CREATE TABLE tareas (id INTEGER PRIMARY KEY AUTOINCREMENT, titulo TEXT NOT NULL, fecha TEXT NOT NULL,
                repeticion TEXT, estado TEXT NOT NULL DEFAULT 'pendiente', avisada INTEGER NOT NULL DEFAULT 0,
                creada TEXT NOT NULL, completada TEXT);
            INSERT INTO tareas (titulo, fecha, creada) VALUES ('Pagar la luz', '2026-10-11 20:00', '2026-10-01 10:00');
        """)
        con.close()
        a = Almacen(self.ruta)
        [t] = a.pendientes()
        self.assertEqual(t.titulo, "Pagar la luz")
        [c] = a.cambios_por_subir()                            # la primera vez se sube todo
        self.assertEqual((c["titulo"], c["fecha"], c["borrada"]), ("Pagar la luz", "2026-10-11 20:00", False))
        self.assertEqual(len(c["id"]), 36)                     # recibió su uuid
        a.con.close()
        self.assertEqual(self.abrir().cambios_por_subir()[0]["id"], c["id"])   # y no cambia al reabrir

    def test_registra_lo_que_falta_subir(self):
        a = self.abrir()
        t = a.agregar("Llamar al banco", datetime.now() + timedelta(hours=2))
        [c] = a.cambios_por_subir()
        a.confirmar_subidas([(c["id"], c["actualizada"])])
        self.assertEqual(a.cambios_por_subir(), [])
        a.editar(t.id, "Llamar al banco (BCP)", t.fecha, None)
        [c2] = a.cambios_por_subir()
        self.assertEqual(c2["titulo"], "Llamar al banco (BCP)")
        a.confirmar_subidas([(c2["id"], c2["actualizada"] - 1)])     # se subió una versión anterior…
        self.assertEqual(len(a.cambios_por_subir()), 1)                # …así que sigue pendiente

    def test_eliminar_se_marca_y_se_sube(self):
        a = self.abrir()
        t = a.agregar("Borrar esto", datetime.now() + timedelta(hours=1))
        a.eliminar(t.id)
        self.assertEqual(a.pendientes(), [])
        self.assertIsNone(a.obtener(t.id))
        self.assertTrue(a.cambios_por_subir()[0]["borrada"])

    def test_aplicar_remotos_gana_el_mas_reciente(self):
        a = self.abrir()
        manana = (datetime.now() + timedelta(days=1)).replace(second=0, microsecond=0)
        remota = {"id": "celu-1", "titulo": "Desde el celular", "fecha": manana.strftime(F), "repeticion": None,
                  "estado": "pendiente", "creada": "2026-10-11 10:00", "completada": None, "actualizada": _ms(),
                  "borrada": False}
        [id_] = a.aplicar_remotos([remota])
        self.assertEqual(a.obtener(id_).titulo, "Desde el celular")
        self.assertEqual(a.cambios_por_subir(), [])            # lo que llega del servidor no se vuelve a subir

        a.editar(id_, "Editada en la laptop", manana, None)    # cambio local más nuevo…
        self.assertEqual(a.aplicar_remotos([{**remota, "titulo": "Vieja"}]), [])   # …una versión vieja no lo pisa
        self.assertEqual(a.obtener(id_).titulo, "Editada en la laptop")

        nueva = _ms() + 1000
        a.aplicar_remotos([{**remota, "estado": "hecha", "actualizada": nueva}])
        self.assertEqual(a.pendientes(), [])                   # completada en el celular
        a.aplicar_remotos([{**remota, "borrada": True, "actualizada": nueva + 1}])
        self.assertIsNone(a.obtener(id_))
        self.assertEqual(a.aplicar_remotos([{"id": "x", "fecha": "mañana"}]), [])   # dato raro: se ignora

    def test_cambio_de_fecha_remoto_vuelve_a_avisar(self):
        a = self.abrir()
        t = a.agregar("Tomar agua", datetime.now() - timedelta(minutes=5))
        a.marcar_avisada(t.id)
        [c] = a.cambios_por_subir()
        nueva = (datetime.now() - timedelta(minutes=1)).strftime(F)
        a.aplicar_remotos([{**c, "fecha": nueva, "actualizada": c["actualizada"] + 10}])
        self.assertEqual([x.titulo for x in a.por_avisar(datetime.now())], ["Tomar agua"])


try:
    from PySide6.QtWidgets import QApplication
except ImportError:
    QApplication = None


class ServidorFalso:
    """Imita /api/sync del servidor de Cloudflare (último cambio gana, cursor por llegada)."""

    def __init__(self):
        self.tareas, self.reloj = {}, 0

    def sync(self, cuerpo):
        for c in cuerpo["cambios"]:
            actual = self.tareas.get(c["id"])
            if not actual or c["actualizada"] > actual["actualizada"]:
                self.reloj += 1
                self.tareas[c["id"]] = {**c, "recibida": self.reloj}
        filas = sorted((t for t in self.tareas.values() if t["recibida"] >= cuerpo["desde"]), key=lambda t: t["recibida"])
        return {"aceptados": 0, "rechazados": [], "completo": True, "cursor": filas[-1]["recibida"] if filas else cuerpo["desde"],
                "cambios": [{k: v for k, v in t.items() if k != "recibida"} for t in filas]}

    def desde_el_celular(self, **campos):
        self.reloj += 1
        base = {"repeticion": None, "estado": "pendiente", "creada": "2026-10-11 10:00", "completada": None,
                "borrada": False, "actualizada": _ms() + self.reloj}
        actual = self.tareas.get(campos["id"], base)
        self.tareas[campos["id"]] = {**actual, **campos, "actualizada": _ms() + 5000 + self.reloj, "recibida": self.reloj}


@unittest.skipIf(QApplication is None, "PySide6 no está instalado")
class TestSincronizacionDelAsistente(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        import interfaz.app as modulo
        self.tmp = tempfile.TemporaryDirectory()
        carpeta = Path(self.tmp.name)
        (carpeta / "nube.json").write_text(json.dumps({"url": "https://lancelot.prueba.workers.dev", "clave": "x"}))
        self.a = modulo.Asistente(self.app, ruta_bd=carpeta / "t.db")
        self.a.voz.habla.decir = lambda *_: None
        self.servidor = ServidorFalso()
        self.a.nube.pedir = self.servidor.sync

    def tearDown(self):
        self.a.salir()
        self.a.almacen.con.close()
        self.tmp.cleanup()

    def sincronizar(self):
        """Lo mismo que hace el reloj de cada minuto, pero sin hilo (para que la prueba sea determinista)."""
        desde = int(self.a.almacen.leer_ajuste("nube_cursor", "0"))
        self.a.nube._trabajar(desde, self.a.almacen.cambios_por_subir())
        self.app.processEvents()

    def test_ida_y_vuelta(self):
        self.a.agregar("Desde la laptop", datetime.now() + timedelta(hours=3), None)
        self.sincronizar()
        self.assertEqual([t["titulo"] for t in self.servidor.tareas.values()], ["Desde la laptop"])
        self.assertIn("Sincronizado", self.a.estado_nube[0])

        en_un_rato = (datetime.now() + timedelta(hours=1)).strftime(F)
        self.servidor.desde_el_celular(id="celu-1", titulo="Desde el celular", fecha=en_un_rato)
        self.sincronizar()
        self.assertEqual(sorted(t.titulo for t in self.a.almacen.pendientes()), ["Desde el celular", "Desde la laptop"])

        # Una vencida que suena en la laptop y se completa en el celular deja de sonar aquí
        hace_rato = (datetime.now() - timedelta(minutes=2)).strftime(F)
        self.servidor.desde_el_celular(id="celu-1", fecha=hace_rato)
        self.sincronizar()
        self.a.revisar()
        self.assertEqual(len(self.a.avisos.cola), 1)
        self.servidor.desde_el_celular(id="celu-1", estado="hecha")
        self.sincronizar()
        self.assertEqual(self.a.avisos.cola, [])
        self.assertEqual([t.titulo for t in self.a.almacen.pendientes()], ["Desde la laptop"])

    def test_sin_conexion_avisa_y_no_pierde_nada(self):
        def caido(_):
            raise OSError("sin internet")
        self.a.nube.pedir = caido
        self.a.agregar("Anotada sin internet", datetime.now() + timedelta(hours=1), None)
        self.sincronizar()
        self.assertTrue(self.a.estado_nube[1])                 # se muestra como error
        self.assertEqual(len(self.a.almacen.cambios_por_subir()), 1)   # sigue esperando para subir
        self.a.nube.pedir = self.servidor.sync
        self.sincronizar()
        self.assertEqual(self.a.almacen.cambios_por_subir(), [])


if __name__ == "__main__":
    unittest.main()
