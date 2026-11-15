@echo off
title Cafe Fekr - Social Bot Runner
echo ========================================================
echo   Cafe Fekr - Authentic Social Bot Suite
echo   Testing with Real User Personas and Actual Tokens
echo ========================================================
echo.

if "%1"=="" (
    echo Launching Interactive Social Bot Suite...
    python -m bots.social.runner
) else (
    python -m bots.social.runner %*
)

pause
