#!/bin/bash
# Kompletter Setup-Test für Pi Media Station

echo "🔧 Pi Media Station - Setup-Test"
echo "================================="

# 1. Python-Version prüfen
echo "1. Python-Version:"
python3 --version

# 2. VLC prüfen
echo -e "\n2. VLC Installation:"
if command -v vlc &> /dev/null; then
    vlc --version | head -1
    echo "✅ VLC verfügbar"
else
    echo "❌ VLC nicht gefunden"
    echo "   Lösung: sudo apt install vlc vlc-bin vlc-plugin-base"
fi

# 3. Python-Module testen
echo -e "\n3. Python-Module:"
echo "   Teste Import..."

# Teste alle wichtigen Module
python3 -c "
import sys
modules = {
    'tkinter': 'GUI Framework',
    'vlc': 'VLC Python Bindings', 
    'os': 'Betriebssystem',
    'threading': 'Threading Support',
    'time': 'Zeit-Funktionen',
    'json': 'JSON Support',
    'subprocess': 'Prozess-Steuerung'
}

success = 0
total = len(modules)

for module, desc in modules.items():
    try:
        __import__(module)
        print(f'   ✅ {module:12} - {desc}')
        success += 1
    except ImportError as e:
        print(f'   ❌ {module:12} - {desc} (FEHLT: {e})')

print(f'\n   Status: {success}/{total} Module verfügbar')

# Spezielle VLC-Tests
try:
    import vlc
    instance = vlc.Instance()
    if instance:
        print('   ✅ VLC Instance kann erstellt werden')
        player = instance.media_player_new()
        if player:
            print('   ✅ VLC Media Player kann erstellt werden')
        else:
            print('   ❌ VLC Media Player Erstellung fehlgeschlagen')
    else:
        print('   ❌ VLC Instance Erstellung fehlgeschlagen')
except Exception as e:
    print(f'   ❌ VLC Test fehlgeschlagen: {e}')
"

# 4. GPIO-Test (nur auf Pi)
echo -e "\n4. GPIO-Test:"
if [[ $(uname -m) == arm* ]] || [[ $(uname -m) == aarch64 ]]; then
    echo "   Raspberry Pi erkannt"
    python3 -c "
try:
    import RPi.GPIO as GPIO
    print('   ✅ RPi.GPIO verfügbar')
except ImportError:
    print('   ❌ RPi.GPIO nicht verfügbar')
    print('   Lösung: pip3 install RPi.GPIO')
"
else
    echo "   Kein Raspberry Pi - GPIO-Test übersprungen"
fi

# 5. Projektstruktur prüfen
echo -e "\n5. Projektstruktur:"
files=(
    "main.py:Haupt-Einstiegspunkt"
    "gui_vlc.py:VLC-GUI"
    "media_player_vlc.py:VLC-Media-Player"
    "sensor.py:Sensor-Thread"
    "config.py:Konfiguration"
    "requirements.txt:Abhängigkeiten"
)

for item in "${files[@]}"; do
    file="${item%%:*}"
    desc="${item##*:}"
    if [[ -f "$file" ]]; then
        size=$(wc -l < "$file" 2>/dev/null || echo "?")
        echo "   ✅ $file ($size Zeilen) - $desc"
    else
        echo "   ❌ $file - $desc (FEHLT)"
    fi
done

# 6. Media-Ordner prüfen
echo -e "\n6. Media-Ordner:"
folders=("videos" "images" "audio")
for folder in "${folders[@]}"; do
    if [[ -d "$folder" ]]; then
        count=$(find "$folder" -type f 2>/dev/null | wc -l)
        echo "   ✅ $folder/ ($count Dateien)"
    else
        echo "   ⚠️  $folder/ (nicht vorhanden, wird erstellt)"
        mkdir -p "$folder"
    fi
done

# 7. Berechtigungen prüfen (nur auf Linux)
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    echo -e "\n7. Berechtigungen:"
    if [[ -r "main.py" && -x "main.py" ]]; then
        echo "   ✅ main.py ausführbar"
    else
        echo "   ⚠️  Setze Ausführungsrechte..."
        chmod +x main.py
    fi
fi

# 8. Zusammenfassung
echo -e "\n🎯 SETUP-STATUS:"
echo "================"

# Teste ob System startfähig ist
if python3 -c "
import sys
try:
    from gui_vlc import VLCMediaStationGUI
    from sensor import SensorThread
    print('✅ Alle Hauptkomponenten importierbar')
    sys.exit(0)
except ImportError as e:
    print(f'❌ Import-Fehler: {e}')
    sys.exit(1)
"; then
    echo "🟢 SYSTEM BEREIT - Kann gestartet werden!"
    echo ""
    echo "🚀 Zum Starten:"
    echo "   python3 main.py                # Test-Modus"  
    echo "   python3 main.py --kiosk        # Kiosk-Modus"
    echo "   python3 main.py --dummy-sensor # Mit Dummy-Sensor"
else
    echo "🔴 SYSTEM NICHT BEREIT"
    echo ""
    echo "🔧 Nächste Schritte:"
    echo "1. Fehlende Module installieren: pip3 install -r requirements.txt"
    echo "2. VLC installieren: sudo apt install vlc vlc-bin vlc-plugin-base"
    echo "3. Test wiederholen: ./setup_test.sh"
fi

echo ""
echo "📋 Für detaillierte Analyse: python3 test_imports.py"