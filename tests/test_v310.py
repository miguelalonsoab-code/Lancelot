"""
v3.10: eventos con aviso anticipado y frases al dejar el mouse sobre la cara.

    python -m unittest tests.test_v310 -v
"""
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from nucleo.almacen import Almacen                                       # noqa: E402
from nucleo.comandos import interpretar_comando                           # noqa: E402
from nucleo.dialogo import DialogoTarea                                   # noqa: E402
from nucleo.frases import (REFLEXIONES, BolsaFrases, guardar_frase_usuario,   # noqa: E402
                           leer_frases_usuario)
from nucleo.interprete import interpretar                                 # noqa: E402
from nucleo.planificador import aviso_previo_pendiente, siguiente_ocurrencia   # noqa: E402
from nucleo.saludo import armar_saludo                                    # noqa: E402

try:
    from PySide6.QtWidgets import QApplication
except ImportError:
    QApplication = None

AHORA = datetime(2026, 10, 7, 6, 30)      # miércoles


def ms(fecha: datetime) -> int:
    return int(fecha.timestamp() * 1000)


class TestInterpreteEventos(unittest.TestCase):
    def test_evento_por_palabra_clave(self):
        r = interpretar("el 15 de noviembre aniversario", AHORA)
        self.assertEqual((r.titulo, r.tipo, r.repeticion, r.avisos), ("Aniversario", "evento", "anual", "7,1"))

    def test_si_empieza_con_verbo_es_tarea(self):
        for texto in ("estudiar para el examen mañana", "comprar regalo de cumpleaños el viernes",
                      "ir al concierto el sábado"):
            self.assertEqual(interpretar(texto, AHORA).tipo, "tarea", texto)

    def test_marca_explicita_y_anticipacion_pedida(self):
        r = interpretar("evento: cena con amigos el sábado, avísame 3 días antes", AHORA)
        self.assertEqual((r.titulo, r.tipo, r.anticipacion, r.avisos), ("Cena con amigos", "evento", "3", "3"))
        r = interpretar("tarea: examen de prueba mañana", AHORA)
        self.assertEqual((r.titulo, r.tipo), ("Examen de prueba", "tarea"))
        self.assertEqual(interpretar("boda de Ana el 12/12 con una semana de anticipación", AHORA).avisos, "7")

    def test_eventos_que_se_repiten_seguido_avisan_menos(self):
        self.assertEqual(interpretar("cada lunes 9am reunión de equipo", AHORA).avisos, "1")
        self.assertIsNone(interpretar("cada día a las 8 reunión diaria", AHORA).avisos)
        self.assertIsNone(interpretar("limpiar la sala el sábado", AHORA).avisos)

    def test_cada_anio(self):
        r = interpretar("pagar el seguro cada año el 10 de enero", AHORA)
        self.assertEqual((r.titulo, r.repeticion, r.fecha), ("Pagar el seguro", "anual", datetime(2027, 1, 10, 9, 0)))
        self.assertEqual(siguiente_ocurrencia(datetime(2028, 2, 29, 9), "anual", datetime(2028, 3, 1)),
                         datetime(2029, 2, 28, 9))


class TestAvisoPrevio(unittest.TestCase):
    def test_una_semana_y_un_dia_antes(self):
        evento, creado = datetime(2026, 11, 15, 20, 0), datetime(2026, 10, 1)
        self.assertIsNone(aviso_previo_pendiente(evento, "7,1", creado, datetime(2026, 11, 8, 8, 59)))
        self.assertEqual(aviso_previo_pendiente(evento, "7,1", creado, datetime(2026, 11, 8, 9, 0)), 7)
        avisado = datetime(2026, 11, 8, 9, 0)
        self.assertIsNone(aviso_previo_pendiente(evento, "7,1", avisado, datetime(2026, 11, 13, 22, 0)))
        self.assertEqual(aviso_previo_pendiente(evento, "7,1", avisado, datetime(2026, 11, 14, 9, 0)), 1)

    def test_no_avisa_lo_que_ya_paso_al_crearlo(self):
        evento = datetime(2026, 11, 15, 9, 0)
        self.assertIsNone(aviso_previo_pendiente(evento, "7,1", datetime(2026, 11, 12, 15), datetime(2026, 11, 12, 16)))


