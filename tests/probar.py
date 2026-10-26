"""Pruebas del ensamblador. Ejecutar desde la raíz del repositorio:

    python tests/probar.py

- Cada tests/*.asm se ensambla y se compara con su .hex (y con su .data.hex
  si existe). Los .hex esperados se generaron con el ensamblador de GNU.
- Cada tests/errores/*.asm debe fallar (código de salida distinto de 0),
  no debe crear el archivo de salida y debe imprimir exactamente su .err.
"""

import os
import subprocess
import sys
import tempfile
import unittest

CARPETA = os.path.dirname(os.path.abspath(__file__))
ENSAMBLADOR = os.path.join(CARPETA, "..", "assembler.py")


def ejecutar(carpeta, asm, *salidas):
    return subprocess.run([sys.executable, ENSAMBLADOR, asm, *salidas],
                          cwd=carpeta, capture_output=True, text=True)


def leer(ruta):
    with open(ruta, encoding="utf-8") as archivo:
        return archivo.read()


class ProgramasCorrectos(unittest.TestCase):
    def test_programas(self):
        programas = sorted(f for f in os.listdir(CARPETA) if f.endswith(".asm"))
        self.assertTrue(programas)
        for asm in programas:
            base = os.path.join(CARPETA, asm[:-4])
            with self.subTest(programa=asm), tempfile.TemporaryDirectory() as tmp:
                salida = os.path.join(tmp, "salida.hex")
                datos = os.path.join(tmp, "salida.data.hex")
                resultado = ejecutar(CARPETA, asm, salida, datos)
                self.assertEqual(resultado.returncode, 0, resultado.stderr)
                self.assertEqual(leer(salida), leer(base + ".hex"))
                if os.path.exists(base + ".data.hex"):
                    self.assertEqual(leer(datos), leer(base + ".data.hex"))


class ProgramasConErrores(unittest.TestCase):
    def test_errores(self):
        carpeta = os.path.join(CARPETA, "errores")
        programas = sorted(f for f in os.listdir(carpeta) if f.endswith(".asm"))
        self.assertTrue(programas)
        for asm in programas:
            with self.subTest(programa=asm), tempfile.TemporaryDirectory() as tmp:
                salida = os.path.join(tmp, "salida.hex")
                resultado = ejecutar(carpeta, asm, salida)
                self.assertNotEqual(resultado.returncode, 0)
                self.assertFalse(os.path.exists(salida), "no debe crear el .hex")
                self.assertEqual(resultado.stderr, leer(os.path.join(carpeta, asm[:-4] + ".err")))

    def test_archivo_inexistente(self):
        resultado = ejecutar(CARPETA, "no_existe.asm", "salida.hex")
        self.assertNotEqual(resultado.returncode, 0)

    def test_argumentos_incorrectos(self):
        resultado = ejecutar(CARPETA, "suma.asm")
        self.assertNotEqual(resultado.returncode, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
