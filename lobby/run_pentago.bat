@echo off
setlocal
title Cafe Fekr - Pentago Lobby Bot (Level 1)

cd /d "%~dp0..\.."

echo ========================================================
echo   Cafe Fekr - Pentago (پنتاگو) Lobby Bot
echo   Mode: Lobby
echo   Difficulty: Level 1 (Beginner / Casual Human)
echo   Status: Listening for rooms to auto-join and play...
echo ========================================================

set "VENV_PYTHON=C:\Users\erfan\Downloads\Python_projects\kafehfekrbackend\.venv\Scripts\python.exe"
if exist "%VENV_PYTHON%" (
    set "PYTHON_CMD=%VENV_PYTHON%"
) else (
    set "PYTHON_CMD=python"
)

echo Using Python: %PYTHON_CMD%
echo.

"%PYTHON_CMD%" "%~dp0..\modes\lobby_bot.py" Pentago

if %ERRORLEVEL% neq 0 (
    echo.
    echo ========================================================
    echo Bot exited with code %ERRORLEVEL%.
    echo ========================================================
)
pause
