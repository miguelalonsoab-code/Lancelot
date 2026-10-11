"""
El oído del asistente: micrófono + reconocimiento de voz con Vosk, 100 % local.

Cómo funciona:
- Un hilo aparte lee el micrófono en trozos de ~0.25 s y se los pasa a Vosk.
- Vosk avisa cuando terminaste una frase (detecta el silencio) y da el texto.
- Dos formas de usarlo:
    1. Escucha continua: espera oír el nombre ("Lancelot ...") al inicio de la frase.
    2. Una orden (atajo de teclado): toma la siguiente frase que digas, sin nombre.
- El micrófono solo está abierto cuando hace falta: si la escucha continua está
  apagada, se abre al pulsar el atajo y se cierra al terminar la orden.

El modelo (39 MB) se descarga solo la primera vez y queda en datos/voz/.
Nada de lo que dices sale de tu laptop.
"""
from __future__ import annotations

import json
import queue
import shutil
import threading
import time
import urllib.request
import zipfile
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from voz.despertar import separar_orden


class Oido(QObject):
    orden = Signal(str)               # texto de la orden, ya sin el nombre
    llamado = Signal()                # dijiste solo el nombre: espera la orden
    escuchando = Signal(bool)         # True mientras espera una orden (la cara lo muestra)
    estado = Signal(str, str)         # (tipo, detalle): "preparando" | "descargando" | "listo" | "error" | "sin_orden"
    oido = Signal(str)                # todo lo que reconoce (para depurar / probar_voz.py)

    def __init__(self, carpeta: Path, nombre_modelo: str, url_modelo: str, variantes: list[str],
                 segundos_espera: int, carpeta_incluida: Path | None = None):
        super().__init__()
        self.carpeta = carpeta
        self.carpeta_incluida = carpeta_incluida      # el modelo que trae el instalador (si hay)
        self.nombre_modelo = nombre_modelo
        self.url_modelo = url_modelo
        self.variantes = variantes
        self.segundos_espera = segundos_espera

        self.continuo = False
        self.listo = False
        self._espera_hasta = 0.0          # >0: esperando una orden hasta ese momento
        self._silenciado = False          # mientras el asistente habla, no se escucha a sí mismo
        self._reiniciar = False
        self._orden_pendiente = False
        self._segundos_orden = segundos_espera
        self._fin = False
        self._hilo: threading.Thread | None = None

    # ============================================================ API (hilo Qt)
    def activar_continuo(self, activo: bool):
        self.continuo = activo
        if activo:
            self._arrancar()

    def escuchar_una_orden(self, segundos: int | None = None):
        self._segundos_orden = segundos or self.segundos_espera + 2
        if self.listo:
            self._espera_hasta = time.monotonic() + self._segundos_orden
        else:
            self._orden_pendiente = True  # la primera vez hay que cargar el modelo antes
        self._reiniciar = True            # descartar lo que estaba a medio oír
        self.escuchando.emit(True)
        self._arrancar()

    def silenciar(self, si: bool):
        self._silenciado = si
        if not si:
            self._reiniciar = True        # no mezclar el final de su propia voz

    def detener(self):
        self._fin = True

    # ================================================================ el hilo
    def _arrancar(self):
        if self._hilo is None or not self._hilo.is_alive():
            self._fin = False
            self._hilo = threading.Thread(target=self._bucle, daemon=True, name="oido")
            self._hilo.start()

    def _bucle(self):
        try:
            import sounddevice as sd
            from vosk import KaldiRecognizer, Model, SetLogLevel
        except Exception as e:
            self.estado.emit("error", f"Faltan librerías de voz ({e}). Ejecuta: pip install -r requirements.txt")
            self._orden_pendiente = False
            self.escuchando.emit(False)
            return
        try:
            SetLogLevel(-1)
            ruta = self._asegurar_modelo()
            self.estado.emit("preparando", "Cargando el modelo de voz…")
            modelo = Model(str(ruta))
            self.listo = True
            self.estado.emit("listo", "")
            if self._orden_pendiente:          # pulsaste el atajo mientras cargaba
                self._orden_pendiente = False
                self._espera_hasta = time.monotonic() + self._segundos_orden
        except Exception as e:
            self.estado.emit("error", f"No se pudo preparar el reconocimiento de voz: {e}")
            self._orden_pendiente = False
            self.continuo = False
            self.escuchando.emit(False)
            return

        audio: queue.Queue[bytes] = queue.Queue()
        stream = None
        rec = None
        while not self._fin:
            necesita_mic = self.continuo or self._espera_hasta > 0
            if not necesita_mic:
                if stream:
                    stream.stop(); stream.close(); stream = None
                time.sleep(0.15)
                continue
            if stream is None:
                try:
                    tasa = int(sd.query_devices(kind="input")["default_samplerate"])
                    stream = sd.RawInputStream(samplerate=tasa, blocksize=tasa // 4, dtype="int16",
                                               channels=1, callback=lambda d, *_: audio.put(bytes(d)))
                    stream.start()
                    rec = KaldiRecognizer(modelo, tasa)
                except Exception as e:
                    self.estado.emit("error", f"No pude abrir el micrófono: {e}")
                    self.continuo = False
                    self._cancelar_espera()
                    stream = None
                    continue

            self._revisar_tiempo()
            try:
                datos = audio.get(timeout=0.3)
            except queue.Empty:
                continue
            if self._reiniciar:
                rec.Reset()
                self._reiniciar = False
                while not audio.empty():
                    audio.get_nowait()
                continue
            if self._silenciado:
                continue
            if rec.AcceptWaveform(datos):
                texto = json.loads(rec.Result()).get("text", "").strip()
                if texto:
                    self.oido.emit(texto)
                    self._procesar(texto)

        if stream:
            stream.stop(); stream.close()

    def _procesar(self, texto: str):
        activado, resto = separar_orden(texto, self.variantes)
        if self._espera_hasta > 0:                 # estaba esperando una orden
            orden_ = resto if activado else texto
            if orden_:
                self._cancelar_espera()
                self.orden.emit(orden_)
            return
        if self.continuo and activado:
            if resto:
                self.orden.emit(resto)
            else:
                self._espera_hasta = time.monotonic() + self.segundos_espera
                self.escuchando.emit(True)
                self.llamado.emit()

    def _revisar_tiempo(self):
        if self._espera_hasta and time.monotonic() > self._espera_hasta:
            self._cancelar_espera()
            self.estado.emit("sin_orden", "")

    def _cancelar_espera(self):
        if self._espera_hasta:
            self._espera_hasta = 0.0
            self.escuchando.emit(False)

    # ========================================================== modelo de voz
    def _asegurar_modelo(self) -> Path:
        return asegurar_modelo(self.carpeta, self.nombre_modelo, self.url_modelo,
                               lambda p: self.estado.emit("descargando", p), self.carpeta_incluida)


