@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Creating the virtual environment...
    python -m venv .venv
    if errorlevel 1 goto :error
    echo Installing dependencies...
    ".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r requirements.txt
    if errorlevel 1 goto :error
)

start "" ".venv\Scripts\pythonw.exe" "app.py"
exit /b 0

:error
echo.
echo Setup failed. Make sure Python 3.11 or newer is installed and on PATH.
pause
exit /b 1
