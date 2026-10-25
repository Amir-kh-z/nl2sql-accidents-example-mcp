@echo off
REM Double-click me AFTER install-plugin.bat: trains, validates and deploys the two reference models
REM (site 2023 doc-11 s42, severity 2022 person-12 s42) so the numbers in the docs appear on your machine.
REM Asks for the database path when the working copy is not at C:\data\israel_accidents\.
setlocal
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0seed-models.ps1" %*
echo.
pause
