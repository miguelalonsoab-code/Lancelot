"""
El "contexto" que la laptop comparte con el celular (v3.19).

La laptop es la que guarda tu horario, tus días libres, tu perfil y tus actividades. Para que el celular
pueda calcular tus horas libres y sugerencias (con la misma lógica, portada a movil/publico/comun/),
la laptop sube una foto de todo eso en cada sincronización, solo cuando cambió:

    {
      "version": 1,
      "perfil":      {"despertar": "06:00", "dormir": "23:00", "meta_estudio": 100, "minutos_para_arrancar": 30,
                      "avisar_huecos": true},
      "horario":     [{"id": 1, "dias": [0,1,2,3,4], "inicio": "08:30", "fin": "17:30", "titulo": "Trabajo", "traslado": 45,
                      "categoria": "trabajo"}],       # categoria: trabajo | clase | otro (v3.22)
      "excepciones": [{"desde": "2026-11-01", "hasta": "2026-11-01", "filtro": "traba", "titulo": "No trabajo"}],
      "actividades": [{"id": 1, "nombre": "Gimnasio", "minutos": 60, "veces_semana": 3, "momento": "tarde"}],
      "hechas":      {"1": ["2026-10-20"]},          # últimos 14 días
      "estudio":     {"2026-10-21": 40},              # minutos estudiados, últimos 7 días
      "evitar":      {"gimnasio": ["tarde"]},         # lo que rechazaste seguido
      "sugeridas":   ["uuid-de-tarea", …],            # tareas agendadas desde sugerencias (no "vencen")
      "hueco_avisado": "2026-10-21 18:15"             # el último hueco que la laptop ya te ofreció
    }

Lógica pura (sin SQLite ni Qt): convierte en ambos sentidos. Los tests y tests/generar_casos.py usan
también la vuelta (de_dict) para armar los mismos escenarios en Python y en JavaScript.
"""
from __future__ import annotations

import hashlib
import json
from datetime import date, time

from nucleo.horario import Bloque, Excepcion, inferir_categoria
from nucleo.perfil import Actividad

VERSION_CONTEXTO = 1


def bloque_a_dict(b: Bloque) -> dict:
    return {"id": b.id, "dias": list(b.dias), "inicio": f"{b.inicio:%H:%M}", "fin": f"{b.fin:%H:%M}",
            "titulo": b.titulo, "traslado": b.traslado, "categoria": b.categoria}


def bloque_de_dict(d: dict) -> Bloque:
    # Un bloque que viene sin categoría (un contexto o una acción de antes de la v3.22) se clasifica por su título
    return Bloque(tuple(d["dias"]), time.fromisoformat(d["inicio"]), time.fromisoformat(d["fin"]), d["titulo"],
                  d.get("id"), d.get("traslado", 0), d.get("categoria") or inferir_categoria(d["titulo"]))


def excepcion_a_dict(e: Excepcion) -> dict:
    return {"desde": e.desde.isoformat(), "hasta": e.hasta.isoformat(), "filtro": e.filtro, "titulo": e.titulo}


def excepcion_de_dict(d: dict) -> Excepcion:
    return Excepcion(date.fromisoformat(d["desde"]), date.fromisoformat(d["hasta"]), d.get("filtro", ""), d["titulo"])


def actividad_a_dict(a: Actividad) -> dict:
    return {"id": a.id, "nombre": a.nombre, "minutos": a.minutos, "veces_semana": a.veces_semana, "momento": a.momento}


def actividad_de_dict(d: dict) -> Actividad:
    return Actividad(d["nombre"], d["minutos"], d.get("veces_semana"), d.get("momento"), d.get("id"))


def armar(perfil, minutos_para_arrancar: int, horario: list[Bloque], excepciones: list[Excepcion],
          hechas: dict[int, list[date]], estudio: dict[date, int], evitar: dict[str, set[str]],
          sugeridas: list[str], hueco_avisado: str | None = None, avisar_huecos: bool = True) -> dict:
    """
    hueco_avisado: inicio ('AAAA-MM-DD HH:MM') del último hueco libre que la laptop ya te ofreció en la burbuja:
    el servidor no repite ese aviso en el celular. avisar_huecos: SUGERENCIAS_EN_CELULAR de config.py.
    """
    return {
        "version": VERSION_CONTEXTO,
        "perfil": {"despertar": f"{perfil.despertar:%H:%M}", "dormir": f"{perfil.dormir:%H:%M}",
                   "meta_estudio": perfil.meta_estudio, "minutos_para_arrancar": minutos_para_arrancar,
                   "avisar_huecos": avisar_huecos},
        "horario": [bloque_a_dict(b) for b in horario],
        "excepciones": [excepcion_a_dict(e) for e in excepciones],
        "actividades": [actividad_a_dict(a) for a in perfil.actividades],
        "hechas": {str(i): sorted(d.isoformat() for d in dias) for i, dias in sorted(hechas.items())},
        "estudio": {d.isoformat(): m for d, m in sorted(estudio.items())},
        "evitar": {n: sorted(ms) for n, ms in sorted(evitar.items())},
        "sugeridas": sorted(sugeridas),
        "hueco_avisado": hueco_avisado,
    }


def huella(contexto: dict) -> str:
    """Para subirlo solo si cambió."""
    return hashlib.sha256(json.dumps(contexto, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]
