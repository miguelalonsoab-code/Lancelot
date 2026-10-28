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
from nucleo.frases import REFLEXIONES             # noqa: E402
from nucleo.interprete import describir_avisos, describir_faltan, interpretar   # noqa: E402
from nucleo.planificador import aviso_previo_pendiente, siguiente_ocurrencia       # noqa: E402
from tests.casos_horario import calcular_horario                                   # noqa: E402
from nucleo.silabas import con_guiones, silabas                                   # noqa: E402

# v3.24: separación en sílabas (el celular debe partir igual que la laptop)
PALABRAS = ["computación", "interacción", "humano", "computador", "gráfica", "trabajo", "sanna", "universidad", "inglés",
            "construcción", "laboratorio", "química", "guitarra", "reunión", "país", "biología", "transporte",
            "inscripción", "perspectiva", "extra", "ahorro", "leer", "chocolate", "llave", "programación", "seminario",
            "taller", "oficina", "clasificar", "matemática", "física", "cuidado", "ciudad", "averiguéis", "pingüino",
            "hoy", "muy", "leyes", "Computación", "observar", "obstrucción", "atlántico", "aéreo", "examen", "Sanna",
            "gimnasio", "pseudo", "psicología", "redes", "Robótica", "UPN", "y", "a", "Guerra", "QUESO", "ÑANDÚ", "rey",
            "brrr", "hielo", "ahí", "creer", "maíz", "vehículo"]
TEXTOS_GUIONES = ["Interacción Humano Computador", "Trabajo en Sanna", "Computación Gráfica 2", "Taller: robótica (UPN)",
                  "Universidad", "", "Clase de redes y comunicaciones", "Reunión de grupo"]

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
    # Eventos (v3.10)
    "el 15 de noviembre aniversario", "el 15 de noviembre es mi aniversario", "cumpleaños de mamá 3 de mayo",
    "evento: cena con amigos el sábado, avísame 3 días antes", "estudiar para el examen mañana",
    "examen de cálculo el 20/10 a las 8am", "comprar regalo de cumpleaños el viernes",
    "evento de la empresa el viernes a las 7pm", "boda de Ana el 12/12 con una semana de anticipación",
    "avísame 2 semanas antes del viaje a Cusco el 30 de noviembre", "limpiar la sala el sábado",
    "tarea: examen de prueba mañana", "primer parcial el 2/11", "viaje cada año 1/1", "evento",
    "nuevo evento concierto el 5/12 a las 9 de la noche", "pagar el seguro cada año el 10 de enero",
    "cita con el dentista el jueves a las 4, avísame un día antes", "ir al concierto el sábado",
    "cada día a las 8 reunión diaria",
    # Duraciones (v3.14)
    "examen el viernes de 8 a 10", "mañana de 7 a 10 de la noche clase de redes", "reunión mañana a las 3 durante 1 hora",
    "el sábado de 9am a 12pm taller de pintura", "gimnasio mañana 18:00-19:30", "mañana de 2 a 4 estudiar",
    "llamar a mamá por 15 minutos a las 8 de la noche", "cita el lunes desde las 10 hasta las 11:30",
    "de lunes a viernes de 9 a 6 trabajar", "mañana de 10 a 9 algo raro", "cada sábado de 8 a 10 inglés",
]

# Avisos previos: (fecha del evento, avisos, desde, ahora) -> qué aviso toca (días antes) o None
AVISOS_PREVIOS = [
    ("2026-11-15 09:00", "7,1", "2026-10-01 10:00", "2026-11-08 08:59"),   # aún no son las 9
    ("2026-11-15 09:00", "7,1", "2026-10-01 10:00", "2026-11-08 09:00"),   # toca 7
    ("2026-11-15 09:00", "7,1", "2026-11-08 09:00", "2026-11-10 12:00"),   # ya avisó 7; el 1 aún no
    ("2026-11-15 09:00", "7,1", "2026-11-08 09:00", "2026-11-14 09:30"),   # toca 1
    ("2026-11-15 09:00", "7,1", "2026-10-01 10:00", "2026-11-14 18:00"),   # laptop apagada: solo el 1
    ("2026-11-15 09:00", "7,1", "2026-11-12 15:00", "2026-11-12 16:00"),   # creado 3 días antes: el 7 no
    ("2026-11-15 09:00", "7,1", "2026-11-12 15:00", "2026-11-14 09:00"),   # …pero el 1 sí
    ("2026-11-15 09:00", "7,1", "2026-10-01 10:00", "2026-11-15 09:00"),   # ya es la hora: aviso normal
    ("2026-11-15 20:00", "3", "2026-10-01 10:00", "2026-11-12 09:00"),
    ("2026-11-15 20:00", "", "2026-10-01 10:00", "2026-11-14 09:00"),
    ("2026-11-15 20:00", "1,x,0,999", "2026-10-01 10:00", "2026-11-14 09:00"),
]
FALTAN = [("2026-10-07 06:30", f) for f in ("2026-10-07 23:00", "2026-10-08 08:00", "2026-10-09 08:00",
                                              "2026-10-14 08:00", "2026-10-21 10:00", "2026-11-04 10:00",
                                              "2026-12-02 10:00")]
# Vocabulario aprendido de las correcciones (ver nucleo/aprendizaje.py)
VOCABULARIO = {"evento": ["taller"], "no_evento": ["cita"], "verbos": ["ir"]}
CON_VOCABULARIO = ["cita con el banco mañana", "taller de cerámica el sábado", "ir al concierto el viernes",
                   "ir a comprar pan mañana", "examen el lunes", "taller", "mañana llevar el carro al taller"]
