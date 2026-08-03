@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo MathOntoSpeak Python environment was not found.
  echo Expected: %CD%\.venv\Scripts\python.exe
  pause
  exit /b 1
)

".venv\Scripts\python.exe" "scripts\start_mathontospeak.py" %*
if errorlevel 1 (
  echo.
  echo MathOntoSpeak stopped because a service could not start.
  pause
)
