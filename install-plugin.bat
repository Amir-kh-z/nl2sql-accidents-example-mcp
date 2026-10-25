@echo off
REM Double-click me. Installs the Road Safety Lab plugin into the NL2SQL app sitting next to this folder.
REM (Windows blocks .ps1 files on a double-click, so this wrapper runs it with the policy bypassed.)
setlocal
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install-plugin.ps1" %*
echo.
pause
