# ==============================================================
#  Survey System - WINDOWS Server Installer (no Docker, no PostgreSQL)
#  Target: Windows Server with RDP (Administrator)
#  What it does:
#    1) Installs Python 3.12 silently (if missing)
#    2) Downloads the app from GitHub to C:\survey-system
#    3) Patches database.py for SQLite (safe, idempotent)
#    4) Creates venv + installs dependencies + Chromium (for PDF)
#    5) Creates SQLite database + base data (provinces, questions)
#    6) Backend (uvicorn) on port 3010  - auto-start on boot
#    7) Frontend port 8090 via built-in portproxy -> 3010
#    8) Opens firewall for 8090 and 3010
#  Result:
#    Frontend : http://<server-ip>:8090/app/
#    Backend  : http://<server-ip>:3010/app/
# ==============================================================

$ErrorActionPreference = "Stop"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$APP_IP   = "130.185.73.157"
$BACKEND  = 3010
$FRONTEND = 8090
$APPDIR   = "C:\survey-system"

Write-Host "==============================================" -ForegroundColor Cyan
Write-Host " Survey System - Windows Installer" -ForegroundColor Cyan
Write-Host "==============================================" -ForegroundColor Cyan

# ---------- 0) must run as Administrator ----------
$wi = [Security.Principal.WindowsIdentity]::GetCurrent()
$wp = New-Object Security.Principal.WindowsPrincipal($wi)
if (-not $wp.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "ERROR: right-click PowerShell and choose 'Run as Administrator', then run this script again." -ForegroundColor Red
    Pause; exit 1
}

# ---------- 1) Python ----------
function Get-PythonExe {
    $candidates = @(
        "C:\Program Files\Python312\python.exe",
        "C:\Program Files\Python311\python.exe",
        "C:\Program Files\Python310\python.exe"
    )
    foreach ($p in $candidates) { if (Test-Path $p) { return $p } }
    $c = Get-Command python -ErrorAction SilentlyContinue
    if ($c) { return $c.Source }
    return $null
}

$PY = Get-PythonExe
if (-not $PY) {
    Write-Host ">> [1/8] Installing Python 3.12 (silent, ~2 minutes)..."
    $inst = "$env:TEMP\python-3.12.8-amd64.exe"
    Invoke-WebRequest "https://www.python.org/ftp/python/3.12.8/python-3.12.8-amd64.exe" -OutFile $inst -UseBasicParsing
    Start-Process $inst -ArgumentList "/quiet", "InstallAllUsers=1", "PrependPath=1", "Include_test=0" -Wait
    $PY = "C:\Program Files\Python312\python.exe"
    if (-not (Test-Path $PY)) { Write-Host "ERROR: Python installation failed." -ForegroundColor Red; Pause; exit 1 }
} else {
    Write-Host ">> [1/8] Python already installed."
}
$env:Path = "C:\Program Files\Python312;C:\Program Files\Python312\Scripts;$env:Path"
Write-Host "   Python: $PY"
& $PY --version

# ---------- 2) Download app ----------
Write-Host ">> [2/8] Downloading app from GitHub..."
if (Test-Path "$APPDIR\app\main.py") {
    Write-Host "   C:\survey-system already exists - keeping current files."
} else {
    $zip = "$env:TEMP\survey-system-main.zip"
    Invoke-WebRequest "https://github.com/samaneh-IT-rose/survey-system/archive/refs/heads/main.zip" -OutFile $zip -UseBasicParsing
    $ex = "$env:TEMP\ss_extract"
    if (Test-Path $ex) { Remove-Item $ex -Recurse -Force }
    Expand-Archive $zip $ex -Force
    $src = (Get-ChildItem $ex | Select-Object -First 1).FullName
    New-Item -ItemType Directory -Path $APPDIR -Force | Out-Null
    Copy-Item "$src\*" $APPDIR -Recurse -Force
    Remove-Item $ex -Recurse -Force
    Write-Host "   Extracted to $APPDIR"
}

