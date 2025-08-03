from flask import Flask, request, Response, send_from_directory, send_file, jsonify
import os
import subprocess
from flask_cors import CORS
import json
import traceback
import shutil

app = Flask(__name__, static_folder="/app/www", static_url_path="/")
CORS(app)

YAML_DIR = "/data/yaml"
OUTPUT_DIR = "/app/www/firmware"
os.makedirs(YAML_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

def get_firmware_paths(name: str):
    build_root = os.path.join(YAML_DIR, ".esphome", "build")
    if not os.path.exists(build_root):
        return None, None

    env_dirs = [
        d for d in os.listdir(build_root)
        if os.path.isdir(os.path.join(build_root, d))
    ]
    if not env_dirs:
        return None, None

    # Sortiere nach Änderungszeit (neuester zuerst)
    env_dirs.sort(key=lambda x: os.path.getmtime(os.path.join(build_root, x)), reverse=True)
    build_env = env_dirs[0]
    build_dir = os.path.join(build_root, build_env, ".pioenvs", build_env)

    bin_path = os.path.join(build_dir, "firmware.bin")
    if not os.path.exists(bin_path):
        bin_path = os.path.join(build_dir, "firmware.factory.bin")

    manifest_path = os.path.join(OUTPUT_DIR, f"{name}.manifest.json")
    return bin_path, manifest_path

@app.route("/compile", methods=["POST"])
def compile_yaml():
    data = request.get_json()
    name = data.get("name", "device").replace(" ", "_").lower()
    config = data.get("configuration", "")

    if not config:
        return Response("❌ No YAML configuration received.\n", status=400, mimetype='text/plain')

    yaml_path = os.path.join(YAML_DIR, f"{name}.yaml")
    with open(yaml_path, "w") as f:
        f.write(config)

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
            shutil.copyfile(bin_path, output_bin)
            try:
                os.remove(bin_path)
            except Exception:
                pass

            manifest_data = {
                "name": f"{name} Firmware",
                "version": "1.0.0",
                "builds": [{
                    "chipFamily": "ESP32",
                    "parts": [{
                        "path": f"firmware/{name}.bin",
                        "offset": 0
                    }]
                }]
            }

            manifest_path = os.path.join(OUTPUT_DIR, f"{name}.manifest.json")
            with open(manifest_path, "w") as f:
                json.dump(manifest_data, f)

            yield "\n✅ Compilation successful!\n"
            yield json.dumps({
                "manifest_url": f"/firmware/{name}.manifest.json"
            }) + "\n"

        except Exception as e:
            traceback.print_exc()
            yield f"💥 Error: {str(e)}\n"

    return Response(generate(), mimetype='text/plain')

@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")

@app.route("/ping")
def ping():
    return "pong"

@app.route("/flash", methods=["POST"])
def flash_device():
    try:
        data = request.get_json()
        name = data.get("name", "").replace(" ", "_").lower()
        method = data.get("method", "ota")

        if not name:
            return jsonify({"error": "No device name provided."}), 400

        yaml_path = os.path.join(YAML_DIR, f"{name}.yaml")
        if not os.path.exists(yaml_path):
            return jsonify({"error": "YAML config not found."}), 404

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

            return jsonify({
                "status": "ok",
                "manifest_url": f"/firmware/{name}.manifest.json"
            })

        else:
            def generate():
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
                    yield "\n✅ Flash successful.\n"
                else:
                    yield f"\n❌ Flash failed with code {returncode}.\n"

            return Response(generate(), mimetype='text/plain')

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route("/firmware/list", methods=["GET"])
def list_firmwares():
    try:
        files = os.listdir(OUTPUT_DIR)
        bin_files = [f for f in files if f.endswith(".bin")]
        return jsonify({"firmwares": bin_files})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8099)
