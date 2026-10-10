"""
Registro de lo que pasa (log) en datos/lancelot.log.

¿Por qué? Lancelot corre con pythonw, sin consola: si algo falla, el error
desaparece sin dejar rastro. Con este archivo cualquier problema se puede diagnosticar.

- Rotativo: cuando el archivo llega a 1 MB se renombra a lancelot.log.1 y empieza
  uno nuevo; se guardan 3 viejos. Nunca crece sin control.
- Captura los errores no previstos (los que antes solo se veían en la terminal),
  también los que ocurren en los hilos de voz.
- Nivel: "INFO" guarda eventos y errores. "DEBUG" además guarda lo que el oído
  reconoce de tu voz (útil para ajustar el nombre o los comandos). Se cambia en config.py.

Uso en cualquier archivo:
    import logging
    log = logging.getLogger(__name__)
    log.info("algo pasó")      log.warning("raro")      log.exception("falló")  (dentro de un except)
"""
from __future__ import annotations

import logging
import sys
import threading
from logging.handlers import RotatingFileHandler
from pathlib import Path


def configurar_registro(ruta: Path, nivel: str = "INFO") -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    archivo = RotatingFileHandler(ruta, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    archivo.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s [%(name)s] %(message)s",
                                           "%Y-%m-%d %H:%M:%S"))
    raiz = logging.getLogger()
    raiz.setLevel(getattr(logging, nivel.upper(), logging.INFO))
    raiz.handlers = [archivo]
    if sys.stderr is not None:                  # con "python main.py" también se ve en la terminal
        consola = logging.StreamHandler()
        consola.setFormatter(logging.Formatter("[%(name)s] %(message)s"))
        raiz.addHandler(consola)

    # Errores que nadie atrapó: en el hilo principal (incluye los de botones y señales de Qt)...
    def excepcion_no_atrapada(tipo, valor, rastro):
        if issubclass(tipo, KeyboardInterrupt):
            return sys.__excepthook__(tipo, valor, rastro)
        logging.getLogger("lancelot").critical("Error no atrapado", exc_info=(tipo, valor, rastro))

    # ...y en los hilos (oído, voz, catálogo de apps)
    def excepcion_en_hilo(args):
        logging.getLogger(f"hilo.{args.thread.name if args.thread else '?'}").critical(
            "Error en un hilo", exc_info=(args.exc_type, args.exc_value, args.exc_traceback))

    sys.excepthook = excepcion_no_atrapada
    threading.excepthook = excepcion_en_hilo
