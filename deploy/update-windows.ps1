# ==============================================================
#  Survey System - WINDOWS UPDATE SCRIPT  (v3 - foolproof)
#  Updates the app code on C:\survey-system.
#  WITHOUT touching: database (data\), logs, venv, run-server.bat
#
#  WHAT IS NEW IN v3 (why your last update did not apply):
#   - v2 silently downloaded from GitHub when the local zip was not
#     found. The GitHub copy is OLD, so the server kept running the
#     old code (healthz without "version", cut logo on login).
#   - v3 NEVER downloads from GitHub. It only uses the local zip.
#   - v3 looks for the zip in more places: next to this script,
#     Downloads, Desktop, Documents, C:\survey-system, any user's
#     Downloads folder, or the path you pass with -ZipPath.
#   - v3 checks the version INSIDE the zip before installing
#     (an old zip is rejected instead of silently reverting).
#   - v3 asks /healthz after the restart and shows the REAL running
#     version, so you can see with your own eyes that it worked.
#
#  HOW TO USE:
#   1) put the new survey-system.zip anywhere (Desktop is fine)
#   2) right-click PowerShell -> Run as Administrator
#   3) powershell -ExecutionPolicy Bypass -File .\update-windows.ps1
#      (or:  .\update-windows.ps1 -ZipPath "C:\path\survey-system.zip")
# ==============================================================

param([string]$ZipPath = "")

$ErrorActionPreference = "Stop"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$APPDIR  = "C:\survey-system"
$BACKEND = 3010

Write-Host "==============================================" -ForegroundColor Cyan
Write-Host " Survey System - Update from LOCAL ZIP (v3)"   -ForegroundColor Cyan
Write-Host "==============================================" -ForegroundColor Cyan

function Stop-WithError($msg) {
    Write-Host ""
    Write-Host "ERROR: $msg" -ForegroundColor Red
    Write-Host ""
    Pause
    exit 1
}

# ---------- 0) checks ----------
$wi = [Security.Principal.WindowsIdentity]::GetCurrent()
$wp = New-Object Security.Principal.WindowsPrincipal($wi)
if (-not $wp.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Stop-WithError "right-click PowerShell and choose 'Run as Administrator', then run this script again."
}
if (-not (Test-Path "$APPDIR\venv\Scripts\python.exe")) {
    Stop-WithError "$APPDIR\venv not found. Run install-windows.ps1 first."
}

# ---------- 1) find the NEW zip on disk (no GitHub download!) ----------
$candidates = New-Object System.Collections.Generic.List[string]
if ($ZipPath -ne "") { $candidates.Add($ZipPath) }
$candidates.Add((Join-Path $PSScriptRoot "survey-system.zip"))
$candidates.Add("$HOME\Downloads\survey-system.zip")
$candidates.Add("$HOME\Desktop\survey-system.zip")
$candidates.Add("$HOME\Documents\survey-system.zip")
$candidates.Add("C:\survey-system\survey-system.zip")
$candidates.Add((Join-Path (Get-Location).Path "survey-system.zip"))

$LOCALZIP = $null
foreach ($c in $candidates) {
    if ($c -and (Test-Path $c)) { $LOCALZIP = $c; break }
}
if (-not $LOCALZIP) {
    try {
        $found = Get-ChildItem "C:\Users\*\Downloads\survey-system.zip" -Force -ErrorAction SilentlyContinue |
                 Sort-Object LastWriteTime -Descending | Select-Object -First 1
        if ($found) { $LOCALZIP = $found.FullName }
    } catch { }
}
if (-not $LOCALZIP) {
    Write-Host ""
    Write-Host "survey-system.zip was NOT FOUND on this computer." -ForegroundColor Red
    Write-Host ""
    Write-Host "Copy the new survey-system.zip (from the chat) to ONE of these folders:" -ForegroundColor Yellow
    Write-Host "  - Desktop" -ForegroundColor Yellow
    Write-Host "  - Downloads" -ForegroundColor Yellow
    Write-Host "  - C:\survey-system" -ForegroundColor Yellow
    Write-Host "then run this script again."
    Write-Host ""
    Write-Host "This script does NOT download from GitHub anymore, because the" -ForegroundColor Yellow
    Write-Host "GitHub copy is OLD and would silently undo your update." -ForegroundColor Yellow
    Pause
    exit 1
}
$zipItem = Get-Item $LOCALZIP
Write-Host ""
Write-Host (" zip found : " + $LOCALZIP) -ForegroundColor Green
Write-Host (" zip date  : " + $zipItem.LastWriteTime) -ForegroundColor Green

# ---------- 2) stop service ----------
Write-Host ">> [1/5] Stopping the service..."
cmd /c 'schtasks /End /TN "SurveySystem" >nul 2>&1'
Start-Sleep -Seconds 3

# ---------- 3) backup ----------
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$backup = "C:\survey-backup-$stamp"
Write-Host ">> [2/5] Backing up current app to $backup ..."
New-Item -ItemType Directory -Path $backup -Force | Out-Null
Copy-Item "$APPDIR\app" "$backup\app" -Recurse -Force
if (Test-Path "$APPDIR\scripts") { Copy-Item "$APPDIR\scripts" "$backup\scripts" -Recurse -Force }

