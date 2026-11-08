# ==============================================================
#  Survey System - PostgreSQL SETUP for WINDOWS Server
#  (راه‌اندازی دیتابیس PostgreSQL روی همان سرور ویندوزی)
#
#  WHAT IT DOES (all steps idempotent - safe to run again):
#    1) Checks if PostgreSQL is already installed
#    2) If not: downloads PostgreSQL 16 and installs it SILENTLY
#    3) Creates database role "survey" and database "surveydb"
#    4) Adds SURVEY_DATABASE_URL to C:\survey-system\run-server.bat
#       (the backend will store everything in PostgreSQL)
#
#  HOW TO USE:
#    1) right-click PowerShell -> Run as Administrator
#    2) cd C:\survey-system\deploy
#    3) powershell -ExecutionPolicy Bypass -File .\setup-postgres-windows.ps1
#       (optional: -SuperPassword "YourStrongPass"  -> password of the
#        postgres SUPERUSER; app itself uses survey/survey internally)
#    4) to move your EXISTING records from SQLite into PostgreSQL:
#       cd C:\survey-system
#       set SURVEY_DATABASE_URL=postgresql+psycopg2://survey:survey@127.0.0.1:5432/surveydb
#       venv\Scripts\python scripts\migrate_sqlite_to_postgres.py
#    5) restart: cmd /c 'schtasks /End /TN "SurveySystem"'
#                cmd /c 'schtasks /Run /TN "SurveySystem"'
#
#  NOTE: until you run this script, the system keeps using SQLite
#        (data\survey.db) - nothing changes by itself.
# ==============================================================

param([string]$SuperPassword = "Srv@Postgres2026")

$ErrorActionPreference = "Stop"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$APPDIR = "C:\survey-system"
$PG_ROOT = "C:\Program Files\PostgreSQL"

function Stop-WithError($msg) {
    Write-Host ""
    Write-Host "ERROR: $msg" -ForegroundColor Red
    Write-Host ""
    Pause
    exit 1
}

# ---------- 0) admin check ----------
$wi = [Security.Principal.WindowsIdentity]::GetCurrent()
$wp = New-Object Security.Principal.WindowsPrincipal($wi)
if (-not $wp.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Stop-WithError "right-click PowerShell and choose 'Run as Administrator', then run this script again."
}

Write-Host "==============================================" -ForegroundColor Cyan
Write-Host " Survey System - PostgreSQL setup (Windows)"    -ForegroundColor Cyan
Write-Host "==============================================" -ForegroundColor Cyan

# ---------- 1) find existing psql ----------
function Find-Psql {
    $cmd = Get-Command psql -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    if (Test-Path $PG_ROOT) {
        $latest = Get-ChildItem $PG_ROOT -Directory | Sort-Object Name -Descending | Select-Object -First 1
        if ($latest -and (Test-Path (Join-Path $latest.FullName "bin\psql.exe"))) {
            return (Join-Path $latest.FullName "bin\psql.exe")
        }
    }
    return $null
}

$psql = Find-Psql

# ---------- 2) install silently if missing ----------
if (-not $psql) {
    Write-Host ">> PostgreSQL not found - installing (silent, ~3-5 minutes)..." -ForegroundColor Yellow
    $installer = "$env:TEMP\postgresql-16.4-1-windows-x64.exe"
    $url = "https://get.enterprisedb.com/postgresql/postgresql-16.4-1-windows-x64.exe"
    try {
        Invoke-WebRequest $url -OutFile $installer -UseBasicParsing -TimeoutSec 600
    } catch {
        Stop-WithError "download of PostgreSQL installer failed ($($_.Exception.Message)). Check internet on the server, or install PostgreSQL manually and run this script again."
    }
    if ((Get-Item $installer).Length -lt 50MB) {
        Stop-WithError "downloaded installer looks incomplete. Delete $installer and run again."
    }
    Write-Host "   running silent setup (service: postgresql-16)..."
    $proc = Start-Process $installer -ArgumentList @(
        "--mode", "unattended",
        "--unattendedmodeui", "none",
        "--superpassword", $SuperPassword,
        "--enable-components", "server,commandlinetools",
        "--disable-components", "pgAdmin,stackbuilder",
        "--servicename", "postgresql-16",
        "--servicepassword", $SuperPassword
    ) -Wait -PassThru
    if ($proc.ExitCode -ne 0) {
        Stop-WithError "PostgreSQL silent install failed (exit $($proc.ExitCode)). Install it manually, then run this script again."
    }
    Start-Sleep -Seconds 5
    $psql = Find-Psql
    if (-not $psql) { Stop-WithError "psql.exe still not found after install." }
}

