@echo off
title Configurar NOVA - API Key Anthropic
echo.
echo  === Configuracion del Agente NOVA ===
echo.
echo  Para usar el agente necesitas una API Key de Anthropic.
echo.
echo  Pasos:
echo  1. Abre: https://console.anthropic.com
echo  2. Inicia sesion o registrate
echo  3. Ve a "API Keys" - haz clic en "Create Key"
echo  4. Copia la key (empieza con sk-ant-)
echo  5. Pegala cuando se te pida abajo
echo.
start "" "https://console.anthropic.com"

set /p APIKEY="Pega tu API Key aqui: "

if "%APIKEY%"=="" (
    echo Key vacia, cancelado.
    pause
    exit /b
)

echo ANTHROPIC_API_KEY=%APIKEY% > "%~dp0config_agente.txt"
echo.
echo  API Key guardada correctamente.
echo  Ahora podes usar el agente NOVA en el dashboard.
echo.
pause
