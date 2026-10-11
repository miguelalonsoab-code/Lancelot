"""
Convierte Lancelot en un programa normal de Windows, con instalador.

Uso (con el entorno virtual activado, desde la carpeta del proyecto):

    pip install pyinstaller          <- solo la primera vez
    python construir.py              <- .exe + instalador (si tienes Inno Setup)
    python construir.py --publicar   <- además, lo sube a GitHub como Release (para la actualización automática)
    python construir.py --sin-instalador
    python construir.py --sin-voz    <- no incluye el modelo de voz ni las voces (instalador más liviano)

Qué hace, en orden:
  1. Revisa que Lancelot esté cerrado (si está abierto, Windows no deja reemplazar el .exe).
  2. Dibuja el ícono a partir de la cara (build\\lancelot.ico).
  3. Llama a PyInstaller: junta Python, PySide6, Vosk, Piper... y tu código en dist\\Lancelot\\.
  3b. Copia el modelo de voz (Vosk) y tus voces Piper a dist\\Lancelot\\recursos: así, en una PC nueva,
      la voz funciona sin descargar nada. Tus tareas y apodos NUNCA van en el instalador.
  4. Si tienes Inno Setup, arma el instalador: dist\\Lancelot-setup-3.7.exe (ver instalador\\lancelot.iss).
  5. Te pregunta si quieres copiar tus datos actuales (tareas, apodos, modelo de voz) a donde los usa
     el .exe, y quita el inicio viejo con iniciar.bat. Luego:
       - con instalador: te ofrece instalar (menú Inicio, inicio con Windows y desinstalador incluidos),
       - sin instalador: crea los accesos de inicio y del menú Inicio apuntando a dist\\Lancelot.

¿Dónde quedan los datos?
  - python main.py  -> carpeta datos\\ del proyecto (para desarrollar y probar)
  - Lancelot.exe    -> %LOCALAPPDATA%\\Lancelot (tus datos "de verdad")
  Así, volver a construir el .exe (que borra dist\\Lancelot entero) nunca toca tus tareas.

Cada vez que cambies el código: cierra Lancelot y vuelve a ejecutar python construir.py.
"""
from __future__ import annotations

import importlib.util
import os
import shutil
import struct
import subprocess
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))

from config import (CARPETA_DATOS_EXE, MODELO_VOSK, MUTEX_WINDOWS, NOMBRE_ASISTENTE,  # noqa: E402
                    REPO_ACTUALIZACIONES, URL_MODELO_VOSK, VERSION)

NOMBRE = NOMBRE_ASISTENTE                  # "Lancelot" -> Lancelot.exe
DIST = RAIZ / "dist"
BUILD = RAIZ / "build"
SALIDA = DIST / NOMBRE
EXE = SALIDA / (NOMBRE + (".exe" if sys.platform == "win32" else ""))
EN_WINDOWS = sys.platform == "win32"
SCRIPT_INSTALADOR = RAIZ / "instalador" / "lancelot.iss"
INSTALADOR = DIST / f"{NOMBRE}-setup-{VERSION}.exe"
CARPETA_INICIO = (Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs"
                  / "Startup")


_APP_QT = None


def app_qt():
    """Una sola app de Qt para todo el script (Qt no deja crear dos)."""
    global _APP_QT
    from PySide6.QtGui import QGuiApplication
    _APP_QT = QGuiApplication.instance() or QGuiApplication([])
    return _APP_QT


def lancelot_abierto() -> bool:
    """Intenta hablar con un Lancelot en marcha (el mismo canal que usa main.py)."""
    from PySide6.QtNetwork import QLocalSocket
    from config import APP_ID_WINDOWS
    app_qt()
    s = QLocalSocket()
    s.connectToServer(APP_ID_WINDOWS)
    abierto = s.waitForConnected(300)
    s.abort()
    return abierto


def titulo(texto: str):
    print(f"\n=== {texto} ===")


def preguntar(texto: str, por_defecto: bool = True) -> bool:
    opciones = "S/n" if por_defecto else "s/N"
    try:
        r = input(f"{texto} [{opciones}] ").strip().lower()
    except EOFError:                                  # sin teclado (p. ej. en una prueba automática)
        return por_defecto
    return por_defecto if not r else r.startswith("s")