$pgBin = Split-Path $psql
Write-Host ("   psql: " + $psql) -ForegroundColor Green

# service up?
$svc = Get-Service | Where-Object { $_.Name -like "postgresql*" -or $_.DisplayName -like "postgresql*" } | Select-Object -First 1
if ($svc -and $svc.Status -ne "Running") {
    Write-Host ">> Starting service $($svc.Name)..."
    Start-Service $svc.Name
    Start-Sleep -Seconds 3
}

# ---------- 3) create role + database (idempotent) ----------
$env:PGPASSWORD = $SuperPassword
$CON = "127.0.0.1"
$PORT = "5432"

Write-Host ">> Creating role 'survey' and database 'surveydb'..."
$roleExists = & (Join-Path $pgBin "psql.exe") -h $CON -p $PORT -U postgres -tAc "SELECT 1 FROM pg_roles WHERE rolname='survey';"
if ("$roleExists".Trim() -ne "1") {
    & (Join-Path $pgBin "psql.exe") -h $CON -p $PORT -U postgres -c "CREATE ROLE survey LOGIN PASSWORD 'survey';"
    Write-Host "   role 'survey' created." -ForegroundColor Green
} else {
    & (Join-Path $pgBin "psql.exe") -h $CON -p $PORT -U postgres -c "ALTER ROLE survey WITH LOGIN PASSWORD 'survey';"
    Write-Host "   role 'survey' already exists (password refreshed)."
}

$dbExists = & (Join-Path $pgBin "psql.exe") -h $CON -p $PORT -U postgres -tAc "SELECT 1 FROM pg_database WHERE datname='surveydb';"
if ("$dbExists".Trim() -ne "1") {
    & (Join-Path $pgBin "psql.exe") -h $CON -p $PORT -U postgres -c "CREATE DATABASE surveydb OWNER survey;"
    Write-Host "   database 'surveydb' created." -ForegroundColor Green
} else {
    Write-Host "   database 'surveydb' already exists."
}
Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue

# ---------- 4) wire SURVEY_DATABASE_URL into run-server.bat ----------
$bat = Join-Path $APPDIR "run-server.bat"
$dsn = "postgresql+psycopg2://survey:survey@127.0.0.1:5432/surveydb"
if (Test-Path $bat) {
    $content = Get-Content $bat -Raw
    if ($content -match "SURVEY_DATABASE_URL") {
        Write-Host ">> run-server.bat already sets SURVEY_DATABASE_URL - left untouched."
    } else {
        $lines = Get-Content $bat
        $out = @($lines[0], "set SURVEY_DATABASE_URL=$dsn") + $lines[1..($lines.Count - 1)]
        Set-Content $bat ($out -join "`r`n") -Encoding ASCII
        Write-Host ">> run-server.bat updated - backend will use PostgreSQL." -ForegroundColor Green
    }
} else {
    Write-Host "" -ForegroundColor Yellow
    Write-Host ">> run-server.bat not found. When you start the backend, set:" -ForegroundColor Yellow
    Write-Host ("   set SURVEY_DATABASE_URL=" + $dsn) -ForegroundColor Yellow
}

# ---------- 5) summary ----------
Write-Host ""
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host " PostgreSQL is READY" -ForegroundColor Green
Write-Host "----------------------------------------------"
Write-Host ("  data source : postgresql+psycopg2://survey:survey@127.0.0.1:5432/surveydb")
Write-Host ("  superuser pw: " + $SuperPassword + "   (keep it safe)")
Write-Host "----------------------------------------------"
Write-Host " NEXT STEPS (to move existing records):"
Write-Host "   cd C:\survey-system"
Write-Host ("   set SURVEY_DATABASE_URL=" + $dsn)
Write-Host "   venv\Scripts\python scripts\migrate_sqlite_to_postgres.py"
Write-Host "   cmd /c 'schtasks /End /TN ""SurveySystem""'"
Write-Host "   cmd /c 'schtasks /Run /TN ""SurveySystem""'"
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host ""
Pause
