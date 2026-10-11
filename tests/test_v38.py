"""
Pruebas de la versión 3.8: actualizaciones desde GitHub y voz incluida en el instalador.
Sin internet: las respuestas de GitHub son diccionarios de ejemplo y las "descargas" son archivos locales.

    python -m unittest tests.test_v38 -v
"""
import hashlib
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from nucleo.version import (es_mas_nueva, leer_release, notas_de_version, numeros,  # noqa: E402
                            resumen_notas)
from voz.habla import voces_piper                                                   # noqa: E402
from voz.oido import asegurar_modelo                                                # noqa: E402


def release(tag="v3.9", nombre="Lancelot-setup-3.9.exe", url=None, **extra):
    """Respuesta de ejemplo de la API de GitHub (solo los campos que usamos)."""
    return {"tag_name": tag, "html_url": "https://github.com/miguel/lancelot/releases/tag/" + tag,
            "body": "- **Novedad uno**\n- Novedad dos", "draft": False, "prerelease": False,
            "assets": [{"name": "notas.txt", "browser_download_url": "https://github.com/x/notas.txt"},
                       {"name": nombre, "size": 1234, "digest": "sha256:ABC123",
                        "browser_download_url": url or f"https://github.com/miguel/lancelot/releases/download/{tag}/{nombre}"}],
            **extra}


class TestVersiones(unittest.TestCase):
    def test_comparar(self):
        self.assertEqual(numeros("v3.10"), (3, 10))
        self.assertTrue(es_mas_nueva("3.10", "3.9"))          # como texto, "3.10" < "3.9": por eso números
        self.assertTrue(es_mas_nueva("4", "3.9.9"))
        self.assertFalse(es_mas_nueva("3.8", "3.8.0"))
        self.assertFalse(es_mas_nueva("3.7", "3.8"))

    def test_leer_release(self):
        act = leer_release(release(), "3.8")
        self.assertEqual((act.version, act.tamano, act.sha256), ("3.9", 1234, "abc123"))
        self.assertTrue(act.url_instalador.endswith("Lancelot-setup-3.9.exe"))

    def test_ignora_lo_que_no_sirve(self):
        self.assertIsNone(leer_release(release(tag="v3.8"), "3.8"))                   # misma versión
        self.assertIsNone(leer_release(release(prerelease=True), "3.8"))              # beta
        self.assertIsNone(leer_release(release(nombre="otra-cosa.exe"), "3.8"))       # sin instalador
        self.assertIsNone(leer_release(release(url="https://sitio-raro.com/Lancelot-setup-3.9.exe"), "3.8"))

    def test_notas_del_readme(self):
        readme = (Path(__file__).resolve().parent.parent / "README.md").read_text(encoding="utf-8")
        self.assertIn("Actualizaciones", notas_de_version(readme, "3.8"))
        self.assertNotIn("## Novedades v3.7", notas_de_version(readme, "3.8"))      # solo su sección
        self.assertEqual(notas_de_version(readme, "9.9"), "Lancelot 9.9")
        self.assertEqual(resumen_notas("- **Uno** con `código`\n- Dos"), "• Uno con código\n• Dos")


class TestVozIncluida(unittest.TestCase):
    def test_modelo_propio_primero_luego_el_incluido(self):
        with tempfile.TemporaryDirectory() as tmp:
            datos, incluida = Path(tmp) / "datos", Path(tmp) / "recursos"
            (incluida / "modelo-x" / "am").mkdir(parents=True)
            self.assertEqual(asegurar_modelo(datos, "modelo-x", "http://no-se-usa", incluida=incluida),
                             incluida / "modelo-x")                                  # sin descargar nada
            (datos / "modelo-x" / "conf").mkdir(parents=True)
            self.assertEqual(asegurar_modelo(datos, "modelo-x", "http://no-se-usa", incluida=incluida),
                             datos / "modelo-x")

    def test_voz_piper_necesita_su_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            carpeta = Path(tmp)
            (carpeta / "es_MX-claude.onnx").write_bytes(b"x")
            (carpeta / "suelta.onnx").write_bytes(b"x")                  # sin .onnx.json: no sirve
            (carpeta / "es_MX-claude.onnx.json").write_text("{}")
            self.assertEqual([p.name for p in voces_piper(carpeta)], ["es_MX-claude.onnx"])
            self.assertEqual(voces_piper(None), [])


try:
    from PySide6.QtWidgets import QApplication
except ImportError:
    QApplication = None


@unittest.skipIf(QApplication is None, "PySide6 no está instalado")
class TestActualizador(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        from interfaz.actualizador import Actualizador
        self.tmp = tempfile.TemporaryDirectory()
        self.carpeta = Path(self.tmp.name)
        self.act = Actualizador("miguel/lancelot", "3.8", self.carpeta / "descargas")
        self.eventos = []
        self.act.encontrada.connect(lambda a, manual: self.eventos.append(("encontrada", a.version, manual)))
        self.act.sin_novedad.connect(lambda t, manual: self.eventos.append(("nada", t, manual)))
        self.act.descargada.connect(lambda r: self.eventos.append(("descargada", Path(r).name)))
        self.act.fallo.connect(lambda t: self.eventos.append(("fallo", t)))

    def tearDown(self):
        self.tmp.cleanup()

    def test_buscar(self):
        self.act.pedir_json = lambda url: release()
        self.act._buscar(manual=True)
        self.act.pedir_json = lambda url: release(tag="v3.8")
        self.act._buscar(manual=False)
        self.app.processEvents()
        self.assertEqual(self.eventos, [("encontrada", "3.9", True),
                                        ("nada", "Tienes la última versión (3.8).", False)])

    def _instalador_falso(self, contenido=b"instalador de prueba"):
        from nucleo.version import Actualizacion
        archivo = self.carpeta / "origen.exe"
        archivo.write_bytes(contenido)
        return Actualizacion("3.9", archivo.as_uri(), "", "", len(contenido),
                             hashlib.sha256(contenido).hexdigest())

    def test_descarga_verificada(self):
        self.act._descargar(self._instalador_falso())
        self.app.processEvents()
        self.assertEqual(self.eventos, [("descargada", "Lancelot-setup-3.9.exe")])

    def test_descarga_alterada_se_descarta(self):
        a = self._instalador_falso()
        a.sha256 = "0" * 64                                          # la huella no coincide
        self.act._descargar(a)
        self.app.processEvents()
        self.assertEqual(self.eventos[0][0], "fallo")
        self.assertEqual(list((self.carpeta / "descargas").iterdir()), [])   # no queda nada a medias

    def test_limpiar_descargas_viejas(self):
        d = self.carpeta / "descargas"
        d.mkdir()
        for nombre in ("Lancelot-setup-3.7.exe", "Lancelot-setup-3.8.exe", "Lancelot-setup-3.9.exe",
                       "Lancelot-setup-3.9.part"):
            (d / nombre).write_bytes(b"x")
        self.act.limpiar_descargas()
        self.assertEqual([p.name for p in d.iterdir()], ["Lancelot-setup-3.9.exe"])


if __name__ == "__main__":
    unittest.main()
