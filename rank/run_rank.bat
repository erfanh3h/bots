@echo off
setlocal
title Cafe Fekr - Main Rank Bot (Level 2)

cd /d "%~dp0..\.."

echo ========================================================
echo   Cafe Fekr - Main Rank Bot
echo   Mode: Main Rank (Pick ^& Ban + Multi-Game Series)
echo   Difficulty: Level 2 (Intermediate)
echo   Status: Connecting to matchmaking queue...
echo ========================================================

set "VENV_PYTHON=C:\Users\erfan\Downloads\Python_projects\kafehfekrbackend\.venv\Scripts\python.exe"

if exist "%VENV_PYTHON%" (
    set "PYTHON_CMD=%VENV_PYTHON%"
) else (
    set "PYTHON_CMD=python"
)

echo Using Python: %PYTHON_CMD%
echo.

set "USER_TOKEN=%~1"

if "%USER_TOKEN%"=="" (
    if defined BOT_TOKEN (
        set "USER_TOKEN=%BOT_TOKEN%"
    ) else (
        set /p USER_TOKEN="Enter Bot JWT Token (or press Enter to auto-authenticate): "
    )
)

echo.
echo Starting Main Rank Bot...
echo.

if not "%USER_TOKEN%"=="" (
    "%PYTHON_CMD%" "%~dp0..\modes\rank_bot.py" --token "%USER_TOKEN%"
) else (
    "%PYTHON_CMD%" "%~dp0..\modes\rank_bot.py"
)

if %ERRORLEVEL% neq 0 (
    echo.
    echo ========================================================
    echo Bot exited with code %ERRORLEVEL%.
    echo ========================================================
)

pause
