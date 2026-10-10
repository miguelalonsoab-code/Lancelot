"""
Sensor: ¿qué ventana tienes al frente?

Usa la API de Windows (user32 / kernel32) a través de ctypes, que viene con Python.
Devuelve solo dos textos: el título de la ventana y el nombre del programa.
    ("(3) YouTube - Google Chrome", "chrome.exe")

En otro sistema operativo devuelve None (el modo estudio funciona igual, solo
que sin detectar distracciones).
"""
from __future__ import annotations

import os
import sys

if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    _user32 = ctypes.windll.user32
    _kernel32 = ctypes.windll.kernel32

    # Declarar tipos evita errores con punteros de 64 bits
    _user32.GetForegroundWindow.restype = wintypes.HWND
    _user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    _user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    _user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    _kernel32.OpenProcess.restype = wintypes.HANDLE
    _kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    _kernel32.QueryFullProcessImageNameW.argtypes = [
        wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
    _kernel32.CloseHandle.argtypes = [wintypes.HANDLE]

    _PERMISO_CONSULTA_LIMITADA = 0x1000   # PROCESS_QUERY_LIMITED_INFORMATION


def ventana_activa() -> tuple[str, str] | None:
    if sys.platform != "win32":
        return None
    try:
        hwnd = _user32.GetForegroundWindow()
        if not hwnd:
            return None

        largo = _user32.GetWindowTextLengthW(hwnd)
        titulo = ctypes.create_unicode_buffer(largo + 1)
        _user32.GetWindowTextW(hwnd, titulo, largo + 1)

        pid = wintypes.DWORD()
        _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        proceso = ""
        h = _kernel32.OpenProcess(_PERMISO_CONSULTA_LIMITADA, False, pid.value)
        if h:
            ruta = ctypes.create_unicode_buffer(512)
            tam = wintypes.DWORD(512)
            if _kernel32.QueryFullProcessImageNameW(h, 0, ruta, ctypes.byref(tam)):
                proceso = os.path.basename(ruta.value).lower()
            _kernel32.CloseHandle(h)
        return titulo.value, proceso
    except Exception:
        return None        # nunca dejar caer el asistente por un sensor
