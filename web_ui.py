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

    @app.route("/api/identity")
    def api_identity():
        """Station-Identität für Discovery / Manager-App."""
        import uuid, platform
        id_path = os.path.join(BASE_DIR, ".station_id")
        try:
            if os.path.exists(id_path):
                with open(id_path, "r") as f:
                    sid = f.read().strip()
            else:
                sid = uuid.uuid4().hex
                with open(id_path, "w") as f:
                    f.write(sid)
        except Exception:
            sid = "unknown"
        return jsonify({
            "id": sid,
            "name": controller.config.get("system_name", "FACES Station"),
            "version": "2.1.0",
            "hostname": platform.node(),
            "active": controller.active,
            "state": controller.state,
        })

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
        """Entfernt eine Datei nur aus den Zonen-Zuordnungen, löscht sie NICHT vom Pi."""
        if media_type not in MEDIA_DIRS:
            return jsonify({"error": "Ungültiger Typ"}), 400
        safe = secure_filename(name)
        removed = False
        for zone in ("near", "far"):
            zc = controller.config.get(zone, {})
            if media_type in zc and safe in zc[media_type]:
                zc[media_type].remove(safe)
                removed = True
        if removed:
            controller.save_config()
        return jsonify({"ok": True, "removed_from_zones": removed})

    @app.route("/api/start", methods=["POST"])
    def api_start():
        controller.start()
        return jsonify({"ok": True})

    @app.route("/api/stop", methods=["POST"])
    def api_stop():
        controller.stop()
        return jsonify({"ok": True})

    # --- System / Network ---
    @app.route("/api/system/network", methods=["GET"])
    def api_system_network_get():
        import subprocess
        info = {"connection": None, "interface": None, "method": None,
                "addresses": [], "gateway": None, "dns": [], "available_connections": []}
        try:
            out = subprocess.check_output(
                ["nmcli", "-t", "-f", "NAME,TYPE,DEVICE,STATE", "connection", "show"],
                timeout=5).decode()
            for line in out.strip().splitlines():
                parts = line.split(":")
                if len(parts) >= 4:
                    name, ctype, dev, state = parts[0], parts[1], parts[2], parts[3]
                    if ctype in ("802-3-ethernet", "ethernet") or "wifi" in ctype:
                        info["available_connections"].append(
                            {"name": name, "type": ctype, "device": dev, "state": state})
                        if state == "activated" and not info["connection"]:
                            info["connection"] = name
                            info["interface"] = dev
        except Exception as e:
            info["error"] = "nmcli nicht verfügbar: " + str(e)
            return jsonify(info), 200
        if info["connection"]:
            try:
                out = subprocess.check_output(
                    ["nmcli", "-t", "-f",
                     "ipv4.method,IP4.ADDRESS,IP4.GATEWAY,IP4.DNS",
                     "connection", "show", info["connection"]],
                    timeout=5).decode()
                for line in out.strip().splitlines():
                    if ":" not in line:
                        continue
                    k, _, v = line.partition(":")
                    if k == "ipv4.method":
                        info["method"] = v
                    elif k.startswith("IP4.ADDRESS"):
                        if v:
                            info["addresses"].append(v)
                    elif k == "IP4.GATEWAY":
                        info["gateway"] = v or None
                    elif k.startswith("IP4.DNS"):
                        if v:
                            info["dns"].append(v)
            except Exception as e:
                info["error"] = str(e)
        return jsonify(info)

    @app.route("/api/system/network", methods=["POST"])
    def api_system_network_set():
        import subprocess, re
        data = request.get_json() or {}
        connection = data.get("connection")
        method = data.get("method")  # "auto" oder "manual"
        if not connection or method not in ("auto", "manual"):
            return jsonify({"error": "connection und method (auto|manual) erforderlich"}), 400
        ip_re = re.compile(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}(/\d{1,2})?$")
        try:
            if method == "auto":
                cmd = ["sudo", "-n", "nmcli", "connection", "modify", connection,
                       "ipv4.method", "auto",
                       "ipv4.addresses", "",
                       "ipv4.gateway", "",
                       "ipv4.dns", ""]
                subprocess.check_output(cmd, stderr=subprocess.STDOUT, timeout=10)
            else:
                addr = (data.get("address") or "").strip()
                gw = (data.get("gateway") or "").strip()
                dns = (data.get("dns") or "").strip()
                if not ip_re.match(addr):
                    return jsonify({"error": "Adresse muss CIDR sein, z.B. 192.168.1.50/24"}), 400
                if "/" not in addr:
                    addr = addr + "/24"
                cmd = ["sudo", "-n", "nmcli", "connection", "modify", connection,
                       "ipv4.method", "manual",
                       "ipv4.addresses", addr,
                       "ipv4.gateway", gw,
                       "ipv4.dns", dns]
                subprocess.check_output(cmd, stderr=subprocess.STDOUT, timeout=10)
            # Verbindung neu aktivieren
            try:
                subprocess.check_output(
                    ["sudo", "-n", "nmcli", "connection", "down", connection],
                    stderr=subprocess.STDOUT, timeout=10)
            except subprocess.CalledProcessError:
                pass
            subprocess.check_output(
                ["sudo", "-n", "nmcli", "connection", "up", connection],
                stderr=subprocess.STDOUT, timeout=15)
            return jsonify({"ok": True})
        except subprocess.CalledProcessError as e:
            return jsonify({"error": "nmcli: " + e.output.decode(errors="ignore")}), 500
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/system/reboot", methods=["POST"])
    def api_system_reboot():
        import subprocess
        try:
            subprocess.Popen(["sudo", "-n", "reboot"])
            return jsonify({"ok": True})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/system/wifi", methods=["GET"])
    def api_system_wifi_get():
        import subprocess
        info = {"enabled": False, "current_ssid": None, "networks": []}
        try:
            out = subprocess.check_output(
                ["nmcli", "-t", "-f", "WIFI", "radio"], timeout=5).decode().strip()
            info["enabled"] = (out.lower() == "enabled")
        except Exception as e:
            info["error"] = "nmcli nicht verfügbar: " + str(e)
            return jsonify(info), 200
        if info["enabled"]:
            try:
                out = subprocess.check_output(
                    ["nmcli", "-t", "-f", "ACTIVE,SSID,SIGNAL,SECURITY", "device", "wifi", "list"],
                    timeout=8).decode()
                seen = set()
                for line in out.strip().splitlines():
                    parts = line.split(":")
                    if len(parts) < 4:
                        continue
                    active, ssid, signal, security = parts[0], parts[1], parts[2], ":".join(parts[3:])
                    if not ssid or ssid in seen:
                        continue
                    seen.add(ssid)
                    if active == "yes":
                        info["current_ssid"] = ssid
                    info["networks"].append({
                        "ssid": ssid,
                        "signal": int(signal) if signal.isdigit() else 0,
                        "security": security,
                        "active": active == "yes",
                    })
                info["networks"].sort(key=lambda n: -n["signal"])
            except Exception as e:
                info["error"] = str(e)
        return jsonify(info)

    @app.route("/api/system/wifi", methods=["POST"])
    def api_system_wifi_set():
        import subprocess
        data = request.get_json() or {}
        try:
            if "enabled" in data:
                state = "on" if data["enabled"] else "off"
                subprocess.check_output(
                    ["sudo", "-n", "nmcli", "radio", "wifi", state],
                    stderr=subprocess.STDOUT, timeout=10)
                return jsonify({"ok": True})
            ssid = (data.get("ssid") or "").strip()
            password = data.get("password") or ""
            if not ssid:
                return jsonify({"error": "ssid erforderlich"}), 400
            cmd = ["sudo", "-n", "nmcli", "device", "wifi", "connect", ssid]
            if password:
                cmd += ["password", password]
            subprocess.check_output(cmd, stderr=subprocess.STDOUT, timeout=30)
            return jsonify({"ok": True})
        except subprocess.CalledProcessError as e:
            return jsonify({"error": "nmcli: " + e.output.decode(errors="ignore")}), 500
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    # --- Media file serving ---
    @app.route("/media/<media_type>/<path:filename>")
    def serve_media(media_type, filename):
        if media_type not in MEDIA_DIRS:
            return "Not found", 404
        return send_from_directory(MEDIA_DIRS[media_type], secure_filename(filename))

    return app
