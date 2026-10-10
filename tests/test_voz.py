"""
Pruebas de la parte de voz que no necesitan micrófono:
    python -m unittest discover tests -v
"""
import sys
import unittest
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from nucleo.comandos import interpretar_comando     # noqa: E402
from nucleo.dialogo import DialogoTarea             # noqa: E402
from nucleo.interprete import interpretar           # noqa: E402
from nucleo.numeros import numeros_a_digitos        # noqa: E402
from voz.apps import App, CatalogoApps              # noqa: E402
from voz.despertar import separar_orden             # noqa: E402

VARIANTES = ["lancelot", "lance lot", "lanzelot", "lance", "lans"]
AHORA = datetime(2026, 10, 8, 20, 0)   # jueves


class TestDespertar(unittest.TestCase):
    def test_casos(self):
        casos = {
            "lancelot abre spotify": (True, "abre spotify"),
            "Lance modo estudio": (True, "modo estudio"),
            "oye lance lot qué hora es": (True, "que hora es"),
            "lancelot": (True, ""),
            "hoy no estudié nada": (False, ""),
            "lanzaron un cohete": (False, ""),       # "lanz..." no basta: tiene que ser la palabra
        }
        for texto, esperado in casos.items():
            with self.subTest(texto=texto):
                self.assertEqual(separar_orden(texto, VARIANTES), esperado)


class TestNumerosHablados(unittest.TestCase):
    def test_conversion(self):
        casos = {
            "mañana a las ocho de la noche pagar la luz": "mañana a las 8 de la noche pagar la luz",
            "en veinte minutos sacar la ropa": "en 20 minutos sacar la ropa",
            "a las siete y cuarenta y cinco": "a las 7 y 45",
            "el quince de octubre": "el 15 de octubre",
            "a la una y media": "a la 1 y media",
            "comprar una pizza": "comprar una pizza",
            "modo estudio cincuenta": "modo estudio 50",
        }
        for texto, esperado in casos.items():
            with self.subTest(texto=texto):
                self.assertEqual(numeros_a_digitos(texto), esperado)

    def test_dictado_completo(self):
        r = interpretar(numeros_a_digitos("recuérdame mañana a las ocho y cuarenta de la noche pagar la luz"), AHORA)
        self.assertEqual((r.titulo, r.fecha), ("Pagar la luz", datetime(2026, 10, 9, 20, 40)))


class TestComandosVoz(unittest.TestCase):
    def test_nuevos(self):
        self.assertEqual(interpretar_comando("abre Spotify").texto, "spotify")
        self.assertEqual(interpretar_comando("ábreme el visual studio code").texto, "visual studio code")
        self.assertEqual(interpretar_comando("¿Qué hora es?").accion, "hora")
        self.assertEqual(interpretar_comando("qué tengo para hoy").accion, "agenda")
        self.assertEqual(interpretar_comando("deja de escuchar").accion, "escucha_off")
        self.assertEqual(interpretar_comando("modo estudio 50").minutos, 50)


class TestCatalogo(unittest.TestCase):
    def setUp(self):
        self.c = CatalogoApps({"youtube": "https://www.youtube.com"})
        for nombre in ["Spotify", "Visual Studio Code", "Microsoft Word", "WordPad", "Calculadora",
                       "Google Chrome", "Configuración"]:
            self.c.apps[nombre.lower().replace("ó", "o")] = App(nombre, nombre, "appid")

    def test_buscar(self):
        casos = {
            "spotify": "Spotify", "visual studio": "Visual Studio Code", "word": "Microsoft Word",
            "la calculadora": "Calculadora", "chrome": "Google Chrome", "configuración": "Configuración",
            "espotifai": "Spotify", "youtube": "Youtube",
        }
        for dicho, nombre in casos.items():
            with self.subTest(dicho=dicho):
                app = self.c.buscar(dicho)
                self.assertIsNotNone(app)
                self.assertEqual(app.nombre, nombre)
        self.assertEqual(self.c.buscar("youtube").tipo, "url")
        self.assertIsNone(self.c.buscar("photoshop"))


