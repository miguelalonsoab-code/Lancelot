"""
Páginas web y navegadores: "abre netflix desde chrome", "busca lofi en youtube".

Cómo se decide la dirección (URL) de lo que dijiste:
  1. Tus páginas de APPS_EXTRA (config.py), si son URL.
  2. SITIOS_CONOCIDOS (config.py): netflix, youtube, gmail, etc.
  3. Si dijiste un dominio ("upn punto edu punto pe"), se arma https://upn.edu.pe
  4. Si no se reconoce, se busca en Google (nunca se inventa una dirección).

Para abrir en un navegador concreto se usa os.startfile("chrome.exe", ..., url):
Windows sabe dónde está instalado cada navegador (registro "App Paths"), así que
no hay que escribir rutas. Solo se aceptan navegadores de la lista NAVEGADORES.
"""
from __future__ import annotations

import difflib
import os
import re
import sys
from urllib.parse import quote_plus

from nucleo.interprete import normalizar

# Cómo lo dices -> ejecutable que Windows conoce
NAVEGADORES = {
    "chrome": "chrome.exe", "google chrome": "chrome.exe",
    "edge": "msedge.exe", "microsoft edge": "msedge.exe",
    "firefox": "firefox.exe", "mozilla firefox": "firefox.exe", "mozilla": "firefox.exe",
    "brave": "brave.exe",
    "opera": "opera.exe",
}
NOMBRE_NAVEGADOR = {"chrome.exe": "Chrome", "msedge.exe": "Edge", "firefox.exe": "Firefox",
                    "brave.exe": "Brave", "opera.exe": "Opera"}

BUSCADORES = {
    "google": "https://www.google.com/search?q={}",
    "youtube": "https://www.youtube.com/results?search_query={}",
    "wikipedia": "https://es.wikipedia.org/w/index.php?search={}",
}


def navegador_exe(dicho: str | None) -> str | None:
    """'google chrome' -> 'chrome.exe'. None = usar el navegador predeterminado."""
    if not dicho:
        return None
    return NAVEGADORES.get(normalizar(dicho).replace("el ", "").strip())


def resolver_sitio(dicho: str, sitios: dict[str, str]) -> tuple[str, str, bool]:
    """
    Devuelve (nombre para mostrar, url, conocido).
    conocido=False significa que no se reconoció y se armó una búsqueda en Google.
    """
    t = normalizar(dicho).strip(" .")
    t = re.sub(r"^(?:la pagina de |la pagina |la web de |el sitio de |pagina de |pagina )", "", t)
    claves = {normalizar(k): (k, v) for k, v in sitios.items()}
    if t in claves:
        nombre, url = claves[t]
        return nombre.title(), url, True
    # Dominio dicho en voz alta: "upn punto edu punto pe" -> "upn.edu.pe"
    dominio = re.sub(r"\s*\bpunto\b\s*", ".", t).replace(" ", "")
    if re.fullmatch(r"[a-z0-9-]+(\.[a-z0-9-]+)+", dominio):
        return dominio, "https://" + dominio, True
    # Parecido (errores del reconocedor): "netflis" -> "netflix"
    parecido = difflib.get_close_matches(t, list(claves), n=1, cutoff=0.75)
    if parecido:
        nombre, url = claves[parecido[0]]
        return nombre.title(), url, True
    return dicho, url_busqueda("google", dicho), False


def url_busqueda(buscador: str, consulta: str) -> str:
    plantilla = BUSCADORES.get(normalizar(buscador), BUSCADORES["google"])
    return plantilla.format(quote_plus(consulta.strip()))


def abrir_url(url: str, exe: str | None = None) -> bool:
    """
    Abre la URL en el navegador pedido (exe) o en el predeterminado.
    Devuelve False si el navegador pedido no está instalado (y se usó el predeterminado).
    """
    if sys.platform != "win32":
        raise OSError("Abrir páginas solo está implementado para Windows")
    if not url.startswith(("http://", "https://")):
        raise ValueError("Solo se abren direcciones http(s)")
    if exe:
        try:
            os.startfile(exe, "open", url)       # Windows busca dónde está instalado
            return True
        except OSError:
            pass
    os.startfile(url)
    return exe is None
