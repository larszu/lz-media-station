@echo off
REM ===========================================================================
REM  LZ Media Station auf Windows starten.
REM
REM  ─── ZWEI BETRIEBSARTEN, und warum die zweite noetig ist ─────────────────
REM
REM    run_windows.bat            Doppelklick: einrichten, starten, Browser auf
REM    run_windows.bat --server   Vordergrund, kein Browser, kein `pause`
REM
REM  Die zweite ist die fuer die AV-Planner-Suite (2026-09-15). Bis dahin gab
REM  es nur die erste, und sie ist fuer einen Aufrufer unbrauchbar:
REM
REM    * `start "" /min ... main.py` koppelt den Server AB. Das Fenster, das
REM      ihn gestartet hat, ist sofort fertig — der Stopp-Knopf der Suite
REM      meldete "beendet", und der Server lief weiter. Beim naechsten Start
REM      belegte er den Port.
REM    * `pause` am Ende wartet auf eine Taste. Ein Aufrufer, der auf das
REM      Ende des Fensters wartet, wartet fuer immer.
REM
REM  Im Dienst-Modus laeuft `main.py` deshalb im VORDERGRUND: nur dann haengt
REM  der Prozess am Aufrufer, und nur dann beendet ihn dessen Stopp wieder.
REM
REM  Alle weiteren Schalter werden an `main.py` durchgereicht.
REM ===========================================================================
SETLOCAL ENABLEDELAYEDEXPANSION
cd /d "%~dp0"

REM --- Betriebsart und durchgereichte Schalter trennen ----------------------
set "DIENST="
set "ARGS="
:naechstes
if "%~1"=="" goto fertig
if /I "%~1"=="--server" (
    set "DIENST=1"
) else (
    set "ARGS=!ARGS! %1"
)
shift
goto naechstes
:fertig

REM --- Interpreter finden: py, dann python ---------------------------------
REM  `py` ist der Launcher des offiziellen Installers und der verlaesslichere
REM  der beiden: `python` kann auf den Store-Alias zeigen, der nur den Store
REM  oeffnet.
set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY (
    where python >nul 2>nul && set "PY=python"
)
if not defined PY (
    echo [FEHLER] Python nicht gefunden.
    echo Bitte Python 3.10+ installieren: https://www.python.org/downloads/
    if not defined DIENST pause
    exit /b 1
)

REM --- Virtuelle Umgebung + Abhaengigkeiten --------------------------------
if not exist ".venv\Scripts\python.exe" (
    echo [*] Erstelle virtuelle Umgebung .venv ...
    %PY% -m venv .venv
    if errorlevel 1 (
        if not defined DIENST pause
        exit /b 1
    )
)
set "VENV=.venv\Scripts\python.exe"

REM Nur installieren, wenn etwas fehlt: ein `pip install` bei JEDEM Start
REM kostet auf einem Messeplatz-WLAN mehr Zeit als der ganze Aufbau.
"%VENV%" -c "import flask" >nul 2>nul
if errorlevel 1 (
    echo [*] Installiere Abhaengigkeiten ...
    "%VENV%" -m pip install --quiet --upgrade pip
    "%VENV%" -m pip install --quiet -r requirements.txt
    if errorlevel 1 (
        echo [FEHLER] Abhaengigkeiten liessen sich nicht installieren.
        if not defined DIENST pause
        exit /b 1
    )
)

if not exist "videos" mkdir videos
if not exist "images" mkdir images
if not exist "audio"  mkdir audio

if defined DIENST (
    REM Vordergrund, kein Browser, kein pause — siehe Kopf.
    "%VENV%" main.py !ARGS!
    exit /b !ERRORLEVEL!
)

echo ========================================================
echo   LZ Media Station - Windows
echo ========================================================
echo.
echo   Web-Admin:  http://localhost:5000/
echo   Anzeige:    http://localhost:5000/display
echo.
echo   Ohne Ultraschallsensor wird nichts gemessen - es loest nichts aus.
echo   Fuer eine Webcam im Admin unter "Abstandsquelle" auf "Kamera"
echo   stellen (siehe docs/sensoren.md).
echo   Zum Beenden Strg-C.
echo.

REM Der Browser geht auf, sobald der Server antwortet — aber der Server
REM laeuft trotzdem im Vordergrund. `start` gilt hier dem BROWSER und nicht
REM dem Server; das ist der Unterschied zur alten Fassung.
start "" /b cmd /c "timeout /t 3 /nobreak >nul & start "" http://localhost:5000/"
"%VENV%" main.py !ARGS!
pause
