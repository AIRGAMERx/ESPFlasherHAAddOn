# server.py
from flask import Flask, request, Response, send_from_directory, jsonify
from flask_cors import CORS
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Tuple, List
import os
import json
import uuid
import shutil
import socket
import subprocess
import traceback
import re

# =========================
# Flask & paths
# =========================
app = Flask(__name__, static_folder="/app/www", static_url_path="/")
_NAME_RE = re.compile(r'(?m)^\s*esphome:\s*(?:#.*)?$|^\s*name:\s*["\']?([^"\']+)["\']?\s*(?:#.*)?$')
CORS(app)

YAML_DIR = "/data/yaml"
OUTPUT_DIR = "/app/www/firmware"
os.makedirs(YAML_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

DEVICES_FILE = Path("/data/devices.json")


# =========================
# Helpers
# =========================
def _iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _atomic_write(path: Path, data: Dict[str, Any]) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def _normalize_name(s: str) -> str:
    return (s or "").strip().replace(" ", "_").lower()


def _load_devices() -> Dict[str, Any]:
    if DEVICES_FILE.exists():
        try:
            db = json.loads(DEVICES_FILE.read_text(encoding="utf-8"))
            changed = False
            db.setdefault("devices", [])
            db.setdefault("version", 1)
            for d in db["devices"]:
                if _migrate_device_inplace(d):
                    changed = True
            if changed:
                _atomic_write(DEVICES_FILE, db)
            return db
        except Exception:
            pass
    return {"devices": [], "version": 1}


def _save_devices(db: Dict[str, Any]) -> None:
    _atomic_write(DEVICES_FILE, db)


def _migrate_device_inplace(d: Dict[str, Any]) -> bool:
    """Normalize legacy records in-place; return True if changed."""
    changed = False
    # id
    if not d.get("id"):
        d["id"] = str(uuid.uuid4())
        changed = True
    # yaml/yaml_snapshot mirror
    y = d.get("yaml")
    ys = d.get("yaml_snapshot")
    if y and not ys:
        d["yaml_snapshot"] = y
        changed = True
    if ys and not y:
        d["yaml"] = ys
        changed = True
    # config_json ensure dict
    cj = d.get("config_json")
    if isinstance(cj, str):
        try:
            d["config_json"] = json.loads(cj)
        except Exception:
            d["config_json"] = {}
        changed = True
    elif cj is None:
        d["config_json"] = {}
        changed = True
    # friendly name
    if not d.get("friendly_name"):
        d["friendly_name"] = d.get("name", "")
        changed = True
    # board label
    if not d.get("board_label") and d.get("board"):
        d["board_label"] = d["board"]
        changed = True
    # timestamps/history
    if not d.get("flashed_at"):
        d["flashed_at"] = _iso_now()
        changed = True
    if not isinstance(d.get("history"), list):
        d["history"] = []
        changed = True
    return changed


def detect_platform_from_yaml(text: str) -> str:
    t = (text or "").lower()
    if "\nesp8266:" in t:
        return "ESP8266"
    if "\nesp32:" in t:
        return "ESP32"
    return "UNKNOWN"


def chip_family_for_platform(platform: str) -> str:
    return "ESP8266" if (platform or "").upper() == "ESP8266" else "ESP32"


def unify_board(payload: Dict[str, Any]) -> Tuple[str, str]:
    """Return (board_label, board_id) from incoming payload."""
    label = payload.get("board_label") or payload.get("board") or payload.get("board_id") or ""
    bid = payload.get("board_id") or ""
    return label, bid


def upsert_device_record(
    *,
    name: str,
    platform: str,
    board_label: str,
    board_id: str,
    yaml_text: str,
    config_json: Optional[Dict[str, Any]] = None,
    firmware_sha256: Optional[str] = None,
    ip: Optional[str] = None,
    mac: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create/update a device entry keyed by (normalized name + platform).
    Keeps simple history of previous flashed_at/firmware_sha256.
    """
    db = _load_devices()
    name_norm = _normalize_name(name)

    existing = next(
        (d for d in db["devices"]
         if _normalize_name(d.get("name", "")) == name_norm and d.get("platform") == platform),
        None
    )

    now_iso = _iso_now()
    if existing:
        hist = existing.get("history", [])
        if existing.get("flashed_at") or existing.get("firmware_sha256"):
            hist.append({
                "flashed_at": existing.get("flashed_at"),
                "firmware_sha256": existing.get("firmware_sha256")
            })
        existing.update({
            "name": name_norm,
            "friendly_name": existing.get("friendly_name") or name,
            "platform": platform,
            "board": board_label,         # legacy field
            "board_label": board_label,
            "board_id": board_id,
            "yaml": yaml_text,
            "yaml_snapshot": yaml_text,
            "config_json": config_json or existing.get("config_json") or {},
            "firmware_sha256": firmware_sha256,
            "ip": ip or existing.get("ip"),
            "mac": mac or existing.get("mac"),
            "flashed_at": now_iso,
            "history": [h for h in hist if h.get("flashed_at")],
        })
        _save_devices(db)
        return existing
    else:
        dev = {
            "id": str(uuid.uuid4()),
            "name": name_norm,
            "friendly_name": name,
            "platform": platform,
            "board": board_label,   # legacy field
            "board_label": board_label,
            "board_id": board_id,
            "yaml": yaml_text,
            "yaml_snapshot": yaml_text,
            "config_json": config_json or {},
            "firmware_sha256": firmware_sha256,
            "ip": ip,
            "mac": mac,
            "tags": [],
            "notes": "",
            "flashed_at": now_iso,
            "history": [],
        }
        db["devices"].append(dev)
        _save_devices(db)
        return dev


def get_firmware_paths(name: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Recursively search /data/yaml/.esphome/build/** for firmware.bin or
    firmware.factory.bin, pick the newest. Prefer firmware.bin when both exist.
    """
    build_root = os.path.join(YAML_DIR, ".esphome", "build")
    if not os.path.isdir(build_root):
        return None, None

    candidates: List[Tuple[float, str]] = []
    for root, _, files in os.walk(build_root):
        for fn in files:
            if fn in ("firmware.bin", "firmware.factory.bin"):
                full = os.path.join(root, fn)
                try:
                    mtime = os.path.getmtime(full)
                    candidates.append((mtime, full))
                except OSError:
                    pass

    if not candidates:
        return None, None

    candidates.sort(key=lambda t: t[0], reverse=True)
    latest_path = candidates[0][1]

    if latest_path.endswith("firmware.factory.bin"):
        maybe_bin = latest_path.replace("firmware.factory.bin", "firmware.bin")
        if os.path.exists(maybe_bin):
            latest_path = maybe_bin

    manifest_path = os.path.join(OUTPUT_DIR, f"{name}.manifest.json")
    return latest_path, manifest_path


def extract_name_from_yaml(text: str) -> Optional[str]:
    # sehr einfache Heuristik: suche die erste "name:"-Zeile nach "esphome:"
    lines = text.splitlines()
    in_esphome = False
    for line in lines:
        if re.match(r'^\s*esphome:\s*$', line):
            in_esphome = True
            continue
        if in_esphome:
            m = re.match(r'^\s*name:\s*["\']?([^"\']+)["\']?', line)
            if m:
                return m.group(1).strip()
            if re.match(r'^\s*\w+:', line):  # nächster Top-Key → raus
                break
    return None


# =========================
# Routes
# =========================
@app.route("/compile", methods=["POST"])
def compile_yaml():
    data = request.get_json(silent=True) or {}
    config = (data.get("configuration") or "").strip()

    if not config:
        return Response("❌ No YAML configuration received.\n",
                        status=400, mimetype="text/plain")

    # Name bevorzugt aus YAML (Option B). Fallback: Request-Name.
    yaml_name = extract_name_from_yaml(config)
    req_name  = (data.get("name") or "device").strip()
    name      = _normalize_name(yaml_name or req_name)

    # YAML dort speichern, wo esphome arbeitet
    yaml_path = os.path.join(YAML_DIR, f"{name}.yaml")
    with open(yaml_path, "w", encoding="utf-8") as f:
        f.write(config)

    # Rest wie gehabt
    platform = data.get("platform") or detect_platform_from_yaml(config)
    board_label, board_id = unify_board(data)
    if not board_id:
        board_id = "esp32dev" if platform == "ESP32" else "d1_mini"
    if not board_label:
        board_label = board_id

    chip_family = chip_family_for_platform(platform)
    # ... (dein bisheriger Code geht hier weiter)


    def generate():
        try:
            yield f"📥 YAML saved: {yaml_path}\n"
            yield "🚀 Starting compilation...\n\n"

            # Wichtig: im YAML_DIR ausführen und nur den Dateinamen übergeben
            proc = subprocess.Popen(
                ["esphome", "compile", f"{name}.yaml"],
                cwd=YAML_DIR,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
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
                yield f"❌ No binary file found under {os.path.join(YAML_DIR, '.esphome', 'build')}.\n"
                return
            else:
                yield f"📦 Found firmware at: {bin_path}\n"

            # Bin in www/firmware spiegeln
            os.makedirs(OUTPUT_DIR, exist_ok=True)
            output_bin = os.path.join(OUTPUT_DIR, f"{name}.bin")
            shutil.copyfile(bin_path, output_bin)
            # Optional: Original behalten; wenn du löschen willst, auskommentierten Block aktivieren
            # try:
            #     os.remove(bin_path)
            # except Exception:
            #     pass

            # Web-Flasher Manifest schreiben
            manifest_data = {
                "name": f"{name} Firmware",
                "version": "1.0.0",
                "builds": [{
                    "chipFamily": chip_family,
                    "parts": [{"path": f"firmware/{name}.bin", "offset": 0}],
                }],
            }
            manifest_path = os.path.join(OUTPUT_DIR, f"{name}.manifest.json")
            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump(manifest_data, f)

            # Registry synchronisieren (falls UI state mitschickt)
            config_json = data.get("config_json") or {}

            saved_dev = upsert_device_record(
                name=name,
                platform=platform,
                board_label=board_label,
                board_id=board_id,
                yaml_text=config,
                config_json=config_json,
                firmware_sha256=None,
            )

            yield "\n✅ Compilation successful!\n"
            # WICHTIG: Device-Objekt mitsenden -> Client kann saved_dev['id'] merken
            yield json.dumps({
                "manifest_url": f"/firmware/{name}.manifest.json",
                "device": saved_dev
            }) + "\n"

        except Exception as e:
            traceback.print_exc()
            yield f"💥 Error: {str(e)}\n"

    return Response(generate(), mimetype="text/plain")



@app.route("/flash", methods=["POST"])
def flash_device():
    try:
        data = request.get_json(silent=True) or {}
        name = _normalize_name(data.get("name", ""))
        method = data.get("method", "ota")
        ip = data.get("ip")
        mac = data.get("mac")

        if not name:
            return jsonify({"error": "No device name provided."}), 400

        yaml_path = os.path.join(YAML_DIR, f"{name}.yaml")
        if not os.path.exists(yaml_path):
            return jsonify({"error": "YAML config not found."}), 404

        config_text = Path(yaml_path).read_text(encoding="utf-8")
        platform = detect_platform_from_yaml(config_text)

        # best-guess board from registry if available
        db = _load_devices()
        existing = next(
            (d for d in db["devices"]
             if _normalize_name(d.get("name", "")) == name and d.get("platform") == platform),
            None
        )
        board_label = existing.get("board_label") if existing else ""
        board_id = existing.get("board_id") if existing else ""
        if not board_id:
            board_id = "esp32dev" if platform == "ESP32" else "d1_mini"
        if not board_label:
            board_label = board_id

        if method == "usb":
            compile_proc = subprocess.run(
                ["esphome", "compile", f"{name}.yaml"],
                cwd=YAML_DIR,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            if compile_proc.returncode != 0:
                return Response(compile_proc.stdout + "\n❌ Compile failed.\n", mimetype="text/plain")

            _, manifest_path = get_firmware_paths(name)
            if not manifest_path:
                return jsonify({"error": "Manifest not found."}), 500

            upsert_device_record(
                name=name,
                platform=platform,
                board_label=board_label,
                board_id=board_id,
                yaml_text=config_text,
                ip=ip,
                mac=mac,
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
                        ["esphome", "run", f"{name}.yaml"],
                        cwd=YAML_DIR,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        bufsize=1,
                    )
                    for line in iter(proc.stdout.readline, ''):
                        yield line
                    proc.stdout.close()
                    returncode = proc.wait()

                    if returncode == 0:
                        upsert_device_record(
                            name=name,
                            platform=platform,
                            board_label=board_label,
                            board_id=board_id,
                            yaml_text=config_text,
                            ip=ip,
                            mac=mac,
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


# =========================
# Device registry API
# =========================
@app.route("/api/devices", methods=["GET"])
def api_list_devices():
    db = _load_devices()
    include = request.args.get("include", "")
    items = []
    for d in db.get("devices", []):
        _migrate_device_inplace(d)
        if include == "full":
            items.append(d)
        else:
            items.append({
                "id": d.get("id"),
                "name": d.get("name"),
                "friendly_name": d.get("friendly_name") or d.get("name"),
                "platform": d.get("platform"),
                # include modern board fields
                "board_id": d.get("board_id"),
                "board_label": d.get("board_label"),
                # legacy field for UI display fallback
                "board": d.get("board") or d.get("board_label") or d.get("board_id"),
                "ip": d.get("ip"),
                "mac": d.get("mac"),
                "flashed_at": d.get("flashed_at"),
                "firmware_sha256": d.get("firmware_sha256"),
            })
    return jsonify({"devices": items}), 200


@app.route("/api/devices/<dev_id>", methods=["GET"])
def api_get_device(dev_id):
    db = _load_devices()
    for d in db["devices"]:
        if d.get("id") == dev_id:
            _migrate_device_inplace(d)
            return jsonify(d), 200
    return jsonify({"error": "Not found"}), 404


@app.route("/api/devices/<dev_id>/yaml", methods=["GET"])
def api_get_device_yaml(dev_id):
    db = _load_devices()
    for d in db["devices"]:
        if d.get("id") == dev_id:
            yaml_text = d.get("yaml") or d.get("yaml_snapshot") or ""
            if not yaml_text:
                return jsonify({"error": "YAML not found"}), 404
            filename = f"{(d.get('name') or 'device')}.yaml"
            return Response(
                yaml_text,
                mimetype="application/x-yaml",
                headers={"Content-Disposition": f'attachment; filename="{filename}"'}
            )
    return jsonify({"error": "Not found"}), 404


@app.route("/api/devices", methods=["POST"])
def api_upsert_device():
    p = request.get_json(silent=True) or {}
    db = _load_devices()

    board_id = p.get("board_id") or p.get("board") or ""
    board_label = p.get("board_label") or ""
    raw_name = p.get("name", "")
    norm_name = _normalize_name(raw_name)
    friendly = p.get("friendly_name") or raw_name or norm_name

    dev = {
        "id": p.get("id") or None,
        "name": norm_name,
        "friendly_name": friendly,
        "platform": p.get("platform", ""),
        "board_id": board_id,
        "board_label": board_label,
        "board": board_id,  # legacy
        "yaml": p.get("yaml") or p.get("yaml_snapshot") or "",
        "yaml_snapshot": p.get("yaml_snapshot") or p.get("yaml") or "",
        "config_json": p.get("config_json") or {},
        "firmware_sha256": p.get("firmware_sha256"),
        "ip": p.get("ip"),
        "mac": p.get("mac"),
        "tags": p.get("tags") or [],
        "notes": p.get("notes") or "",
        "flashed_at": p.get("flashed_at") or _iso_now(),
        "history": p.get("history") or [],
    }

    # upsert by id first
    idx = None
    if dev["id"]:
        for i, d in enumerate(db["devices"]):
            if d.get("id") == dev["id"]:
                idx = i
                break

    # else upsert by (name + platform)
    if idx is None and dev["name"] and dev["platform"]:
        for i, d in enumerate(db["devices"]):
            if _normalize_name(d.get("name", "")) == dev["name"] and d.get("platform") == dev["platform"]:
                idx = i
                dev["id"] = d.get("id")
                break

    # update or insert
    if idx is not None:
        hist = db["devices"][idx].get("history", [])
        if db["devices"][idx].get("flashed_at") or db["devices"][idx].get("firmware_sha256"):
            hist.append({
                "flashed_at": db["devices"][idx].get("flashed_at"),
                "firmware_sha256": db["devices"][idx].get("firmware_sha256"),
            })
        dev["history"] = [h for h in hist if h.get("flashed_at")]
        db["devices"][idx] = {**db["devices"][idx], **dev}
    else:
        dev["id"] = dev["id"] or str(uuid.uuid4())
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
    return jsonify({"ok": True}), 200


# =========================
# Scanning (simple TCP)
# =========================
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
            found_devices.append({"ip": ip, "ports": open_ports})

    return jsonify(found_devices)


# =========================
# Static & misc
# =========================
@app.route("/")
def index():
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


# =========================
# Entrypoint
# =========================
if __name__ == "__main__":
    # For local testing; in HA add-on this is managed by s6.
    app.run(host="0.0.0.0", port=8099)
