"""
Escenarios de horario, días libres y sugerencias (v3.19) para el contrato Python ↔ JavaScript.

tests/generar_casos.py los calcula con la lógica de Python (la referencia) y los guarda en
tests/casos_interprete.json, clave "horario". movil/pruebas/horario.test.mjs comprueba que
movil/publico/comun/horario.js y recomendador.js dan exactamente lo mismo.
"""
from __future__ import annotations

from datetime import date, datetime, time

from nucleo.contexto import actividad_de_dict, bloque_de_dict, excepcion_de_dict
from nucleo.horario import (choque, describir_dias, describir_libre, duracion_minutos, hablar_duracion, huecos,
                            interpretar_excepcion)
from nucleo.horario import Bloque, interpretar_bloque
from nucleo.perfil import interpretar_actividad, leer_hora
from nucleo.recomendador import describir_plan, recomendar

F = "%Y-%m-%d %H:%M"
TRABAJO = {"dias": [0, 1, 2, 3, 4], "inicio": "08:30", "fin": "17:30", "titulo": "Trabajo en Sanna", "traslado": 45}
CLASES = {"dias": [1, 3], "inicio": "19:00", "fin": "22:00", "titulo": "Clase de redes", "traslado": 0}
SABADOS = {"dias": [5], "inicio": "08:00", "fin": "12:00", "titulo": "Inglés", "traslado": 15}
GIM = {"id": 1, "nombre": "Gimnasio", "minutos": 60, "veces_semana": 3, "momento": "tarde"}
LEER = {"id": 2, "nombre": "Leer", "minutos": 30, "veces_semana": None, "momento": "noche"}
CORRER = {"id": 3, "nombre": "Correr", "minutos": 40, "veces_semana": 2, "momento": "manana"}
YOGA = {"id": 4, "nombre": "Yoga", "minutos": 45, "veces_semana": 7, "momento": None}

EXCEPCIONES = [
    ("2026-10-21", "el 1 de noviembre no trabajo"), ("2026-10-21", "Vacaciones del 20 al 30 de diciembre"),
    ("2026-10-21", "mañana no tengo clases"), ("2026-10-21", "el viernes es feriado"),
    ("2026-10-21", "el 15 tengo libre"), ("2026-10-21", "del 28 de diciembre al 3 de enero son mis vacaciones"),
    ("2026-10-21", "no voy al gimnasio el lunes"), ("2026-10-21", "El lunes 3 de noviembre no voy a la Universidad"),
    ("2026-10-21", "pasado mañana no trabajo"), ("2026-10-21", "no trabajo"), ("2026-10-21", "del 5 al 2 de mayo"),
    ("2026-10-21", "el 31 no trabajo"), ("2026-12-30", "el 2 no trabajo"), ("2026-10-21", "el 31 de febrero libre"),
    ("2026-10-21", "feriado el 8 de diciembre"), ("2026-10-21", "del 1 de enero al 30 de junio vacaciones"),
    ("2026-10-21", "hoy es mi día libre"), ("2026-10-21", "del 10 al 12 no hay clases"),
]

HUECOS = [   # (día, bloques, despertar, dormir, ahora, mínimo, excepciones, extras)
    ("2026-10-22", [TRABAJO, CLASES], "06:00", "23:00", None, 30, [], []),
    ("2026-10-22", [TRABAJO, CLASES], "06:00", "23:00", "2026-10-22 18:40", 30, [], []),
    ("2026-10-22", [TRABAJO, CLASES], "06:30", "00:30", None, 30, [], []),
    ("2026-10-22", [TRABAJO, CLASES], "06:00", "23:00", None, 30,
     [{"desde": "2026-10-22", "hasta": "2026-10-22", "filtro": "clase", "titulo": "No tengo clases"}], []),
    ("2026-10-22", [TRABAJO, CLASES], "06:00", "23:00", None, 30,
     [{"desde": "2026-10-20", "hasta": "2026-10-25", "filtro": "", "titulo": "Vacaciones"}], []),
    ("2026-10-24", [TRABAJO, SABADOS], "07:00", "23:30", None, 30, [],
     [("2026-10-24 15:00", "2026-10-24 17:00", "Cine"), ("2026-10-25 08:00", "2026-10-25 10:00", "Otro día")]),
    ("2026-10-24", [SABADOS], "07:00", "23:30", "2026-10-24 23:10", 1, [], []),
    ("2026-10-26", [], "06:00", "22:00", None, 30, [], []),
]

