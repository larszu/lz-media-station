#!/usr/bin/env python3
"""
FACES Exhibition - Einfaches Web Interface für Content-Upload
Mobile-friendly Interface für schnelle Video/Audio/Bild-Updates
"""

from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_socketio import SocketIO, emit
import json
import os
from pathlib import Path
from datetime import datetime
import threading

app = Flask(__name__)
app.config['SECRET_KEY'] = 'faces_exhibition_2024'
socketio = SocketIO(app, cors_allowed_origins="*")

class FacesWebInterface:
    def __init__(self):
        self.stations = {}  # Live-Status aller Stationen
        self.exhibition_active = False
        
        # Einfache Konfiguration
        self.config = {
            'global_ambient_audio': 'gemurmel_basis.wav',
            'ambient_volume': 0.3,
            'interaction_volume': 0.8,
            'ducking_level': 0.1,  # Wie stark Ambient gedämpft wird
            'fade_duration': 2.0
        }
        
    def init_database(self):
        """Initialisiert SQLite für Besucheranalytics"""
        conn = sqlite3.connect('faces_exhibition.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS interactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                station_id TEXT,
                timestamp DATETIME,
                duration REAL,
                visitor_count INTEGER,
                content_played TEXT,
                interaction_type TEXT
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS station_status (
                station_id TEXT PRIMARY KEY,
                last_heartbeat DATETIME,
                is_active BOOLEAN,
                current_content TEXT,
                error_count INTEGER
            )
        ''')
        
        conn.commit()
        conn.close()

web_interface = FacesWebInterface()

@app.route('/')
def dashboard():
    """Haupt-Dashboard für Exhibition Management"""
    return render_template('dashboard.html', 
                         stations=web_interface.stations,
                         exhibition_active=web_interface.exhibition_active)

@app.route('/api/stations')
def get_stations():
    """API: Alle Stationen und deren Status"""
    return jsonify({
        'stations': web_interface.stations,
        'exhibition_active': web_interface.exhibition_active,
        'total_interactions_today': get_daily_interaction_count()
    })

@app.route('/api/station/<station_id>/config', methods=['GET', 'POST'])
def station_config(station_id):
    """API: Station-Konfiguration abrufen/setzen"""
    if request.method == 'GET':
        return jsonify(web_interface.config_manager.station_configs.get(station_id, {}))
    
    elif request.method == 'POST':
        config = request.json
        web_interface.config_manager.station_configs[station_id] = config
        web_interface.config_manager.save_configs()
        
        # Live-Update an Station senden
        socketio.emit('config_update', {
            'station_id': station_id,
            'config': config
        }, room=f'station_{station_id}')
        
        return jsonify({'status': 'success'})

@app.route('/api/content/upload', methods=['POST'])
def upload_content():
    """API: Content-Upload für Stationen"""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    station_id = request.form.get('station_id', 'all')
    content_type = request.form.get('content_type', 'auto')
    
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    # Content-Typ automatisch erkennen
    if content_type == 'auto':
        ext = Path(file.filename).suffix.lower()
        if ext in ['.jpg', '.jpeg', '.png', '.gif']:
            content_type = 'images'
        elif ext in ['.mp4', '.avi', '.mov', '.mkv']:
            content_type = 'videos'
        elif ext in ['.mp3', '.wav', '.ogg', '.m4a']:
            content_type = 'audio'
        else:
            return jsonify({'error': 'Unsupported file type'}), 400
    
    # Datei speichern
    if station_id == 'all':
        # Zu allen Stationen verteilen
        for sid in web_interface.stations.keys():
            save_path = Path(f'content/{sid}/{content_type}') 
            save_path.mkdir(parents=True, exist_ok=True)
            file.save(save_path / file.filename)
    else:
        save_path = Path(f'content/{station_id}/{content_type}')
        save_path.mkdir(parents=True, exist_ok=True) 
        file.save(save_path / file.filename)
    
    # Stationen über neuen Content informieren
    socketio.emit('content_updated', {
        'station_id': station_id,
        'content_type': content_type,
        'filename': file.filename
    })
    
    return jsonify({'status': 'success', 'filename': file.filename})

@app.route('/api/exhibition/control', methods=['POST'])
def exhibition_control():
    """API: Exhibition starten/stoppen/pausieren"""
    action = request.json.get('action')
    
    if action == 'start':
        web_interface.exhibition_active = True
        socketio.emit('exhibition_control', {'action': 'start'})
        
    elif action == 'stop':
        web_interface.exhibition_active = False
        socketio.emit('exhibition_control', {'action': 'stop'})
        
    elif action == 'pause':
        socketio.emit('exhibition_control', {'action': 'pause'})
    
    return jsonify({'status': 'success', 'action': action})

@app.route('/api/analytics/interactions')
def get_interaction_analytics():
    """API: Interaktions-Analytics"""
    conn = sqlite3.connect('faces_exhibition.db')
    cursor = conn.cursor()
    
    # Interaktionen der letzten 24h
    cursor.execute('''
        SELECT station_id, COUNT(*) as count, AVG(duration) as avg_duration
        FROM interactions 
        WHERE timestamp > datetime('now', '-1 day')
        GROUP BY station_id
    ''')
    
    station_stats = cursor.fetchall()
    
    # Beliebteste Zeiten
    cursor.execute('''
        SELECT strftime('%H', timestamp) as hour, COUNT(*) as count
        FROM interactions
        WHERE timestamp > datetime('now', '-1 day') 
        GROUP BY hour
        ORDER BY hour
    ''')
    
    hourly_stats = cursor.fetchall()
    conn.close()
    
    return jsonify({
        'station_stats': [{'station_id': s[0], 'interactions': s[1], 'avg_duration': s[2]} for s in station_stats],
        'hourly_stats': [{'hour': int(h[0]), 'interactions': h[1]} for h in hourly_stats]
    })

# WebSocket Events für Live-Updates
@socketio.on('station_connect')
def handle_station_connect(data):
    """Station meldet sich am Web-Interface an"""
    station_id = data['station_id']
    web_interface.stations[station_id] = {
        'id': station_id,
        'status': 'online',
        'last_heartbeat': datetime.now().isoformat(),
        'current_content': None,
        'visitor_present': False
    }
    
    # Station einem Room zuweisen für gezielte Updates
    join_room(f'station_{station_id}')
    emit('station_registered', {'station_id': station_id})

@socketio.on('station_heartbeat')
def handle_station_heartbeat(data):
    """Regelmäßiger Heartbeat von Stationen"""
    station_id = data['station_id']
    if station_id in web_interface.stations:
        web_interface.stations[station_id].update({
            'last_heartbeat': datetime.now().isoformat(),
            'status': data.get('status', 'online'),
            'current_content': data.get('current_content'),
            'visitor_present': data.get('visitor_present', False),
            'error_count': data.get('error_count', 0)
        })
    
    # Status an Dashboard weiterleiten
    emit('station_status_update', {
        'station_id': station_id,
        'data': web_interface.stations[station_id]
    }, broadcast=True)

@socketio.on('interaction_logged')
def handle_interaction_logged(data):
    """Station meldet Besucher-Interaktion"""
    # In Datenbank speichern
    conn = sqlite3.connect('faces_exhibition.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO interactions 
        (station_id, timestamp, duration, visitor_count, content_played, interaction_type)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (
        data['station_id'],
        datetime.now(),
        data.get('duration', 0),
        data.get('visitor_count', 1), 
        data.get('content_played', ''),
        data.get('interaction_type', 'proximity')
    ))
    
    conn.commit()
    conn.close()
    
    # Live-Update an Dashboard
    emit('new_interaction', data, broadcast=True)

def get_daily_interaction_count():
    """Heutige Interaktions-Anzahl"""
    conn = sqlite3.connect('faces_exhibition.db')
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM interactions WHERE date(timestamp) = date('now')")
    count = cursor.fetchone()[0]
    conn.close()
    return count

if __name__ == '__main__':
    # Content-Ordner erstellen
    Path('content').mkdir(exist_ok=True)
    Path('templates').mkdir(exist_ok=True)
    Path('static').mkdir(exist_ok=True)
    
    print("🎭 FACES Exhibition Web Interface gestartet!")
    print("📱 Dashboard: http://localhost:8080")
    print("🚀 Mobile-optimiert für Content-Upload und Station-Management")
    
    socketio.run(app, host='0.0.0.0', port=8080, debug=True)