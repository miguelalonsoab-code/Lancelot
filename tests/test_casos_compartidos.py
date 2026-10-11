"""
El JSON de casos compartidos (tests/casos_interprete.json) debe coincidir con el intérprete de Python.
Si esta prueba falla, cambiaste el intérprete: regenera con  python tests/generar_casos.py
y luego revisa la versión JavaScript con  cd movil && npm test
"""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.generar_casos import RUTA, calcular   # noqa: E402


class TestCasosCompartidos(unittest.TestCase):
    def test_json_al_dia(self):
        guardado = json.loads(RUTA.read_text(encoding="utf-8"))
        actual = calcular()
        self.assertEqual(guardado["casos"], actual["casos"])
        self.assertEqual(guardado["comandos"], actual["comandos"])


if __name__ == "__main__":
    unittest.main()
