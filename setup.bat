@echo off
REM ==============================================================================
REM Orbital Pulse — Windows Setup Launcher (Batch wrapper for setup.ps1)
REM ==============================================================================
REM This batch script bypasses PowerShell execution policies to run setup.ps1.

cd /d "%~dp0"
echo ==================================================================
echo Starting Orbital Pulse Windows Setup...
echo ==================================================================

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup.ps1" %*

if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] Setup script encountered an error (exit code %ERRORLEVEL%).
    pause
    exit /b %ERRORLEVEL%
)

exit /b 0
