"""
La voz del asistente.

Dos motores:
- Piper: voces neuronales, suenan bastante naturales. Gratis y sin internet.
  Basta con poner un archivo .onnx y su .onnx.json en datos/voces/.
- Windows: las voces que ya trae el sistema (p. ej. Sabina o Helena), usadas DIRECTAMENTE a través de
  SAPI (la interfaz de voz de Windows). Se usan si no hay ninguna voz Piper.
  Antes de la v3.12.1 se usaban a través de la librería pyttsx3, pero esta tiene un fallo conocido:
  en un hilo que vive mucho tiempo dice la PRIMERA frase y después se queda muda, sin dar error.
  pyttsx3 queda solo como último recurso si SAPI no se puede abrir.

Todo se ejecuta en un hilo aparte con una cola: así hablar nunca congela la cara.
Mientras habla emite 'empezo' / 'termino' para que el oído no se escuche a sí mismo.
"""
from __future__ import annotations

import queue
import re
import sys
import tempfile
import threading
import wave
from pathlib import Path

from PySide6.QtCore import QObject, Signal


def limpiar_para_hablar(texto: str) -> str:
    """Quita emojis y símbolos que el motor leería raro ("✓", "·", "→")."""
    texto = texto.replace("·", ",").replace("→", ",").replace("\n", ". ")
    texto = re.sub(r"[^\w\s.,;:¿?¡!%'\"()-]", "", texto)
    return re.sub(r"\s+", " ", texto).strip()


def voces_piper(carpeta: Path | None) -> list[Path]:
    """Archivos .onnx que tienen al lado su .onnx.json (Piper necesita los dos)."""
    if not carpeta or not carpeta.is_dir():
        return []
    return sorted(p for p in carpeta.glob("*.onnx") if p.with_name(p.name + ".json").exists())


