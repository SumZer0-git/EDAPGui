@echo off
REM Requirements installer for EDAPGui
REM Always creates/uses a private virtual environment (venv) next to this script,
REM so the global Python installation is never touched.
REM Usage: install_requirements.bat [nopause]

REM Work relative to this script's folder, regardless of where it was started from
cd /d "%~dp0"

echo Installing EDAPGui Requirements...
echo ================================

if exist "venv\Scripts\python.exe" (
    venv\Scripts\python.exe -c "import sys; sys.exit(0 if sys.version_info[:2] == (3, 12) else 1)"
    if errorlevel 1 (
        echo Error: The existing virtual environment must use Python 3.12.
        echo Remove the existing "venv" folder and run this installer again.
        goto fail
    )
    goto install
)

py -3.12 --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python 3.12 was not found. Please install Python 3.12.
    goto fail
)
set PYTHON_CMD=py -3.12

:create_venv
echo Creating virtual environment using: %PYTHON_CMD%
%PYTHON_CMD% -m venv venv
if not exist "venv\Scripts\python.exe" (
    echo Error: Failed to create virtual environment
    goto fail
)

:install
venv\Scripts\python.exe -m pip install --upgrade pip
venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 (
    echo Error: Failed to install requirements
    REM Remove the incomplete venv so the next run starts clean
    rmdir /s /q venv
    goto fail
)

echo.
echo Requirements installation complete!
echo Start the program with: start_ed_ap.bat
if /i not "%~1"=="nopause" pause
exit /b 0

:fail
if /i not "%~1"=="nopause" pause
exit /b 1
