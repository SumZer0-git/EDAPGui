@echo off
REM EDAPGui Startup Script
REM Uses a private venv next to this script (created on first start) and runs EDAPGui

REM Work relative to this script's folder, regardless of where it was started from
cd /d "%~dp0"

if not exist "venv\Scripts\python.exe" (
    echo Creating Python virtual environment and installing requirements...
    echo This may take a few minutes, please wait...
    call install_requirements.bat nopause
    if errorlevel 1 (
        pause
        exit /b 1
    )
)

venv\Scripts\python.exe -c "import sys; sys.exit(0 if sys.version_info[:2] == (3, 12) else 1)"
if errorlevel 1 (
    echo Error: The virtual environment must use Python 3.12.
    echo Remove the existing "venv" folder and run install_requirements.bat.
    pause
    exit /b 1
)

echo Starting EDAPGui...
venv\Scripts\python.exe src\main.py
