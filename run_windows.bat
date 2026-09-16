@echo off
REM LZ Media Station - Windows Launcher
REM Doppelklick: startet Server + öffnet Browser
SETLOCAL ENABLEDELAYEDEXPANSION

cd /d "%~dp0"

echo ========================================================
echo   LZ Media Station - Windows
echo ========================================================
echo.

REM Python pruefen
where python >nul 2>nul
if errorlevel 1 (
    echo [FEHLER] Python nicht gefunden.
    echo Bitte Python 3.10+ installieren: https://www.python.org/downloads/
    pause
    exit /b 1
)

REM Virtuelle Umgebung anlegen, falls nicht vorhanden
if not exist ".venv\Scripts\python.exe" (
    echo [*] Erstelle virtuelle Umgebung .venv ...
    python -m venv .venv
)

REM Abhaengigkeiten installieren
echo [*] Installiere Abhaengigkeiten ...
".venv\Scripts\python.exe" -m pip install --quiet --upgrade pip
".venv\Scripts\python.exe" -m pip install --quiet -r requirements.txt

REM Medien-Ordner anlegen
if not exist "videos" mkdir videos
if not exist "images" mkdir images
if not exist "audio"  mkdir audio

REM Server im Hintergrund starten
echo [*] Starte Server auf http://localhost:5000 ...
start "" /min ".venv\Scripts\python.exe" main.py

REM Kurz warten und Browser oeffnen
timeout /t 3 /nobreak >nul
start "" "http://localhost:5000/"

echo.
echo Server laeuft. Fenster schliessen oder Strg+C im Server-Fenster zum Beenden.
echo (Ohne Ultraschallsensor wird nichts gemessen. Fuer eine Webcam im Admin
echo  unter "Abstandsquelle" auf "Kamera" stellen -- siehe docs/sensoren.md.)
echo.
pause
