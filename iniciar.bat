@echo off
REM Inicia el asistente sin ventana de consola
cd /d "%~dp0"
start "" ".venv\Scripts\pythonw.exe" main.py