class TestJuegosYEscritorio(unittest.TestCase):
    def test_steam_con_dos_bibliotecas(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            steam, d = Path(tmp) / "Steam", Path(tmp) / "SteamLibrary"
            (steam / "steamapps").mkdir(parents=True)
            (d / "steamapps").mkdir(parents=True)
            ruta_d = str(d).replace("\\", "\\\\")       # en el .vdf las \ van dobles
            (steam / "steamapps" / "libraryfolders.vdf").write_text(
                f'"libraryfolders"\n{{\n "0" {{ "path" "{steam}" }}\n "1" {{ "path" "{ruta_d}" }}\n}}')
            (d / "steamapps" / "appmanifest_570.acf").write_text(
                '"AppState"\n{\n\t"appid"\t\t"570"\n\t"name"\t\t"Dota 2"\n}')
            (steam / "steamapps" / "appmanifest_228980.acf").write_text(
                '"AppState" { "appid" "228980" "name" "Steamworks Common Redistributables" }')
            juegos = CatalogoApps.juegos_steam(steam)
            self.assertEqual([(j.nombre, j.destino) for j in juegos], [("Dota 2", "steam://rungameid/570")])

            c = CatalogoApps()
            for j in juegos:
                c.apps[j.nombre.lower()] = j
            self.assertEqual(c.buscar("dota").nombre, "Dota 2")          # "abre dota"
            from nucleo.numeros import numeros_a_digitos
            self.assertEqual(c.buscar(numeros_a_digitos("dota dos")).nombre, "Dota 2")  # dicho por voz

    def test_escritorio(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "Fortnite.url").write_text("[InternetShortcut]")
            (Path(tmp) / "notas.txt").write_text("x")
            apps = CatalogoApps.accesos_escritorio([Path(tmp), Path(tmp) / "no_existe"])
            self.assertEqual([a.nombre for a in apps], ["Fortnite"])


class TestWeb(unittest.TestCase):
    SITIOS = {"netflix": "https://www.netflix.com", "youtube": "https://www.youtube.com"}

    def test_comandos(self):
        from voz.web import navegador_exe
        c = interpretar_comando("abre netflix desde chrome")
        self.assertEqual((c.accion, c.texto, navegador_exe(c.navegador)), ("abrir_web", "netflix", "chrome.exe"))
        c = interpretar_comando("entra a youtube en el navegador")
        self.assertEqual((c.accion, c.texto, c.navegador), ("abrir_web", "youtube", None))
        c = interpretar_comando("abre la página de netflix con google chrome")
        self.assertEqual((c.texto, navegador_exe(c.navegador)), ("pagina de netflix", "chrome.exe"))
        c = interpretar_comando("busca música para estudiar en youtube desde edge")
        self.assertEqual((c.accion, c.texto, c.destino, navegador_exe(c.navegador)),
                         ("buscar", "musica para estudiar", "youtube", "msedge.exe"))
        # Sin navegador sigue siendo el "abre" normal (app del menú Inicio)
        self.assertEqual(interpretar_comando("abre netflix").accion, "abrir")

    def test_resolver(self):
        from voz.web import resolver_sitio
        self.assertEqual(resolver_sitio("netflix", self.SITIOS)[1], "https://www.netflix.com")
        self.assertEqual(resolver_sitio("la pagina de netflix", self.SITIOS)[1], "https://www.netflix.com")
        self.assertEqual(resolver_sitio("netflis", self.SITIOS)[1], "https://www.netflix.com")   # mal oído
        self.assertEqual(resolver_sitio("upn punto edu punto pe", self.SITIOS)[1], "https://upn.edu.pe")
        nombre, url, conocido = resolver_sitio("recetas de pollo", self.SITIOS)
        self.assertFalse(conocido)
        self.assertEqual(url, "https://www.google.com/search?q=recetas+de+pollo")


class TestApodos(unittest.TestCase):
    def test_comando(self):
        c = interpretar_comando("cuando diga el código abre visual studio code")
        self.assertEqual((c.accion, c.texto, c.destino), ("apodo", "el codigo", "visual studio code"))
        c = interpretar_comando("si te digo música abres spotify")
        self.assertEqual((c.texto, c.destino), ("musica", "spotify"))
        # El (.+?) perezoso corta en el PRIMER "abre"
        c = interpretar_comando("cuando diga trabajo abre el abre fácil")
        self.assertEqual((c.texto, c.destino), ("trabajo", "abre facil"))
        self.assertEqual(interpretar_comando("olvida el apodo el código").texto, "el codigo")
        self.assertEqual(interpretar_comando("mis apodos").accion, "apodos")

    def test_catalogo_con_apodos(self):
        c = CatalogoApps()
        c.apps["visual studio code"] = App("Visual Studio Code", "VSCode", "appid")
        c.apps["spotify"] = App("Spotify", "Spotify", "appid")
        c.agregar_alias("el codigo", "Visual Studio Code")
        self.assertEqual(c.buscar("el código").nombre, "Visual Studio Code")
        self.assertEqual(c.buscar("código").nombre, "Visual Studio Code")
        # Un apodo con el mismo nombre que una app real no la rompe, y al quitarlo vuelve
        c.agregar_alias("spotify", "Visual Studio Code")
        self.assertEqual(c.buscar("spotify").nombre, "Visual Studio Code")
        c.quitar_alias("spotify")
        self.assertEqual(c.buscar("spotify").nombre, "Spotify")
        # Apodo hacia sí misma no entra en bucle
        c.agregar_alias("spotify", "Spotify")
        self.assertEqual(c.buscar("spotify").nombre, "Spotify")

    def test_guardar_en_base_de_datos(self):
        import tempfile
        from nucleo.almacen import Almacen
        with tempfile.TemporaryDirectory() as tmp:
            a = Almacen(Path(tmp) / "t.db")
            a.guardar_apodo("el codigo", "Visual Studio Code")
            a.guardar_apodo("el codigo", "Cursor")              # actualizar, no duplicar
            self.assertEqual(a.apodos(), [("el codigo", "Cursor")])
            self.assertTrue(a.borrar_apodo("el codigo"))
            self.assertFalse(a.borrar_apodo("el codigo"))
            a.con.close()


class TestDialogo(unittest.TestCase):
    def test_falta_fecha(self):
        d = DialogoTarea("recuérdame comprar pan", "Comprar pan", None, None)
        self.assertEqual(d.siguiente().tipo, "preguntar")
        paso = d.responder("mañana a las ocho de la noche", AHORA)
        self.assertEqual((paso.tipo, paso.titulo, paso.fecha),
                         ("crear", "Comprar pan", datetime(2026, 10, 9, 20, 0)))

    def test_falta_titulo(self):
        d = DialogoTarea("recuérdame mañana a las 5", "", datetime(2026, 10, 9, 17, 0), None)
        self.assertEqual(d.siguiente().texto, "¿Qué te recuerdo?")
        paso = d.responder("llamar al banco", AHORA)
        self.assertEqual((paso.tipo, paso.titulo), ("crear", "Llamar al banco"))

    def test_faltan_los_dos_y_responde_todo_junto(self):
        d = DialogoTarea("recuérdame", "", None, None)
        paso = d.responder("estudiar SQL el viernes a las cuatro de la tarde", AHORA)
        self.assertEqual((paso.tipo, paso.titulo, paso.fecha),
                         ("crear", "Estudiar SQL", datetime(2026, 10, 9, 16, 0)))

    def test_no_entiende_dos_veces_se_rinde(self):
        d = DialogoTarea("recuérdame comprar pan", "Comprar pan", None, None)
        self.assertEqual(d.responder("el gato", AHORA).tipo, "preguntar")
        self.assertEqual(d.responder("azul", AHORA).tipo, "rendirse")

    def test_cancelar(self):
        d = DialogoTarea("recuérdame comprar pan", "Comprar pan", None, None)
        self.assertEqual(d.responder("olvídalo", AHORA).tipo, "cancelar")

    def test_repeticion_en_la_respuesta(self):
        d = DialogoTarea("recuérdame tomar agua", "Tomar agua", None, None)
        paso = d.responder("todos los días a las diez", AHORA)
        self.assertEqual((paso.tipo, paso.repeticion), ("crear", "diaria"))


if __name__ == "__main__":
    unittest.main()
