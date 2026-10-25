@echo off
REM Double-click me AFTER install-plugin.bat: adds the chat channel (the MCP server) and registers it with
REM Claude Code (user scope, via `claude mcp add`) and with Claude Desktop when it is installed.
REM QUIT Claude Desktop first (tray icon -> Quit) - it rewrites its config while open.
REM Asks for the database path when the working copy is not at C:\data\israel_accidents\.
setlocal
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install-plugin.ps1" -Mcp %*
echo.
pause
