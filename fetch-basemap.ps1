# fetch-basemap.ps1 - one-time download of the offline street basemap for the map tab.
#
# Runs tools\fetch_basemap.py with the app's Python (the same interpreter the plugin is installed into),
# then places the file where the page serves it from. Optional: without it the map uses its data-canvas
# style. Re-runnable; stop the app first, because the file it writes is the one the app is serving.
[CmdletBinding()]
param(
    [string]$AppPath = "",
    [int]$MaxZoom = 0,          # 0 = the tileset's own maximum (~170 MB); 13 gives a ~100 MB file
    [switch]$AssetsOnly,        # refresh only the small committed glyphs/sprites
    [switch]$NoPrompt
)

$ErrorActionPreference = "Stop"
$plugin = $PSScriptRoot

function Info($m) { Write-Host $m }
function Good($m) { Write-Host $m -ForegroundColor Green }
function Warn($m) { Write-Host $m -ForegroundColor Yellow }
function Die($m)  { Write-Host ""; Write-Host $m -ForegroundColor Red; exit 1 }

function Test-AppFolder($path) {
    if (-not $path) { return $false }
    try { $path = (Resolve-Path -LiteralPath $path -ErrorAction Stop).Path } catch { return $false }
    return (Test-Path (Join-Path $path "api\main.py")) -and (Test-Path (Join-Path $path "run.ps1"))
}

Write-Host ""
Write-Host "Road Safety Lab - offline basemap" -ForegroundColor Cyan

$parent = Split-Path $plugin -Parent
$app = $null
$candidates = @($AppPath, $env:NL2SQL_APP, (Join-Path $parent "app"), (Join-Path $parent "nl2sql-app-closed-core"))
try { $candidates += (Get-ChildItem -LiteralPath $parent -Directory | Where-Object { $_.FullName -ne $plugin } | ForEach-Object FullName) } catch { }
foreach ($c in $candidates) { if (Test-AppFolder $c) { $app = (Resolve-Path -LiteralPath $c).Path; break } }
if (-not $app) { Die "Could not find the app folder. Run install-plugin.bat first, or pass -AppPath." }

$py = Join-Path $app ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) { Die "The app has no .venv yet - run install-plugin.bat first." }

$running = $false
try { $running = [bool](Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue) } catch { }
if ($running) {
    Warn "The app appears to be running on port 8000. It serves the very file this script rewrites."
    if (-not $NoPrompt) {
        $a = Read-Host "  Stop the app, then press Enter to continue (or type s to skip the check)"
        if ($a -match '^[sS]') { Warn "  continuing anyway" }
    }
}

$args = @()
if ($AssetsOnly) { $args += "--assets-only" }
if ($MaxZoom -gt 0) { $args += "--maxzoom"; $args += "$MaxZoom" }

Info "  this downloads roughly 170 MB and can take several minutes ..."
$env:PYTHONUTF8 = "1"
& $py (Join-Path $plugin "tools\fetch_basemap.py") @args
if ($LASTEXITCODE -ne 0) { Die "The basemap fetch failed - see the messages above. The map still works without it." }

Write-Host ""
Good "Basemap ready. Restart the app (or just reload the page) and the map tab shows real streets."
Write-Host ""