# ----------------------------------------------------------------- 1. revisar
def revisar_requisitos():
    titulo("1. Revisando")
    if importlib.util.find_spec("PyInstaller") is None:
        print("Falta PyInstaller. Instálalo con:\n\n    pip install pyinstaller\n")
        sys.exit(1)
    if not EN_WINDOWS:
        print("Aviso: no estás en Windows. Se construirá un ejecutable para ESTE sistema, no un .exe.")
    if sys.prefix == sys.base_prefix:
        print("Aviso: el entorno virtual no parece activado (.venv). Si falla, actívalo y repite.")
    if lancelot_abierto():
        print(f"{NOMBRE} está abierto. Ciérralo (clic derecho en la cara → Salir) y vuelve a intentar.")
        sys.exit(1)
    if SALIDA.exists():
        # Si Lancelot.exe está abierto, Windows bloquea sus archivos: renombrar la carpeta falla
        prueba = SALIDA.with_name(NOMBRE + "_borrando")
        try:
            if prueba.exists():
                shutil.rmtree(prueba)
            SALIDA.rename(prueba)
            shutil.rmtree(prueba)
        except PermissionError:
            print(f"{NOMBRE} está abierto. Ciérralo (clic derecho en la cara → Salir) y vuelve a intentar.")
            sys.exit(1)
    print("Todo listo.")


# ------------------------------------------------------------------ 2. ícono
def crear_icono() -> Path:
    """Dibuja la cara en varios tamaños y arma un .ico (cada tamaño va como PNG adentro)."""
    titulo("2. Ícono")
    from PySide6.QtCore import QBuffer, QByteArray, QIODevice
    from interfaz.cara import pixmap_cara

    app_qt()                                          # QPixmap necesita una app de Qt
    imagenes = []
    for lado in (256, 64, 48, 32, 16):
        datos = QByteArray()
        buffer = QBuffer(datos)
        buffer.open(QIODevice.WriteOnly)
        pixmap_cara(lado).save(buffer, "PNG")
        imagenes.append((lado, bytes(datos)))

    # Formato ICO: cabecera (6 bytes) + una entrada de 16 bytes por imagen + las imágenes
    cabecera = struct.pack("<HHH", 0, 1, len(imagenes))
    desplazamiento = 6 + 16 * len(imagenes)
    entradas, cuerpo = b"", b""
    for lado, png in imagenes:
        medida = 0 if lado >= 256 else lado            # 0 significa 256 en el formato ICO
        entradas += struct.pack("<BBBBHHII", medida, medida, 0, 0, 1, 32, len(png), desplazamiento)
        cuerpo += png
        desplazamiento += len(png)
    BUILD.mkdir(exist_ok=True)
    ruta = BUILD / "lancelot.ico"
    ruta.write_bytes(cabecera + entradas + cuerpo)
    print(f"Ícono: {ruta.relative_to(RAIZ)}")
    return ruta


# ------------------------------------------------------------- 3. PyInstaller
def argumentos_pyinstaller(icono: Path) -> list[str]:
    args = [
        str(RAIZ / "main.py"),
        "--name", NOMBRE,
        "--windowed",                    # sin ventana negra de consola
        "--onedir",                      # una carpeta (arranca mucho más rápido que --onefile)
        "--noconfirm", "--clean",
        "--icon", str(icono),
        "--distpath", str(DIST),
        "--workpath", str(BUILD / "trabajo"),
        "--specpath", str(BUILD),
        "--paths", str(RAIZ),
    ]
    # Cosas que algunas librerías mencionan pero Lancelot no usa (p. ej. piper.train es para
    # ENTRENAR voces y arrastra torch, scipy, pandas...). Dejarlas fuera ahorra cientos de MB.
    for modulo in ("tkinter", "piper.train", "torch", "scipy", "pandas", "matplotlib", "IPython",
                   "onnxruntime.transformers", "onnxruntime.quantization", "onnxruntime.tools"):
        args += ["--exclude-module", modulo]

    def hay(modulo: str) -> bool:
        return importlib.util.find_spec(modulo) is not None

    # Paquetes que cargan archivos propios (DLL, datos) y PyInstaller no adivina solo
    if hay("vosk"):
        args += ["--collect-all", "vosk"]                     # libvosk.dll
    if hay("piper"):
        args += ["--collect-data", "piper",                   # espeak-ng-data (pronunciación)
                 "--collect-binaries", "piper"]               # el puente con espeak (.pyd)
    if hay("_sounddevice_data"):
        args += ["--collect-data", "_sounddevice_data"]       # PortAudio (micrófono)
    if hay("pyttsx3"):
        args += ["--hidden-import", "pyttsx3.drivers", "--hidden-import", "pyttsx3.drivers.sapi5"]
    if hay("comtypes"):
        args += ["--collect-submodules", "comtypes"]          # incluye la interfaz de voz de Windows ya generada
    faltan = [m for m in ("vosk", "sounddevice", "pyttsx3") if not hay(m)]
    if faltan:
        print(f"Aviso: no están instalados {', '.join(faltan)}; el .exe funcionará sin esa parte de la voz.")
    return args