# ---------- 4) extract, verify version, copy ----------
Write-Host ">> [3/5] Preparing the new code..."
$zip = "$env:TEMP\survey-update.zip"
$ex  = "$env:TEMP\ss_update"
Copy-Item $LOCALZIP $zip -Force
if (Test-Path $ex) { Remove-Item $ex -Recurse -Force }
Expand-Archive $zip $ex -Force

# detect layout: files at zip root, or inside one wrapper folder
if (Test-Path "$ex\app") {
    $src = $ex
} else {
    $cand = Get-ChildItem $ex -Directory | Select-Object -First 1
    if ($cand -and (Test-Path (Join-Path $cand.FullName "app"))) {
        $src = $cand.FullName
    } else {
        Stop-WithError "could not find 'app' folder inside the zip. Send this screen to the developer."
    }
}

# version guard: an OLD zip is rejected BEFORE it can revert the server
$zipVersion = ""
$zipCfg = Join-Path $src "app\config.py"
if (Test-Path $zipCfg) {
    $cfgText = Get-Content $zipCfg -Raw
    if ($cfgText -match 'APP_VERSION\s*=\s*"([^"]+)"') { $zipVersion = $Matches[1] }
}
if (-not $zipVersion) {
    Write-Host ""
    Write-Host "This zip is OLD (it has no version marker)." -ForegroundColor Red
    Write-Host "The server was NOT changed. Get the NEW survey-system.zip" -ForegroundColor Yellow
    Write-Host "from the chat and run this script again." -ForegroundColor Yellow
    Pause
    exit 1
}
Write-Host (" zip version: " + $zipVersion) -ForegroundColor Green

Write-Host ">> [4/5] Copying new files..."
robocopy "$src\app" "$APPDIR\app" /MIR /NFL /NDL /NJH /NJS | Out-Null
if ($LASTEXITCODE -ge 8) { Stop-WithError "robocopy failed on app (code $LASTEXITCODE)" }
if (Test-Path "$src\scripts") { robocopy "$src\scripts" "$APPDIR\scripts" /MIR /NFL /NDL /NJH /NJS | Out-Null }
if (Test-Path "$src\deploy")  { robocopy "$src\deploy"  "$APPDIR\deploy"  /MIR /NFL /NDL /NJH /NJS | Out-Null }
Copy-Item "$src\requirements.txt" "$APPDIR\requirements.txt" -Force
if (Test-Path "$src\README.md") { Copy-Item "$src\README.md" "$APPDIR\README.md" -Force }
Remove-Item $ex -Recurse -Force

# ---------- 5) restart + REAL version check ----------
Write-Host ">> [5/5] Restarting the service..."
cmd /c 'schtasks /Run /TN "SurveySystem" >nul 2>&1'
Write-Host "   Waiting for server to start..."
Start-Sleep -Seconds 20

$ok = $false
foreach ($try in 1..2) {
    try {
        $r = Invoke-WebRequest "http://127.0.0.1:$BACKEND/healthz" -UseBasicParsing -TimeoutSec 15
        $j = $r.Content | ConvertFrom-Json
        if ($j.version) {
            Write-Host ""
            Write-Host ("   Server is UP - running version: " + $j.version) -ForegroundColor Green
            if ($j.version -eq $zipVersion) {
                Write-Host "   SUCCESS: the new version is really running now." -ForegroundColor Green
            } else {
                Write-Host ("   WARNING: expected " + $zipVersion + " but server says " + $j.version) -ForegroundColor Yellow
            }
        } else {
            Write-Host ""
            Write-Host "   Server answered WITHOUT a version -> OLD code is still running!" -ForegroundColor Red
            Write-Host "   Send this screen to the developer." -ForegroundColor Red
        }
        $ok = $true
        break
    } catch {
        if ($try -eq 1) {
            Write-Host "   Server did not answer yet - waiting 20 more seconds..." -ForegroundColor Yellow
            Start-Sleep -Seconds 20
        }
    }
}
if (-not $ok) {
    Write-Host ""
    Write-Host "   ERROR: server did not start. Last log lines:" -ForegroundColor Red
    Get-Content "$APPDIR\logs\server.log" -Tail 30 -ErrorAction SilentlyContinue
    Write-Host ""
    Write-Host ("   To rollback: copy " + $backup + "\app over " + $APPDIR + "\app and restart SurveySystem.") -ForegroundColor Yellow
} else {
    Write-Host ""
    Write-Host "  NOW OPEN THE APP and press Ctrl+F5 on the login page:" -ForegroundColor Yellow
    Write-Host ("    http://127.0.0.1:" + $BACKEND + "/app/login") -ForegroundColor Yellow
    Write-Host "  The footer of the login page shows the version number." -ForegroundColor Yellow
    Write-Host "  If you forgot a password, in PowerShell:" -ForegroundColor Gray
    Write-Host "    cd C:\survey-system" -ForegroundColor Gray
    Write-Host "    venv\Scripts\python scripts\reset_password.py --list" -ForegroundColor Gray
    Write-Host "    venv\Scripts\python scripts\reset_password.py admin" -ForegroundColor Gray
    Write-Host "  (your old survey records are all safe)" -ForegroundColor Gray
}
Write-Host ""
Pause
