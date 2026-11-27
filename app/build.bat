@echo off
setlocal
cd /d "%~dp0"
set "ROOT=%~dp0.."
set "VENV=%ROOT%\.venv"

if not exist "%VENV%\Scripts\python.exe" (
    echo Creating virtual environment...
    python -m venv "%VENV%" || goto :error
)

echo Installing dependencies...
"%VENV%\Scripts\python.exe" -m pip install --upgrade pip --quiet || goto :error
"%VENV%\Scripts\python.exe" -m pip install -r requirements.txt pyinstaller --quiet || goto :error

echo Building BNDGG-Vault.exe...
"%VENV%\Scripts\python.exe" -m PyInstaller BNDGG-Vault.spec --noconfirm --clean --distpath "%ROOT%\dist" --workpath "%ROOT%\build" || goto :error

echo.
echo Done: %ROOT%\dist\BNDGG-Vault.exe
pause
exit /b 0

:error
echo.
echo Build failed.
pause
exit /b 1