CHOQUES = [   # (inicio, minutos, bloques, excepciones)
    ("2026-10-23 08:00", 120, [TRABAJO], []), ("2026-10-23 08:00", 30, [TRABAJO], []),
    ("2026-10-23 12:00", None, [TRABAJO], []), ("2026-10-24 09:00", 60, [TRABAJO], []),
    ("2026-10-23 12:00", None, [TRABAJO], [{"desde": "2026-10-23", "hasta": "2026-10-23", "filtro": "traba",
                                            "titulo": "No trabajo"}]),
    ("2026-10-22 21:30", 60, [TRABAJO, CLASES], []),
]

PLANES = [   # (día, bloques, despertar, dormir, actividades, hechas_semana, hechas_hoy, estudio, meta, evitar, ahora)
    ("2026-10-24", [TRABAJO, CLASES], "06:00", "23:00", [GIM, LEER, CORRER], {1: 1}, [], 20, 120, {}, None),
    ("2026-10-22", [TRABAJO, CLASES], "06:00", "23:00", [GIM, LEER, CORRER], {1: 1}, [], 20, 120, {}, None),
    ("2026-10-26", [TRABAJO, CLASES], "06:00", "23:00", [GIM, LEER, CORRER], {1: 1}, [], 20, 120, {}, None),
    ("2026-10-24", [TRABAJO, CLASES], "06:00", "23:00", [GIM, LEER, CORRER], {1: 3, 3: 1}, [3], 120, 120, {}, None),
    ("2026-10-24", [TRABAJO, CLASES], "06:00", "23:00", [GIM, CORRER], {1: 3, 3: 2}, [], 150, 120, {}, None),
    ("2026-10-22", [TRABAJO, CLASES], "06:00", "23:00", [GIM, YOGA], {}, [], 0, 100, {"gimnasio": ["tarde"]}, None),
    ("2026-10-25", [], "06:00", "23:00", [GIM, CORRER, YOGA, LEER], {1: 2, 4: 5}, [], 0, 0, {}, None),
    ("2026-10-22", [TRABAJO, CLASES], "06:00", "23:00", [GIM, LEER], {}, [], 0, 240, {}, "2026-10-22 18:20"),
    ("2026-10-22", [TRABAJO], "06:00", "06:00", [GIM], {}, [], 0, 60, {"gimnasio": ["tarde", "noche", "manana"]}, None),
    ("2026-10-21", [TRABAJO], "06:00", "23:00", [], {}, [], 0, 60, {}, "2026-10-21 23:40"),
]


ACTIVIDADES = [
    "gimnasio 1 hora 3 veces por semana en la tarde", "Leer 30 min todos los días en la noche",
    "correr 40 minutos 2 veces por semana por la mañana", "Ir al gimnasio hora y media tres veces por semana",
    "hacer yoga media hora diario", "practicar guitarra 2h 15min 5 veces por semana", "Natación una vez por semana",
    "las tardes salir a caminar 45 min", "1 hora 3 veces por semana", "dibujar 20 veces por semana",
    "Meditar 10 min cada día en las mañanas", "inglés 1 hora y media 2 veces a la semana de la noche",
]


BLOQUES = [
    "de lunes a viernes de 9am a 6pm trabajo", "martes y jueves de 7 a 10 de la noche clase de redes",
    "sábados de 8 a 12 inglés", "lunes, miércoles y viernes de 2 a 4 gimnasio", "todos los días de 13:00 a 14:00 almuerzo",
    "fines de semana de 10 a 1 fútbol", "de lunes a viernes 8:30-17:30 Trabajo en Sanna", "miércoles de 6 a 8 de la tarde taller",
    "lunes de 10pm a 12am turno", "los domingos de 9 a 11", "trabajo de 9 a 6", "lunes almuerzo", "lunes de 22 a 2 turno noche",
    "de lunes a viernes de 8:30 a 5:30 trabajo, traslado 45 min", "martes de 7 a 10 de la noche clases con 1 hora de viaje",
    "miércoles de 7:30 pm a 10:40 pm Computación Gráfica", "viernes de 9:10 pm a 10:40 pm Computación Gráfica",
    "sábados de 2:30 pm a 7:20 pm Interacción Humano Computador", "de viernes a lunes de 6 a 7 correr",
    "Tengo los jueves de 18:00 a 20:00 reunión de grupo", "de lunes a viernes de 9 a 6 trabajo con 30 minutos de traslado",
]
HORAS = [("a las 6:30", "despertar"), ("las 11 de la noche", "dormir"), ("11pm", "dormir"), ("a las 11", "dormir"),
         ("a las 12", "dormir"), ("6", "despertar"), ("7am", "dormir"), ("a las 1 de la mañana", "dormir"),
         ("10:45 p.m.", "dormir"), ("temprano", "despertar"), ("25", "dormir")]