class Voz(QObject):
    empezo = Signal()
    termino = Signal()
    estado = Signal(str)             # descripción de la voz en uso o del error

    def __init__(self, motor: str, carpeta_voces: Path, preferida: str, velocidad: float,
                 carpeta_incluida: Path | None = None):
        super().__init__()
        self.motor = motor
        self.carpeta_voces = carpeta_voces
        self.carpeta_incluida = carpeta_incluida      # voces que trae el instalador (si hay)
        self.preferida = preferida.lower()
        self.velocidad = velocidad
        self._cola: queue.Queue[str] = queue.Queue()
        self._hilo = threading.Thread(target=self._bucle, daemon=True, name="voz")

    def iniciar(self):
        """Se llama después de conectar las señales, para no perder el aviso de qué voz se usa."""
        self._hilo.start()

    def decir(self, texto: str):
        texto = limpiar_para_hablar(texto)
        if texto:
            self._cola.put(texto)

    def callar_pendientes(self):
        while not self._cola.empty():
            self._cola.get_nowait()

    # ------------------------------------------------------------------ hilo
    def _bucle(self):
        hablar = self._preparar()
        if hablar is None:
            return
        while True:
            texto = self._cola.get()
            self.empezo.emit()
            try:
                hablar(texto)
            except Exception as e:
                self.estado.emit(f"Error al hablar: {e}")
            finally:
                self.termino.emit()

    def _preparar(self):
        onnx = voces_piper(self.carpeta_voces) or voces_piper(self.carpeta_incluida)   # primero las tuyas
        if self.motor in ("auto", "piper") and onnx:
            try:
                return self._preparar_piper(onnx[0])
            except Exception as e:
                self.estado.emit(f"No pude cargar la voz Piper ({e}); uso la de Windows")
        try:
            return self._preparar_windows()
        except Exception as e:
            self.estado.emit(f"Sin voz: {e}")
            return None

    def _preparar_piper(self, ruta: Path):
        from piper import PiperVoice
        from piper.config import SynthesisConfig
        import winsound

        voz = PiperVoice.load(str(ruta))
        ajustes = SynthesisConfig(length_scale=1.0 / max(0.5, self.velocidad))
        temporal = Path(tempfile.gettempdir()) / "lancelot_frase.wav"   # no ensucia la carpeta de voces

        def hablar(texto: str):
            with wave.open(str(temporal), "wb") as wav:
                voz.synthesize_wav(texto, wav, syn_config=ajustes)
            winsound.PlaySound(str(temporal), winsound.SND_FILENAME)   # espera a que termine

        self.estado.emit(f"Voz Piper: {ruta.stem}")
        return hablar

    def _preparar_windows(self):
        if sys.platform == "win32":
            import pythoncom               # el motor de Windows (COM) necesita esto en hilos nuevos
            pythoncom.CoInitialize()
            try:
                return self._preparar_sapi()
            except Exception as e:         # SAPI no disponible (muy raro): se intenta con pyttsx3
                self.estado.emit(f"No pude abrir la voz de Windows directamente ({e}); pruebo con pyttsx3")
        return self._preparar_pyttsx3()

    def _preparar_sapi(self):
        """
        SAPI.SpVoice: el mismo motor que usa el Narrador de Windows. Speak(texto, 0) habla y ESPERA a que
        termine, así que funciona igual en la primera frase que en la número cien.
        """
        import win32com.client

        sapi = win32com.client.Dispatch("SAPI.SpVoice")
        tokens = [sapi.GetVoices().Item(i) for i in range(sapi.GetVoices().Count)]
        if tokens:
            elegida = max(tokens, key=lambda t: self._puntaje(t.GetDescription(), _idioma_sapi(t)))
            sapi.Voice = elegida
            self.estado.emit(f"Voz de Windows: {elegida.GetDescription()}")
        sapi.Rate = velocidad_sapi(self.velocidad)

        def hablar(texto: str):
            sapi.Speak(texto, 0)            # 0 = síncrono: vuelve cuando terminó de hablar

        return hablar

    def _puntaje(self, nombre: str, idiomas: str) -> int:
        """Prefiere la voz que pediste en config; si no, una en español."""
        nombre = (nombre or "").lower()
        if self.preferida and self.preferida in nombre:
            return 3
        idiomas = (idiomas or "").lower()
        es = ("spanish" in nombre or "español" in nombre or "es-" in idiomas or "es_" in idiomas
              or idiomas.endswith("0a") or idiomas == "a"
              or any(n in nombre for n in ("sabina", "helena", "laura", "pablo", "raul", "dalia", "jorge")))
        return 2 if es else 0

    def _preparar_pyttsx3(self):
        import pyttsx3

        motor = pyttsx3.init()
        voces = motor.getProperty("voices")

        def puntaje(v):
            return self._puntaje(v.name, " ".join(str(x) for x in (getattr(v, "languages", []) or [])))

        if voces:
            elegida = max(voces, key=puntaje)
            motor.setProperty("voice", elegida.id)
            self.estado.emit(f"Voz de Windows: {elegida.name}")
        motor.setProperty("rate", int(175 * self.velocidad))

        def hablar(texto: str):
            motor.say(texto)
            motor.runAndWait()

        return hablar


def velocidad_sapi(velocidad: float) -> int:
    """VOZ_VELOCIDAD (1.0 normal, 1.2 más rápido) -> la escala de SAPI (-10 a 10, 0 = normal)."""
    return max(-10, min(10, round((velocidad - 1.0) * 10)))


def _idioma_sapi(token) -> str:
    """Código de idioma de la voz en SAPI, en hexadecimal ('80a' = español de México). Vacío si no se puede."""
    try:
        return str(token.GetAttribute("Language") or "")
    except Exception:
        return ""


def voces_windows() -> list[str]:
    """Nombres de las voces de Windows instaladas (para probar_voz.py)."""
    import win32com.client
    voces = win32com.client.Dispatch("SAPI.SpVoice").GetVoices()
    return [voces.Item(i).GetDescription() for i in range(voces.Count)]
