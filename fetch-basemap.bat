@echo off
REM Optional, one time: download the offline street basemap for the map tab (~170 MB, needs internet).
REM Without it the map runs in its dark data-canvas style - everything works, just no street background.
setlocal
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0fetch-basemap.ps1" %*
echo.
pause