class TestAlmacenEventos(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ruta = Path(self.tmp.name) / "t.db"

    def tearDown(self):
        self.tmp.cleanup()

    def abrir(self):
        a = Almacen(self.ruta)
        self.addCleanup(a.con.close)
        return a

    def test_migra_una_base_de_la_v39(self):
        a = Almacen(self.ruta)
        a.agregar("Pagar la luz", datetime(2026, 10, 11, 20, 0))
        for columna in ("tipo", "anticipacion", "aviso_previo"):   # así era la base antes de esta versión
            a.con.execute(f"ALTER TABLE tareas DROP COLUMN {columna}")
        a.con.commit()
        a.con.close()
        [t] = self.abrir().pendientes()
        self.assertEqual((t.titulo, t.tipo, t.anticipacion), ("Pagar la luz", "tarea", None))

    def test_aviso_anticipado_una_sola_vez_y_sin_sincronizar(self):
        a = self.abrir()
        t = a.agregar("Aniversario", datetime(2026, 11, 15, 9, 0), "anual", "evento", "7,1")
        a.con.execute("UPDATE tareas SET actualizada = ? WHERE id = ?", (ms(datetime(2026, 10, 1)), t.id))
        a.confirmar_subidas([(c["id"], c["actualizada"]) for c in a.cambios_por_subir()])
        momento = datetime(2026, 11, 8, 9, 5)
        [(evento, dias)] = a.por_avisar_antes(momento)
        self.assertEqual((evento.titulo, dias), ("Aniversario", 7))
        a.marcar_aviso_previo(evento.id, momento)
        self.assertEqual(a.por_avisar_antes(momento + timedelta(hours=3)), [])
        self.assertEqual(a.cambios_por_subir(), [])                   # avisar no es un cambio para el celular
        [(_, dias)] = a.por_avisar_antes(datetime(2026, 11, 14, 9, 0))
        self.assertEqual(dias, 1)

    def test_eventos_pasados_se_cierran_solos(self):
        a = self.abrir()
        unico = a.agregar("Concierto", datetime(2026, 10, 5, 21, 0), None, "evento", "7,1")
        cumple = a.agregar("Cumpleaños de mamá", datetime(2026, 10, 5, 9, 0), "anual", "evento", "7,1")
        tarea = a.agregar("Pagar la luz", datetime(2026, 10, 5, 20, 0))
        hoy = a.agregar("Examen", datetime(2026, 10, 7, 8, 0), None, "evento", "7,1")
        self.assertEqual(sorted(a.cerrar_eventos_pasados(AHORA)), sorted([unico.id, cumple.id]))
        self.assertEqual(a.obtener(unico.id).estado, "hecha")
        self.assertEqual(a.obtener(cumple.id).fecha, datetime(2027, 10, 5, 9, 0))
        self.assertEqual(a.obtener(tarea.id).estado, "pendiente")    # una tarea vencida sigue esperándote
        self.assertEqual(a.obtener(hoy.id).estado, "pendiente")      # el de hoy, todavía no

    def test_sincroniza_tipo_y_anticipacion(self):
        a = self.abrir()
        a.agregar("Examen final", datetime(2026, 12, 1, 8, 0), None, "evento", "3")
        [c] = a.cambios_por_subir()
        self.assertEqual((c["tipo"], c["anticipacion"]), ("evento", "3"))
        # Del celular: lo pasan a tarea. Y un servidor viejo (sin esos campos) no borra lo que hay.
        a.aplicar_remotos([{**c, "tipo": "tarea", "anticipacion": None, "actualizada": c["actualizada"] + 1}])
        self.assertEqual((a.pendientes()[0].tipo, a.pendientes()[0].anticipacion), ("tarea", None))
        a.editar(a.pendientes()[0].id, "Examen final", datetime(2026, 12, 1, 8, 0), None, "evento", "7,1")
        viejo = {k: v for k, v in a.cambios_por_subir()[0].items() if k not in ("tipo", "anticipacion")}
        a.aplicar_remotos([{**viejo, "titulo": "Examen final (aula 201)", "actualizada": viejo["actualizada"] + 1}])
        t = a.pendientes()[0]
        self.assertEqual((t.titulo, t.tipo, t.anticipacion), ("Examen final (aula 201)", "evento", "7,1"))

    def test_editar_sin_tipo_lo_conserva(self):
        a = self.abrir()
        t = a.agregar("Boda de Ana", datetime(2026, 12, 12, 18, 0), None, "evento", "7,1")
        a.editar(t.id, "Boda de Ana y Luis", t.fecha, None)
        self.assertEqual((a.obtener(t.id).tipo, a.obtener(t.id).anticipacion), ("evento", "7,1"))


class TestSaludoYDialogo(unittest.TestCase):
    def test_saludo_menciona_eventos_cercanos(self):
        from nucleo.almacen import Tarea
        pendientes = [Tarea(1, "Aniversario", datetime(2026, 10, 10, 9, 0), "anual", "pendiente", False, "evento", "7,1"),
                      Tarea(2, "Viaje", datetime(2026, 12, 1, 9, 0), None, "pendiente", False, "evento", "7,1")]
        s = armar_saludo(datetime(2026, 10, 7, 8, 0), pendientes, 0, "Miguel")
        self.assertIn("📅 Se acerca: Aniversario (faltan 3 días)", s.texto)
        self.assertNotIn("Viaje", s.texto)
        self.assertIn("Se acerca Aniversario, faltan 3 días.", s.hablado)

    def test_dialogo_descubre_el_evento_en_la_respuesta(self):
        d = DialogoTarea("recuérdame el 15 de noviembre", "", datetime(2026, 11, 15, 9, 0), None)
        paso = d.siguiente()
        self.assertEqual(paso.texto, "¿Qué te recuerdo?")
        paso = d.responder("aniversario", AHORA)
        self.assertEqual((paso.tipo, paso.titulo, paso.clase, paso.repeticion, paso.avisos),
                         ("crear", "Aniversario", "evento", "anual", "7,1"))


class TestFrases(unittest.TestCase):
    def test_bolsa_sin_repetir(self):
        b = BolsaFrases(REFLEXIONES)
        primera_vuelta = [b.sacar() for _ in REFLEXIONES]
        self.assertEqual(sorted(primera_vuelta), sorted(REFLEXIONES))
        self.assertNotEqual(b.sacar(), primera_vuelta[-1])           # al rellenar, no repite la última
        b.cambiar_frases(["Una", "Otra"])
        self.assertEqual(sorted([b.sacar(), b.sacar()]), ["Otra", "Una"])

    def test_las_tres_frases_de_miguel(self):
        for frase in ("No dejes para mañana lo que puedes hacer hoy.", "El día depende de ti, puedes hacerlo grandioso.",
                      "No dejes que tus malos pensamientos te controlen, tú puedes controlarlos."):
            self.assertIn(frase, REFLEXIONES)
        self.assertGreaterEqual(len(REFLEXIONES), 40)

    def test_archivo_de_frases(self):
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = Path(carpeta) / "frases.txt"
            self.assertTrue(guardar_frase_usuario(ruta, "  el que persevera,   alcanza "))
            self.assertFalse(guardar_frase_usuario(ruta, "El que persevera alcanza."))    # ya estaba
            self.assertFalse(guardar_frase_usuario(ruta, "no dejes para mañana lo que puedes hacer hoy"))
            with ruta.open("a", encoding="utf-8") as f:
                f.write("\n# un comentario\nSonríe, que hoy sale bien\n")
            self.assertEqual(leer_frases_usuario(ruta), ["El que persevera, alcanza", "Sonríe, que hoy sale bien"])
            self.assertTrue(ruta.read_text(encoding="utf-8").startswith("# Tus frases"))

    def test_comando_conserva_tildes(self):
        c = interpretar_comando("Lancelot guarda esta frase: Sonríe, Miguel".replace("Lancelot ", ""))
        self.assertEqual((c.accion, c.texto), ("guardar_frase", "Sonríe, Miguel"))
        self.assertEqual(interpretar_comando("motívame").accion, "frase")


@unittest.skipIf(QApplication is None, "PySide6 no está instalado")
class TestAsistenteV310(unittest.TestCase):
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

    def tearDown(self):
        self.a.salir()
        self.a.almacen.con.close()
        self.tmp.cleanup()

    def test_frase_al_dejar_el_mouse_solo_si_esta_libre(self):
        self.assertTrue((Path(self.tmp.name) / "frases.txt").exists())   # el archivo para tus frases
        self.a.cara.reposo.emit()
        self.assertEqual(self.a.burbuja.cabecera.text(), "💬 Lancelot")
        self.assertIn(self.a.burbuja.titulo.text(), REFLEXIONES)
        self.a.burbuja.ocultar()
        self.a.cara.reposo.emit()                                   # muy seguido: no insiste
        self.assertFalse(self.a.burbuja.isVisible())
        self.a._ultima_frase = None
        self.a.ejecutar_comando(interpretar_comando("modo estudio"))
        self.a.burbuja.ocultar()
        self.a.cara.reposo.emit()                                   # estudiando: no interrumpe
        self.assertFalse(self.a.burbuja.isVisible())

    def test_dime_una_frase_y_guardar_una(self):
        self.a.ejecutar_comando(interpretar_comando("guarda esta frase: Hoy toca brillar, Miguel"), por_voz=True)
        self.assertIn("Guardada", self.a.burbuja.titulo.text())
        self.assertEqual(self.dichos[-1], "Listo, guardé tu frase.")
        self.assertIn("Hoy toca brillar, Miguel", leer_frases_usuario(Path(self.tmp.name) / "frases.txt"))
        self.a.ejecutar_comando(interpretar_comando("dime una frase"))
        self.assertEqual(self.a.burbuja.cabecera.text(), "💬 Lancelot")
        self.assertIn("Hoy toca brillar, Miguel", self.a.bolsa_frases.frases)   # ya está en la bolsa

    def test_aviso_anticipado_en_la_burbuja(self):
        ahora = datetime.now()
        t = self.a.almacen.agregar("Aniversario", ahora + timedelta(days=7), "anual", "evento", "7,1")
        self.a.almacen.por_avisar_antes = lambda _ahora: [(self.a.almacen.obtener(t.id), 7)]
        self.a.revisar()
        self.assertEqual(self.a.burbuja.cabecera.text(), "📅 Se acerca")
        self.assertIn("Aniversario: falta 1 semana", self.a.burbuja.titulo.text())
        self.assertTrue(any("se acerca Aniversario" in d for d in self.dichos))

    def test_evento_por_voz(self):
        self.a.voz.procesar_orden("el 15 de diciembre es mi aniversario")
        [t] = self.a.almacen.pendientes()
        self.assertEqual((t.titulo, t.tipo, t.repeticion, t.anticipacion), ("Mi aniversario", "evento", "anual", "7,1"))
        self.assertIn("📅 Evento", self.a.burbuja.titulo.text())

    def test_panel_selector_tarea_evento(self):
        p = self.a.panel
        p.entrada.setText("examen de cálculo el 20/12 a las 8am")
        self.assertEqual(p.selector_tipo.currentData(), "evento")
        self.assertIn("avisa 7 y 1 días antes", p.vista.text())
        p.selector_tipo.setCurrentIndex(p.selector_tipo.findData("tarea"))   # lo corriges a mano
        p._al_enviar()
        [t] = self.a.almacen.pendientes()
        self.assertEqual((t.titulo, t.tipo, t.anticipacion), ("Examen de cálculo", "tarea", None))
        p.empezar_edicion(t)
        p.selector_tipo.setCurrentIndex(p.selector_tipo.findData("evento"))
        p._al_enviar()
        t = self.a.almacen.obtener(t.id)
        self.assertEqual((t.tipo, t.anticipacion), ("evento", "7,1"))


if __name__ == "__main__":
    unittest.main()
