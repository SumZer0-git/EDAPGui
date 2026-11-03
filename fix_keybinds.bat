@echo off
REM Fills gaps and resolves conflicts in the Elite Dangerous keybindings EDAP needs.
REM Elite Dangerous must be closed. Options: --dry-run (preview only), --yes (fill gaps without asking)

cd /d "%~dp0"

if not exist "venv\Scripts\python.exe" (
    echo The virtual environment does not exist yet. Run start_ed_ap.bat or install_requirements.bat first.
    pause
    exit /b 1
)

venv\Scripts\python.exe src\fix_keybinds.py %*
pause
