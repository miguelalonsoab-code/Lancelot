"""
Versiones y actualizaciones: lógica pura (sin internet ni ventanas), fácil de probar.

Cómo funciona la búsqueda de actualizaciones:
  1. Publicas una "Release" en GitHub (python construir.py --publicar) con el instalador adjunto.
  2. Lancelot pregunta a la API de GitHub cuál es la última release de tu repositorio.
  3. leer_release() decide si es más nueva que la instalada y dónde está el instalador.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

PATRON_INSTALADOR = re.compile(r"^Lancelot-setup-[\d.]+\.exe$", re.IGNORECASE)
ORIGENES_PERMITIDOS = ("https://github.com/", "https://objects.githubusercontent.com/")


@dataclass
class Actualizacion:
    version: str              # "3.8"
    url_instalador: str       # descarga directa del Lancelot-setup-3.8.exe
    url_pagina: str           # la página de la release (para leer las novedades)
    notas: str                # texto de la release
    tamano: int               # bytes del instalador
    sha256: str | None        # huella del archivo, si GitHub la informa (sirve para verificar la descarga)


def numeros(version: str) -> tuple[int, ...]:
    """'v3.10' -> (3, 10). Así 3.10 es mayor que 3.9 (como texto sería al revés)."""
    partes = re.findall(r"\d+", version)
    return tuple(int(p) for p in partes) or (0,)


def es_mas_nueva(remota: str, local: str) -> bool:
    a, b = numeros(remota), numeros(local)
    largo = max(len(a), len(b))                         # 3.8 == 3.8.0
    return a + (0,) * (largo - len(a)) > b + (0,) * (largo - len(b))


def leer_release(datos: dict, version_local: str) -> Actualizacion | None:
    """
    'datos' es la respuesta de https://api.github.com/repos/USUARIO/REPO/releases/latest.
    Devuelve None si no es más nueva o si no trae un instalador válido.
    """
    if datos.get("draft") or datos.get("prerelease"):
        return None
    version = (datos.get("tag_name") or "").lstrip("vV")
    if not version or not es_mas_nueva(version, version_local):
        return None
    for asset in datos.get("assets") or []:
        url = asset.get("browser_download_url") or ""
        if PATRON_INSTALADOR.match(asset.get("name") or "") and url.startswith(ORIGENES_PERMITIDOS):
            digest = asset.get("digest") or ""
            return Actualizacion(
                version=version,
                url_instalador=url,
                url_pagina=datos.get("html_url") or "",
                notas=(datos.get("body") or "").strip(),
                tamano=int(asset.get("size") or 0),
                sha256=digest.split(":", 1)[1].lower() if digest.startswith("sha256:") else None,
            )
    return None


def notas_de_version(readme: str, version: str) -> str:
    """
    Saca del README la sección '## Novedades vX.Y…' (hasta el siguiente título '# ' o '## ').
    El (?!…) del patrón evita que "3.8" confunda la sección de la "3.8.1".
    """
    m = re.search(rf"^## Novedades v{re.escape(version)}(?![\w.]).*?$(.*?)(?=^##? |\Z)", readme, re.M | re.S)
    return m.group(1).strip() if m else f"Lancelot {version}"


def resumen_notas(notas: str, maximo: int = 180) -> str:
    """Primeras líneas de las novedades, sin formato Markdown, para que quepan en la burbuja."""
    texto = re.sub(r"\*\*|`|^#+\s*", "", notas, flags=re.M)
    lineas = [re.sub(r"^[-*]\s+", "• ", ln.strip()) for ln in texto.splitlines() if ln.strip()]
    resultado = ""
    for linea in lineas:
        if len(resultado) + len(linea) > maximo:
            break
        resultado += ("\n" if resultado else "") + linea
    return resultado or (lineas[0][:maximo] + "…" if lineas else "")
