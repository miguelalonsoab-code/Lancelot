"""
v3.22: categorías del horario (trabajo, clase, otro) con colores y el nombre del bloque en el calendario.

    python -m unittest tests.test_v322 -v
"""
import json
import os
import sqlite3
import sys
import tempfile
import unittest
from datetime import date, time, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from nucleo import contexto
from nucleo.agenda import agenda_del_dia
from nucleo.almacen import Almacen
from nucleo.horario import (CATEGORIAS, Bloque, inferir_categoria, interpretar_bloque, siguiente_categoria)

try:
    from PySide6.QtWidgets import QApplication
except ImportError:
    QApplication = None


class TestCategorias(unittest.TestCase):
    def test_se_deduce_del_titulo(self):
        casos = {"Trabajo en Sanna": "trabajo", "trabajar desde casa": "trabajo", "TURNO NOCHE": "trabajo", "Oficina": "trabajo",
                 "Clase de redes": "clase", "Clases particulares": "clase", "Curso de Python": "clase", "UPN": "clase",
                 "Universidad": "clase", "Taller de robótica": "clase", "Laboratorio de física": "clase",
                 "Inglés": "otro", "Gimnasio": "otro", "Ocupado": "otro", "": "otro"}
        for titulo, esperada in casos.items():
            self.assertEqual(inferir_categoria(titulo), esperada, titulo)

    def test_la_primera_palabra_que_coincide_decide(self):
        self.assertEqual(inferir_categoria("Clase de trabajo social"), "clase")
        self.assertEqual(inferir_categoria("Trabajo en la universidad"), "trabajo")

    def test_no_confunde_palabras_parecidas(self):
        self.assertEqual(inferir_categoria("Clasificar fotos"), "otro")        # empieza con «clas» pero no es «clase»
        self.assertEqual(inferir_categoria("Educación física"), "otro")

    def test_el_botón_da_la_vuelta_completa(self):
        c, vistas = "trabajo", []
        for _ in range(3):
            c = siguiente_categoria(c)
            vistas.append(c)
        self.assertEqual(vistas, ["clase", "otro", "trabajo"])
        self.assertEqual(siguiente_categoria("rara"), "otro")

    def test_una_categoria_rara_nunca_rompe_el_bloque(self):
        b = Bloque((0,), time(8), time(9), "X", categoria="estudio")
        self.assertEqual(b.categoria, "otro")
        self.assertEqual(Bloque((0,), time(8), time(9), "X").categoria, "otro")          # el valor por omisión
        self.assertEqual(set(CATEGORIAS), {"trabajo", "clase", "otro"})

    def test_al_anotar_un_bloque_se_clasifica(self):
        b = interpretar_bloque("martes y jueves de 7 a 10 de la noche clase de redes")
        self.assertEqual((b.titulo, b.categoria), ("Clase de redes", "clase"))
        self.assertEqual(interpretar_bloque("de lunes a viernes de 9am a 6pm trabajo").categoria, "trabajo")
        self.assertEqual(interpretar_bloque("sábados de 8 a 12 inglés").categoria, "otro")
        self.assertEqual(interpretar_bloque("los domingos de 9 a 11").categoria, "otro")      # sin título: «Ocupado»

    def test_el_contexto_lleva_la_categoria_y_acepta_la_falta_de_ella(self):
        b = Bloque((0, 1), time(8, 30), time(17, 30), "Trabajo en Sanna", 4, 45, "trabajo")
        d = contexto.bloque_a_dict(b)
        self.assertEqual(d["categoria"], "trabajo")
        self.assertEqual(contexto.bloque_de_dict(d), b)                          # ida y vuelta sin perder nada
        sin = {k: v for k, v in d.items() if k != "categoria"}
        self.assertEqual(contexto.bloque_de_dict({**sin, "titulo": "Clase de redes"}).categoria, "clase")   # v3.21: se deduce
        self.assertEqual(contexto.bloque_de_dict({**d, "categoria": "otro"}).categoria, "otro")             # la elegida manda
        self.assertEqual(contexto.bloque_de_dict({**d, "categoria": "zzz"}).categoria, "otro")
        # Cambiar solo la categoría cambia la huella: así la laptop sube el contexto de nuevo al celular
        self.assertNotEqual(contexto.huella({"horario": [d]}), contexto.huella({"horario": [{**d, "categoria": "otro"}]}))

    def test_la_agenda_marca_la_categoria_de_cada_bloque(self):
        lunes = date(2026, 10, 26)
        bloques = [Bloque((0,), time(8, 30), time(17, 30), "Trabajo", 1, 0, "trabajo"),
                   Bloque((0,), time(19), time(22), "Clase de redes", 2, 0, "clase"),
                   Bloque((0,), time(22), time(23), "Misa", 3, 0, "otro")]
        items = agenda_del_dia(lunes, bloques, [], [], [])
        self.assertEqual([(i.titulo, i.categoria) for i in items], [("Trabajo", "trabajo"), ("Clase de redes", "clase"),
                                                                    ("Misa", "otro")])


