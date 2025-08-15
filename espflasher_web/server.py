# server.py
from flask import Flask, request, Response, send_from_directory, jsonify
import os
import subprocess
from flask_cors import CORS
import json
import traceback
import shutil
import socket
from pathlib import Path
from datetime import datetime, timezone
import uuid

# ---------- Flask setup ----------
app = Flask(__name__, static_folder="/app/www", static_url_path="/")
# Wenn UI über Ingress/gleiches Origin läuft, ist CORS nicht nötig – ansonsten hier eingeschränkt lassen
CORS(app)

# ---------- Paths ----------
YAML_DIR = "/data/yaml"
OUTPUT_DIR = "/app/www/firmware"
os.makedirs(YAML_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

DEVICES_FILE = Path("/data/devices.json")

# ---------- Helpers: devices registry ----------
def _load_devices():
    if DEVICES_FILE.exists():
        try:
            return json.loads(DEVICES_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"devices": [], "version": 1}

def _save_devices(db):
    DEVICES_FILE.write_text(json.dumps(db, ensure_ascii=False, indent=2), encoding="utf-8")

def _iso_now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

def detect_platform_from_yaml(text: str) -> str:
    t = text.lower()
    if "\nesp8266:" in t:
        return "ESP8266"
    if "\nesp32:" in t:
        return "ESP32"
    return "UNKNOWN"

def chip_family_for_platform(platform: str) -> str:
    return "ESP8266" if platform.upper() == "ESP8266" else "ESP32"

def upsert_device_record(*, name: str, platform: str, board: str, yaml_text: str,
                         firmware_sha256: str | None = None, ip: str | None = None,
                         mac: str | None = None):
    """Create/update a device entry keyed by (name+platform). Keeps simple history."""
    db = _load_devices()
    # try to find existing by name+platform
    existing = next((d for d in db["devices"]
                     if d.get("name") == name and d.get("platform") == platform), None)

    now_iso = _iso_now()
    if existing:
        # history append
        hist = existing.get("history", [])
        if existing.get("flashed_at") or existing.get("firmware_sha256"):
            hist.append({
                "flashed_at": existing.get("flashed_at"),
                "firmware_sha256": existing.get("firmware_sha256")
            })
        existing.update({
            "friendly_name": existing.get("friendly_name") or name,
            "board": board,
            "yaml": yaml_text,
            "firmware_sha256": firmware_sha256,
            "ip": ip or existing.get("ip"),
            "mac": mac or existing.get("mac"),
            "flashed_at": now_iso,
            "history": [h for h in hist if h.get("flashed_at")]
        })
    else:
        db["devices"].append({
            "id": str(uuid.uuid4()),
            "name": name,
            "friendly_name": name,
            "platform": platform,
            "board": board,
            "yaml": yaml_text,
            "firmware_sha256": firmware_sha256,
            "ip": ip,
            "mac": mac,
            "tags": [],
            "notes": "",
            "flashed_at": now_iso,
            "history": []
        })
    _save_devices(db)

# ---------- Build artifacts ----------
def get_firmware_paths(name: str):
    """Find the latest built firmware .bin in ESPHome build tree and our manifest target path."""
    build_root = os.path.join(YAML_DIR, ".esphome", "build")
    if not os.path.exists(build_root):
        return None, None

    env_dirs = [d for d in os.listdir(build_root)
                if os.path.isdir(os.path.join(build_root, d))]
    if not env_dirs:
        return None, None

    env_dirs.sort(key=lambda x: os.path.getmtime(os.path.join(build_root, x)), reverse=True)
    build_env = env_dirs[0]
    build_dir = os.path.join(build_root, build_env, ".pioenvs", build_env)

    bin_path = os.path.join(build_dir, "firmware.bin")
    if not os.path.exists(bin_path):
        bin_path = os.path.join(build_dir, "firmware.factory.bin")

    manifest_path = os.path.join(OUTPUT_DIR, f"{name}.manifest.json")
    return bin_path, manifest_path

# ---------- Routes ----------

@app.route("/compile", methods=["POST"])
def compile_yaml():
    data = request.get_json(silent=True) or {}
    name = data.get("name", "device").replace(" ", "_").lower()
    config = data.get("configuration", "")

    if not config:
        return Response("❌ No YAML configuration received.\n", status=400, mimetype="text/plain")

    yaml_path = os.path.join(YAML_DIR, f"{name}.yaml")
    with open(yaml_path, "w", encoding="utf-8") as f:
        f.write(config)

    platform = data.get("platform") or detect_platform_from_yaml(config)
    board = data.get("board") or ("esp32dev" if platform == "ESP32" else "nodemcuv2")
    chip_family = chip_family_for_platform(platform)

    def generate():
        try:
            yield f"📥 YAML saved: {yaml_path}\n"
            yield "🚀 Starting compilation...\n\n"

            proc = subprocess.Popen(
                ["esphome", "compile", yaml_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )

            for line in iter(proc.stdout.readline, ''):
                yield line

            proc.stdout.close()
            returncode = proc.wait()

            if returncode != 0:
                yield f"\n❌ Compilation failed with code {returncode}.\n"
                return

            bin_path, _ = get_firmware_paths(name)
            if not bin_path or not os.path.exists(bin_path):
                yield "❌ No binary file found.\n"
                return

            output_bin = os.path.join(OUTPUT_DIR, f"{name}.bin")
            os.makedirs(OUTPUT_DIR, exist_ok=True)
            shutil.copyfile(bin_path, output_bin)
            try:
                os.remove(bin_path)
            except Exception:
                pass

            # Optional: compute sha256 if you like (needs hashlib)
            firmware_sha256 = None
            # with open(output_bin, "rb") as fb:
            #     import hashlib
            #     firmware_sha256 = hashlib.sha256(fb.read()).hexdigest()

            manifest_data = {
                "name": f"{name} Firmware",
                "version": "1.0.0",
                "builds": [{
                    "chipFamily": chip_family,
                    "parts": [{
                        "path": f"firmware/{name}.bin",
                        "offset": 0
                    }]
                }]
            }

            manifest_path = os.path.join(OUTPUT_DIR, f"{name}.manifest.json")
            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump(manifest_data, f)

            # upsert device registry
            upsert_device_record(
                name=name,
                platform=platform,
                board=board,
                yaml_text=config,
                firmware_sha256=firmware_sha256
            )

            yield "\n✅ Compilation successful!\n"
            yield json.dumps({
                "manifest_url": f"/firmware/{name}.manifest.json"
            }) + "\n"

        except Exception as e:
            traceback.print_exc()
            yield f"💥 Error: {str(e)}\n"

    return Response(generate(), mimetype="text/plain")


@app.route("/flash", methods=["POST"])
def flash_device():
    try:
        data = request.get_json(silent=True) or {}
        name = data.get("name", "").replace(" ", "_").lower()
        method = data.get("method", "ota")
        ip = data.get("ip")
        mac = data.get("mac")

        if not name:
            return jsonify({"error": "No device name provided."}), 400

        yaml_path = os.path.join(YAML_DIR, f"{name}.yaml")
        if not os.path.exists(yaml_path):
            return jsonify({"error": "YAML config not found."}), 404

        # Load YAML content to detect platform/board for registry
        config_text = Path(yaml_path).read_text(encoding="utf-8")
        platform = detect_platform_from_yaml(config_text)
        board = "esp32dev" if platform == "ESP32" else "nodemcuv2"

        if method == "usb":
            compile_proc = subprocess.run(
                ["esphome", "compile", yaml_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True
            )

            if compile_proc.returncode != 0:
                return Response(compile_proc.stdout + "\n❌ Compile failed.\n", mimetype="text/plain")

            _, manifest_path = get_firmware_paths(name)
            if not manifest_path or not os.path.exists(manifest_path):
                return jsonify({"error": "Manifest not found."}), 500

            # Mark as "last flashed" in registry even for USB path
            upsert_device_record(
                name=name, platform=platform, board=board, yaml_text=config_text, ip=ip, mac=mac
            )

            return jsonify({
                "status": "ok",
                "manifest_url": f"/firmware/{name}.manifest.json"
            })

        else:
            def generate():
                try:
                    yield f"🚀 Starting OTA flash for {yaml_path}...\n\n"
                    proc = subprocess.Popen(
                        ["esphome", "run", yaml_path],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        bufsize=1
                    )

                    for line in iter(proc.stdout.readline, ''):
                        yield line

                    proc.stdout.close()
                    returncode = proc.wait()

                    if returncode == 0:
                        # mark device flashed in registry
                        upsert_device_record(
                            name=name, platform=platform, board=board, yaml_text=config_text, ip=ip, mac=mac
                        )
                        yield "\n✅ Flash successful.\n"
                    else:
                        yield f"\n❌ Flash failed with code {returncode}.\n"
                except Exception as e:
                    traceback.print_exc()
                    yield f"\n💥 Error during flash: {str(e)}\n"

            return Response(generate(), mimetype="text/plain")

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

# ---------- Device registry API ----------

@app.route("/api/devices", methods=["GET"])
def api_list_devices():
    return _load_devices()

@app.route("/api/devices/<dev_id>", methods=["GET"])
def api_get_device(dev_id):
    db = _load_devices()
    for d in db["devices"]:
        if d.get("id") == dev_id:
            return d
    return jsonify({"error": "Not found"}), 404

@app.route("/api/devices", methods=["POST"])
def api_upsert_device():
    """
    Body: { id?, name, friendly_name?, platform, board, yaml, firmware_sha256?, ip?, mac?, tags?, notes? }
    """
    payload = request.get_json(silent=True) or {}
    db = _load_devices()

    dev = {
        "id": payload.get("id") or str(uuid.uuid4()),
        "name": payload.get("name", ""),
        "friendly_name": payload.get("friendly_name") or payload.get("name", ""),
        "platform": payload.get("platform", ""),
        "board": payload.get("board", ""),
        "yaml": payload.get("yaml", ""),
        "firmware_sha256": payload.get("firmware_sha256"),
        "ip": payload.get("ip"),
        "mac": payload.get("mac"),
        "tags": payload.get("tags") or [],
        "notes": payload.get("notes") or "",
        "flashed_at": payload.get("flashed_at") or _iso_now(),
        "history": payload.get("history") or []
    }

    # upsert by id
    for i, d in enumerate(db["devices"]):
        if d.get("id") == dev["id"]:
            # move current to history if present
            hist = d.get("history", [])
            if d.get("flashed_at") or d.get("firmware_sha256"):
                hist.append({"flashed_at": d.get("flashed_at"), "firmware_sha256": d.get("firmware_sha256")})
            dev["history"] = [h for h in hist if h.get("flashed_at")]
            db["devices"][i] = dev
            _save_devices(db)
            return dev

    db["devices"].append(dev)
    _save_devices(db)
    return dev

@app.route("/api/devices/<dev_id>", methods=["DELETE"])
def api_delete_device(dev_id):
    db = _load_devices()
    before = len(db["devices"])
    db["devices"] = [d for d in db["devices"] if d.get("id") != dev_id]
    if len(db["devices"]) == before:
        return jsonify({"error": "Not found"}), 404
    _save_devices(db)
    return {"ok": True}

# ---------- Scanning ----------
@app.route('/scan', methods=['GET'])
def scan():
    """
    Simple TCP port scan across a /24 subnet.
    Example: /scan?subnet=192.168.178&ports=80,6053
    """
    subnet = request.args.get('subnet', '192.168.178')
    ports_raw = request.args.get('ports', '80')
    ports = [int(p.strip()) for p in ports_raw.split(',') if p.strip().isdigit()]

    found_devices = []

    for i in range(1, 255):
        ip = f"{subnet}.{i}"
        open_ports = []
        for port in ports:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(0.25)
                result = sock.connect_ex((ip, port))
                sock.close()
                if result == 0:
                    open_ports.append(port)
            except Exception:
                pass
        if open_ports:
            found_devices.append({
                "ip": ip,
                "ports": open_ports
            })

    return jsonify(found_devices)

# ---------- Static + misc ----------
@app.route("/")
def index():
    # Serves /app/www/index.html
    return send_from_directory(app.static_folder, "index.html")

@app.route("/firmware/list", methods=["GET"])
def list_firmwares():
    try:
        files = os.listdir(OUTPUT_DIR)
        bin_files = [f for f in files if f.endswith(".bin")]
        return jsonify({"firmwares": bin_files})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/ping")
def ping():
    return "pong"

# ---------- Entrypoint ----------
if __name__ == "__main__":
    # In Home Assistant add-ons usually run under s6; this is fine for local testing.
    app.run(host="0.0.0.0", port=8099)