def empaquetar(icono: Path):
    titulo("3. Empaquetando con PyInstaller (tarda unos minutos)")
    inicio = time.monotonic()
    r = subprocess.run([sys.executable, "-m", "PyInstaller", *argumentos_pyinstaller(icono)], cwd=RAIZ)
    if r.returncode != 0 or not EXE.exists():
        print("\nPyInstaller falló. Lee el error de arriba (las últimas líneas suelen decir qué falta).")
        sys.exit(1)
    peso = sum(f.stat().st_size for f in SALIDA.rglob("*") if f.is_file()) / 1024 ** 2
    print(f"\nListo en {time.monotonic() - inicio:.0f} s: {EXE.relative_to(RAIZ)}  ({peso:.0f} MB en total)")


# ------------------------------------------------------------ 3b. recursos
def copiar_recursos():
    """
    Modelo de voz y voces Piper dentro del programa (dist\\Lancelot\\recursos).
    Se buscan en tus datos de desarrollo y en los del .exe; si el modelo no está, se descarga.
    """
    titulo("3b. Voz incluida")
    from voz.habla import voces_piper
    from voz.oido import asegurar_modelo, modelo_valido

    destino = SALIDA / "recursos"
    origenes = [RAIZ / "datos", CARPETA_DATOS_EXE]

    modelo = next((o / "voz" / MODELO_VOSK for o in origenes if modelo_valido(o / "voz" / MODELO_VOSK)), None)
    if modelo is None:
        print("No tengo el modelo de voz a mano; lo descargo (39 MB, solo esta vez)…")
        try:
            modelo = asegurar_modelo(BUILD / "descargas", MODELO_VOSK, URL_MODELO_VOSK,
                                     lambda p: print(f"  {p}"))
        except Exception as e:
            print(f"No pude descargarlo ({e}). El instalador irá sin modelo: lo bajará al activar la voz.")
    if modelo:
        shutil.copytree(modelo, destino / "voz" / MODELO_VOSK)
        print(f"Modelo de voz: {MODELO_VOSK}")

    voces = next((v for v in (voces_piper(o / "voces") for o in origenes) if v), [])
    for onnx in voces:
        (destino / "voces").mkdir(parents=True, exist_ok=True)
        for archivo in (onnx, onnx.with_name(onnx.name + ".json")):
            shutil.copy2(archivo, destino / "voces" / archivo.name)
        print(f"Voz Piper: {onnx.stem}")
    if not voces:
        print("Sin voces Piper: el .exe usará las voces de Windows (como ahora).")
    if destino.exists():
        peso = sum(f.stat().st_size for f in destino.rglob("*") if f.is_file()) / 1024 ** 2
        print(f"Recursos incluidos: {peso:.0f} MB")


# ------------------------------------------------------------- 4. instalador
def buscar_inno() -> Path | None:
    """ISCC.exe es el compilador de Inno Setup. Se busca en el registro, en el PATH y en sus carpetas típicas."""
    if not EN_WINDOWS:
        return None
    candidatos = []
    import winreg
    for raiz in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        for vista in (winreg.KEY_WOW64_32KEY, winreg.KEY_WOW64_64KEY):
            for version in ("6", "7"):
                clave = rf"Software\Microsoft\Windows\CurrentVersion\Uninstall\Inno Setup {version}_is1"
                try:
                    with winreg.OpenKey(raiz, clave, 0, winreg.KEY_READ | vista) as k:
                        candidatos.append(Path(winreg.QueryValueEx(k, "InstallLocation")[0]) / "ISCC.exe")
                except OSError:
                    pass
    if ruta := shutil.which("iscc"):
        candidatos.append(Path(ruta))
    for variable in ("ProgramFiles(x86)", "ProgramFiles", "LOCALAPPDATA"):
        base = Path(os.environ.get(variable, "")) / ("Programs" if variable == "LOCALAPPDATA" else "")
        candidatos += [base / "Inno Setup 6" / "ISCC.exe", base / "Inno Setup 7" / "ISCC.exe"]
    return next((c for c in candidatos if c.is_file()), None)


