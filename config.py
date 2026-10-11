"""
Configuración general del asistente.
Todo lo que quieras personalizar (nombre, colores, tiempos) está aquí,
para no tener que buscar valores sueltos dentro del código.
"""
import os
import sys
from pathlib import Path

# --- Identidad ---------------------------------------------------------------
NOMBRE_ASISTENTE = "Lancelot"           # cómo se llama (burbujas, notificaciones, voz)
NOMBRE_USUARIO = "Miguel"               # cómo te llama al avisarte
APP_ID_WINDOWS = "miguel.asistente.recordatorios"  # para que Windows agrupe sus notificaciones
VERSION = "3.8"                         # sale en el panel y en el instalador (súbela en cada versión)
MUTEX_WINDOWS = "LancelotEnEjecucion"   # el instalador lo busca para saber si Lancelot está abierto

# --- Rutas -------------------------------------------------------------------
# Si corre como Lancelot.exe (empaquetado con construir.py), sus datos viven en
# %LOCALAPPDATA%\Lancelot: así reconstruir el .exe nunca borra tus tareas.
# Si corre con "python main.py", usa la carpeta datos/ del proyecto, como siempre.
EMPAQUETADO = getattr(sys, "frozen", False)
CARPETA_PROYECTO = Path(__file__).resolve().parent
CARPETA_DATOS_EXE = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local") / NOMBRE_ASISTENTE
CARPETA_DATOS = CARPETA_DATOS_EXE if EMPAQUETADO else CARPETA_PROYECTO / "datos"
# Recursos que vienen DENTRO del instalador (modelo de voz y voces Piper), junto a Lancelot.exe.
# Se usan solo si no los tienes ya en tu carpeta de datos. Con "python main.py" no hay.
CARPETA_RECURSOS = Path(sys.executable).parent / "recursos" if EMPAQUETADO else None
RUTA_BD = CARPETA_DATOS / "tareas.db"
RUTA_REGISTRO = CARPETA_DATOS / "lancelot.log"   # registro de eventos y errores
CARPETA_RESPALDOS = CARPETA_DATOS / "respaldos"  # copia diaria de tareas.db
RESPALDOS_A_CONSERVAR = 7
NIVEL_REGISTRO = "INFO"           # "DEBUG" también guarda lo que el oído reconoce de tu voz

# --- Tiempos -----------------------------------------------------------------
SEGUNDOS_ENTRE_REVISIONES = 10    # cada cuánto el núcleo revisa si algo venció
HORA_POR_DEFECTO = (9, 0)         # si dices "mañana" sin hora, se asume 09:00
MINUTOS_POSPONER = 10             # botón "+10 min" de la burbuja
HORA_DORMIR = 23                  # desde esta hora la cara se duerme si no hay nada pendiente
HORA_DESPERTAR = 6

# --- Actualizaciones -------------------------------------------------------------
# Repositorio de GitHub donde publicas las versiones ("usuario/repositorio"). Vacío = no busca.
# Debe ser PÚBLICO (o tener sus Releases en un repositorio público): ver README, "Actualizaciones".
REPO_ACTUALIZACIONES = ""
HORAS_ENTRE_BUSQUEDAS = 6
BUSCAR_ACTUALIZACIONES_EN_DESARROLLO = False   # con "python main.py" se actualiza con git pull

# --- Saludo del día ------------------------------------------------------------
SALUDO_ACTIVO = True              # el primer saludo del día con tus pendientes y tu racha
HORA_SALUDO = HORA_DESPERTAR      # no saluda antes de esta hora (laptop prendida toda la noche)
SALUDO_HABLADO = True             # además de la burbuja, lo dice en voz alta (salvo modo silencio)
SEGUNDOS_SALUDO = 20              # cuánto queda visible la burbuja del saludo

# --- Apariencia de la cara ---------------------------------------------------
TAMANO_CARA = 150                 # diámetro en píxeles
FPS_ANIMACION = 30

COLORES = {
    "fondo_bisel": "#16181d",     # el "cuerpo" alrededor de la pantalla
    "pantalla": "#050608",        # la pantalla negra donde viven los ojos
    "ojos": "#f2f5f7",
    # El anillo cambia de color según el estado:
    "tranquilo": "#4fd1c5",       # nada pendiente para hoy
    "pendiente": "#f6c453",       # hay tareas para hoy
    "alerta": "#ff6b4a",          # algo venció y está esperando respuesta
    "feliz": "#5be37d",           # acabas de completar algo
    "dormido": "#3a4a6b",         # de noche y sin pendientes
    # Modo estudio
    "estudio": "#8b7cf6",         # enfocado (el anillo se va vaciando con el tiempo)
    "descanso": "#5be3c8",        # en descanso
    "esperando": "#8b7cf6",       # terminó el descanso, esperando que sigas
    "sospecha": "#ff9f43",        # detectó una distracción
    # Voz
    "escuchando": "#4fc3ff",      # esperando que le digas algo
}

# --- Modos -------------------------------------------------------------------
# Puedes renombrarlos: es solo el texto que se muestra.
NOMBRES_MODO = {
    "normal": "Normal",
    "estudio": "Modo estudio",
    "silencio": "Modo silencio",
}

