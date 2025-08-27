#!/bin/bash
# VLC-Reparatur-Script für Raspberry Pi

echo "=== VLC Komplett-Installation für Raspberry Pi ==="

# 1. Alte Installation entfernen
echo "1. Entferne alte VLC-Installation..."
sudo apt remove --purge vlc vlc-bin vlc-plugin-* -y
sudo apt autoremove -y

# 2. Repository aktualisieren
echo "2. Aktualisiere Paket-Repository..."
sudo apt update

# 3. VLC komplett neu installieren
echo "3. Installiere VLC neu..."
sudo apt install -y vlc vlc-bin vlc-plugin-base vlc-plugin-video-output
sudo apt install -y vlc-plugin-visualization vlc-data

# 4. Python VLC-Bindings
echo "4. Installiere Python VLC-Modul..."
pip3 install --upgrade python-vlc

# 5. Abhängigkeiten prüfen
echo "5. Prüfe VLC-Installation..."
vlc --version
echo ""

# 6. Python-Modul testen
echo "6. Teste Python VLC-Modul..."
python3 -c "
try:
    import vlc
    print('✓ VLC Python-Modul OK')
    
    # Instance-Test ohne Parameter
    inst = vlc.Instance()
    if inst is None:
        print('✗ VLC Instance ist None')
    else:
        print('✓ VLC Instance OK')
        
        # Media Player Test
        player = inst.media_player_new()
        if player is None:
            print('✗ Media Player ist None')
        else:
            print('✓ Media Player OK')
            
except Exception as e:
    print(f'✗ VLC-Test fehlgeschlagen: {e}')
"

echo ""
echo "=== Installation abgeschlossen ==="
echo "Testen Sie nun: python3 test_imports.py"