# ---------- 3) Patch database.py for SQLite ----------
Write-Host ">> [3/8] Preparing database engine (SQLite)..."
$patchPy = "$env:TEMP\_patch_db.py"
@'
import re, io
p = r"C:\survey-system\app\database.py"
s = io.open(p, encoding="utf-8").read()
if "check_same_thread" in s:
    print("   database.py already OK")
else:
    new = (
        'if DATABASE_URL.startswith("sqlite"):\n'
        '    engine = create_engine(\n'
        '        DATABASE_URL,\n'
        '        connect_args={"check_same_thread": False},\n'
        '        pool_pre_ping=True,\n'
        '    )\n'
        'else:\n'
        '    engine = create_engine(\n'
        '        DATABASE_URL,\n'
        '        pool_pre_ping=True,\n'
        '        pool_size=5,\n'
        '        max_overflow=10,\n'
        '    )'
    )
    s2 = re.sub(r"engine = create_engine\(.*?\n\)", new, s, flags=re.S)
    if s2 == s:
        print("   WARNING: could not patch database.py automatically")
    else:
        io.open(p, "w", encoding="utf-8").write(s2)
        print("   database.py patched for SQLite")
'@ | Set-Content $patchPy -Encoding ASCII
& $PY $patchPy
Remove-Item $patchPy -Force

# ---------- 4) venv + dependencies ----------
Write-Host ">> [4/8] Creating virtual environment and installing dependencies (5-10 min)..."
Push-Location $APPDIR
if (-not (Test-Path "venv\Scripts\python.exe")) { & $PY -m venv venv }
$VPY = "$APPDIR\venv\Scripts\python.exe"
$PIP_MIRRORS = @(
    "https://mirror-pypi.runflare.com/simple",
    "https://mirrors.aliyun.com/pypi/simple/",
    "https://pypi.org/simple"
)
$ok = $false
foreach ($m in $PIP_MIRRORS) {
    $hn = ([Uri]$m).Host
    Write-Host "   Trying mirror: $m ..."
    & $VPY -m pip install -r requirements.txt -i $m --trusted-host $hn --timeout 90 --retries 5
    if ($LASTEXITCODE -eq 0) { $ok = $true; break }
    Write-Host "   Mirror failed, trying next..." -ForegroundColor Yellow
}
if (-not $ok) { Write-Host "ERROR: pip install failed on all mirrors." -ForegroundColor Red; Pause; exit 1 }

# ---------- 5) Chromium for PDF ----------
# NOTE: Chromium MUST be in a global path (C:\playwright-browsers), NOT the
# current user's profile, because the service runs as SYSTEM and would
# otherwise not find the browser (PDF export would fail with error 500).
Write-Host ">> [5/8] Downloading Chromium for PDF export (2-5 min, one time)..."
New-Item -ItemType Directory -Path "C:\playwright-browsers" -Force | Out-Null
$env:PLAYWRIGHT_BROWSERS_PATH = "C:\playwright-browsers"
& $VPY -m playwright install chromium
if ($LASTEXITCODE -ne 0) {
    Write-Host "   Retrying Chromium with mirror (npmmirror)..." -ForegroundColor Yellow
    $env:PLAYWRIGHT_DOWNLOAD_HOST = "https://cdn.npmmirror.com/binaries/playwright"
    & $VPY -m playwright install chromium
    if ($LASTEXITCODE -ne 0) { Write-Host "ERROR: Chromium download failed." -ForegroundColor Red; Pause; exit 1 }
}
icacls "C:\playwright-browsers" /grant *S-1-5-18:(OI)(CI)F /T | Out-Null

# ---------- 6) Database + base data ----------
Write-Host ">> [6/8] Creating database and base data..."
New-Item -ItemType Directory -Path "$APPDIR\data" -Force | Out-Null
$env:SURVEY_DATABASE_URL = "sqlite:///C:/survey-system/data/survey.db"
$env:SURVEY_SELF_URL     = "http://127.0.0.1:$BACKEND"
& $VPY scripts\seed.py

