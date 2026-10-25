# install-plugin.ps1 - install the Road Safety Lab plugin into a sibling NL2SQL app clone.
#
# Double-click `install-plugin.bat` instead of running this by hand; the .bat only bypasses the
# execution policy for this one file and keeps the window open.
#
# What it does, in order: find the app folder (a sibling by default), make sure that app has a working
# Python environment (offering to run the app's own install.ps1 if it does not), install the plugin from
# the committed wheel in release\ (no build step, no internet needed), add the optional [ml] tier
# (xgboost - the studio/model features) when the app's Python can take it, verify the install through the
# engine's own discovery, and tell you what to do next.
#
#   .\install-plugin.ps1                        # find the app automatically
#   .\install-plugin.ps1 -AppPath C:\path\to\app
#   .\install-plugin.ps1 -NoMl                  # skip xgboost (analytical tier only)
#   .\install-plugin.ps1 -FromSource            # install from the source tree instead of the wheel (dev)
#   .\install-plugin.ps1 -Reinstall             # replace an installed copy of the SAME version (a repair)
#   .\install-plugin.ps1 -Mcp                   # also the chat channel: the MCP server + Claude Desktop registration
#   .\install-plugin.ps1 -Mcp -DbPath C:\data\israel_accidents\israel_accidents.duckdb
#   .\install-plugin.ps1 -Mcp -NoClaudeCode   # register with Claude Desktop only (skip `claude mcp add`)
[CmdletBinding()]
param(
    [string]$AppPath = "",
    [switch]$NoMl,
    [switch]$FromSource,
    [switch]$Reinstall,     # replace the installed copy even when it is already the wheel's version (repair)
    [switch]$NoPrompt,
    [switch]$CheckOnly,     # find the app + report what is installed, change nothing
    [switch]$Mcp,           # M1: install the [mcp] tier and register the server with Claude Desktop
    [string]$DbPath = "C:\data\israel_accidents\israel_accidents.duckdb",   # the working copy the chat answers over
    [string]$McpConfigPath = "",    # override the Claude Desktop config file (tests); default: detected (MSIX-aware)
    [switch]$NoClaudeCode           # -Mcp: skip the Claude Code registration (claude mcp add); Desktop only
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
Write-Host "Road Safety Lab - plugin installer" -ForegroundColor Cyan
Write-Host "  plugin: $plugin"

# -- 1. the app ----------------------------------------------------------------------------------------
Step "[1/5] finding the NL2SQL app"
$parent = Split-Path $plugin -Parent
$candidates = New-Object System.Collections.Generic.List[string]
foreach ($c in @($AppPath, $env:NL2SQL_APP,
                 (Join-Path $parent "app"),
                 (Join-Path $parent "nl2sql-app-closed-core"),
                 (Join-Path $parent "nl2sql-app"))) {
    if ($c) { $candidates.Add($c) }
}
# any other sibling folder that looks like the app (an unpacked clone under any name)
try {
    Get-ChildItem -LiteralPath $parent -Directory -ErrorAction Stop |
        Where-Object { $_.FullName -ne $plugin } |
        ForEach-Object { $candidates.Add($_.FullName) }
} catch { }

$app = $null
foreach ($c in $candidates) { if (Test-AppFolder $c) { $app = (Resolve-Path -LiteralPath $c).Path; break } }

if (-not $app -and -not $NoPrompt) {
    Warn "  Could not find the app next to this folder."
    Info  "  It is the clone of github.com/Amir-kh-z/nl2sql-app-closed-core (the folder holding run.ps1)."
    $typed = Read-Host "  Full path to the app folder (Enter to give up)"
    if ($typed -and (Test-AppFolder $typed)) { $app = (Resolve-Path -LiteralPath $typed).Path }
}
if (-not $app) {
    Die @"
No NL2SQL app found.
Put this plugin folder NEXT TO the app clone, for example:

    C:\nl2sql\app\                      <- the clone of nl2sql-app-closed-core (has run.ps1)
    C:\nl2sql\nl2sql-roadsafety-lab\    <- this folder

then double-click install-plugin.bat again, or run:
    .\install-plugin.ps1 -AppPath C:\nl2sql\app
"@
}
Good "  app: $app"

# -- 2. the app's python -------------------------------------------------------------------------------
Step "[2/5] the app's Python environment"
$venvPy = Join-Path $app ".venv\Scripts\python.exe"
$appInstaller = Join-Path $app "install.ps1"
if (-not (Test-Path $venvPy) -and -not $CheckOnly) {
    if (-not (Test-Path $appInstaller)) {
        Die "The app has no .venv and no install.ps1 - is '$app' really the app clone?"
    }
    Warn "  The app has no .venv yet (it is created by the app's own installer)."
    $answer = "y"
    if (-not $NoPrompt) { $answer = Read-Host "  Run the app's install.ps1 now? This can take a few minutes [Y/n]" }
    if ($answer -eq "" -or $answer -match '^[yY]') {
        Push-Location $app
        try { & powershell -NoProfile -ExecutionPolicy Bypass -File $appInstaller }
        finally { Pop-Location }
    }
}
if (-not (Test-Path $venvPy)) {
    if ($CheckOnly) { Warn "  no .venv yet - the app's install.ps1 has not been run"; Write-Host ""; exit 0 }
    Die @"
The app still has no .venv\Scripts\python.exe.
Install the app first (open a terminal in the app folder and run .\install.ps1), then re-run this installer.
"@
}

$pyVersion = (& $venvPy -c "import sys; print('%d.%d' % sys.version_info[:2])").Trim()
Good "  python $pyVersion  ($venvPy)"

# pip is present in a normal venv, but a `uv sync` environment can be pip-less: fall back to `uv pip`.
$hasPip = $true
try { & $venvPy -m pip --version *> $null; $hasPip = ($LASTEXITCODE -eq 0) } catch { $hasPip = $false }
$uv = Get-Command uv -ErrorAction SilentlyContinue
if (-not $hasPip -and -not $uv) {
    Die "The app's Python has no pip and uv is not installed. Re-run the app's install.ps1, then try again."
}
function Invoke-Pip([string[]]$pipArgs) {
    # Out-Host, not the pipeline: without it pip's own output becomes part of this function's return value
    # and the caller compares an ARRAY to 0 - a successful install then reads as a failure.
    if ($hasPip) { & $venvPy -m pip @pipArgs | Out-Host }
    else { & uv pip @pipArgs --python $venvPy | Out-Host }
    return $LASTEXITCODE
}
if (-not $hasPip) { Info "  (no pip in that environment - using 'uv pip')" }

# -- 3. install ----------------------------------------------------------------------------------------
if ($CheckOnly) {
    Step "[3/5] -CheckOnly: nothing will be installed"
    $probe = "import json;from importlib.metadata import version" +
             ";print(json.dumps({'installed': version('nl2sql-roadsafety-lab')}))"
    try { $r = & $venvPy -X utf8 -c $probe; Good "  currently installed: $r" }
    catch { Warn "  the plugin is not installed in this app yet" }
    Write-Host ""
    exit 0
}
Step "[3/5] installing the plugin"
$target = $null
if (-not $FromSource) {
    # Sort by the parsed VERSION, never by name: "0.9.0" sorts after "0.10.0" as text, so a name sort would
    # happily install the older wheel the first time two of them sit side by side.
    $wheels = @(Get-ChildItem -LiteralPath (Join-Path $plugin "release") -Filter "*.whl" -ErrorAction SilentlyContinue)
    $wheel = $wheels | Sort-Object @{ Expression = {
        $part = ($_.BaseName -split "-")[1]
        try { [version]$part } catch { [version]"0.0.0" } } } -Descending | Select-Object -First 1
    if ($wheel) {
        $target = $wheel.FullName
        Info "  from the packaged wheel: $($wheel.Name)"
        if ($wheels.Count -gt 1) { Info "  ($($wheels.Count) wheels in release\ - taking the newest version)" }
    }
}
if (-not $target) {
    $target = $plugin
    Info "  from the source tree (needs internet for the build backend)"
}

# The pre-rename generation of THIS plugin was distributed as `nl2sql-accidents` (until 2026-09-08). Left in
# place it would sit beside the new package as a second module + a second page. The course owner's own plugin
# carries the SAME distribution name, so never uninstall by name alone: fingerprint the installed summary
# (ours says "correct-by-construction"; his says "KPIs, hotspots, weather risk") and touch only ours.
$oldSummary = ""
try { $oldSummary = (& $venvPy -m pip show nl2sql-accidents 2>$null | Select-String -Pattern "^Summary:" | ForEach-Object { $_.Line }) } catch { }
if ($oldSummary -and $oldSummary -match "correct-by-construction") {
    Warn "  an older generation of this plugin is installed under its previous name (nl2sql-accidents)."
    $answer = "y"
    if (-not $NoPrompt) { $answer = Read-Host "  Remove it so the app shows one Road Safety Lab, not two? [Y/n]" }
    if ($answer -eq "" -or $answer -match '^[yY]') {
        $code = Invoke-Pip @("uninstall", "-y", "nl2sql-accidents")
        if ($code -eq 0) { Good "  previous generation removed" } else { Warn "  could not remove it - the app may list two road-safety modules" }
    }
} elseif ($oldSummary) {
    Info "  (a different package named nl2sql-accidents is installed - not this plugin; left untouched)"
}

# Same version already installed? Then do not touch it (install-chat.bat and every re-run land here): a pip
# reinstall replaces files that a running roadsafety-mcp.exe or the app may hold open - WinError 32 and a
# half-removed package (bit the kit's acceptance 2026-10-25). -Reinstall forces the replacement (a repair).
$prevEap = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$installedVersion = ""
try {
    $probeOut = & $venvPy -X utf8 -c "from importlib.metadata import version; print(version('nl2sql-roadsafety-lab'))" 2>&1
    $first = [string](@($probeOut) | Select-Object -First 1)
    if ($first -match '^\d+\.\d+') { $installedVersion = $first.Trim() }
} catch { $installedVersion = "" }
finally { $ErrorActionPreference = $prevEap }
$wheelVersion = if ($wheel) { ($wheel.BaseName -split "-")[1] } else { "" }
$skipInstall = $false
if ($wheel -and -not $Reinstall -and $installedVersion -and ($installedVersion -eq $wheelVersion)) {
    Info "  already installed: $installedVersion is the packaged wheel's version - left as is (-Reinstall replaces it)"
    $skipInstall = $true
}
if (-not $skipInstall) {
    # Who holds this environment's files? The app (uvicorn) must be stopped by the person; a chat session's
    # roadsafety-mcp server can be stopped here (the chat reconnects on its next session).
    $appLower = $app.ToLower()
    $holders = @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
                 Where-Object { $_.CommandLine -and $_.CommandLine.ToLower().Contains($appLower + "\.venv\") -and $_.ProcessId -ne $PID })
    $mcpHolders = @($holders | Where-Object { $_.CommandLine -match "roadsafety-mcp" })
    $otherHolders = @($holders | Where-Object { $_.CommandLine -notmatch "roadsafety-mcp" })
    if ($otherHolders.Count -gt 0) {
        $otherHolders | ForEach-Object { Warn ("  running from this environment: " + $_.CommandLine.Substring(0, [Math]::Min(160, $_.CommandLine.Length))) }
        Die "The app (or another program) is running from this environment and holds the plugin's files. Stop it (Ctrl+C in its window) and re-run."
    }
    if ($mcpHolders.Count -gt 0) {
        Warn "  a chat session is holding the plugin's server (roadsafety-mcp, $($mcpHolders.Count) process(es)) - pip cannot replace files in use."
        $answer = "y"
        if (-not $NoPrompt) { $answer = Read-Host "  Stop them now? The chat reconnects on its next session [Y/n]" }
        if ($answer -eq "" -or $answer -match '^[yY]') {
            foreach ($h in $mcpHolders) { Stop-Process -Id $h.ProcessId -Force -ErrorAction SilentlyContinue }
            Start-Sleep -Seconds 2
            Good "  stopped"
        } else {
            Die "Cannot replace files in use. Close the chat sessions that use roadsafety (Claude Code / Claude Desktop) and re-run."
        }
    }
    $code = Invoke-Pip @("install", "--upgrade", "--force-reinstall", "--no-deps", $target)
    if ($code -ne 0) { Die "The plugin did not install - see the messages above. If an earlier install was interrupted, re-run with -Reinstall." }
    Good "  plugin installed"
}

# the [ml] tier: xgboost powers the studio (train/validate/deploy) and the map's model colouring.
# Everything else works without it, so a failure here is a warning, never a failed install.
$mlOk = $false
if ($NoMl) {
    Info "  skipping the ml tier (-NoMl): the analytical tier works, studio actions will ask for xgboost"
} elseif ([version]$pyVersion -lt [version]"3.12") {
    Warn "  python $pyVersion cannot install xgboost (needs 3.12+): installing the analytical tier only"
} else {
    Info "  adding the ml tier (xgboost) - this one needs internet ..."
    $code = Invoke-Pip @("install", "--upgrade", "xgboost")
    if ($code -eq 0) { $mlOk = $true; Good "  ml tier ready" }
    else { Warn "  xgboost did not install - the analytical tier still works; re-run this installer later" }
}

# the [mcp] tier: the chat channel. The SDK comes from PyPI (internet, like xgboost); the server itself ships
# in the wheel (nl2sql_roadsafety.mcp + the roadsafety-mcp console script).
$mcpOk = $false
if ($Mcp) {
    Info "  adding the mcp tier (the Claude chat channel) - this one needs internet ..."
    $code = Invoke-Pip @("install", "--upgrade", "mcp>=2,<3")
    if ($code -eq 0) { $mcpOk = $true; Good "  mcp tier ready" }
    else { Warn "  the mcp SDK did not install - the app still works; re-run this installer with -Mcp later" }
}

# a reinstall replaces the whole package folder, taking any previously placed basemap with it: put it
# back from this clone's cache (gitignored, written by fetch-basemap.bat) so upgrades keep the street map
$cachedMap = Join-Path $plugin "web\basemap"
if (Test-Path $cachedMap) {
    $files = Get-ChildItem -LiteralPath $cachedMap -File -ErrorAction SilentlyContinue
    if ($files) {
        Info "  restoring the offline basemap from this clone's cache ..."
        & $venvPy -X utf8 (Join-Path $plugin "tools\fetch_basemap.py") --sync-only
    }
}

# -- 4. verify -----------------------------------------------------------------------------------------
Step "[4/5] checking the install"
$check = @'
import json, sys
from importlib.metadata import version
from pathlib import Path
out = {"version": version("nl2sql-roadsafety-lab")}
from nl2sql_engine.modules import discover, discover_pages
reg = discover()
mod = next((m for m in reg.modules if m.name == "roadsafety"), None)
out["actions"] = len(mod.actions) if mod else 0
out["problems"] = [f"{p.name}: {p.reason}" for p in reg.problems if "roadsafety" in str(p.name)]
pages, page_problems = discover_pages()
page = next((p for p in pages if p.name == "roadsafety"), None)
out["page"] = bool(page) and Path(page.path, "index.html").exists()
out["page_problems"] = [f"{p.name}: {p.reason}" for p in page_problems if "roadsafety" in str(p.name)]
try:
    import xgboost; out["xgboost"] = xgboost.__version__
except Exception: out["xgboost"] = None
try:
    import mcp; from nl2sql_roadsafety.mcp import server; out["mcp"] = version("mcp")
except Exception: out["mcp"] = None
print(json.dumps(out))
'@
$tmp = Join-Path $env:TEMP "nl2sql_roadsafety_check.py"
Set-Content -LiteralPath $tmp -Value $check -Encoding UTF8
$raw = & $venvPy -X utf8 $tmp
Remove-Item -LiteralPath $tmp -ErrorAction SilentlyContinue
if ($LASTEXITCODE -ne 0) { Die "The plugin is installed but the app cannot load it - see above. Re-run this installer with -Reinstall (an earlier install may have been interrupted)." }
$info = $raw | ConvertFrom-Json
if ($info.problems -or $info.page_problems) {
    Die ("The app reports a problem with the plugin: " + ($info.problems + $info.page_problems -join " | "))
}
if ($info.actions -lt 1 -or -not $info.page) { Die "The plugin loaded but its actions or page are missing." }
Good ("  nl2sql-roadsafety-lab " + $info.version + " - " + $info.actions + " actions + the page" +
      $(if ($info.xgboost) { " - xgboost " + $info.xgboost } else { " - no xgboost (analytical tier)" }) +
      $(if ($info.mcp) { " - mcp " + $info.mcp } else { "" }))

# -- 4b. the chat channel: register the server with Claude Desktop (and say how for Claude Code) ------------
# The config file is JSON that Claude Desktop rewrites while it runs (Ephraim's slide-19 stumble: a running
# Desktop overwrote his edit). So: refuse while Claude.exe runs, back the file up, merge one entry, ASCII only.
if ($Mcp -and $mcpOk) {
    Step "[4b] registering the chat channel"
    $exe = Join-Path $app ".venv\Scripts\roadsafety-mcp.exe"
    if (-not (Test-Path $exe)) { $exe = Join-Path $app ".venv\Scripts\roadsafety-mcp" }
    if (-not (Test-Path $DbPath) -and -not $NoPrompt) {
        Warn "  database not found at $DbPath"
        $typed = Read-Host "  Full path to your israel_accidents.duckdb (Enter to keep the path above)"
        if ($typed) { $DbPath = $typed.Trim('"') }
    }
    if (-not (Test-Path $DbPath)) {
        Warn "  database not found at $DbPath - the server will start and every tool will say so."
        Warn "  Re-run with -DbPath <path to israel_accidents.duckdb> once the working copy is in place."
    }
    # the JSON merge runs in Python (nl2sql_roadsafety.mcp.register): Windows PowerShell 5.1 has no hashtable
    # JSON round-trip, and the merge must keep every other server the person already registered
    # the path is DETECTED by the module: the Store (MSIX) build of Claude Desktop virtualizes %APPDATA% and reads
    # its config under %LOCALAPPDATA%\Packages\Claude_*\LocalCache\Roaming\Claude - a file written to the real
    # Roaming folder is silently ignored (bit us 2026-09-23). -McpConfigPath overrides (tests).
    # Which config file does Claude Desktop read? Three locations have been true at different times: the classic
    # installer's %APPDATA%\Claude; the Store (MSIX) build's virtualized %LOCALAPPDATA%\Packages\Claude_*\LocalCache\
    # Roaming\Claude (PITFALLS 2026-09-23); and the Store build's real data folder %LOCALAPPDATA%\Claude-Data\
    # claude_<package id>\, where Desktop 3.6556 keeps and REWRITES its config (PITFALLS 2026-10-25: the module's own
    # detection wrote the LocalCache file, which Desktop never read). So the installer does not guess: it writes the
    # same entry into EVERY location that exists on this machine - a file Desktop does not read is harmless - and
    # names each one.
    $cfgs = @()
    if ($McpConfigPath) {
        $cfgs = @($McpConfigPath)
    } else {
        $cfgs += (Join-Path $env:APPDATA "Claude\claude_desktop_config.json")
        if ($env:LOCALAPPDATA) {
            Get-ChildItem (Join-Path $env:LOCALAPPDATA "Packages") -Directory -Filter "Claude_*" -ErrorAction SilentlyContinue | ForEach-Object {
                $virtual = Join-Path $_.FullName "LocalCache\Roaming\Claude"
                if (Test-Path $virtual) { $cfgs += (Join-Path $virtual "claude_desktop_config.json") }
            }
            Get-ChildItem (Join-Path $env:LOCALAPPDATA "Claude-Data") -Directory -Filter "claude_*" -ErrorAction SilentlyContinue | ForEach-Object {
                $cfgs += (Join-Path $_.FullName "claude_desktop_config.json")
            }
        }
    }
    $cfg = $cfgs[0]
    # "Is Claude Desktop running?" - decided by PATH, not by name: Claude Code's CLI and its VS Code extension
    # binary are also called claude.exe (twelve of them on the instructor's machine during the kit's acceptance,
    # 2026-10-25), and a name match would refuse to write the config for every participant working from VS Code.
    # Desktop = any OTHER process named Claude (Store build under WindowsApps\Claude_*, classic installer under
    # %LOCALAPPDATA%\AnthropicClaude); a process whose path cannot be read stays on the safe side (counted).
    $desktopProcs = @(Get-Process -Name "Claude" -ErrorAction SilentlyContinue | Where-Object {
        $procPath = ""
        try { $procPath = [string]$_.Path } catch { $procPath = "" }
        -not ($procPath -match 'anthropic\.claude-code|\\\.vscode\\|\\\.local\\bin\\claude\.exe$|\\claude-code\\')
    })
    $desktopRunning = ($desktopProcs.Count -gt 0)
    if ($desktopRunning -and -not $McpConfigPath) {
        Warn "  Claude Desktop is running - it rewrites its config file while open, so nothing was written."
        $seen = @($desktopProcs | ForEach-Object { try { [string]$_.Path } catch { $_.ProcessName } } | Select-Object -Unique)
        Warn ("  (seen: " + ($seen -join "; ") + ")")
        Warn "  Quit Claude Desktop completely (tray icon -> Quit) and re-run this installer with -Mcp,"
        Warn ("  or paste this under ""mcpServers"" in " + ($cfgs -join " and ") + " :")
        & $venvPy -X utf8 -m nl2sql_roadsafety.mcp.register --config $cfg --exe $exe --db $DbPath --print-only | Out-Host
    } else {
        foreach ($c in $cfgs) {
            $report = & $venvPy -X utf8 -m nl2sql_roadsafety.mcp.register --config $c --exe $exe --db $DbPath
            if ($LASTEXITCODE -ne 0) { Die "  $c exists but is not valid JSON - fix or remove it, then re-run with -Mcp." }
            $r = $report | ConvertFrom-Json
            if ($r.backup) { Info "  backup: $($r.backup)" }
            Good "  Claude Desktop: 'roadsafety' registered in $c (servers: $($r.servers -join ', '))"
        }
        if ($cfgs.Count -gt 1) { Info "  ($($cfgs.Count) locations - Desktop reads one of them; the others are harmless)" }
        Info "  (restart Claude Desktop - the tool catalog is read when the app starts)"
    }
    # -- 4c. Claude Code (terminal / VS Code extension): the same server at USER scope, so every folder sees it.
    # `claude mcp add` refuses a name that already exists, so an existing entry is removed first (a re-run after
    # moving the app or the database re-points it). No `claude` on PATH, or -NoClaudeCode: print the one-liner.
    # Native commands: the preference is relaxed around them (the PS 5.1 quirk below) and the exit code decides.
    Write-Host ""
    $addLine = "claude mcp add --scope user roadsafety -e NL2SQL_ROADSAFETY_DB=""$DbPath"" -e PYTHONUTF8=1 -- ""$exe"""
    $claudeCli = Get-Command claude -ErrorAction SilentlyContinue
    if ($claudeCli -and -not $NoClaudeCode) {
        Step "[4c] registering the chat channel with Claude Code (user scope)"
        # Windows PowerShell 5.1: under $ErrorActionPreference = Stop, a native command's FIRST stderr line becomes a
        # terminating error as soon as the error stream is redirected - and `claude mcp remove` on a missing entry
        # writes exactly one (bit the kit's rehearsal 2026-10-25: the add never ran). So the preference is relaxed
        # around the two calls and the exit code is what decides.
        $added = $false
        $prevEap = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        try {
            $null = & claude mcp remove --scope user roadsafety 2>&1
            $out = & claude mcp add --scope user roadsafety -e "NL2SQL_ROADSAFETY_DB=$DbPath" -e "PYTHONUTF8=1" -- "$exe" 2>&1
            $added = ($LASTEXITCODE -eq 0)
            foreach ($line in @($out)) { Info ("    " + "$line") }
        } catch { $added = $false; Warn ("  " + $_.Exception.Message) }
        finally { $ErrorActionPreference = $prevEap }
        if ($added) {
            Good "  Claude Code: roadsafety registered (user scope) - open a NEW session; in VS Code reload the window."
            Info "  (check: claude mcp get roadsafety  /  inside a session: /mcp)"
        } else {
            Warn "  claude mcp add did not succeed - run it by hand, once, from any folder:"
            Info "    $addLine"
        }
    } else {
        if ($NoClaudeCode) { Info "  Claude Code registration skipped (-NoClaudeCode). To add it later, from any folder:" }
        else { Info "  Claude Code (terminal / VS Code) - no claude command on PATH here; once it is, from any folder:" }
        Info "    $addLine"
    }
}

# -- 5. next steps -------------------------------------------------------------------------------------
Step "[5/5] done"
$running = $false
try { $running = [bool](Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue) } catch { }
Write-Host ""
if ($running) {
    Warn "Something is already serving port 8000. The app reads plugins ONCE at startup:"
    Warn "stop it (Ctrl+C in its window) and start it again, or the new tab will not appear."
} else {
    Good "Start the app:  cd `"$app`"  ;  .\run.ps1        (then http://localhost:8000)"
}
Write-Host ""
# ASCII only in everything this script prints: the console code page mangles Hebrew, and an emoji above
# the BMP cannot even be built with [char] (it threw here on the first run).
Info "In the app: add your accidents database as a connection (Connections -> add the .duckdb file),"
Info "then open the road-safety item in the sidebar (the traffic-light icon). The map tab works out of the"
Info "box; for the offline street basemap run fetch-basemap.bat once (a ~170 MB download, optional)."
if (-not $mlOk -and -not $NoMl) {
    Info "Studio/model features need xgboost - re-run this installer when you have internet."
}
if (-not $Mcp) {
    Info "Chat channel (Claude Code / Claude Desktop): double-click install-chat.bat next (quit Claude Desktop first)."
    Info "Reference models (site_ranking, what_if, explain ...): double-click seed-models.bat once."
}
Write-Host ""
