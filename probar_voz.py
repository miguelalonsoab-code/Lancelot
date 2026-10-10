"""
Diagnóstico de voz, paso a paso. Ejecuta (con el entorno activado):

    python probar_voz.py

1. Muestra tus micrófonos.
2. Descarga el modelo de voz si hace falta (39 MB, una sola vez).
3. Te escucha 20 segundos y escribe TODO lo que entiende.
   -> Di "Lancelot" y "Lance" varias veces: si aparece escrito distinto,
      agrega esa forma a PALABRAS_ACTIVACION en config.py.
4. Lista las voces disponibles y dice una frase de prueba.
"""
import json
import queue
import sys
import time

from config import (CARPETA_VOCES, CARPETA_VOZ, MODELO_VOSK, NOMBRE_ASISTENTE, PALABRAS_ACTIVACION,
                    URL_MODELO_VOSK, VOZ_MOTOR, VOZ_VELOCIDAD, VOZ_WINDOWS_PREFERIDA)
from nucleo.numeros import numeros_a_digitos
from voz.despertar import separar_orden
from voz.oido import asegurar_modelo


def paso(n, titulo):
    print(f"\n=== Paso {n}: {titulo} ===")


def main():
    paso(1, "micrófonos")
    import sounddevice as sd
    entrada = sd.query_devices(kind="input")
    print(f"Micrófono por defecto: {entrada['name']} ({int(entrada['default_samplerate'])} Hz)")

    paso(2, "modelo de voz")
    ruta = asegurar_modelo(CARPETA_VOZ, MODELO_VOSK, URL_MODELO_VOSK, lambda p: print(f"  descargando… {p}"))
    print(f"Modelo listo en: {ruta}")
    from vosk import KaldiRecognizer, Model, SetLogLevel
    SetLogLevel(-1)
    modelo = Model(str(ruta))

    paso(3, "escuchar 20 segundos")
    print(f"Habla ahora. Prueba: «{NOMBRE_ASISTENTE}», «Lance», «{NOMBRE_ASISTENTE} abre la calculadora»,")
    print("«recuérdame mañana a las ocho de la noche pagar la luz».\n")
    tasa = int(entrada["default_samplerate"])
    rec = KaldiRecognizer(modelo, tasa)
    audio = queue.Queue()
    fin = time.monotonic() + 20
    with sd.RawInputStream(samplerate=tasa, blocksize=tasa // 4, dtype="int16", channels=1,
                           callback=lambda d, *_: audio.put(bytes(d))):
        while time.monotonic() < fin:
            if rec.AcceptWaveform(audio.get()):
                texto = json.loads(rec.Result()).get("text", "")
                if texto:
                    activado, orden = separar_orden(texto, PALABRAS_ACTIVACION)
                    marca = f"  ✅ te llamó → orden: «{numeros_a_digitos(orden)}»" if activado else ""
                    print(f"  oí: «{texto}»{marca}")
    print("\nSi dijiste el nombre y no salió ✅, copia cómo lo escribió y agrégalo a PALABRAS_ACTIVACION.")

    paso(4, "voces")
    onnx = sorted(CARPETA_VOCES.glob("*.onnx")) if CARPETA_VOCES.is_dir() else []
    print(f"Voces Piper en {CARPETA_VOCES}: {[p.name for p in onnx] or 'ninguna'}")
    if sys.platform == "win32":
        import pyttsx3
        motor = pyttsx3.init()
        print("Voces de Windows:")
        for v in motor.getProperty("voices"):
            print(f"  - {v.name}")
    from voz.habla import Voz
    from PySide6.QtCore import QCoreApplication
    app = QCoreApplication(sys.argv)                           # Voz usa señales de Qt
    voz = Voz(VOZ_MOTOR, CARPETA_VOCES, VOZ_WINDOWS_PREFERIDA, VOZ_VELOCIDAD)
    voz.estado.connect(lambda t: print(f"  {t}"))
    voz.termino.connect(app.quit)
    voz.iniciar()
    voz.decir(f"Hola, soy {NOMBRE_ASISTENTE}. Así sueno.")
    app.exec()
    print("\nListo. Si todo salió bien, la voz ya funciona en el asistente.")


if __name__ == "__main__":
    main()
