# ==============================================================
#  Survey System - WINDOWS UPDATE SCRIPT
#  Updates the app code on C:\survey-system from GitHub (main branch)
#  WITHOUT touching: database (data\), logs, venv, run-server.bat
#
#  What it does:
#    1) Stops the SurveySystem task
#    2) Backs up the current app folder (one click rollback possible)
#    3) Downloads the latest code from GitHub
#    4) Copies app/ scripts/ deploy/ requirements.txt README.md
#    5) Restarts the service and checks health
#
#  Run: right-click PowerShell -> Run as Administrator ->
#       powershell -ExecutionPolicy Bypass -File .\update-windows.ps1
# ==============================================================

$ErrorActionPreference = "Stop"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$APPDIR   = "C:\survey-system"
$REPO     = "https://github.com/samaneh-IT-rose/survey-system/archive/refs/heads/main.zip"
$BACKEND  = 3010

Write-Host "==============================================" -ForegroundColor Cyan
Write-Host " Survey System - Update from GitHub" -ForegroundColor Cyan
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

# ---------- 3) download ----------
Write-Host ">> [3/5] Downloading latest code from GitHub..."
$zip = "$env:TEMP\survey-update.zip"
$ex  = "$env:TEMP\ss_update"
Invoke-WebRequest $REPO -OutFile $zip -UseBasicParsing
if (Test-Path $ex) { Remove-Item $ex -Recurse -Force }
Expand-Archive $zip $ex -Force
$src = (Get-ChildItem $ex | Select-Object -First 1).FullName

# ---------- 4) copy new code (database and settings are NOT touched) ----------
Write-Host ">> [4/5] Copying new files..."
Copy-Item "$src\app" "$APPDIR\app" -Recurse -Force
if (Test-Path "$src\scripts") { Copy-Item "$src\scripts" "$APPDIR\scripts" -Recurse -Force }
if (Test-Path "$src\deploy")  { Copy-Item "$src\deploy"  "$APPDIR\deploy"  -Recurse -Force }
Copy-Item "$src\requirements.txt" "$APPDIR\requirements.txt" -Force
Copy-Item "$src\README.md" "$APPDIR\README.md" -Force
Remove-Item $ex -Recurse -Force
Remove-Item $zip -Force

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
    Write-Host "  (if you already used the app with users before, your old admin password still works)" -ForegroundColor Gray
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
