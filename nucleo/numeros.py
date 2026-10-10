"""
Números dichos en voz -> dígitos.

El reconocedor de voz escribe lo que oye en palabras: "a las ocho de la noche",
"en veinte minutos", "el quince de octubre". El intérprete de fechas espera
dígitos ("a las 8"), así que antes se traduce:

    "mañana a las ocho y media pagar la luz" -> "mañana a las 8 y media pagar la luz"
    "a las siete y cuarenta"                 -> "a las 7 y 40"
    "modo estudio cincuenta"                 -> "modo estudio 50"

"un" / "una" NO se convierten (el intérprete ya entiende "en una hora" y
"comprar una pizza" debe seguir igual), salvo en "a la una" -> "a la 1".
"""
from __future__ import annotations

from nucleo.interprete import normalizar

_BASICOS = {
    "cero": 0, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6, "siete": 7,
    "ocho": 8, "nueve": 9, "diez": 10, "once": 11, "doce": 12, "trece": 13, "catorce": 14,
    "quince": 15, "dieciseis": 16, "diecisiete": 17, "dieciocho": 18, "diecinueve": 19,
    "veinte": 20, "veintiuno": 21, "veintiun": 21, "veintiuna": 21, "veintidos": 22,
    "veintitres": 23, "veinticuatro": 24, "veinticinco": 25, "veintiseis": 26,
    "veintisiete": 27, "veintiocho": 28, "veintinueve": 29,
    "treinta": 30, "cuarenta": 40, "cincuenta": 50, "sesenta": 60, "noventa": 90,
    "cien": 100, "ciento veinte": 120,
}
_DECENAS = {"treinta": 30, "cuarenta": 40, "cincuenta": 50}
_UNIDADES = {"uno": 1, "una": 1, "un": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5,
             "seis": 6, "siete": 7, "ocho": 8, "nueve": 9}


def numeros_a_digitos(texto: str) -> str:
    palabras = texto.split()
    norm = [normalizar(p) for p in palabras]
    salida: list[str] = []
    i = 0
    while i < len(palabras):
        n = norm[i]
        # "treinta y cinco"
        if n in _DECENAS and i + 2 < len(palabras) and norm[i + 1] == "y" and norm[i + 2] in _UNIDADES:
            salida.append(str(_DECENAS[n] + _UNIDADES[norm[i + 2]]))
            i += 3
            continue
        # "ciento veinte"
        if n == "ciento" and i + 1 < len(palabras) and norm[i + 1] == "veinte":
            salida.append("120")
            i += 2
            continue
        # "a la una" -> "a la 1"
        if n in ("una", "uno") and i >= 1 and norm[i - 1] == "la":
            salida.append("1")
            i += 1
            continue
        if n in _BASICOS:
            salida.append(str(_BASICOS[n]))
        else:
            salida.append(palabras[i])
        i += 1
    return " ".join(salida)
