#!/usr/bin/env python3
"""
FACES Exhibition - Einfaches Web Interface für Content-Upload
Mobile-friendly Interface für Video/Audio/Bild-Upload ohne Schnickschnack
"""

from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_socketio import SocketIO, emit
import json
import os
from pathlib import Path
from datetime import datetime
import shutil

app = Flask(__name__)
app.config['SECRET_KEY'] = 'faces_exhibition_2024'
socketio = SocketIO(app, cors_allowed_origins="*")

class SimpleFacesInterface:
    def __init__(self):
        self.stations = {}  # Live-Status aller Stationen
        self.exhibition_active = False
        
        # Einfache globale Einstellungen
        self.global_config = {
            'ambient_audio_file': 'gemurmel_basis.wav',
            'ambient_volume': 0.3,
            'interaction_volume': 0.8,
            'audio_ducking_level': 0.1,  # Ambient-Dämpfung bei Interaktion
            'fade_duration': 2.0,
            'sensor_distance': 100,  # cm
            'interaction_timeout': 30  # Sekunden
        }

web_interface = SimpleFacesInterface()

@app.route('/')
def dashboard():
    """Einfaches Dashboard - nur das Nötige"""
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>FACES Exhibition Control</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body { font-family: Arial; margin: 20px; background: #f5f5f5; }
            .container { max-width: 800px; margin: 0 auto; background: white; padding: 20px; border-radius: 10px; }
            .upload-area { border: 2px dashed #ccc; padding: 40px; text-align: center; margin: 20px 0; }
            .upload-area.dragover { border-color: #007cba; background: #f0f8ff; }
            .station-list { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; }
            .station { padding: 15px; border: 1px solid #ddd; border-radius: 5px; }
            .station.online { border-color: #4CAF50; }
            .station.offline { border-color: #f44336; }
            button { padding: 10px 20px; background: #007cba; color: white; border: none; border-radius: 5px; cursor: pointer; }
            button:hover { background: #005a87; }
            .config-section { margin: 20px 0; padding: 15px; background: #f9f9f9; border-radius: 5px; }
            input, select { padding: 8px; margin: 5px; border: 1px solid #ddd; border-radius: 3px; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🎭 FACES Exhibition Control</h1>
            
            <div class="config-section">
                <h3>📁 Content Upload</h3>
                <div class="upload-area" id="uploadArea">
                    <p>📱 Drag & Drop Files Here</p>
                    <p>oder <button onclick="document.getElementById('fileInput').click()">Dateien Auswählen</button></p>
                    <input type="file" id="fileInput" multiple accept="video/*,audio/*,image/*" style="display:none">
                </div>
                
                <label>Upload zu Station:</label>
                <select id="targetStation">
                    <option value="all">🔄 Alle Stationen</option>
                </select>
            </div>
            
            <div class="config-section">
                <h3>🎚️ Audio Settings</h3>
                <label>Ambient Volume: <input type="range" id="ambientVolume" min="0" max="1" step="0.1" value="0.3"></label>
                <label>Interaction Volume: <input type="range" id="interactionVolume" min="0" max="1" step="0.1" value="0.8"></label>
                <label>Audio Ducking: <input type="range" id="duckingLevel" min="0" max="1" step="0.1" value="0.1"></label>
                <button onclick="updateAudioSettings()">💾 Audio Settings Speichern</button>
            </div>
            
            <div class="config-section">
                <h3>📊 Station Status</h3>
                <div class="station-list" id="stationList">
                    <div class="station offline">
                        <h4>Station 1</h4>
                        <p>Status: Offline</p>  
                        <p>Content: -</p>
                    </div>
                </div>
            </div>
            
            <div class="config-section">
                <button onclick="startExhibition()" id="startBtn">▶️ Exhibition Starten</button>
                <button onclick="stopExhibition()" id="stopBtn" style="background: #f44336;">⏹️ Exhibition Stoppen</button>
            </div>
        </div>
        
        <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
        <script>
            const socket = io();
            
            // File Upload
            const uploadArea = document.getElementById('uploadArea');
            const fileInput = document.getElementById('fileInput');
            
            uploadArea.addEventListener('dragover', (e) => {
                e.preventDefault();
                uploadArea.classList.add('dragover');
            });
            
            uploadArea.addEventListener('dragleave', () => {
                uploadArea.classList.remove('dragover');
            });
            
            uploadArea.addEventListener('drop', (e) => {
                e.preventDefault();
                uploadArea.classList.remove('dragover');
                handleFiles(e.dataTransfer.files);
            });
            
            fileInput.addEventListener('change', (e) => {
                handleFiles(e.target.files);
            });
            
            function handleFiles(files) {
                const targetStation = document.getElementById('targetStation').value;
                
                for (let file of files) {
                    const formData = new FormData();
                    formData.append('file', file);
                    formData.append('station_id', targetStation);
                    
                    fetch('/api/content/upload', {
                        method: 'POST',
                        body: formData
                    })
                    .then(response => response.json())
                    .then(data => {
                        if (data.status === 'success') {
                            alert(`📁 ${file.name} erfolgreich hochgeladen!`);
                        } else {
                            alert(`❌ Fehler beim Upload: ${data.error}`);
                        }
                    });
                }
            }
            
            function updateAudioSettings() {
                const settings = {
                    ambient_volume: document.getElementById('ambientVolume').value,
                    interaction_volume: document.getElementById('interactionVolume').value,
                    audio_ducking_level: document.getElementById('duckingLevel').value
                };
                
                fetch('/api/audio/settings', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(settings)
                })
                .then(response => response.json())
                .then(data => alert('🎚️ Audio Settings gespeichert!'));
            }
            
            function startExhibition() {
                fetch('/api/exhibition/start', {method: 'POST'})
                .then(() => alert('▶️ Exhibition gestartet!'));
            }
            
            function stopExhibition() {
                fetch('/api/exhibition/stop', {method: 'POST'})
                .then(() => alert('⏹️ Exhibition gestoppt!'));
            }
            
            // Station Status Updates
            socket.on('station_status', function(data) {
                updateStationDisplay(data);
            });
            
            function updateStationDisplay(stations) {
                const list = document.getElementById('stationList');
                const select = document.getElementById('targetStation');
                
                // Station Liste aktualisieren
                list.innerHTML = '';
                select.innerHTML = '<option value="all">🔄 Alle Stationen</option>';
                
                Object.values(stations).forEach(station => {
                    // Station Status
                    const div = document.createElement('div');
                    div.className = `station ${station.status}`;
                    div.innerHTML = `
                        <h4>${station.id}</h4>
                        <p>Status: ${station.status}</p>
                        <p>Content: ${station.current_content || '-'}</p>
                    `;
                    list.appendChild(div);
                    
                    // Station Select Option
                    const option = document.createElement('option');
                    option.value = station.id;
                    option.textContent = station.id;
                    select.appendChild(option);
                });
            }
        </script>
    </body>
    </html>
    '''

@app.route('/api/content/upload', methods=['POST'])
def upload_content():
    """Content-Upload - Videos, Audio, Bilder"""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    station_id = request.form.get('station_id', 'all')
    
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    # Content-Typ basierend auf Dateiendung
    ext = Path(file.filename).suffix.lower()
    if ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp']:
        content_type = 'images'
    elif ext in ['.mp4', '.avi', '.mov', '.mkv', '.webm', '.m4v']:
        content_type = 'videos'
    elif ext in ['.mp3', '.wav', '.ogg', '.m4a', '.aac']:
        content_type = 'audio'
    else:
        return jsonify({'error': f'Unsupported file type: {ext}'}), 400
    
    # Sichere Dateinamen
    safe_filename = file.filename.replace(' ', '_').replace('(', '').replace(')', '')
    
    # Datei speichern
    if station_id == 'all':
        # Zu allen Stationen verteilen (falls welche vorhanden)
        if web_interface.stations:
            for sid in web_interface.stations.keys():
                save_path = Path(f'content/{sid}/{content_type}') 
                save_path.mkdir(parents=True, exist_ok=True)
                file.seek(0)  # File pointer zurücksetzen
                file.save(save_path / safe_filename)
        else:
            # Fallback: Zu globalem content Ordner
            save_path = Path(f'content/global/{content_type}')
            save_path.mkdir(parents=True, exist_ok=True) 
            file.save(save_path / safe_filename)
    else:
        save_path = Path(f'content/{station_id}/{content_type}')
        save_path.mkdir(parents=True, exist_ok=True) 
        file.save(save_path / safe_filename)
    
    # Stationen über neuen Content informieren
    socketio.emit('content_updated', {
        'station_id': station_id,
        'content_type': content_type,
        'filename': safe_filename
    })
    
    return jsonify({'status': 'success', 'filename': safe_filename, 'content_type': content_type})

@app.route('/api/audio/settings', methods=['POST'])
def update_audio_settings():
    """Audio-Einstellungen aktualisieren"""
    settings = request.json
    web_interface.global_config.update(settings)
    
    # An alle Stationen senden
    socketio.emit('audio_settings_update', web_interface.global_config)
    
    return jsonify({'status': 'success'})

@app.route('/api/exhibition/start', methods=['POST'])
def start_exhibition():
    """Exhibition starten"""
    web_interface.exhibition_active = True
    socketio.emit('exhibition_start', {'ambient_file': web_interface.global_config['ambient_audio_file']})
    return jsonify({'status': 'started'})

@app.route('/api/exhibition/stop', methods=['POST']) 
def stop_exhibition():
    """Exhibition stoppen"""
    web_interface.exhibition_active = False
    socketio.emit('exhibition_stop', {})
    return jsonify({'status': 'stopped'})

@app.route('/api/stations')
def get_stations():
    """Station Status"""
    return jsonify(web_interface.stations)

# WebSocket Events für Station-Kommunikation
@socketio.on('station_connect')
def handle_station_connect(data):
    """Station meldet sich an"""
    station_id = data['station_id']
    web_interface.stations[station_id] = {
        'id': station_id,
        'status': 'online',
        'last_heartbeat': datetime.now().isoformat(),
        'current_content': None,
        'visitor_present': False
    }
    
    emit('station_registered', {
        'station_id': station_id,
        'config': web_interface.global_config
    })
    
    # Status-Update an Web-Interface
    socketio.emit('station_status', web_interface.stations)

@socketio.on('station_heartbeat')
def handle_station_heartbeat(data):
    """Station Heartbeat"""
    station_id = data['station_id']
    if station_id in web_interface.stations:
        web_interface.stations[station_id].update({
            'last_heartbeat': datetime.now().isoformat(),
            'status': 'online',
            'current_content': data.get('current_content'),
            'visitor_present': data.get('visitor_present', False)
        })
    
    socketio.emit('station_status', web_interface.stations)

if __name__ == '__main__':
    # Content-Ordner erstellen
    Path('content').mkdir(exist_ok=True)
    
    print("🎭 FACES Exhibition - Simple Web Interface")
    print("📱 Dashboard: http://localhost:8080")
    print("📁 Drag & Drop Content-Upload")
    print("🎚️ Audio Ducking Controls")
    
    socketio.run(app, host='0.0.0.0', port=8080, debug=True)