def crear_instalador(iscc: Path, icono: Path) -> bool:
    titulo("4. Instalador (Inno Setup)")
    if INSTALADOR.exists():
        INSTALADOR.unlink()
    r = subprocess.run([str(iscc), "/Qp",                    # silencioso, solo muestra el progreso
                        f"/DVersionApp={VERSION}", f"/DCarpetaApp={SALIDA}", f"/DIcono={icono}",
                        f"/DSalida={DIST}", f"/DMutexApp={MUTEX_WINDOWS}", str(SCRIPT_INSTALADOR)])
    if r.returncode != 0 or not INSTALADOR.exists():
        print("Inno Setup falló (el error está arriba). El .exe igual quedó listo en dist\\Lancelot.")
        return False
    print(f"Instalador: {INSTALADOR.relative_to(RAIZ)}  ({INSTALADOR.stat().st_size / 1024 ** 2:.0f} MB)")
    return True


# ---------------------------------------------------------------- 6. publicar
def buscar_gh() -> str | None:
    """GitHub CLI: la herramienta oficial de GitHub para la terminal."""
    candidatos = [shutil.which("gh"), str(Path(os.environ.get("ProgramFiles", "")) / "GitHub CLI" / "gh.exe")]
    return next((c for c in candidatos if c and Path(c).is_file()), None)


def publicar():
    """Crea la Release vX.Y en GitHub con el instalador adjunto y las novedades del README."""
    titulo("6. Publicar en GitHub")
    from nucleo.version import notas_de_version
    if not REPO_ACTUALIZACIONES:
        print("Primero escribe tu repositorio en config.py:  REPO_ACTUALIZACIONES = \"usuario/repositorio\"")
        return
    gh = buscar_gh()
    if not gh:
        print("Falta GitHub CLI. Instálalo y conéctalo (una sola vez):\n"
              "    winget install --id GitHub.cli -e\n    gh auth login\n"
              "Luego cierra y abre la terminal, y repite: python construir.py --publicar")
        return
    pendientes = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, cwd=RAIZ).stdout
    if pendientes.strip():
        print("Ojo: tienes cambios sin commit. La Release se crea sobre lo último que subiste a GitHub.")
    if not preguntar(f"¿Publicar Lancelot {VERSION} en github.com/{REPO_ACTUALIZACIONES}?"):
        return
    notas = BUILD / "notas.md"
    notas.write_text(notas_de_version((RAIZ / "README.md").read_text(encoding="utf-8"), VERSION), encoding="utf-8")
    r = subprocess.run([gh, "release", "create", f"v{VERSION}", str(INSTALADOR), "--repo", REPO_ACTUALIZACIONES,
                        "--title", f"{NOMBRE} {VERSION}", "--notes-file", str(notas)], cwd=RAIZ)
    if r.returncode != 0:
        print(f"No se pudo publicar. Si dice que «v{VERSION}» ya existe, sube VERSION en config.py y reconstruye.")
    else:
        print(f"Publicado: https://github.com/{REPO_ACTUALIZACIONES}/releases/tag/v{VERSION}\n"
              "Los Lancelot instalados lo verán en las próximas horas (o al decir «busca actualizaciones»).")


# --------------------------------------------------------------- 5. opciones
def copiar_datos():
    """La primera vez: lleva tus tareas, apodos, voces y modelo a la carpeta del .exe."""
    origen, destino = RAIZ / "datos", CARPETA_DATOS_EXE
    if not (origen / "tareas.db").exists():
        return
    if (destino / "tareas.db").exists():
        print(f"El .exe ya tiene sus datos en {destino} (no los toco).")
        return
    if not preguntar(f"¿Copiar tus datos actuales (tareas, apodos, voces) a {destino}?"):
        print("El .exe empezará sin tareas.")
        return
    shutil.copytree(origen, destino, dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("lancelot.log*", "_ultima_frase.wav"))
    print(f"Datos copiados. Desde ahora, Lancelot.exe usa {destino}")


