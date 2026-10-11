"""
Buscar, descargar e instalar actualizaciones desde las Releases de GitHub.

Todo lo que toca internet corre en un hilo aparte (la cara nunca se congela) y avisa
con señales de Qt. Las decisiones (preguntarte, cuándo instalar) las toma app.py.

Seguridad:
  - Solo descarga desde github.com, y solo un archivo llamado Lancelot-setup-X.Y.exe.
  - Si GitHub informa la huella SHA-256 del archivo, se comprueba: un archivo dañado
    o cambiado en el camino se descarta y no se ejecuta.
  - No envía nada tuyo: solo pregunta "¿cuál es la última versión?".
"""
from __future__ import annotations

import hashlib
import json
import logging
import subprocess
import sys
import threading
import urllib.error
import urllib.request
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from nucleo.version import Actualizacion, leer_release, numeros

log = logging.getLogger(__name__)

API = "https://api.github.com/repos/{repo}/releases/latest"


class Actualizador(QObject):
    encontrada = Signal(object, bool)     # Actualizacion, ¿la pediste tú?
    sin_novedad = Signal(str, bool)       # explicación, ¿la pediste tú?
    descargada = Signal(str)              # ruta del instalador ya verificado
    fallo = Signal(str)

    def __init__(self, repo: str, version_local: str, carpeta_descargas: Path):
        super().__init__()
        self.repo = repo.strip().strip("/")
        self.version_local = version_local
        self.carpeta = carpeta_descargas
        self._ocupado = False

    # ------------------------------------------------------------------ buscar
    def buscar(self, manual: bool = False):
        if not self.repo or self._ocupado:
            return
        self._ocupado = True
        threading.Thread(target=self._buscar, args=(manual,), daemon=True, name="actualizaciones").start()

    def _buscar(self, manual: bool):
        try:
            datos = self.pedir_json(API.format(repo=self.repo))
            act = leer_release(datos, self.version_local)
            if act:
                log.info("actualización disponible: %s", act.version)
                self.encontrada.emit(act, manual)
            else:
                self.sin_novedad.emit(f"Tienes la última versión ({self.version_local}).", manual)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                texto = (f"No encontré versiones publicadas en «{self.repo}». "
                         "¿El repositorio es privado o aún no tiene Releases?")
            else:
                texto = f"GitHub respondió con un error ({e.code}). Lo intento más tarde."
            log.warning("buscar actualizaciones: HTTP %s", e.code)
            self.sin_novedad.emit(texto, manual)
        except Exception as e:                              # sin internet, DNS, etc.
            log.warning("buscar actualizaciones: %s", e)
            self.sin_novedad.emit("No pude conectarme a GitHub. ¿Hay internet?", manual)
        finally:
            self._ocupado = False

    def pedir_json(self, url: str) -> dict:
        """Separado para poder reemplazarlo en las pruebas."""
        pedido = urllib.request.Request(url, headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": f"Lancelot/{self.version_local}",      # GitHub exige un User-Agent
        })
        with urllib.request.urlopen(pedido, timeout=15) as r:
            return json.load(r)

    # --------------------------------------------------------------- descargar
    def descargar(self, act: Actualizacion):
        if self._ocupado:
            return
        self._ocupado = True
        threading.Thread(target=self._descargar, args=(act,), daemon=True, name="descarga").start()

    def _descargar(self, act: Actualizacion):
        destino = self.carpeta / f"Lancelot-setup-{act.version}.exe"
        parcial = destino.with_suffix(".part")
        try:
            self.carpeta.mkdir(parents=True, exist_ok=True)
            huella = hashlib.sha256()
            pedido = urllib.request.Request(act.url_instalador,
                                            headers={"User-Agent": f"Lancelot/{self.version_local}"})
            with urllib.request.urlopen(pedido, timeout=30) as r, open(parcial, "wb") as f:
                while bloque := r.read(1024 * 256):
                    f.write(bloque)
                    huella.update(bloque)
            if act.tamano and parcial.stat().st_size != act.tamano:
                raise ValueError("la descarga quedó incompleta")
            if act.sha256 and huella.hexdigest() != act.sha256:
                raise ValueError("la huella SHA-256 no coincide (archivo dañado o modificado)")
            parcial.replace(destino)
            log.info("instalador descargado: %s", destino.name)
            self.descargada.emit(str(destino))
        except Exception as e:
            parcial.unlink(missing_ok=True)
            log.exception("no se pudo descargar la actualización")
            self.fallo.emit(f"No pude descargar la versión {act.version}: {e}")
        finally:
            self._ocupado = False

    # ---------------------------------------------------------------- instalar
    @staticmethod
    def instalar(ruta: str):
        """
        Lanza el instalador en modo /SILENT (solo barra de progreso, sin preguntas) unos
        segundos DESPUÉS, para que Lancelot alcance a cerrarse y suelte sus archivos.
        Al terminar, el instalador vuelve a abrir Lancelot (ver [Run] en lancelot.iss).
        """
        if sys.platform != "win32":
            log.info("instalar %s (solo en Windows)", ruta)
            return
        p = ruta.replace("'", "''")
        orden = (f"Start-Sleep -Seconds 4; "
                 f"Start-Process -FilePath '{p}' -ArgumentList '/SILENT','/NORESTART'")
        subprocess.Popen(["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", orden],
                         creationflags=0x08000000 | 0x00000200)   # sin ventana · grupo propio (sobrevive al cierre)

    def limpiar_descargas(self):
        """Borra instaladores viejos (de versiones iguales o anteriores a la actual)."""
        if not self.carpeta.is_dir():
            return
        for archivo in self.carpeta.glob("Lancelot-setup-*"):
            version = archivo.name.removeprefix("Lancelot-setup-").split(".exe")[0].removesuffix(".part")
            if archivo.suffix == ".part" or numeros(version) <= numeros(self.version_local):
                archivo.unlink(missing_ok=True)
