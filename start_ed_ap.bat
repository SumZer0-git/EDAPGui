@echo off
REM EDAPGui Startup Script
REM Creates Python venv with 3.11/3.10/3.9 (whichever is available) and runs EDAPGui

REM Check if venv exists
if not exist "venv\Scripts\python.exe" (
    echo Creating Python virtual environment...
    echo This may take a moment, please wait...
    
    REM Try Python versions in order of preference: 3.11, 3.10, 3.9, then fallback
    set PYTHON_CMD=
    
    REM Try py launcher with specific versions (Windows Python Launcher)
    py -3.11 --version >nul 2>&1
    if %errorlevel% == 0 (
        set PYTHON_CMD=py -3.11
        echo Found Python 3.11 via py launcher
        goto create_venv
    )
    
    py -3.10 --version >nul 2>&1
    if %errorlevel% == 0 (
        set PYTHON_CMD=py -3.10
        echo Found Python 3.10 via py launcher
        goto create_venv
    )
    
    py -3.9 --version >nul 2>&1
    if %errorlevel% == 0 (
        set PYTHON_CMD=py -3.9
        echo Found Python 3.9 via py launcher
        goto create_venv
    )
    
    REM Try py launcher with latest
    py --version >nul 2>&1
    if %errorlevel% == 0 (
        for /f "tokens=2" %%i in ('py --version 2^>^&1') do (
            echo Found Python %%i via py launcher
            set PYTHON_CMD=py
            goto create_venv
        )
    )
    
    REM Fallback to python command
    python --version >nul 2>&1
    if %errorlevel% == 0 (
        for /f "tokens=2" %%i in ('python --version 2^>^&1') do (
            echo Found Python %%i
            set PYTHON_CMD=python
            goto create_venv
        )
    )
    
    echo Error: No suitable Python installation found. Please install Python 3.9, 3.10, or 3.11.
    pause
    exit /b 1
    
    :create_venv
    %PYTHON_CMD% -m venv venv
    
    if not exist "venv\Scripts\python.exe" (
        echo Error: Failed to create virtual environment
        pause
        exit /b 1
    )
    
    echo Installing requirements...
    venv\Scripts\pip.exe install --upgrade pip
    venv\Scripts\pip.exe install -r requirements.txt
    
    if %errorlevel% neq 0 (
        echo Error: Failed to install requirements
        pause
        exit /b 1
    )
    
    echo Virtual environment setup complete!
)

REM Run EDAPGui with venv python
echo Starting EDAPGui...
venv\Scripts\python.exe EDAPGui.py