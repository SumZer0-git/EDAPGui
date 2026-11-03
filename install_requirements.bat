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
    venv\Scripts\python.exe -c "import sys; sys.exit(0 if sys.version_info[:2] in ((3, 12), (3, 13)) else 1)"
    if errorlevel 1 (
        echo Error: The existing virtual environment must use Python 3.12 or 3.13.
        echo Remove the existing "venv" folder and run this installer again.
        goto fail
    )
    venv\Scripts\python.exe -c "import importlib.metadata as m,sys; expected={'paddleocr':'3.6.0','paddlepaddle':'3.2.2','numpy':'2.2.6','opencv-contrib-python':'4.10.0.84','requests':'2.34.2'}; names={d.metadata['Name'].lower() for d in m.distributions() if d.metadata.get('Name')}; sys.exit(0 if all(m.version(name)==version for name,version in expected.items()) and not names.intersection({'opencv-python','opencv-python-headless'}) else 1)"
    if errorlevel 1 (
        echo Error: The existing virtual environment has outdated or conflicting dependencies.
        echo Remove the existing "venv" folder and run this installer again.
        goto fail
    )
    goto install
)

py -3.13 --version >nul 2>&1
if not errorlevel 1 (
    set PYTHON_CMD=py -3.13
    goto create_venv
)
py -3.12 --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python 3.12 or 3.13 was not found. Please install a supported version of Python.
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

venv\Scripts\python.exe -c "import importlib.metadata as m,sys; expected={'paddleocr':'3.6.0','paddlepaddle':'3.2.2','numpy':'2.2.6','opencv-contrib-python':'4.10.0.84','requests':'2.34.2'}; names={d.metadata['Name'].lower() for d in m.distributions() if d.metadata.get('Name')}; sys.exit(0 if all(m.version(name)==version for name,version in expected.items()) and not names.intersection({'opencv-python','opencv-python-headless'}) else 1)"
if errorlevel 1 (
    echo Error: The installed dependencies do not match the supported OCR stack.
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
