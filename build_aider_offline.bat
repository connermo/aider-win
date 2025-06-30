@echo off
chcp 65001 > nul
title Aider Offline Package Builder

echo ===============================================
echo           Aider Offline Package Builder
echo ===============================================
echo.
echo This script will automatically build a complete offline Windows version of Aider
echo Suitable for internal networks, using OpenAI Compatible API
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not detected, please install Python 3.10 or higher
    echo Download from: https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [INFO] Detected Python version:
python --version

echo.
echo Starting build process...
echo This may take a few minutes, please be patient...
echo.

REM Run build script
python build_offline_windows_package.py

if errorlevel 1 (
    echo.
    echo [ERROR] Build failed, please check the error messages above
    pause
    exit /b 1
)

echo.
echo ===============================================
echo              Build Complete!
echo ===============================================
echo.
echo Generated files are located in the dist directory:
echo - aider_windows_offline/          (extracted directory)
echo - aider_windows_offline.zip       (compressed package)
echo.
echo Next steps:
echo 1. Copy aider_windows_offline.zip to the target Windows machine
echo 2. Extract to any directory
echo 3. Edit .aider.conf.yml to set your API parameters
echo 4. Run start_aider.bat to start using
echo.

pause 