def _powershell(orden: str) -> str:
    r = subprocess.run(["powershell", "-NoProfile", "-Command", orden], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", creationflags=0x08000000)   # sin ventana
    return r.stdout


def _crear_acceso(ruta_lnk: Path):
    p = lambda ruta: str(ruta).replace("'", "''")     # noqa: E731  (comillas simples para PowerShell)
    _powershell(f"$s = (New-Object -ComObject WScript.Shell).CreateShortcut('{p(ruta_lnk)}'); "
                f"$s.TargetPath = '{p(EXE)}'; $s.WorkingDirectory = '{p(SALIDA)}'; "
                f"$s.IconLocation = '{p(EXE)},0'; $s.Description = '{NOMBRE}'; $s.Save()")


def quitar_inicio_viejo(con_instalador: bool):
    """
    Busca en la carpeta de Inicio lo que abría Lancelot "a mano" (iniciar.bat, pythonw main.py)
    para que no se abran dos. Con instalador, también el acceso que apuntaba a dist\\Lancelot
    (el instalador crea uno nuevo apuntando a la versión instalada).
    """
    pistas = ["iniciar.bat", "main.py"] + ([str(SALIDA).lower()] if con_instalador else [])
    viejos = []
    for archivo in CARPETA_INICIO.glob("*"):
        contenido = ""
        if archivo.suffix.lower() == ".lnk":
            p = str(archivo).replace("'", "''")
            contenido = _powershell(f"$s = (New-Object -ComObject WScript.Shell).CreateShortcut('{p}'); "
                                    "$s.TargetPath + ' ' + $s.Arguments")
        elif archivo.suffix.lower() in (".bat", ".cmd", ".vbs"):
            contenido = archivo.read_text(errors="ignore")
        if any(pista in contenido.lower() for pista in pistas):
            viejos.append(archivo)
    for viejo in viejos:
        if preguntar(f"Encontré un inicio anterior «{viejo.name}». ¿Lo quito para que no se abran dos?"):
            viejo.unlink()
            print(f"Quitado: {viejo.name}")


def inicio_con_windows():
    if preguntar(f"¿Iniciar {NOMBRE}.exe al encender la laptop?"):
        _crear_acceso(CARPETA_INICIO / f"{NOMBRE}.lnk")
        print(f"{NOMBRE}.exe se iniciará con Windows.")


def menu_inicio():
    carpeta = Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs"
    if preguntar(f"¿Agregar {NOMBRE} al menú Inicio (para abrirlo buscándolo)?"):
        _crear_acceso(carpeta / f"{NOMBRE}.lnk")
        print("Agregado. Búscalo con la tecla Windows.")


def main():
    con_instalador = "--sin-instalador" not in sys.argv
    revisar_requisitos()
    icono = crear_icono()
    empaquetar(icono)
    if "--sin-voz" not in sys.argv:
        copiar_recursos()

    instalador_listo = False
    if con_instalador:
        iscc = buscar_inno()
        if iscc:
            instalador_listo = crear_instalador(iscc, icono)
        elif EN_WINDOWS:
            titulo("4. Instalador")
            print("No encontré Inno Setup, así que no armo el instalador (el .exe sí está listo).\n"
                  "Para tenerlo: winget install --id JRSoftware.InnoSetup -e -s winget\n"
                  "y vuelve a ejecutar python construir.py")

    titulo("5. Opciones")
    copiar_datos()
    if "--publicar" in sys.argv:
        if instalador_listo:
            publicar()
        else:
            print("No hay instalador, así que no hay nada que publicar (necesitas Inno Setup).")
    if not EN_WINDOWS:
        print(f"\nListo: {EXE.relative_to(RAIZ)}")
        return
    quitar_inicio_viejo(instalador_listo)
    if instalador_listo:
        if preguntar(f"¿Instalar {NOMBRE} {VERSION} ahora?"):
            subprocess.Popen([str(INSTALADOR)])           # el asistente de instalación sigue por su cuenta
            print("Se abrió el instalador. Sigue los pasos en su ventana.")
        else:
            print(f"Cuando quieras, abre {INSTALADOR.relative_to(RAIZ)}. Puedes copiarlo a otra PC.")
    else:
        inicio_con_windows()
        menu_inicio()
        print(f"\nTodo listo. Abre {EXE.relative_to(RAIZ)} (doble clic) para probarlo.")


if __name__ == "__main__":
    main()
