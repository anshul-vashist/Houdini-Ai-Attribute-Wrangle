@echo off
setlocal
cd /d "%~dp0"
title AI Attribute Wrangle - Setup

echo =======================================================
echo   AI Attribute Wrangle - 1-Click Setup Wizard
echo =======================================================
echo.

where python >nul 2>&1
if %ERRORLEVEL% equ 0 (
    echo Launching Setup Wizard...
    start "" pythonw installer_gui.py
    if %ERRORLEVEL% neq 0 (
        python installer_gui.py
    )
    exit /b 0
)

where py >nul 2>&1
if %ERRORLEVEL% equ 0 (
    echo Launching Setup Wizard via Python Launcher...
    start "" pyw installer_gui.py
    if %ERRORLEVEL% neq 0 (
        py installer_gui.py
    )
    exit /b 0
)

echo [WARNING] Python was not found in your system PATH.
echo.
echo You can still install in 1 click directly inside Houdini:
echo 1. Launch SideFX Houdini.
echo 2. Go to File -^> Run Script... and choose:
echo    "%~dp0install_in_houdini.py"
echo.
pause