# ---------- 7) run-server.bat ----------
Write-Host ">> [7/8] Creating startup script and auto-start task..."
$bat = @"
@echo off
cd /d $APPDIR
if not exist logs mkdir logs
set SURVEY_DATABASE_URL=sqlite:///C:/survey-system/data/survey.db
set SURVEY_SELF_URL=http://127.0.0.1:$BACKEND
set PLAYWRIGHT_BROWSERS_PATH=C:\playwright-browsers
"$APPDIR\venv\Scripts\python.exe" -m uvicorn app.main:app --host 0.0.0.0 --port $BACKEND --log-level info >> "$APPDIR\logs\server.log" 2>&1
"@
$bat | Set-Content "$APPDIR\run-server.bat" -Encoding ASCII

schtasks /Create /F /TN "SurveySystem" /SC ONSTART /RU SYSTEM /TR "$APPDIR\run-server.bat" | Out-Null
schtasks /Run /TN "SurveySystem" | Out-Null

# ---------- 8) Firewall + port forwarding 8090 -> 3010 ----------
Write-Host ">> [8/8] Opening firewall ports ($FRONTEND frontend, $BACKEND backend)..."
New-NetFirewallRule -DisplayName "Survey Web $FRONTEND" -Direction Inbound -Protocol TCP -LocalPort $FRONTEND -Action Allow -ErrorAction SilentlyContinue | Out-Null
New-NetFirewallRule -DisplayName "Survey API $BACKEND" -Direction Inbound -Protocol TCP -LocalPort $BACKEND  -Action Allow -ErrorAction SilentlyContinue | Out-Null
cmd /c "netsh interface portproxy delete v4tov4 listenport=$FRONTEND listenaddress=0.0.0.0 >nul 2>&1"
cmd /c "netsh interface portproxy add v4tov4 listenport=$FRONTEND listenaddress=0.0.0.0 connectport=$BACKEND connectaddress=127.0.0.1"

# ---------- final check ----------
Write-Host ">> Waiting for server to start..."
Start-Sleep -Seconds 20
try {
    $r = Invoke-WebRequest "http://127.0.0.1:$BACKEND/app/" -UseBasicParsing -TimeoutSec 10
    Write-Host "   Local check: HTTP $($r.StatusCode) - server is UP" -ForegroundColor Green
} catch {
    Write-Host "   WARNING: server did not answer yet. It may need 1 more minute." -ForegroundColor Yellow
    Write-Host "   Check log file: $APPDIR\logs\server.log" -ForegroundColor Yellow
}
Pop-Location

Write-Host ""
Write-Host "==============================================" -ForegroundColor Green
Write-Host "  INSTALLATION COMPLETE" -ForegroundColor Green
Write-Host "==============================================" -ForegroundColor Green
Write-Host "  Frontend (open in browser):" -ForegroundColor Green
Write-Host "     http://$APP_IP`:$FRONTEND/app/" -ForegroundColor Yellow
Write-Host "  Backend:" -ForegroundColor Green
Write-Host "     http://$APP_IP`:$BACKEND/app/" -ForegroundColor Yellow
Write-Host ""
Write-Host "  Manage the service:" -ForegroundColor Green
Write-Host "     schtasks /Run /TN SurveySystem    (start)" -ForegroundColor Gray
Write-Host "     schtasks /End /TN SurveySystem    (stop)" -ForegroundColor Gray
Write-Host "     Log file: $APPDIR\logs\server.log" -ForegroundColor Gray
Write-Host "==============================================" -ForegroundColor Green
Write-Host ""
Write-Host "NOTE: if the page does not open from outside, the hosting company" -ForegroundColor Yellow
Write-Host "      also blocks the port at datacenter level. In that case tell" -ForegroundColor Yellow
Write-Host "      your provider to open TCP ports 8090 and 3010." -ForegroundColor Yellow
Write-Host ""
Pause