def modelo_valido(ruta: Path) -> bool:
    return (ruta / "am").is_dir() or (ruta / "conf").is_dir()


def asegurar_modelo(carpeta: Path, nombre_modelo: str, url: str, avisar=print,
                    incluida: Path | None = None) -> Path:
    """
    Devuelve la carpeta del modelo. Busca, en orden:
      1. en tus datos (carpeta), 2. el que trae el instalador (incluida),
      3. si no está en ninguno, lo descarga y descomprime en tus datos (una sola vez).
    """
    destino = carpeta / nombre_modelo
    if modelo_valido(destino):
        return destino
    if incluida and modelo_valido(incluida / nombre_modelo):
        return incluida / nombre_modelo
    carpeta.mkdir(parents=True, exist_ok=True)
    zip_path = carpeta / "modelo.zip"
    ultimo = [-1]

    def progreso(bloques, tam_bloque, total):
        if total > 0:
            pct = min(100, bloques * tam_bloque * 100 // total)
            if pct // 10 != ultimo[0]:
                ultimo[0] = pct // 10
                avisar(f"{pct} %")

    urllib.request.urlretrieve(url, zip_path, progreso)
    with zipfile.ZipFile(zip_path) as z:
        for miembro in z.namelist():                # seguridad: nada fuera de la carpeta
            if miembro.startswith(("/", "\\")) or ".." in Path(miembro).parts:
                raise ValueError("El zip del modelo tiene rutas sospechosas")
        z.extractall(carpeta)
    zip_path.unlink(missing_ok=True)
    if not destino.is_dir():                        # por si el zip trae otro nombre de carpeta
        carpetas = [p for p in carpeta.iterdir() if p.is_dir() and p.name.startswith("vosk-model")]
        if not carpetas:
            raise FileNotFoundError("No encontré el modelo dentro del zip")
        shutil.move(str(carpetas[0]), destino)
    return destino