# --- Pomodoro ----------------------------------------------------------------
MINUTOS_ENFOQUE = 25
MINUTOS_DESCANSO = 5
MINUTOS_DESCANSO_LARGO = 15
CICLOS_PARA_DESCANSO_LARGO = 4
META_ESTUDIO_DIARIO = 100         # minutos por día; se marca con una línea en el gráfico semanal

# --- Distracciones (solo durante el modo estudio) ----------------------------
# Se busca cada palabra en el TÍTULO de la ventana activa o en el nombre del programa.
# Nada se guarda ni se envía: solo se compara en el momento.
# Formato:  "texto a buscar": "nombre que se muestra"
DISTRACCIONES = {
    "youtube": "YouTube", "tiktok": "TikTok", "instagram": "Instagram",
    "facebook": "Facebook", "netflix": "Netflix", "twitch": "Twitch",
    "reddit": "Reddit", "twitter": "Twitter / X", "prime video": "Prime Video",
    "disney+": "Disney+", "crunchyroll": "Crunchyroll",
    "steam.exe": "Steam", "epicgameslauncher": "Epic Games",
}
SEGUNDOS_DE_GRACIA = 60          # cuánto tiempo seguido en una distracción antes de avisar
MINUTOS_ENTRE_AVISOS_DISTRACCION = 5
SEGUNDOS_MENSAJE = 12            # cuánto dura visible una burbuja de aliento


# --- Voz: escuchar -------------------------------------------------------------
# Formas en que el reconocedor puede escribir el nombre. Si al probar (probar_voz.py)
# ves que te entiende otra cosa cuando dices "Lancelot" o "Lance", agrégala aquí.
PALABRAS_ACTIVACION = ["lancelot", "lance lot", "lanzelot", "lanselot", "lance", "lans", "lanz"]
SEGUNDOS_ESPERA_ORDEN = 7         # si solo dices "Lancelot", cuánto espera la orden
# Atajo para hablar sin decir el nombre: se pulsa una vez y hablas (termina al callarte)
ATAJO_HABLAR = "Ctrl+Alt+Espacio"
MODELO_VOSK = "vosk-model-small-es-0.42"
URL_MODELO_VOSK = "https://alphacephei.com/vosk/models/vosk-model-small-es-0.42.zip"
CARPETA_VOZ = CARPETA_DATOS / "voz"          # aquí se descarga el modelo (39 MB, una sola vez)

# --- Voz: hablar ---------------------------------------------------------------
# "auto": usa una voz Piper si pones un archivo .onnx (y su .onnx.json) en datos/voces/;
#         si no hay, usa las voces que trae Windows.
VOZ_MOTOR = "auto"                # "auto" | "piper" | "windows"
CARPETA_VOCES = CARPETA_DATOS / "voces"
VOZ_WINDOWS_PREFERIDA = ""        # parte del nombre de la voz de Windows, p. ej. "Sabina" o "Helena"
VOZ_VELOCIDAD = 1.0               # 1.0 normal · 1.2 más rápido · 0.9 más lento
HABLAR_RECORDATORIOS = True       # decir en voz alta las tareas cuando vencen
HABLAR_MENSAJES_ESTUDIO = True    # decir los mensajes de fin de pomodoro, descanso, distracción

# --- Apps y páginas extra para "abre ..." -----------------------------------------
# Lo que está en tu menú Inicio se encuentra solo. Aquí van páginas web o apodos:
#   "apodo": "https://pagina.com"            -> abre la página
#   "apodo": "Nombre de la app en el menú"   -> apodo de esa app, p. ej. "el código": "Visual Studio Code"
#   "apodo": "C:\\ruta\\al\\programa.exe"     -> abre ese programa
# Páginas que entiende por nombre: "abre netflix", "abre netflix desde chrome".
# Agrega las tuyas (por ejemplo, el aula virtual de la UPN).
SITIOS_CONOCIDOS = {
    "netflix": "https://www.netflix.com",
    "youtube": "https://www.youtube.com",
    "gmail": "https://mail.google.com", "correo": "https://mail.google.com",
    "whatsapp": "https://web.whatsapp.com", "whatsapp web": "https://web.whatsapp.com",
    "facebook": "https://www.facebook.com",
    "instagram": "https://www.instagram.com",
    "tiktok": "https://www.tiktok.com",
    "twitter": "https://x.com", "x": "https://x.com",
    "twitch": "https://www.twitch.tv",
    "crunchyroll": "https://www.crunchyroll.com",
    "disney": "https://www.disneyplus.com", "disney plus": "https://www.disneyplus.com",
    "prime video": "https://www.primevideo.com", "amazon prime": "https://www.primevideo.com",
    "spotify": "https://open.spotify.com",
    "github": "https://github.com",
    "drive": "https://drive.google.com", "google drive": "https://drive.google.com",
    "classroom": "https://classroom.google.com",
    "google": "https://www.google.com",
    "maps": "https://maps.google.com", "google maps": "https://maps.google.com",
    "traductor": "https://translate.google.com",
    "claude": "https://claude.ai",
    "linkedin": "https://www.linkedin.com",
    "outlook": "https://outlook.live.com",
    "canva": "https://www.canva.com",
}

APPS_EXTRA = {
    "youtube": "https://www.youtube.com",
    "gmail": "https://mail.google.com",
    "correo": "https://mail.google.com",
    "whatsapp web": "https://web.whatsapp.com",
}
