"""
Separar palabras en sílabas (v3.24), para partir los nombres largos con guion: «Com-pu-ta-ción».

Lo usa la vista Semana de la laptop: Qt no sabe partir en sílabas y cortaba «Computa|ción» en cualquier letra.
Es lo mismo que movil/publico/comun/silabas.js; tests/generar_casos.py guarda los resultados de aquí
y movil/pruebas/silabas.test.mjs comprueba que el celular da exactamente lo mismo.

Reglas (las de la RAE, simplificadas):
  - «ch», «ll» y «rr» cuentan como UNA consonante; en «que/qui» y «gue/gui» la «u» no suena: va con la consonante.
  - Una consonante entre vocales va con la vocal de después: ca-sa.
  - Dos consonantes se separan (can-to), salvo los grupos que no se separan: pr br tr dr cr gr fr pl bl cl gl fl
    (o-tro, ha-blar).
  - Tres: si las dos últimas son un grupo, se separa la primera (in-glés, com-pra); si no, las dos primeras se
    quedan atrás (trans-por-te).
  - Cuatro o más: dos atrás y el resto adelante (ins-crip-ción, cons-truc-ción).
  - Vocales seguidas: dos fuertes (a e o, y también í ú con tilde) se separan (le-er, pa-ís); fuerte + débil
    sin tilde o débil + débil forman diptongo y no se separan (reu-nión, ciu-dad).
  - La «y» es vocal solo al final de la palabra (hoy, muy); si no, consonante (le-yes).
  - La «h» se trata como consonante (a-ho-rro).
Para partir una línea además se exige dejar al menos 2 letras a cada lado (no «u-niversidad»).

Lógica pura: sin Qt.
"""
from __future__ import annotations

import re

VOCALES = set("aeiouáéíóúü")
FUERTES = set("aeoáéíóú")                  # í y ú con tilde rompen el diptongo: valen como fuertes
INSEPARABLES = {"pr", "br", "tr", "dr", "cr", "gr", "fr", "pl", "bl", "cl", "gl", "fl", "kr", "kl"}
GUION_SUAVE = "­"                      # invisible; si la línea se parte ahí, se dibuja «-»
MINIMO_A_CADA_LADO = 2
_PALABRA = re.compile(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+")


def _unidades(palabra: str) -> list[tuple[str, bool]]:
    """La palabra en unidades (texto original, ¿es vocal?): «guitarra» -> gu i t a rr a."""
    p = palabra.lower()
    salida, i = [], 0
    while i < len(p):
        dos = p[i:i + 2]
        if dos in ("ch", "ll", "rr"):
            salida.append((palabra[i:i + 2], False))
            i += 2
        elif dos in ("qu", "gu") and i + 2 < len(p) and p[i + 2] in "eiéí":
            salida.append((palabra[i:i + 2], False))            # «que», «gui»: la u no suena
            i += 2
        else:
            c = p[i]
            vocal = c in VOCALES or (c == "y" and i == len(p) - 1 and i > 0)
            salida.append((palabra[i], vocal))
            i += 1
    return salida


def _hiato(a: str, b: str) -> bool:
    """¿Estas dos vocales seguidas van en sílabas distintas?"""
    a, b = a.lower(), b.lower()
    return (a in FUERTES and b in FUERTES) or a == b


def silabas(palabra: str) -> list[str]:
    """'Computación' -> ['Com', 'pu', 'ta', 'ción']. Una palabra sin vocales queda entera."""
    u = _unidades(palabra)
    cortes = []                                  # índices de unidad donde EMPIEZA una sílaba nueva
    i = 0
    while i < len(u) and not u[i][1]:            # consonantes del principio: van con la primera vocal
        i += 1
    while i < len(u):
        j = i + 1                                # fin del núcleo vocálico que empieza en i
        while j < len(u) and u[j][1]:
            if _hiato(u[j - 1][0], u[j][0]):
                break
            j += 1
        if j < len(u) and u[j][1]:               # hiato: la sílaba siguiente empieza en la otra vocal
            cortes.append(j)
            i = j
            continue
        k = j                                    # consonantes hasta la próxima vocal
        while k < len(u) and not u[k][1]:
            k += 1
        if k == len(u):                          # consonantes del final: van con la última sílaba
            break
        n = k - j
        grupo = lambda a, b: (u[a][0] + u[b][0]).lower() in INSEPARABLES
        if n == 0:
            corte = j
        elif n == 1:
            corte = j
        elif n == 2:
            corte = j if grupo(j, j + 1) else j + 1
        elif n == 3:
            corte = j + 1 if grupo(j + 1, j + 2) else j + 2
        else:
            corte = j + 2
        cortes.append(corte)
        i = k
    partes, desde = [], 0
    for c in cortes:
        partes.append("".join(x for x, _ in u[desde:c]))
        desde = c
    partes.append("".join(x for x, _ in u[desde:]))
    return [p for p in partes if p]


def puntos_de_corte(palabra: str) -> list[int]:
    """Posiciones (en letras) donde se puede partir la palabra con guion, dejando 2 letras a cada lado."""
    salida, pos = [], 0
    for s in silabas(palabra)[:-1]:
        pos += len(s)
        if MINIMO_A_CADA_LADO <= pos <= len(palabra) - MINIMO_A_CADA_LADO:
            salida.append(pos)
    return salida


def con_guiones(texto: str, marca: str = GUION_SUAVE) -> str:
    """El texto con 'marca' en cada punto de corte de cada palabra: «Com­pu­ta­ción Grá­fi­ca» (guiones invisibles)."""
    def partir(m: re.Match) -> str:
        palabra = m.group(0)
        cortes = puntos_de_corte(palabra)
        if not cortes:
            return palabra
        trozos, desde = [], 0
        for c in cortes:
            trozos.append(palabra[desde:c])
            desde = c
        trozos.append(palabra[desde:])
        return marca.join(trozos)
    return _PALABRA.sub(partir, texto)
