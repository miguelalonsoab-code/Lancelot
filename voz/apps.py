"""
Catálogo de aplicaciones para "Lancelot, abre ...".

De dónde salen las apps:
1. El comando de Windows `Get-StartApps`: devuelve TODO lo que aparece en tu
   menú Inicio (programas clásicos y apps de la Tienda, como Spotify o WhatsApp).
2. Si eso falla, se buscan los accesos directos (.lnk) de las carpetas del menú Inicio.
3. APPS_EXTRA de config.py: alias tuyos, incluidas páginas web.

Seguridad: solo se abre algo que esté en este catálogo. La voz nunca ejecuta
comandos arbitrarios del sistema.
"""
from __future__ import annotations

import difflib
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from nucleo.interprete import normalizar

_SIN_VENTANA = 0x08000000          # CREATE_NO_WINDOW: que no parpadee una consola


@dataclass
class App:
    nombre: str        # cómo se muestra: "Spotify"
    destino: str       # AppID de Windows, ruta a un .lnk o una URL
    tipo: str          # "appid" | "archivo" | "url" | "alias" (apodo de otra app del catálogo)


class CatalogoApps:
    def __init__(self, extra: dict[str, str] | None = None):
        self.apps: dict[str, App] = {}          # clave = nombre normalizado
        self._tapadas: dict[str, App] = {}      # apps reales "tapadas" por un apodo con su mismo nombre
        for alias, destino in (extra or {}).items():
            self.agregar_alias(alias, destino)

    def agregar_alias(self, alias: str, destino: str):
        """
        destino puede ser:
          - una página o protocolo: "https://..." , "spotify:" , "shell:AppsFolder\\..."
          - una ruta: "C:\\Program Files\\...\\app.exe"
          - el NOMBRE de otra app del catálogo: "Visual Studio Code"  (apodo)
        """
        if re.match(r"^[a-z]:\\", destino, re.I) or destino.lower().endswith((".exe", ".lnk")):
            tipo = "archivo"
        elif re.match(r"^[a-z][a-z0-9+.-]*:", destino, re.I):
            tipo = "url"
        else:
            tipo = "alias"
        clave = normalizar(alias)
        if clave in self.apps and self.apps[clave].tipo != "alias":
            self._tapadas[clave] = self.apps[clave]
        self.apps[clave] = App(alias.title(), destino, tipo)

    def quitar_alias(self, alias: str):
        clave = normalizar(alias)
        if clave in self.apps and self.apps[clave].tipo == "alias":
            del self.apps[clave]
            if clave in self._tapadas:                  # devolver la app real que tapaba
                self.apps[clave] = self._tapadas.pop(clave)

    # ------------------------------------------------------------ cargar
    def cargar_de_windows(self) -> int:
        """Lento (~1 s): llamarlo en segundo plano. Devuelve cuántas apps encontró."""
        if sys.platform != "win32":
            return 0
        encontradas = self._get_start_apps() or self._accesos_directos()
        # Steam casi nunca crea accesos en el menú Inicio: se leen sus juegos instalados
        # y, además, los accesos directos del escritorio (juegos de Epic, programas portables…)
        encontradas += self.juegos_steam(ruta_steam()) + self.accesos_escritorio(carpetas_escritorio())
        for app in encontradas:
            self.apps.setdefault(normalizar(app.nombre), app)   # los alias tuyos ganan
        return len(encontradas)

    # --------------------------------------------------------- juegos de Steam
    @staticmethod
    def juegos_steam(steam: Path | None) -> list[App]:
        """
        Steam guarda un archivo 'appmanifest_<id>.acf' por cada juego instalado, en cada
        biblioteca (puedes tener juegos en C: y en D:). Las bibliotecas están listadas en
        steamapps/libraryfolders.vdf. Para abrir un juego basta la URL steam://rungameid/<id>.
        """
        if not steam or not steam.is_dir():
            return []
        bibliotecas = {steam}
        vdf = steam / "steamapps" / "libraryfolders.vdf"
        if vdf.is_file():
            texto = vdf.read_text(encoding="utf-8", errors="replace")
            for ruta in re.findall(r'"path"\s+"(.+?)"', texto):
                bibliotecas.add(Path(ruta.replace("\\\\", "\\")))
        juegos = []
        for biblioteca in bibliotecas:
            for manifiesto in (biblioteca / "steamapps").glob("appmanifest_*.acf"):
                texto = manifiesto.read_text(encoding="utf-8", errors="replace")
                appid = re.search(r'"appid"\s+"(\d+)"', texto)
                nombre = re.search(r'"name"\s+"(.+?)"', texto)
                if appid and nombre and not re.search(r"redistributable|steamworks|proton|runtime",
                                                      nombre.group(1), re.I):
                    juegos.append(App(nombre.group(1), f"steam://rungameid/{appid.group(1)}", "url"))
        return juegos

    # ------------------------------------------------- accesos del escritorio
    @staticmethod
    def accesos_escritorio(carpetas: list[Path]) -> list[App]:
        apps = []
        for carpeta in carpetas:
            if carpeta.is_dir():
                for archivo in list(carpeta.glob("*.lnk")) + list(carpeta.glob("*.url")):
                    apps.append(App(archivo.stem, str(archivo), "archivo"))
        return apps

    def _get_start_apps(self) -> list[App]:
        orden = ("[Console]::OutputEncoding=[Text.Encoding]::UTF8; "
                 "Get-StartApps | Select-Object Name, AppID | ConvertTo-Json -Compress")
        try:
            r = subprocess.run(["powershell", "-NoProfile", "-Command", orden], capture_output=True,
                               timeout=25, creationflags=_SIN_VENTANA)
            datos = json.loads(r.stdout.decode("utf-8", errors="replace") or "[]")
        except Exception:
            return []
        if isinstance(datos, dict):
            datos = [datos]
        return [App(d["Name"], d["AppID"], "appid") for d in datos if d.get("Name") and d.get("AppID")]

    def _accesos_directos(self) -> list[App]:
        carpetas = [Path(os.environ.get("PROGRAMDATA", "")) / "Microsoft/Windows/Start Menu/Programs",
                    Path(os.environ.get("APPDATA", "")) / "Microsoft/Windows/Start Menu/Programs"]
        apps = []
        for carpeta in carpetas:
            if carpeta.is_dir():
                for lnk in carpeta.rglob("*.lnk"):
                    if "uninstall" not in lnk.stem.lower() and "desinstalar" not in lnk.stem.lower():
                        apps.append(App(lnk.stem, str(lnk), "archivo"))
        return apps

    # ------------------------------------------------------------- buscar
    def buscar(self, consulta: str) -> App | None:
        app = self._buscar(consulta, self.apps)
        if app and app.tipo == "alias":          # apodo: buscar la app REAL a la que apunta
            reales = {k: v for k, v in self.apps.items() if v.tipo != "alias"} | self._tapadas
            return self._buscar(app.destino, reales)
        return app

    def _buscar(self, consulta: str, apps: dict[str, App]) -> App | None:
        q = normalizar(consulta).strip(" .")
        q = re.sub(r"^(?:el|la|los|las|mi|un|una|app|aplicacion|programa)\s+", "", q)
        q = re.sub(r"\s+(?:por favor|porfa|porfavor)$", "", q)
        if not q:
            return None
        if q in apps:
            return apps[q]
        # 1) Lo dicho aparece como palabra(s) completas: "word" -> "microsoft word",
        #    "visual studio" -> "visual studio code"
        candidatos = [k for k in apps if re.search(r"\b" + re.escape(q) + r"\b", k)]
        # 2) Lo dicho es el comienzo de un nombre: "spoti" -> "spotify"
        if not candidatos:
            candidatos = [k for k in apps if k.startswith(q)]
        if candidatos:
            return apps[min(candidatos, key=len)]       # el nombre más corto suele ser el principal
        # Parecido (errores del reconocedor): "espotifai" -> "spotify"
        parecido = difflib.get_close_matches(q, list(apps), n=1, cutoff=0.72)
        return apps[parecido[0]] if parecido else None

    # -------------------------------------------------------------- abrir
    @staticmethod
    def abrir(app: App) -> None:
        if sys.platform != "win32":
            raise OSError("Abrir apps solo está implementado para Windows")
        if app.tipo == "appid":
            os.startfile("shell:AppsFolder\\" + app.destino)
        else:
            os.startfile(app.destino)        # .lnk, .exe o URL (se abre en tu navegador)


# ---------------------------------------------------------------- ubicaciones
def ruta_steam() -> Path | None:
    """Dónde está instalado Steam: primero lo que dice el registro de Windows."""
    if sys.platform == "win32":
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as clave:
                return Path(winreg.QueryValueEx(clave, "SteamPath")[0])
        except OSError:
            pass
    for candidato in (Path(r"C:\Program Files (x86)\Steam"), Path(r"C:\Program Files\Steam")):
        if candidato.is_dir():
            return candidato
    return None


def carpetas_escritorio() -> list[Path]:
    """El escritorio puede estar en el perfil, dentro de OneDrive (en español: 'Escritorio') o ser el público."""
    casa = Path(os.environ.get("USERPROFILE", Path.home()))
    onedrive = Path(os.environ.get("OneDrive", casa / "OneDrive"))
    publico = Path(os.environ.get("PUBLIC", r"C:\Users\Public"))
    return [casa / "Desktop", casa / "Escritorio", onedrive / "Desktop", onedrive / "Escritorio",
            publico / "Desktop"]
