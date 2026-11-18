@echo off
setlocal
cd /d "%~dp0"
title RouteFlow - Managua
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" app.py
) else (
  echo [RouteFlow] No se encontro el entorno virtual .venv.
  echo Abre CMD en esta carpeta y ejecuta:
  echo   py -3.14 -m venv .venv
  echo   .venv\Scripts\python.exe -m pip install -r requirements.txt
  pause
)
