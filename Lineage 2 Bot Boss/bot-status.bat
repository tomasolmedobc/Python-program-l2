@echo off
title Epic Raid Boss Tracker - Estado
echo === Estado del bot (PM2) ===
pm2 list
echo.
echo === Ultimas 50 lineas de log ===
pm2 logs l2-raidboss-bot --lines 50 --nostream
echo.
pause
