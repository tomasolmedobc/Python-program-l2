@echo off
cd /d "%~dp0"
title Epic Raid Boss Tracker
echo Iniciando el bot...
echo (dejar esta ventana abierta mientras quieras que el bot este conectado)
echo.
node src\index.js
echo.
echo El bot se detuvo o hubo un error. Revisa el mensaje de arriba.
pause
