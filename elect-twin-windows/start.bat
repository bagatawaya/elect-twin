@echo off
setlocal
cd /d "%~dp0"

echo [Elect Twin Windows Launcher]
echo Checking Python installation...
py -3 --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Python 3 was not found. Please install Python 3.10+ from python.org or the Microsoft Store.
    pause
    exit /b 1
)

echo Starting Elect Twin in local developer mode...
py -3 ..\elect-twin-mac\twin.py %*
pause
