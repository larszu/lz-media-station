"""Flask Web-UI + Media-Server für FACES Media Station"""
import os
import socket
from flask import Flask, render_template, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MEDIA_DIRS = {
    "videos": os.path.join(BASE_DIR, "videos"),
    "images": os.path.join(BASE_DIR, "images"),
    "audio": os.path.join(BASE_DIR, "audio"),
}
ALLOWED_EXT = {
    "videos": {".mp4", ".mkv", ".avi", ".mov", ".webm"},
    "images": {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"},
    "audio": {".mp3", ".wav", ".ogg", ".m4a", ".flac", ".aac"},
}


def _detect_lan_ip():
    """Beste Schätzung der LAN-IP."""
    # 1) UDP-Trick (funktioniert wenn Default-Route da ist)
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        ip = s.getsockname()[0]
        if ip and not ip.startswith("127."):
            return ip
    except Exception:
        pass
    finally:
        s.close()
    # 2) Fallback: alle aufgelösten IPs prüfen, erste nicht-Loopback nehmen
    try:
        host = socket.gethostname()
        for info in socket.getaddrinfo(host, None, socket.AF_INET):
            ip = info[4][0]
            if ip and not ip.startswith("127."):
                return ip
    except Exception:
        pass
    # 3) Letzter Ausweg: Linux 'hostname -I'
    try:
        import subprocess
        out = subprocess.check_output(["hostname", "-I"], timeout=2).decode().strip()
        for ip in out.split():
            if ip and not ip.startswith("127.") and ":" not in ip:
                return ip
    except Exception:
        pass
    return "127.0.0.1"


def create_app(controller):
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024 * 1024

    # --- Pages ---
    @app.route("/")
    def launch():
        return render_template("launch.html")

    @app.route("/admin")
    def admin():
        return render_template("admin.html")

    @app.route("/display")
    def display():
        return render_template("display.html")

    # --- API ---
    @app.route("/api/status")
    def api_status():
        cfg_ip = (controller.config.get("display_ip") or "").strip()
        port = controller.config.get("web_port", 5000)
        host_ip = cfg_ip or _detect_lan_ip()
        return jsonify({
            "distance": round(controller.sensor.distance, 3),
            "state": controller.state,
            "active": controller.active,
            "dummy_sensor": controller.sensor.use_dummy,
            "host_ip": host_ip,
            "web_port": port,
            "remote_url": "http://" + host_ip + ":" + str(port) + "/admin",
            "config": controller.config,
        })

    @app.route("/api/scene")
    def api_scene():
        return jsonify(controller.get_scene())

    @app.route("/api/config", methods=["POST"])
    def api_config():
        data = request.get_json()
        if not data:
            return jsonify({"error": "Keine Daten"}), 400
        simple = {
            "system_name": str, "threshold_m": float, "delay_s": float,
            "gpio_trigger": int, "gpio_echo": int, "web_port": int,
            "image_interval_s": float, "master_volume": int,
            "video_volume": int, "audio_volume": int,
            "video_resume": bool,
            "display_ip": str,
        }
        for key, cast in simple.items():
            if key in data:
                try:
                    controller.config[key] = cast(data[key])
                except (ValueError, TypeError):
                    pass
        for zone in ("near", "far"):
            if zone in data and isinstance(data[zone], dict):
                if not isinstance(controller.config.get(zone), dict):
                    controller.config[zone] = {"videos": [], "images": [], "audio": []}
                for mt in ("videos", "images", "audio"):
                    if mt in data[zone] and isinstance(data[zone][mt], list):
                        controller.config[zone][mt] = [
                            secure_filename(f) for f in data[zone][mt] if f
                        ]
        controller.save_config()
        return jsonify({"ok": True, "config": controller.config})

    @app.route("/api/media/<media_type>")
    def api_list_media(media_type):
        if media_type not in MEDIA_DIRS:
            return jsonify({"error": "Ungültiger Typ"}), 400
        d = MEDIA_DIRS[media_type]
        exts = ALLOWED_EXT[media_type]
        files = []
        if os.path.isdir(d):
            for f in sorted(os.listdir(d)):
                if os.path.splitext(f)[1].lower() in exts:
                    size = os.path.getsize(os.path.join(d, f)) / (1024 * 1024)
                    files.append({"name": f, "size_mb": round(size, 1)})
        return jsonify(files)

    @app.route("/api/upload/<media_type>", methods=["POST"])
    def api_upload(media_type):
        if media_type not in MEDIA_DIRS:
            return jsonify({"error": "Ungültiger Typ"}), 400
        if "file" not in request.files:
            return jsonify({"error": "Keine Datei"}), 400
        f = request.files["file"]
        if not f.filename:
            return jsonify({"error": "Kein Dateiname"}), 400
        name = secure_filename(f.filename)
        if os.path.splitext(name)[1].lower() not in ALLOWED_EXT[media_type]:
            return jsonify({"error": "Format nicht erlaubt"}), 400
        os.makedirs(MEDIA_DIRS[media_type], exist_ok=True)
        f.save(os.path.join(MEDIA_DIRS[media_type], name))
        return jsonify({"ok": True, "name": name})

    @app.route("/api/media/<media_type>/<name>", methods=["DELETE"])
    def api_delete_media(media_type, name):
        if media_type not in MEDIA_DIRS:
            return jsonify({"error": "Ungültiger Typ"}), 400
        safe = secure_filename(name)
        path = os.path.join(MEDIA_DIRS[media_type], safe)
        if os.path.isfile(path):
            os.remove(path)
            for zone in ("near", "far"):
                zc = controller.config.get(zone, {})
                if media_type in zc and safe in zc[media_type]:
                    zc[media_type].remove(safe)
            controller.save_config()
            return jsonify({"ok": True})
        return jsonify({"error": "Nicht gefunden"}), 404

    @app.route("/api/start", methods=["POST"])
    def api_start():
        controller.start()
        return jsonify({"ok": True})

    @app.route("/api/stop", methods=["POST"])
    def api_stop():
        controller.stop()
        return jsonify({"ok": True})

    # --- Media file serving ---
    @app.route("/media/<media_type>/<path:filename>")
    def serve_media(media_type, filename):
        if media_type not in MEDIA_DIRS:
            return "Not found", 404
        return send_from_directory(MEDIA_DIRS[media_type], secure_filename(filename))

    return app
