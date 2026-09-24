@echo off
setlocal

set "PROJECT_DIR=%~dp0"
set "VENV_DIR=%PROJECT_DIR%.venv"
set "PIP_CACHE_DIR=%VENV_DIR%\.pip-cache"
set "PIP_DISABLE_PIP_VERSION_CHECK=1"

cd /d "%PROJECT_DIR%" || exit /b 1

if not exist "%VENV_DIR%\Scripts\python.exe" (
    py -3 -m venv "%VENV_DIR%"
    if errorlevel 1 exit /b %errorlevel%
)

"%VENV_DIR%\Scripts\python.exe" -m pip install --quiet -r "%PROJECT_DIR%requirements.txt"
if errorlevel 1 exit /b %errorlevel%

"%VENV_DIR%\Scripts\python.exe" "%PROJECT_DIR%main.py" %*
exit /b %errorlevel%
