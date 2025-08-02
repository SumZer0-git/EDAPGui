 @echo off
REM Quick Requirements Installer for EDAPGui
REM Installs requirements.txt using the best available Python version

echo Installing EDAPGui Requirements...
echo ================================

REM Try py launcher with specific versions first
py -3.11 --version >nul 2>&1
if %errorlevel% == 0 (
    echo Using Python 3.11 via py launcher
    py -3.11 -m pip install --upgrade pip
    py -3.11 -m pip install -r requirements.txt
    goto done
)

py -3.10 --version >nul 2>&1
if %errorlevel% == 0 (
    echo Using Python 3.10 via py launcher
    py -3.10 -m pip install --upgrade pip
    py -3.10 -m pip install -r requirements.txt
    goto done
)

py -3.9 --version >nul 2>&1
if %errorlevel% == 0 (
    echo Using Python 3.9 via py launcher
    py -3.9 -m pip install --upgrade pip
    py -3.9 -m pip install -r requirements.txt
    goto done
)

py --version >nul 2>&1
if %errorlevel% == 0 (
    for /f "tokens=2" %%i in ('py --version 2^>^&1') do (
        echo Using Python %%i via py launcher
    )
    py -m pip install --upgrade pip
    py -m pip install -r requirements.txt
    goto done
)

REM Fallback to python command
python --version >nul 2>&1
if %errorlevel% == 0 (
    for /f "tokens=2" %%i in ('python --version 2^>^&1') do (
        echo Using Python %%i
    )
    python -m pip install --upgrade pip
    python -m pip install -r requirements.txt
    goto done
)

echo Error: No Python installation found. Please install Python 3.9, 3.10, or 3.11.
pause
exit /b 1

:done
echo.
echo Requirements installation complete!
echo You can now run: python EDAPGui.py
echo Or use: start_ed_ap.bat (recommended)
pause