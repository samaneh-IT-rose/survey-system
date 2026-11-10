@echo off
rem ==================================================================
rem  Survey System (Rahaye Zendegi) - One-click local run
rem  Double-click this file on ANY Windows PC. No server needed.
rem  Requirement: Python 3.10 or newer  https://www.python.org/downloads/
rem  (During Python setup, tick "Add python.exe to PATH")
rem
rem  It creates a local folder "venv", installs dependencies (first run
rem  only), stores data in "data\survey.db" (SQLite - no PostgreSQL
rem  needed) and opens http://127.0.0.1:8090/app/ in your browser.
rem  First login: admin / admin123  (you must change it right away)
rem  To stop: close this black window.
rem  If port 8090 is busy, change 8090 below to e.g. 8091 (3 places).
rem ==================================================================
setlocal
cd /d "%~dp0"
set PORT=8090

set PYEXE=python
where python >nul 2>nul
if errorlevel 1 (
    where py >nul 2>nul
    if errorlevel 1 (
        echo [ERROR] Python not found.
        echo         Install Python 3.10+ from https://www.python.org/downloads/
        echo         and tick "Add python.exe to PATH" during setup, then run again.
        pause
        exit /b 1
    )
    set PYEXE=py
)

if not exist "venv\Scripts\python.exe" (
    echo [1/3] Creating virtual environment ...
    %PYEXE% -m venv venv
    if errorlevel 1 (
        echo [ERROR] Could not create venv. Check the Python installation.
        pause
        exit /b 1
    )
)

echo [2/3] Installing dependencies - first run takes a few minutes ...
"venv\Scripts\python.exe" -m pip install -q -r requirements.txt
if errorlevel 1 (
    echo        PyPI failed - trying mirror ...
    "venv\Scripts\python.exe" -m pip install -q -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com --timeout 90 --retries 5
    if errorlevel 1 (
        echo [ERROR] pip install failed. Check your internet connection and run again.
        pause
        exit /b 1
    )
)

if not exist "data" mkdir data

echo [3/3] Starting server:  http://127.0.0.1:%PORT%/app/
echo         First login: admin / admin123   ^(change it on first login^)
echo         Keep this window open. Closing it stops the server.
echo.

start "" cmd /c "timeout /t 3 >nul & start http://127.0.0.1:%PORT%/app/"

set SURVEY_DATABASE_URL=sqlite:///data/survey.db
set SURVEY_SELF_URL=http://127.0.0.1:%PORT%
"venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port %PORT%

echo.
echo Server stopped.
pause
