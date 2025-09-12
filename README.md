# ESPFlasher Web — Home Assistant Add‑on

Flash **ESP32/ESP8266** devices, build YAML visually, and manage previous flashes — all from a sleek web UI inside **Home Assistant**.

> Hobby project. PRs & feedback welcome! 

---

##  Features

-  **OTA** — Compile and flash ESPHome firmware (OTA)
-  **Visual config editor** — Basic setup, buses (I²C/SPI/UART/OneWire), components, and live **YAML preview**
-  **Device history** — View, restore, download YAML for previous flashes
-  **Saved components (presets)** — Reuse your favorite sensor/display configs
-  **ESP pinout overlay** — Quickly check used pins
-  **Theme & i18n** — Light/Dark/System, languages: **English, Deutsch, Français**
-  **Backend API configurable** — Set base URL/port, test with `/ping`

---



---

##  Screenshots 
Main
<img width="2558" height="1293" alt="image" src="https://github.com/user-attachments/assets/80ffab25-3042-49e2-bd0f-0c9b39929ae5" />
Bus Configuration
<img width="2553" height="1300" alt="image" src="https://github.com/user-attachments/assets/fbd1cbca-8252-4b3e-b923-11164aa2c570" />
Components Selection
<img width="2554" height="1289" alt="image" src="https://github.com/user-attachments/assets/37e88dfd-eac9-4215-bc7f-47895e3fa897" />
Pinout
<img width="2266" height="1243" alt="image" src="https://github.com/user-attachments/assets/98d27e1d-94ee-4396-9c7c-63e10facc5b7" />






---

##  Installation (Home Assistant)

1) **Add Repository**  
Open **Settings → Add‑ons → Add‑on Store → ⋮ → Repositories** and add:
```
https://github.com/AIRGAMERx/ESPFlasherHAAddOn
```

2) **Install** the add‑on named **ESPFlasher Web**.

3) **Start** the add‑on and click **Open Web UI**.

> If you run the UI standalone, set the API base/port in **Settings → API Connection** and use **Test Connection**.

---

## 🏁 Quick Start

1. **Basic Settings** – Device name, platform/board, Wi‑Fi, core services (API/OTA/Web)
2. **Buses** – Enable/configure I²C, SPI, UART, OneWire
3. **Components** – Browse components & recipes, add to your build, configure options
4. **YAML Preview** – Inspect generated YAML, copy or download
5. **Compile & Flash** – Build firmware and flash via OTA
6. **Devices** – View previous flashes, restore config to the editor, download YAML
7. **Saved Components** – Manage your reusable presets (export/import JSON)

---

##  Language & Theme

- Switch language from the **AppBar** (🌐 icon): **English / Deutsch / Français / System default**
- Switch theme with the **Theme** (☀️/🌙) button: **Light / Dark / System**

---

##  Requirements

- Home Assistant (for the add‑on experience), or a reachable backend API for standalone web
- ESPHome toolchain available inside the add‑on container (handled by the add‑on)

---

##  Architecture (high level)

- **Frontend:** Flutter Web app (Material 3, i18n, persistent settings)
- **Backend (in add‑on):** Serves the web app and exposes endpoints such as:
  - `GET /api/devices` — list previous flashes
  - `GET /api/devices/:id` — device details (YAML/config snapshot)
  - `GET /api/devices/:id/yaml` — fetch YAML
  - `DELETE /api/devices/:id` — remove from registry
  - `GET /ping` — connectivity test used by “Test Connection”

Exact endpoints may evolve — see the code for current definitions.

---

##  Troubleshooting

- **API Test fails**: Use **Settings → API Connection → Test Connection**. Check base URL, port, and network reachability. Endpoint must return `200` with body `pong` on `/ping`.
- **Compile errors**: Inspect the YAML preview, check board/platform IDs, and verify component options.
- **OTA not working**: Confirm device is online and reachable; verify API/OTA passwords.

---

##  Security Notes

The add‑on may request elevated capabilities to access serial devices and expose a local API. Only install from trusted sources and review permissions. If you plan to expose it outside your LAN, put it behind proper authentication and TLS.

---

## Roadmap (Ideas)

-  **First‑run wizard** to guide beginners through a minimal working config
-  More components, smarter presets & recipe suggestions
- Import from raw YAML to pre‑fill the visual editor
-  Hardware sanity checks (boot‑strap pins, conflicts)
-  Wi‑Fi provisioning helpers
-  Guided flashing for absolute beginners

Have ideas? Please open an issue!

---

##  Contributing

1. Fork the repo & create a feature branch
2. Commit with clear messages
3. Open a Pull Request — include screenshots/GIFs for UI changes

Bug reports are welcome — include repro steps and logs where possible.

---

## 🧾 License

**MIT License** — see [LICENSE](LICENSE).

---

##  Credits

Created by **[AIRGAMERx](https://github.com/AIRGAMERx)**  
Built on the shoulders of:
- [ESPHome](https://esphome.io/)
- Home Assistant add‑on ecosystem
- Flutter & the wider open‑source community

---

##  Support & Links

- **GitHub Repository:** <https://github.com/AIRGAMERx/ESPFlasherHAAddOn>
- **Issues (Bugs/Feature Requests):** <https://github.com/AIRGAMERx/ESPFlasherHAAddOn/issues>
- **Buy Me a Coffee:** <https://buymeacoffee.com/airgamer>

## ⚠ Disclaimer & Support Policy

This is a **hobby project**. There’s **no warranty**, **no guaranteed support**, and **no response-time SLA**. I’m happy to receive constructive feedback — please be kind and patient. 

Before opening an issue:
-  First **search existing issues** and check the **docs**.
-  Provide **repro steps**, **logs/error messages**, your **versions** (add-on/app, ESPHome, Home Assistant, browser), and relevant **YAML/configs**.
-  **Feature requests**: describe the **use case** — **PRs** are very welcome!
-  For **security** topics, please **don’t post publicly** (use GitHub Security Advisory or email if available).

Kindness > demands. Thanks! 

  



