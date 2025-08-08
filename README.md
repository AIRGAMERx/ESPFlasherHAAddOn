# ESPFlasher Web Add-on for Home Assistant

**Flash and configure your ESP32 devices directly from Home Assistant using a modern web interface.**

---

## 🔧 Features

- 🧩 Seamless integration with Home Assistant
- 🌐 Web-based interface (accessible from Home Assistant sidebar)
- ⚡ Compile and flash ESPHome firmware directly to ESP32 devices
- 🔌 OTA flashing and Web Serial USB flashing support
- 🧠 Auto-detect toolchains, manage pins, and device configuration
- 💾 Caching and build optimization for faster compile times

---

## 🚀 Getting Started

1. **Add Repository**
   In Home Assistant, navigate to **Settings > Add-ons > Add-on Store > ... > Repositories** and add:

   ```
   https://github.com/AIRGAMERx/ESPFlasherHAAddOn
   ```

2. **Install the Add-on**
   After adding the repository, look for **ESPFlasher Web** and install it.

3. **Start the Add-on**
   Once installed, start the add-on and open the Web UI.

---

## 📁 Folder Mapping

The add-on uses the following folder mounts:

| Folder     | Description                      |
|------------|----------------------------------|
| `config/`  | Home Assistant config (read/write) |
| `share/`   | Shared data between add-ons      |
| `cache/`   | PlatformIO/ESPHome build cache    |
| `www/`     | Optional static files (read/write) |

---

## 🔒 Security

This add-on requires elevated permissions to access serial ports and use OTA features. It runs with `host_network: true` and has access to:

- USB devices (`/dev/ttyUSB*`, `/dev/ttyACM*`)
- Raw IO access (`SYS_RAWIO`)

Home Assistant may rate the security level lower due to this access. Only install trusted add-ons from trusted sources.

---

## 📦 Development

This add-on is in active development. If you encounter bugs or want to contribute, feel free to open issues or pull requests on GitHub:

👉 [ESPFlasherHAAddOn on GitHub](https://github.com/AIRGAMERx/ESPFlasherHAAddOn)

---

## 🧠 Credits

Developed by [AIRGAMERx](https://github.com/AIRGAMERx)

Built on top of:
- [ESPHome](https://esphome.io/)
- [Home Assistant Add-on system](https://developers.home-assistant.io/docs/add-ons/)

---

## 📜 License

MIT License