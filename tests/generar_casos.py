"""
Genera tests/casos_interprete.json: frases de ejemplo con lo que entiende el intérprete de Python.

El intérprete existe dos veces: en Python (laptop) y en JavaScript (servidor y celular).
Este archivo es el "contrato" entre los dos: la prueba de JavaScript (movil/pruebas)
exige exactamente los mismos resultados. Si mejoras el intérprete de Python:

    python tests/generar_casos.py       <- regenera el JSON
    cd movil && npm test                <- muestra qué debe cambiar en la versión JavaScript

Para agregar un caso, súmalo a FRASES y regenera.
"""
import json
import sys
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from nucleo.comandos import interpretar_comando   # noqa: E402
from nucleo.interprete import interpretar         # noqa: E402

RUTA = RAIZ / "tests" / "casos_interprete.json"
AHORAS = [datetime(2026, 10, 7, 6, 30),      # miércoles temprano
          datetime(2026, 10, 10, 22, 15)]    # sábado de noche (prueba los "ya pasó, mañana")
FRASES = [
    "mañana 8pm pagar la luz", "en 20 minutos estirar la espalda", "en media hora sacar la ropa",
    "el viernes a las 3 llamar al banco", "15/10 10:30 entregar informe", "el 20 de octubre cumple de Juan",
    "cada lunes 9am reunión de equipo", "tomar pastilla todos los días a las 10 de la noche",
    "esta noche a las 8 llamar a mamá", "recuérdame que mañana por la tarde debo ir al banco",
    "a las 8 de la mañana correr", "al mediodía almorzar", "a la 1 y media cita", "comprar 2 panes",
    "revisar 31/02", "de lunes a viernes a las 7 tomar agua", "en 2 horas revisar el horno",
    "pasado mañana a las 5 llamar a Dagi", "el lunes entregar trabajo", "hoy 8am desayunar",
    "18 hrs salir del trabajo", "a medianoche apagar la compu", "cada mes pagar el internet",
    "el 3 de enero de 2027 renovar DNI", "en 3 días devolver libro", "Recuérdame a las 7 y 40 sacar al perro",
    "cada domingo lavar ropa", "mañana a las 12 almuerzo con Juan", "a las 9:15 pm ver serie",
    "Anota: comprar leche mañana", "dentro de 1 hora tomar agua", "el próximo martes a las 4 dentista",
    "1/1 año nuevo", "mañana", "llamar al médico", "esta tarde ir al gimnasio", "cada semana regar plantas",
    "a las 7 de la tarde clase de inglés", "el sábado por la mañana correr", "hoy a las 11 de la noche dormir",
]
FORMATO = "%Y-%m-%d %H:%M"

# Comandos: frases que NO son tareas (o que sí lo son, cuando el resultado es null)
COMANDOS = [
    "modo estudio", "modo estudio 50", "a estudiar", "pausa", "seguir", "terminar", "modo silencio",
    "quita el silencio", "resumen", "resumen semanal", "¿Cómo voy esta semana?", "Buenos días", "hola",
    "qué tengo vencido", "pasa las vencidas a mañana", "mueve todas las tareas vencidas para mañana",
    "busca actualizaciones", "¿qué versión tienes?", "cuando diga el código abre visual studio code",
    "olvida el apodo código", "mis apodos", "abre netflix desde chrome", "busca lofi en youtube desde edge",
    "abre spotify", "¿Qué hora es?", "¿Qué tengo para hoy?", "mis pendientes", "escúchame", "deja de escuchar",
    "mañana 8pm pagar la luz", "estudiar para el examen mañana", "pagar vencidas mañana 8pm",
]


def calcular() -> dict:
    casos = []
    for ahora in AHORAS:
        for frase in FRASES:
            r = interpretar(frase, ahora)
            casos.append({"ahora": ahora.strftime(FORMATO), "texto": frase, "titulo": r.titulo,
                          "fecha": r.fecha.strftime(FORMATO) if r.fecha else None, "repeticion": r.repeticion})
    comandos = []
    for frase in COMANDOS:
        c = interpretar_comando(frase)
        comandos.append({"texto": frase, "comando": c and {"accion": c.accion, "minutos": c.minutos,
                                                          "texto": c.texto, "destino": c.destino,
                                                          "navegador": c.navegador}})
    return {"_comentario": "Generado por tests/generar_casos.py con el intérprete de Python (la referencia). "
                           "La versión JavaScript del celular debe dar exactamente lo mismo.",
            "casos": casos, "comandos": comandos}


if __name__ == "__main__":
    RUTA.write_text(json.dumps(calcular(), ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    datos = calcular()
    print(f"{len(datos['casos'])} frases y {len(datos['comandos'])} comandos guardados en {RUTA.relative_to(RAIZ)}")
