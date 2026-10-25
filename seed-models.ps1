# seed-models.ps1 - train, validate and deploy the two reference models the docs quote
# (site: through 2023, doc-11, seed 42 - severity: through 2022, person-12, seed 42).
#
# Double-click `seed-models.bat` instead of running this by hand. Run install-plugin.bat FIRST (the plugin
# and xgboost must be in the app's environment). The app need not be running; the models land under the
# shared data dir (%LOCALAPPDATA%\nl2sql-core\accidents\models\) where the app, the page and the chat read them.
#
#   .\seed-models.ps1                                   # find the app automatically, default database path
#   .\seed-models.ps1 -DbPath D:\data\israel_accidents.duckdb
#   .\seed-models.ps1 -Force                            # train again even if a family is already deployed
[CmdletBinding()]
param(
    [string]$AppPath = "",
    [string]$DbPath = "C:\data\israel_accidents\israel_accidents.duckdb",
    [switch]$Force,
    [switch]$NoPrompt
)

$ErrorActionPreference = "Stop"
$plugin = $PSScriptRoot

function Info($m) { Write-Host $m }
function Step($m) { Write-Host ""; Write-Host $m -ForegroundColor Cyan }
function Good($m) { Write-Host $m -ForegroundColor Green }
function Warn($m) { Write-Host $m -ForegroundColor Yellow }
function Die($m)  { Write-Host ""; Write-Host $m -ForegroundColor Red; exit 1 }

function Test-AppFolder($path) {
    if (-not $path) { return $false }
    try { $path = (Resolve-Path -LiteralPath $path -ErrorAction Stop).Path } catch { return $false }
    return (Test-Path (Join-Path $path "api\main.py")) -and (Test-Path (Join-Path $path "run.ps1"))
}

Write-Host ""
Write-Host "Road Safety Lab - reference models" -ForegroundColor Cyan

# -- 1. the app (the same search as install-plugin.ps1: a sibling folder) --------------------------------
Step "[1/3] finding the NL2SQL app"
$parent = Split-Path $plugin -Parent
$candidates = New-Object System.Collections.Generic.List[string]
foreach ($c in @($AppPath, $env:NL2SQL_APP,
                 (Join-Path $parent "app"),
                 (Join-Path $parent "nl2sql-app-closed-core"),
                 (Join-Path $parent "nl2sql-app"))) {
    if ($c) { $candidates.Add($c) }
}
try {
    Get-ChildItem -LiteralPath $parent -Directory -ErrorAction Stop |
        Where-Object { $_.FullName -ne $plugin } |
        ForEach-Object { $candidates.Add($_.FullName) }
} catch { }
$app = $null
foreach ($c in $candidates) { if (Test-AppFolder $c) { $app = (Resolve-Path -LiteralPath $c).Path; break } }
if (-not $app) { Die "No NL2SQL app found next to this folder. Run install-plugin.bat first, or pass -AppPath C:\path\to\app" }
Good "  app: $app"

$venvPy = Join-Path $app ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPy)) { Die "The app has no .venv yet - run install-plugin.bat first (it creates it)." }
$probeOk = $false
try { & $venvPy -X utf8 -c "import nl2sql_roadsafety, xgboost" *> $null; $probeOk = ($LASTEXITCODE -eq 0) } catch { $probeOk = $false }
if (-not $probeOk) { Die "The plugin or xgboost is missing from the app's environment - run install-plugin.bat first (with internet for xgboost)." }

# -- 2. the database -----------------------------------------------------------------------------------
Step "[2/3] the database"
if (-not (Test-Path $DbPath) -and -not $NoPrompt) {
    Warn "  database not found at $DbPath"
    $typed = Read-Host "  Full path to your israel_accidents.duckdb (Enter to give up)"
    if ($typed) { $DbPath = $typed.Trim([char]34) }
}
if (-not (Test-Path $DbPath)) { Die "No database at $DbPath - re-run with -DbPath <path to israel_accidents.duckdb>" }
Good "  $DbPath (opened read-only)"

# -- 3. train -> validate -> deploy, in-process --------------------------------------------------------
Step "[3/3] training the two reference models (usually under a minute; nothing else needs to run)"
$pyArgs = @((Join-Path $plugin "tools\seed_models.py"), "--db", $DbPath)
if ($Force) { $pyArgs += "--force" }
& $venvPy -X utf8 @pyArgs
$code = $LASTEXITCODE
Write-Host ""
if ($code -eq 0) {
    Good "Both model families are deployed. In the app: the studio tab lists them; site_ranking, the excess map,"
    Good "severity_predict, what_if and the explain actions now answer. (No restart needed - models are read per call.)"
} else {
    Warn "Seeding did not finish cleanly (exit $code) - read the messages above; re-run after fixing the cause."
}
exit $code