def _f(texto: str | None) -> datetime | None:
    return datetime.strptime(texto, F) if texto else None


def _t(texto: str) -> time:
    return time.fromisoformat(texto)


def _libres(dia, bloques, despertar, dormir, ahora, minimo, excepciones, extras):
    return huecos(date.fromisoformat(dia), [bloque_de_dict(b) for b in bloques], _t(despertar), _t(dormir), _f(ahora),
                  minimo, [excepcion_de_dict(e) for e in excepciones], [(_f(a), _f(b), t) for a, b, t in extras])


def _sugerencia(s) -> dict:
    return {"nombre": s.nombre, "inicio": s.inicio.strftime(F), "fin": s.fin.strftime(F), "motivo": s.motivo,
            "clase": s.clase, "actividad_id": s.actividad_id}


def calcular_horario() -> dict:
    excepciones = []
    for hoy, texto in EXCEPCIONES:
        r = interpretar_excepcion(texto, date.fromisoformat(hoy))
        excepciones.append({"hoy": hoy, "texto": texto, "resultado": r if isinstance(r, str) else {
            "desde": r.desde.isoformat(), "hasta": r.hasta.isoformat(), "filtro": r.filtro, "titulo": r.titulo}})
    salida_huecos = []
    for caso in HUECOS:
        libres = _libres(*caso)
        dia, bloques, despertar, dormir, ahora, minimo, excs, extras = caso
        salida_huecos.append({"dia": dia, "bloques": bloques, "despertar": despertar, "dormir": dormir, "ahora": ahora,
                              "minimo": minimo, "excepciones": excs, "extras": extras,
                              "libres": [[a.strftime(F), b.strftime(F)] for a, b in libres],
                              "texto": describir_libre(libres)})
    choques = []
    for inicio, minutos_, bloques, excs in CHOQUES:
        b = choque(_f(inicio), minutos_, [bloque_de_dict(x) for x in bloques], [excepcion_de_dict(e) for e in excs])
        choques.append({"inicio": inicio, "minutos": minutos_, "bloques": bloques, "excepciones": excs,
                        "choca": b.titulo if b else None})
    planes = []
    for dia, bloques, despertar, dormir, acts, semana, hoy, estudio, meta, evitar, ahora in PLANES:
        libres = _libres(dia, bloques, despertar, dormir, ahora, 30, [], [])
        p = recomendar(date.fromisoformat(dia), libres, [actividad_de_dict(a) for a in acts], semana, set(hoy),
                       estudio, meta, evitar={k: set(v) for k, v in evitar.items()})
        texto, hablado = describir_plan(p)
        planes.append({"dia": dia, "bloques": bloques, "despertar": despertar, "dormir": dormir, "actividades": acts,
                       "hechas_semana": {str(k): v for k, v in semana.items()}, "hechas_hoy": hoy, "estudio": estudio,
                       "meta": meta, "evitar": evitar, "ahora": ahora,
                       "sugerencias": [_sugerencia(s) for s in p.sugerencias], "sin_lugar": p.sin_lugar,
                       "texto": texto, "hablado": hablado})
    textos = {"dias": {",".join(map(str, d)): describir_dias(d) for d in [(0, 1, 2, 3, 4), (1, 3), (0, 2, 4),
                                                                          tuple(range(7)), (5,), (5, 6)]},
              "duracion": {str(m): duracion_minutos(m) for m in (5, 45, 60, 90, 135)},
              "hablar": {str(m): hablar_duracion(m) for m in (15, 30, 60, 90, 135, 120)}}
    actividades = []
    for texto in ACTIVIDADES:
        a = interpretar_actividad(texto)
        actividades.append({"texto": texto, "resultado": a if isinstance(a, str) else {
            "nombre": a.nombre, "minutos": a.minutos, "veces_semana": a.veces_semana, "momento": a.momento},
            "descripcion": None if isinstance(a, str) else a.describir()})
    bloques = []
    for texto in BLOQUES:
        b = interpretar_bloque(texto)
        bloques.append({"texto": texto, "resultado": b if not isinstance(b, Bloque) else {
            "dias": list(b.dias), "inicio": f"{b.inicio:%H:%M}", "fin": f"{b.fin:%H:%M}", "titulo": b.titulo,
            "traslado": b.traslado}})
    horas = [{"texto": t, "para": p, "hora": (lambda h: h and f"{h:%H:%M}")(leer_hora(t, p))} for t, p in HORAS]
    return {"excepciones": excepciones, "huecos": salida_huecos, "choques": choques, "planes": planes,
            "textos": textos, "actividades": actividades, "bloques": bloques, "horas": horas}
