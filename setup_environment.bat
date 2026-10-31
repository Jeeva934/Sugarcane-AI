@echo off
title Sugarcane-AI Environment Setup
echo ======================================================================
echo           Sugarcane-AI Automated Project Setup
echo ======================================================================
echo.

:: 1. Check Python
echo [1/4] Checking Python installation...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not added to PATH!
    echo Please install Python 3.10 or later from https://www.python.org/
    pause
    exit /b 1
)
python --version

:: 2. Check Node.js
echo.
echo [2/4] Checking Node.js and npm...
node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Node.js is not installed or not added to PATH!
    echo Please install Node.js (v18, v20, or v22) from https://nodejs.org/
    pause
    exit /b 1
)
node --version
npm --version

:: 3. Python Virtual Environment & Dependencies
echo.
echo [3/4] Setting up Python backend virtual environment...
if not exist "venv" (
    echo Creating virtual environment 'venv'...
    python -m venv venv
)
echo Activating virtual environment...
call venv\Scripts\activate.bat

echo Upgrading pip and installing backend dependencies...
python -m pip install --upgrade pip
pip install -r requirements.txt

:: 4. Frontend Dependencies
echo.
echo [4/4] Installing frontend dependencies...
cd frontend
call npm install
cd ..

echo.
echo ======================================================================
echo           Setup Completed Successfully!
echo ======================================================================
echo.
echo To start the application, simply double-click "start_project.bat"
echo.
pause
