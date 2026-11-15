@echo off
chcp 65001 >nul
title Cafe Fekr - Bot Backend Server (Port 5003)

cd /d "%~dp0.."

set "VENV_PYTHON=C:\Users\erfan\Downloads\Python_projects\kafehfekrbackend\.venv\Scripts\python.exe"
if exist "%VENV_PYTHON%" (
    set "PYTHON_CMD=%VENV_PYTHON%"
) else (
    set "PYTHON_CMD=python"
)

"%PYTHON_CMD%" -m bots.server
pause
