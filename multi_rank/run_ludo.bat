@echo off
chcp 65001 >nul
title Cafe Fekr - Ludo Multi-Rank Bot (4-Player)
echo ========================================================
echo   Cafe Fekr - Ludo (منچ) 4-Player Multi-Rank Bot
echo ========================================================
set PYTHON_CMD=python
if exist "%~dp0..\..\.venv\Scripts\python.exe" set PYTHON_CMD="%~dp0..\..\.venv\Scripts\python.exe"
if exist "%~dp0..\.venv\Scripts\python.exe" set PYTHON_CMD="%~dp0..\.venv\Scripts\python.exe"
%PYTHON_CMD% "%~dp0..\modes\multi_rank_bot.py" Ludo %*
pause
