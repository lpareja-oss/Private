@echo off
title Novedades - ClicOH
echo.
echo  === Iniciando Tablero de Novedades - ClicOH ===
echo.

set PYTHON=C:\Users\Asus\AppData\Local\Programs\Python\Python312\python.exe
set STREAMLIT=C:\Users\Asus\AppData\Local\Programs\Python\Python312\Scripts\streamlit.exe

REM Ir a la carpeta del proyecto
cd /d "%~dp0"

REM Crear config de Streamlit (sin BOM)
if not exist "%USERPROFILE%\.streamlit" mkdir "%USERPROFILE%\.streamlit"
(echo [browser]& echo gatherUsageStats = false) > "%USERPROFILE%\.streamlit\config.toml"

echo  Abriendo tablero en http://localhost:8502
echo  Presiona Ctrl+C para detener.
echo.

start "" "http://localhost:8502"
"%STREAMLIT%" run Seguimiento.py --server.port 8502 --server.headless true

pause
