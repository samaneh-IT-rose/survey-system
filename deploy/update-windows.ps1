# ==============================================================
#  Survey System - WINDOWS UPDATE SCRIPT  (v2 - robust zip layout)
#  Updates the app code on C:\survey-system.
#  WITHOUT touching: database (data\), logs, venv, run-server.bat
#
#  Two ways to get the new code:
#    A) LOCAL ZIP (recommended, works offline):
#       put the new "survey-system.zip" in the SAME folder as this script
#       (or in your Downloads folder), then run the script.
#    B) GITHUB (fallback): if no local zip is found, it downloads main branch.
#
#  Works with BOTH zip layouts:
#    - files at zip root (app\, scripts\, ...)
#    - one wrapper folder (survey-system\app\, ...)
#  Uses robocopy /MIR so old unused files are removed and the app
#  folder stays exactly like the new version.
#
#  Run: right-click PowerShell -> Run as Administrator ->
#       powershell -ExecutionPolicy Bypass -File .\update-windows.ps1
# ==============================================================

$ErrorActionPreference = "Stop"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$APPDIR   = "C:\survey-system"
$REPO     = "https://github.com/samaneh-IT-rose/survey-system/archive/refs/heads/main.zip"
$BACKEND  = 3010

# مسیرهای احتمالی zip محلی: کنار همین اسکریپت یا Downloads
$LOCALZIP = Join-Path $PSScriptRoot "survey-system.zip"
if (-not (Test-Path $LOCALZIP)) { $LOCALZIP = "$HOME\Downloads\survey-system.zip" }
$USELOCAL = Test-Path $LOCALZIP

Write-Host "==============================================" -ForegroundColor Cyan
if ($USELOCAL) {
    Write-Host " Survey System - Update from LOCAL ZIP" -ForegroundColor Cyan
    Write-Host " zip: $LOCALZIP" -ForegroundColor Cyan
} else {
    Write-Host " Survey System - Update from GitHub" -ForegroundColor Cyan
}
Write-Host "==============================================" -ForegroundColor Cyan

# ---------- 0) checks ----------
$wi = [Security.Principal.WindowsIdentity]::GetCurrent()
$wp = New-Object Security.Principal.WindowsPrincipal($wi)
if (-not $wp.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "ERROR: right-click PowerShell and choose 'Run as Administrator', then run this script again." -ForegroundColor Red
    Pause; exit 1
}
if (-not (Test-Path "$APPDIR\venv\Scripts\python.exe")) {
    Write-Host "ERROR: $APPDIR\venv not found. Run install-windows.ps1 first." -ForegroundColor Red
    Pause; exit 1
}

# ---------- 1) stop service ----------
Write-Host ">> [1/5] Stopping the service..."
cmd /c 'schtasks /End /TN "SurveySystem" >nul 2>&1'
Start-Sleep -Seconds 3

# ---------- 2) backup ----------
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$backup = "C:\survey-backup-$stamp"
Write-Host ">> [2/5] Backing up current app to $backup ..."
New-Item -ItemType Directory -Path $backup -Force | Out-Null
Copy-Item "$APPDIR\app" "$backup\app" -Recurse -Force
if (Test-Path "$APPDIR\scripts") { Copy-Item "$APPDIR\scripts" "$backup\scripts" -Recurse -Force }

# ---------- 3) source code (local zip or GitHub) ----------
Write-Host ">> [3/5] Preparing the new code..."
$zip = "$env:TEMP\survey-update.zip"
$ex  = "$env:TEMP\ss_update"
if ($USELOCAL) {
    Write-Host "   Using the local zip found on disk."
    Copy-Item $LOCALZIP $zip -Force
} else {
    Write-Host "   No local zip found - downloading from GitHub..."
    Invoke-WebRequest $REPO -OutFile $zip -UseBasicParsing
}
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
        Write-Host "ERROR: could not find 'app' folder inside the zip. Send this message to the developer." -ForegroundColor Red
        Pause; exit 1
    }
}

# ---------- 4) copy new code (database and settings are NOT touched) ----------
Write-Host ">> [4/5] Copying new files..."
robocopy "$src\app" "$APPDIR\app" /MIR /NFL /NDL /NJH /NJS | Out-Null
if ($LASTEXITCODE -ge 8) { Write-Host "ERROR: robocopy failed on app (code $LASTEXITCODE)" -ForegroundColor Red; Pause; exit 1 }
if (Test-Path "$src\scripts") { robocopy "$src\scripts" "$APPDIR\scripts" /MIR /NFL /NDL /NJH /NJS | Out-Null }
if (Test-Path "$src\deploy")  { robocopy "$src\deploy"  "$APPDIR\deploy"  /MIR /NFL /NDL /NJH /NJS | Out-Null }
Copy-Item "$src\requirements.txt" "$APPDIR\requirements.txt" -Force
Copy-Item "$src\README.md" "$APPDIR\README.md" -Force
Remove-Item $ex -Recurse -Force
if (-not $USELOCAL) { Remove-Item $zip -Force }

# sanity check: a file that only exists in the NEW version
if (Test-Path "$APPDIR\app\auth.py") {
    Write-Host "   New code verified (auth.py found)." -ForegroundColor Green
} else {
    Write-Host "WARNING: app\auth.py not found - the zip may be old. Tell the developer." -ForegroundColor Yellow
}

# ---------- 5) restart + health check ----------
Write-Host ">> [5/5] Restarting the service..."
cmd /c 'schtasks /Run /TN "SurveySystem" >nul 2>&1'
Write-Host "   Waiting for server to start..."
Start-Sleep -Seconds 20
try {
    $r = Invoke-WebRequest "http://127.0.0.1:$BACKEND/healthz" -UseBasicParsing -TimeoutSec 15
    Write-Host "   Server is UP - update complete." -ForegroundColor Green
    Write-Host ""
    Write-Host "  IMPORTANT: now open the app and log in:" -ForegroundColor Yellow
    Write-Host "    username: admin" -ForegroundColor Yellow
    Write-Host "    password: admin123  (you will be asked to change it)" -ForegroundColor Yellow
    Write-Host "  (your old survey records are all safe)" -ForegroundColor Gray
} catch {
    Write-Host "   WARNING: server did not answer yet. Waiting 20 more seconds..." -ForegroundColor Yellow
    Start-Sleep -Seconds 20
    try {
        $r = Invoke-WebRequest "http://127.0.0.1:$BACKEND/healthz" -UseBasicParsing -TimeoutSec 15
        Write-Host "   Server is UP - update complete." -ForegroundColor Green
    } catch {
        Write-Host "   ERROR: server did not start. Show last log lines:" -ForegroundColor Red
        Get-Content "$APPDIR\logs\server.log" -Tail 30 -ErrorAction SilentlyContinue
        Write-Host "  To rollback: copy $backup\app over $APPDIR\app and restart SurveySystem." -ForegroundColor Yellow
    }
}
Write-Host ""
Pause
