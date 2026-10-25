@echo off
chcp 65001 >nul
title Compilation TinySA Monitor
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo Python n'est pas installe. Tentative d'installation via winget...
    winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements
    echo.
    echo Python vient d'etre installe : FERME cette fenetre puis relance build.bat.
    pause
    exit /b
)

echo [1/3] Installation des dependances...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt pyinstaller
if errorlevel 1 goto erreur

echo [2/3] Compilation...
for /f "delims=" %%T in ('python -c "from PySide6.QtCore import QLibraryInfo as Q; print(Q.path(Q.LibraryPath.TranslationsPath))"') do set QTTR=%%T
python -m PyInstaller --noconfirm --onefile --noconsole --name TinySA-Monitor --icon assets\icone.ico --add-data "assets\icone.png;." --add-data "%QTTR%\qtbase_fr.qm;PySide6/Qt/translations" tinysa_monitor.py
if errorlevel 1 goto erreur

echo [3/3] Termine !
echo.
echo   Ton exe est ici :  %~dp0dist\TinySA-Monitor.exe
echo.
start "" "%~dp0dist"
pause
exit /b

:erreur
echo.
echo *** Une erreur est survenue, copie le message ci-dessus et envoie-le moi. ***
pause
