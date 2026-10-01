@echo off
if not exist "%~dp0.venv\Scripts\python.exe" (
    echo Primero prepara el entorno siguiendo el README.
    pause
    exit /b 1
)
"%~dp0.venv\Scripts\python.exe" "%~dp0main.py" %*
set "fraseyaExit=%ERRORLEVEL%"
pause
exit /b %fraseyaExit%
