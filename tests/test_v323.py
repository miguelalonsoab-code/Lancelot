"""
v3.23: el diseño del sistema de Lancelot en el horario — colores nuevos, iconos de línea en vez de emoji,
selector Trabajo · Clase · Otro y cambio de categoría desde el celular.

    python -m unittest tests.test_v323 -v
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from config import COLORES
from nucleo.horario import CATEGORIAS, ICONO_CATEGORIA, TEXTO_CLARO, TEXTO_OSCURO, texto_sobre

try:
    from PySide6.QtWidgets import QApplication
except ImportError:
    QApplication = None


def contraste(a: str, b: str) -> float:
    """Contraste WCAG entre dos colores #rrggbb."""
    def luz(c):
        def lineal(v):
            v /= 255
            return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
        n = int(c.lstrip("#"), 16)
        return 0.2126 * lineal(n >> 16 & 255) + 0.7152 * lineal(n >> 8 & 255) + 0.0722 * lineal(n & 255)
    x, y = sorted((luz(a), luz(b)), reverse=True)
    return (x + 0.05) / (y + 0.05)


class TestColoresEIconos(unittest.TestCase):
    def test_sin_emoji_y_sin_naranja(self):
        for c in CATEGORIAS:
            self.assertRegex(ICONO_CATEGORIA[c], r"^[a-z]+$")                   # nombre de icono, no emoji
        self.assertNotEqual(COLORES["bloque_clase"].lower(), "#f2994a")        # el naranja es «vencida» en el diseño

    def test_el_nombre_se_lee_sobre_cada_categoria(self):
        self.assertEqual(texto_sobre(COLORES["bloque_clase"]), TEXTO_OSCURO)    # lavanda: texto oscuro
        self.assertEqual(texto_sobre(COLORES["bloque_trabajo"]), TEXTO_CLARO)
        self.assertEqual(texto_sobre(COLORES["bloque_otro"]), TEXTO_CLARO)
        for c in CATEGORIAS:
            fondo = COLORES[f"bloque_{c}"]
            self.assertGreaterEqual(contraste(fondo, texto_sobre(fondo)), 4.5, c)

    def test_las_tres_se_distinguen_tambien_por_claridad(self):
        """Para daltonismo: no basta el tono, cada par de categorías difiere en luminosidad."""
        colores = [COLORES[f"bloque_{c}"] for c in CATEGORIAS]
        for i in range(3):
            for j in range(i + 1, 3):
                self.assertGreater(contraste(colores[i], colores[j]), 1.3, (colores[i], colores[j]))

    def test_heredar_categoria(self):
        from datetime import time
        from nucleo.horario import Bloque, heredar_categoria
        hay = [Bloque((2,), time(19, 30), time(22, 40), "Computación Gráfica", 1, 0, "clase")]
        nuevo = Bloque((4,), time(21, 10), time(22, 40), "COMPUTACION GRAFICA ", categoria="otro")
        self.assertEqual(heredar_categoria(nuevo, hay).categoria, "clase")       # sin tildes ni mayúsculas
        otro = Bloque((4,), time(8), time(9), "Inglés", categoria="otro")
        self.assertEqual(heredar_categoria(otro, hay).categoria, "otro")

    def test_texto_sobre_cualquier_color(self):
        self.assertEqual(texto_sobre("#ffffff"), TEXTO_OSCURO)
        self.assertEqual(texto_sobre("#000000"), TEXTO_CLARO)
        self.assertEqual(texto_sobre("ffd166"), TEXTO_OSCURO)                    # sin «#» también