class TestAlmacenCategorias(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ruta = Path(self.tmp.name) / "t.db"

    def tearDown(self):
        self.tmp.cleanup()

    def test_ida_y_vuelta_y_cambio(self):
        a = Almacen(self.ruta)
        b = a.agregar_bloque(interpretar_bloque("martes y jueves de 7 a 10 de la noche clase de redes"))
        self.assertEqual(a.horario()[0].categoria, "clase")
        self.assertTrue(a.cambiar_categoria(b.id, "otro"))
        self.assertEqual(a.horario()[0].categoria, "otro")
        self.assertFalse(a.cambiar_categoria(b.id, "estudio"))                   # categoría que no existe
        self.assertFalse(a.cambiar_categoria(999, "clase"))                      # bloque que no existe
        self.assertEqual(a.horario()[0].categoria, "otro")
        a.con.close()

    def test_la_base_de_la_v321_se_migra_y_clasifica_lo_que_ya_tenias(self):
        con = sqlite3.connect(self.ruta)       # el horario como lo dejaba la v3.21: sin la columna «categoria»
        con.executescript("""
            CREATE TABLE horario (id INTEGER PRIMARY KEY AUTOINCREMENT, dias TEXT NOT NULL, inicio TEXT NOT NULL,
                                  fin TEXT NOT NULL, titulo TEXT NOT NULL, traslado INTEGER NOT NULL DEFAULT 0);
            INSERT INTO horario (dias, inicio, fin, titulo, traslado) VALUES
                ('0,1,2,3,4', '08:30', '17:30', 'Trabajo en Sanna', 45),
                ('1,3', '19:00', '22:00', 'Clase de redes', 0),
                ('5', '08:00', '12:00', 'Inglés', 15);
        """)
        con.commit()
        con.close()
        a = Almacen(self.ruta)
        self.assertEqual({b.titulo: (b.categoria, b.traslado) for b in a.horario()},
                         {"Trabajo en Sanna": ("trabajo", 45), "Clase de redes": ("clase", 0), "Inglés": ("otro", 15)})
        trabajo = next(b for b in a.horario() if b.titulo == "Trabajo en Sanna")
        a.cambiar_categoria(trabajo.id, "otro")                                  # lo corriges a mano…
        a.con.close()
        a = Almacen(self.ruta)                                                   # …y al reabrir no se vuelve a «arreglar»
        self.assertEqual(next(b for b in a.horario() if b.titulo == "Trabajo en Sanna").categoria, "otro")
        a.con.close()


@unittest.skipIf(QApplication is None, "PySide6 no está instalado")
class TestAsistenteV322(unittest.TestCase):
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
        self.a.agregar_bloque("martes y jueves de 7 a 10 de la noche clase de redes")
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

    def categorias(self):
        return {b.titulo: b.categoria for b in self.a.almacen.horario()}

    def botones_de_categoria(self):
        """Los botones de categoría de las filas que hay ahora en la lista (las filas viejas se borran con retraso)."""
        from PySide6.QtWidgets import QPushButton
        lista = self.a.panel.lista_horario
        widgets = [lista.itemWidget(lista.item(i)) for i in range(lista.count())]
        return [b for w in widgets if w for b in w.findChildren(QPushButton) if b.toolTip().startswith("Categoría")]

    def test_salir_detiene_los_relojes(self):
        """Un reloj vivo tras salir() revisaba una base ya cerrada (se veía en las pruebas, con asistentes de antes)."""
        from PySide6.QtCore import QTimer
        self.assertTrue(any(t.isActive() for t in self.a.findChildren(QTimer)))
        self.a.salir()
        self.assertFalse(any(t.isActive() for t in self.a.findChildren(QTimer)))

    def test_lo_que_anotas_ya_viene_clasificado(self):
        self.assertEqual(self.categorias(), {"Trabajo": "trabajo", "Clase de redes": "clase"})

    def test_el_boton_de_la_pestana_horario_cambia_la_categoria(self):
        # v3.23: en vez de un botón que da la vuelta, cada bloque tiene Trabajo · Clase · Otro (ver test_v323)
        self.a.refrescar()
        marcados = lambda: [b.text() for b in self.botones_de_categoria() if b.isChecked()]
        self.assertEqual(marcados(), ["Trabajo", "Clase"])
        otro_de_la_clase = self.botones_de_categoria()[5]                       # 2.º bloque, 3.ª opción
        otro_de_la_clase.click()
        self.assertEqual(self.categorias()["Clase de redes"], "otro")
        self.assertEqual(marcados(), ["Trabajo", "Otro"])                       # la lista se redibuja con el cambio

    def test_el_cambio_llega_al_celular_en_la_siguiente_sincronizacion(self):
        self.sincronizar()
        self.assertEqual({b["titulo"]: b["categoria"] for b in self.servidor.contexto["horario"]},
                         {"Trabajo": "trabajo", "Clase de redes": "clase"})
        clase = next(b for b in self.a.almacen.horario() if b.titulo == "Clase de redes")
        self.a.cambiar_categoria_bloque(clase.id, "trabajo")
        self.sincronizar()
        self.assertEqual({b["titulo"]: b["categoria"] for b in self.servidor.contexto["horario"]}["Clase de redes"], "trabajo")

    def test_un_bloque_hecho_en_el_celular_se_guarda_con_su_categoria(self):
        base = {"dias": [4], "inicio": "18:00", "fin": "20:00", "traslado": 0}
        self.servidor.del_celular("bloque", {**base, "titulo": "Guardia", "categoria": "trabajo"})
        self.servidor.del_celular("bloque", {**base, "titulo": "Curso de Python"})        # celular sin actualizar: sin categoría
        self.servidor.del_celular("bloque", {**base, "titulo": "Misa", "categoria": "otro"})
        self.sincronizar()
        self.assertEqual(self.categorias(), {"Trabajo": "trabajo", "Clase de redes": "clase", "Guardia": "trabajo",
                                             "Curso de Python": "clase", "Misa": "otro"})

    def test_la_semana_dibuja_los_bloques_con_color_y_nombre(self):
        from PySide6.QtGui import QColor
        from interfaz.semana_cal import ALTO_MINIMO_NOMBRE, color_bloque
        trabajo, clase, otro = (color_bloque(c) for c in CATEGORIAS)
        self.assertEqual(len({trabajo.name(), clase.name(), otro.name()}), 3)            # tres colores distintos
        self.assertLess(color_bloque("trabajo", True).alpha(), trabajo.alpha())           # el día libre se apaga
        self.assertEqual(color_bloque("zzz").name(), otro.name())

        p = self.a.panel
        lunes = self.hoy - timedelta(days=self.hoy.weekday())
        p.ver_calendario(lunes)
        p.b_semana.click()
        self.a.refrescar()
        p.resize(520, 760)
        p.show()
        self.app.processEvents()
        imagen = p.semana_cal.grab().toImage()
        self.assertFalse(imagen.isNull())
        # En la columna del lunes hay un bloque de trabajo (azul) y no hay nada de clase (naranja)
        ancho = p.semana_cal._ancho_columna()
        x = int(30 + ancho / 2)
        azul = QColor("#5b8def")
        colores = [QColor(imagen.pixel(x, y)) for y in range(imagen.height())]
        self.assertTrue(any(abs(c.blue() - azul.blue()) < 40 and c.blue() > c.red() + 40 for c in colores))
        self.assertGreater(ALTO_MINIMO_NOMBRE, 0)
        p.hide()


if __name__ == "__main__":
    unittest.main()
