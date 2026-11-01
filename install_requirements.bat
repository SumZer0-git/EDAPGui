@echo off
REM Requirements installer for EDAPGui
REM Always creates/uses a private virtual environment (venv) next to this script,
REM so the global Python installation is never touched.
REM Usage: install_requirements.bat [nopause]

REM Work relative to this script's folder, regardless of where it was started from
cd /d "%~dp0"

echo Installing EDAPGui Requirements...
echo ================================

if exist "venv\Scripts\python.exe" goto install

set PYTHON_CMD=
py -3.11 --version >nul 2>&1
if %errorlevel% == 0 set PYTHON_CMD=py -3.11
if defined PYTHON_CMD goto create_venv

py -3.10 --version >nul 2>&1
if %errorlevel% == 0 set PYTHON_CMD=py -3.10
if defined PYTHON_CMD goto create_venv

py -3.9 --version >nul 2>&1
if %errorlevel% == 0 set PYTHON_CMD=py -3.9
if defined PYTHON_CMD goto create_venv

py --version >nul 2>&1
if %errorlevel% == 0 set PYTHON_CMD=py
if defined PYTHON_CMD goto create_venv

python --version >nul 2>&1
if %errorlevel% == 0 set PYTHON_CMD=python
if defined PYTHON_CMD goto create_venv

echo Error: No Python installation found. Please install Python 3.9, 3.10, or 3.11.
goto fail

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
