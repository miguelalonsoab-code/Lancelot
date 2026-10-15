"""
Sincronización con el servidor de Cloudflare (y, a través de él, con el celular).

Cada minuto, y unos segundos después de cada cambio que hagas en la laptop:

    laptop ──{ desde, cambios de aquí }──► /api/sync ──► servidor
    laptop ◄──{ cambios de allá, cursor }──────────────┘

Todo lo que toca internet corre en un hilo aparte y avisa con una señal; los cambios a la
base de datos los hace app.py en el hilo principal (SQLite no se comparte entre hilos).

La dirección y la clave las escribe "npm run configurar" en nube.json, dentro de tu carpeta de datos.
Sin ese archivo, Lancelot funciona igual que antes, sin sincronizar.
"""
from __future__ import annotations

import json
import logging
import threading
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

from PySide6.QtCore import QObject, Signal

log = logging.getLogger(__name__)


@dataclass
class Resultado:
    ok: bool
    subidos: list[dict] = field(default_factory=list)     # lo que se mandó (para marcarlo como sincronizado)
    cambios: list[dict] = field(default_factory=list)     # lo que llegó del servidor
    cursor: int = 0
    completo: bool = True
    rechazados: list[dict] = field(default_factory=list)
    error: str = ""


def leer_configuracion(ruta: Path) -> tuple[str, str] | None:
    """(url, clave) de nube.json, o None si no está o está incompleto."""
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
        url, clave = str(datos["url"]).rstrip("/"), str(datos["clave"])
    except (OSError, ValueError, KeyError, TypeError):
        return None
    if not url.startswith("https://") or not clave:
        return None
    return url, clave


class Sincronizador(QObject):
    terminado = Signal(object)            # Resultado

    def __init__(self, url: str, clave: str, version: str):
        super().__init__()
        self.url, self.clave, self.version = url, clave, version
        self.ocupado = False

    def sincronizar(self, desde: int, cambios: list[dict]) -> bool:
        """Empieza en segundo plano. Devuelve False si ya había una sincronización en curso."""
        if self.ocupado:
            return False
        self.ocupado = True
        threading.Thread(target=self._trabajar, args=(desde, cambios), daemon=True, name="sincronizar").start()
        return True

    def _trabajar(self, desde: int, cambios: list[dict]):
        try:
            datos = self.pedir({"desde": desde, "cambios": cambios})
            resultado = Resultado(True, cambios, datos.get("cambios", []), int(datos.get("cursor", desde)),
                                  bool(datos.get("completo", True)), datos.get("rechazados", []))
        except urllib.error.HTTPError as e:
            texto = ("La clave no coincide con la del servidor. Vuelve a ejecutar «npm run configurar»."
                     if e.code == 401 else f"El servidor respondió con un error ({e.code}).")
            log.warning("sincronizar: HTTP %s", e.code)
            resultado = Resultado(False, error=texto)
        except Exception as e:                                    # sin internet, DNS, tiempo agotado…
            log.info("sincronizar: sin conexión (%s)", e)
            resultado = Resultado(False, error="Sin conexión con el servidor. Lo intento de nuevo en un minuto.")
        finally:
            self.ocupado = False
        self.terminado.emit(resultado)

    def pedir(self, cuerpo: dict) -> dict:
        """Separado para poder reemplazarlo en las pruebas."""
        pedido = urllib.request.Request(
            self.url + "/api/sync", data=json.dumps(cuerpo).encode("utf-8"), method="POST",
            headers={"Authorization": f"Bearer {self.clave}", "Content-Type": "application/json",
                     "User-Agent": f"Lancelot/{self.version}"})
        with urllib.request.urlopen(pedido, timeout=20) as r:
            return json.load(r)
