# ==============================================================
#  Survey System - PDF REPAIR SCRIPT (Windows)
#  Fixes the error:  {"detail":{"message":"Unexpected server error ..."}}
#  when clicking the PDF button in the archive.
#
#  WHY THIS HAPPENS:
#    Chromium (the browser that makes PDFs) was downloaded into the
#    Administrator user's profile folder. But the app service runs as
#    "SYSTEM", which uses a DIFFERENT profile folder -> browser not found
#    -> PDF fails, everything else keeps working.
#
#  WHAT THIS SCRIPT DOES (safe, can be run again anytime):
#    1) Installs Chromium into the GLOBAL folder  C:\playwright-browsers
#       (visible to SYSTEM, Administrator, every account)
#    2) Updates C:\survey-system\run-server.bat so the app can find it
#    3) Restarts the SurveySystem service
#    4) Makes a real PDF test and shows the result
#  Run: right-click PowerShell -> "Run as Administrator" -> run this file
# ==============================================================

$ErrorActionPreference = "Stop"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$APPDIR     = "C:\survey-system"
$BACKEND    = 3010
$BROWSERS   = "C:\playwright-browsers"

Write-Host "==============================================" -ForegroundColor Cyan
Write-Host " Survey System - PDF Repair" -ForegroundColor Cyan
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
$VPY = "$APPDIR\venv\Scripts\python.exe"
Write-Host ">> [1/5] Checks OK. Python: $VPY"

# ---------- 1) install Chromium into the GLOBAL folder ----------
Write-Host ">> [2/5] Installing Chromium into $BROWSERS (2-5 min, one time)..."
New-Item -ItemType Directory -Path $BROWSERS -Force | Out-Null
$env:PLAYWRIGHT_BROWSERS_PATH = $BROWSERS
Remove-Item Env:PLAYWRIGHT_DOWNLOAD_HOST -ErrorAction SilentlyContinue
& $VPY -m playwright install chromium
if ($LASTEXITCODE -ne 0) {
    Write-Host "   Trying mirror (npmmirror)..." -ForegroundColor Yellow
    $env:PLAYWRIGHT_DOWNLOAD_HOST = "https://cdn.npmmirror.com/binaries/playwright"
    & $VPY -m playwright install chromium
    if ($LASTEXITCODE -ne 0) { Write-Host "ERROR: Chromium download failed. Check internet connection." -ForegroundColor Red; Pause; exit 1 }
}
# make sure the SYSTEM account can use this folder
icacls $BROWSERS /grant "*S-1-5-18:(OI)(CI)F" /T | Out-Null
Write-Host "   Chromium installed in global folder." -ForegroundColor Green

# quick local launch test (inside this script's environment)
$env:SURVEY_DATABASE_URL = "sqlite:///C:/survey-system/data/survey.db"
& $VPY -c "from playwright.sync_api import sync_playwright; p = sync_playwright().start(); b = p.chromium.launch(args=['--no-sandbox']); b.close(); p.stop(); print('   CHROMIUM_LAUNCH_OK')"
if ($LASTEXITCODE -ne 0) { Write-Host "ERROR: Chromium launch test failed." -ForegroundColor Red; Pause; exit 1 }

# ---------- 2) update run-server.bat ----------
Write-Host ">> [3/5] Updating run-server.bat..."
$bat = @"
@echo off
cd /d $APPDIR
if not exist logs mkdir logs
set SURVEY_DATABASE_URL=sqlite:///C:/survey-system/data/survey.db
set SURVEY_SELF_URL=http://127.0.0.1:$BACKEND
set PLAYWRIGHT_BROWSERS_PATH=$BROWSERS
"$APPDIR\venv\Scripts\python.exe" -m uvicorn app.main:app --host 0.0.0.0 --port $BACKEND --log-level info >> "$APPDIR\logs\server.log" 2>&1
"@
$bat | Set-Content "$APPDIR\run-server.bat" -Encoding ASCII
# keep the scheduled task pointing at the same bat (in case it was deleted)
cmd /c 'schtasks /Create /F /TN "SurveySystem" /SC ONSTART /RU SYSTEM /TR "C:\survey-system\run-server.bat" >nul 2>&1'

# ---------- 3) restart service ----------
Write-Host ">> [4/5] Restarting the service..."
cmd /c 'schtasks /End /TN "SurveySystem" >nul 2>&1'
Start-Sleep -Seconds 3
cmd /c 'schtasks /Run /TN "SurveySystem" >nul 2>&1'
Write-Host "   Waiting for server to start..."
Start-Sleep -Seconds 20

# ---------- 4) end-to-end PDF test ----------
Write-Host ">> [5/5] Testing PDF generation (end to end)..."
$ok = $false
try {
    $r = Invoke-WebRequest "http://127.0.0.1:$BACKEND/healthz" -UseBasicParsing -TimeoutSec 10
    Write-Host "   Server is UP (healthz OK)."
} catch {
    Write-Host "   WARNING: server did not answer yet. Waiting 20 more seconds..." -ForegroundColor Yellow
    Start-Sleep -Seconds 20
}

$sid = (& $VPY -c "import sqlite3; con = sqlite3.connect(r'C:\survey-system\data\survey.db'); row = con.execute('select max(id) from surveys').fetchone(); print(row[0] if row and row[0] else 0)").ToString().Trim()
if ($sid -and "$sid" -ne "0") {
    try {
        $pdf = Invoke-WebRequest "http://127.0.0.1:$BACKEND/api/surveys/$sid/pdf" -UseBasicParsing -TimeoutSec 90
        $bytes = $pdf.Content
        if ($bytes.Length -gt 1000 -and $bytes[0] -eq 0x25 -and $bytes[1] -eq 0x50) {
            Write-Host "   PDF TEST PASSED - record $sid returned a real PDF ($([math]::Round($bytes.Length/1KB)) KB)." -ForegroundColor Green
            $ok = $true
        } else {
            Write-Host "   PDF test returned unexpected content." -ForegroundColor Yellow
        }
    } catch {
        Write-Host "   PDF HTTP test failed: $($_.Exception.Message)" -ForegroundColor Yellow
    }
} else {
    Write-Host "   No records in database yet - skipped HTTP PDF test (Chromium launch test already passed)." -ForegroundColor Yellow
    $ok = $true
}

Write-Host ""
if ($ok) {
    Write-Host "==============================================" -ForegroundColor Green
    Write-Host "  PDF REPAIR COMPLETE - try the PDF button again" -ForegroundColor Green
    Write-Host "  in the archive page (press F5 first)." -ForegroundColor Green
    Write-Host "==============================================" -ForegroundColor Green
} else {
    Write-Host "  PDF test did not pass. Show last errors in the log:" -ForegroundColor Yellow
    Write-Host "  ---------------------------------------------" -ForegroundColor Gray
    Get-Content "$APPDIR\logs\server.log" -Tail 30 -ErrorAction SilentlyContinue
    Write-Host "  ---------------------------------------------" -ForegroundColor Gray
    Write-Host "  Send the lines above to your support chat." -ForegroundColor Yellow
}
Write-Host ""
Pause
