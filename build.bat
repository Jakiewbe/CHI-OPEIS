@echo off
:: build.bat — Clean build, test, package for CHI-OPEIS
:: Usage: double-click or run from repo root

setlocal
set PROJECT_ROOT=%~dp0

echo [1/4] Cleaning previous build artifacts...
rmdir /s /q "%PROJECT_ROOT%build" 2>nul
rmdir /s /q "%PROJECT_ROOT%dist" 2>nul

echo [2/4] Running tests...
set QT_QPA_PLATFORM=offscreen
cd /d "%PROJECT_ROOT%"
call .venv\Scripts\activate.bat
python -m pytest -q
if %ERRORLEVEL% neq 0 (
    echo Tests failed. Aborting.
    exit /b 1
)

echo [3/4] Building with PyInstaller...
pyinstaller --noconfirm CHI-OPEIS.spec
if %ERRORLEVEL% neq 0 (
    echo Build failed. Aborting.
    exit /b 1
)

echo [4/4] Creating release archive...
cd /d "%PROJECT_ROOT%dist"
powershell -NoProfile -Command "Compress-Archive -Path 'CHI-OPEIS\*' -DestinationPath 'CHI-OPEIS-release.zip' -Force"
cd /d "%PROJECT_ROOT%"

echo.
echo Done.
echo   Bundle:  dist\CHI-OPEIS\
echo   Archive: dist\CHI-OPEIS-release.zip