REPETICIONES = [("2026-02-28 09:00", "anual", "2026-10-07 06:30"), ("2028-02-29 09:00", "anual", "2028-03-01 06:30"),
                ("2026-10-31 09:00", "mensual", "2026-11-01 06:30")]
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
    "Guarda esta frase: El que persevera, alcanza.", "guarda esta frase la constancia gana",
    "Motívame", "¿Me dices una frase?", "dime una frase", "anota esta frase:   Sonríe, que hoy sale bien",
    "mi horario", "¿Cuándo estoy libre?", "tiempo libre mañana", "Horario: de lunes a viernes de 9am a 6pm Trabajo",
    "estoy ocupado martes y jueves de 7 a 10 de la noche clase de Redes", "borra el horario de trabajo",
    "horario de clases de la universidad",
    "El 1 de noviembre no trabajo", "Vacaciones del 20 al 30 de diciembre", "mañana no tengo clases",
    "el viernes es feriado", "el 15 tengo libre", "no voy al gimnasio el lunes", "mis días libres",
    "¿qué tiempo tengo libre mañana?", "comprar maleta para las vacaciones el viernes",
    "del 28 de diciembre al 3 de enero son mis vacaciones",
    "¿Qué hago hoy?", "recomiéndame algo para mañana", "¿qué puedo hacer?", "sugerencias",
    "Más tarde, a las 8", "luego a las 8:30 de la noche", "más tarde a las 8 llamar a mamá",
    "Agéndalo", "agenda las sugerencias", "vuelve a sugerirme todo", "Ya fui al gimnasio", "hice yoga", "terminé de leer", "fui a la piscina", "ya terminé",
    "¿Qué sabes de mí?", "me despierto a las 6:30", "Me duermo a las 11 de la noche", "meta de estudio 120 minutos",
    "Actividad: Gimnasio 1 hora 3 veces por semana en la tarde", "me gusta leer 30 min todos los días",
    "mis actividades", "borra la actividad gimnasio", "al trabajo tardo 45 minutos", "quiero hacer ejercicio mañana",
    # v3.24: categoría de un bloque
    "Computación Gráfica es clase", "computación gráfica es una clase", "marca inglés como otro",
    "pon Trabajo en Sanna como trabajo", "la categoría de IHC es curso", "categoría de inglés: otra cosa",
    "cambia el bloque de redes como clase", "Interacción Humano Computador es un curso", "la chamba es trabajo",
    "esto es otro tema", "hoy es clase de redes", "mañana es trabajo", "esto es trabajo", "inglés es otro",
    "mañana 8pm clase de redes", "marca la tarea como hecha",
]


def calcular() -> dict:
    casos = []
    for ahora in AHORAS:
        for frase in FRASES:
            r = interpretar(frase, ahora, {})
            casos.append({"ahora": ahora.strftime(FORMATO), "texto": frase, "titulo": r.titulo,
                          "fecha": r.fecha.strftime(FORMATO) if r.fecha else None, "repeticion": r.repeticion,
                          "tipo": r.tipo, "anticipacion": r.anticipacion, "avisos": r.avisos, "duracion": r.duracion})
    comandos = []
    for frase in COMANDOS:
        c = interpretar_comando(frase)
        comandos.append({"texto": frase, "comando": c and {"accion": c.accion, "minutos": c.minutos,
                                                          "texto": c.texto, "destino": c.destino,
                                                          "navegador": c.navegador}})
    leer = lambda texto: datetime.strptime(texto, FORMATO)   # noqa: E731
    avisos = [{"fecha": f, "avisos": a, "desde": d, "ahora": h,
               "toca": aviso_previo_pendiente(leer(f), a, leer(d), leer(h))} for f, a, d, h in AVISOS_PREVIOS]
    faltan = [{"ahora": h, "fecha": f, "texto": describir_faltan(leer(f), leer(h))} for h, f in FALTAN]
    textos_avisos = {a: describir_avisos(a) for a in ("7,1", "1", "3", "14,7,1", None)}
    repeticiones = [{"fecha": f, "repeticion": r, "ahora": h,
                     "siguiente": siguiente_ocurrencia(leer(f), r, leer(h)).strftime(FORMATO)} for f, r, h in REPETICIONES]
    return {"_comentario": "Generado por tests/generar_casos.py con el intérprete de Python (la referencia). "
                           "La versión JavaScript del celular debe dar exactamente lo mismo.",
            "casos": casos, "comandos": comandos, "avisos_previos": avisos, "faltan": faltan,
            "textos_avisos": {str(k): v for k, v in textos_avisos.items()}, "repeticiones": repeticiones,
            "vocabulario": VOCABULARIO, "reflexiones": REFLEXIONES, "horario": calcular_horario(),
            "silabas": {"palabras": [{"palabra": w, "silabas": silabas(w)} for w in PALABRAS],
                        "guiones": [{"texto": t, "resultado": con_guiones(t, "-")} for t in TEXTOS_GUIONES]},
            "con_vocabulario": [{"texto": t, "tipo": interpretar(t, AHORAS[0], VOCABULARIO).tipo,
                                 "sin_vocabulario": interpretar(t, AHORAS[0], {}).tipo} for t in CON_VOCABULARIO]}


if __name__ == "__main__":
    RUTA.write_text(json.dumps(calcular(), ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    datos = calcular()
    print(f"{len(datos['casos'])} frases y {len(datos['comandos'])} comandos guardados en {RUTA.relative_to(RAIZ)}")