@unittest.skipIf(QApplication is None, "PySide6 no está instalado")
class TestAsistenteV323(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setQuitOnLastWindowClosed(False)

    def setUp(self):
        import interfaz.app as modulo
        from tests.test_v319 import ServidorConAcciones
        self.tmp = tempfile.TemporaryDirectory()
        carpeta = Path(self.tmp.name)
        (carpeta / "nube.json").write_text(json.dumps({"url": "https://lancelot.prueba.workers.dev", "clave": "x"}))
        self.a = modulo.Asistente(self.app, ruta_bd=carpeta / "t.db")
        self.a.voz.habla.decir = lambda *_: None
        self.servidor = ServidorConAcciones()
        self.a.nube.pedir = self.servidor.sync
        self.a.agregar_bloque("de lunes a viernes de 8:30 a 5:30 trabajo, traslado 45 min")
        self.a.agregar_bloque("sábados de 8 a 12 inglés")

    def tearDown(self):
        self.a.salir()
        self.a.almacen.con.close()
        self.tmp.cleanup()

    def sincronizar(self):
        desde = int(self.a.almacen.leer_ajuste("nube_cursor", "0"))
        self.a.nube._trabajar(desde, self.a.almacen.cambios_por_subir(), self.a._preferencias_para_subir(),
                              self.a._extra_para_subir())
        self.app.processEvents()

    def categorias(self):
        return {b.titulo: b.categoria for b in self.a.almacen.horario()}

    def selectores(self):
        """[(bloque, [botones Trabajo/Clase/Otro])] de las filas actuales de la pestaña Horario."""
        from PySide6.QtWidgets import QPushButton
        lista = self.a.panel.lista_horario
        salida = []
        for i in range(lista.count()):
            w = lista.itemWidget(lista.item(i))
            botones = [b for b in w.findChildren(QPushButton) if b.objectName() == "categoria"] if w else []
            if botones:
                salida.append(botones)
        return salida

    def test_iconos_se_dibujan(self):
        from interfaz.iconos import TRAZOS, icono, icono_dos_estados, pixmap
        for c in CATEGORIAS:
            self.assertIn(ICONO_CATEGORIA[c], TRAZOS)
            self.assertFalse(icono(ICONO_CATEGORIA[c], "#ffffff").isNull())
            imagen = pixmap(ICONO_CATEGORIA[c], "#ffffff", 16).toImage()
            self.assertTrue(any(imagen.pixelColor(x, y).alpha() > 0
                                for x in range(imagen.width()) for y in range(imagen.height())), c)   # dibujó algo
        self.assertTrue(icono("no_existe", "#fff").isNull())
        self.assertFalse(icono_dos_estados("maletin", "#888888", "#ffffff").isNull())

    def test_selector_de_tres_opciones(self):
        self.a.refrescar()
        filas = self.selectores()
        self.assertEqual([[b.text() for b in f] for f in filas], [["Trabajo", "Clase", "Otro"]] * 2)
        self.assertEqual([[b.isChecked() for b in f] for f in filas], [[True, False, False], [False, False, True]])
        self.assertFalse(filas[0][0].icon().isNull())                             # con su icono de línea
        filas[1][1].click()                                                       # Inglés -> Clase
        self.assertEqual(self.categorias()["Inglés"], "clase")
        self.assertEqual([b.isChecked() for b in self.selectores()[1]], [False, True, False])

    def test_la_agenda_muestra_la_categoria_con_palabra_e_icono(self):
        from datetime import date, timedelta
        from PySide6.QtWidgets import QLabel, QWidget
        p = self.a.panel
        sabado = date.today() + timedelta(days=(5 - date.today().weekday()) % 7 or 7)
        p.ver_calendario(sabado)
        self.a.refrescar()
        filas = [p.lista_agenda.itemWidget(p.lista_agenda.item(i)) for i in range(p.lista_agenda.count())]
        chips = [c for f in filas if f for c in f.findChildren(QWidget, "chip")]
        self.assertEqual(len(chips), 1)                                          # solo el bloque de Inglés
        textos = [lab.text() for lab in chips[0].findChildren(QLabel) if lab.text()]
        self.assertEqual(textos, ["Otro"])
        self.assertTrue(any(lab.pixmap() is not None and not lab.pixmap().isNull()
                            for lab in chips[0].findChildren(QLabel)))           # el icono

    def test_leyenda_solo_en_la_vista_semana(self):
        from datetime import date
        from PySide6.QtWidgets import QLabel
        p = self.a.panel
        p.ver_calendario(date.today())
        self.assertFalse(p.leyenda_semana.isVisible())
        p.b_semana.click()
        self.assertTrue(p.leyenda_semana.isVisible())
        palabras = [lab.text() for lab in p.leyenda_semana.findChildren(QLabel) if lab.text()]
        self.assertEqual(palabras[:3], ["Trabajo", "Clase", "Otro"])
        p.b_mes.click()
        self.assertFalse(p.leyenda_semana.isVisible())

    def test_mismo_nombre_misma_categoria(self):
        self.a.agregar_bloque("miércoles de 7:30 pm a 10:40 pm Computación Gráfica")
        cg = next(b for b in self.a.almacen.horario() if b.titulo == "Computación Gráfica")
        self.assertEqual(cg.categoria, "otro")                                   # un curso no dice «clase»
        self.a.cambiar_categoria_bloque(cg.id, "clase")
        self.a.agregar_bloque("viernes de 9:10 pm a 10:40 pm computación gráfica")
        self.assertEqual(sorted(b.categoria for b in self.a.almacen.horario() if "gráfica" in b.titulo.lower()),
                         ["clase", "clase"])

    def test_categoria_cambiada_desde_el_celular(self):
        self.sincronizar()
        ingles = next(b for b in self.servidor.contexto["horario"] if b["titulo"] == "Inglés")
        self.servidor.del_celular("categoria_bloque", {"id": ingles["id"], "categoria": "clase"})
        self.servidor.del_celular("categoria_bloque", {"id": 999, "categoria": "trabajo"})      # ya no existe: se ignora
        self.sincronizar()
        self.assertEqual(self.categorias(), {"Trabajo": "trabajo", "Inglés": "clase"})
        self.assertIn("Categoría: Inglés → Clase", self.a.burbuja.titulo.text())
        self.sincronizar()                                                       # la laptop confirma y sube el cambio
        self.assertEqual(next(b for b in self.servidor.contexto["horario"] if b["titulo"] == "Inglés")["categoria"], "clase")
        self.assertEqual(self.servidor.acciones, [])


if __name__ == "__main__":
    unittest.main()
