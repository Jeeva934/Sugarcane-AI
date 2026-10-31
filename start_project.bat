@echo off
title Sugarcane-AI Launcher
echo ======================================================================
echo           Starting Sugarcane-AI Decision Support System
echo ======================================================================
echo.

:: 1. Activate Virtual Environment if exists
if exist "venv\Scripts\activate.bat" (
    set "PYTHON_EXE=venv\Scripts\python.exe"
) else (
    set "PYTHON_EXE=python"
)

:: 2. Launch FastAPI Backend in a separate window
echo [1/2] Starting FastAPI Backend on http://127.0.0.1:8000 ...
start "Sugarcane-AI Backend (FastAPI)" cmd /k "set PYTHONPATH=%CD%\backend && %PYTHON_EXE% -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --reload"

:: 3. Launch Vite Frontend in a separate window
echo [2/2] Starting Vite Frontend on http://127.0.0.1:5173 ...
start "Sugarcane-AI Frontend (Vite)" cmd /k "cd frontend && npm run dev"

:: 4. Wait 3 seconds and open browser
echo.
echo Launching your browser at http://localhost:5173 ...
timeout /t 3 >nul
start http://localhost:5173

echo.
echo Application is running!
echo Backend:  http://127.0.0.1:8000
echo Frontend: http://localhost:5173
echo.
echo Keep both terminal windows open while using the application.
echo.
