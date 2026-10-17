# IoT-Based Intelligent Power Grid Fault Detection and Automatic Restoration System

An IoT-enabled power distribution grid **prototype/simulator** that detects electrical
faults, identifies the affected distribution section, isolates it with simulated
switches, and automatically restores healthy sections through an **alternate feeder**
when all safety interlocks are satisfied.

> **Disclaimer:** This is a *simulation* project for final-year ECE demonstration.
> All measurements are clearly labeled simulated values. No physical fault-location
> accuracy is claimed.

---

## 1. Features

| Module | Capability |
|---|---|
| Grid Simulation | One main source, main feeder, 3 distribution sections, loads, alternate feeder + tie breaker |
| Fault Detection | Overcurrent, undervoltage, overvoltage, short-circuit-like conditions, with filtering + confirmation delay |
| Fault Isolation | Automatic switch opening, switching interlocks, operation timeouts |
| Auto-Restoration | Healthy downstream sections restored via alternate feeder after safety checks |
| Sensor / Comm Failure Handling | Frozen-reading detection, offline flags, telemetry rejection |
| IoT Layer | ESP32 firmware posts telemetry over REST; optional MQTT publisher |
| Dashboard | HTML/CSS/JS + Chart.js live schematic, charts, fault log, controls |
| Persistence | SQLite fault/event log |
| Testing | Python `unittest` suite for simulation + API |

### Section states
`HEALTHY -> FAULTY -> ISOLATED -> RESTORING -> RESTORED` (and back to `HEALTHY` after repair/clear).

---

## 2. Project Structure

```
power-grid-fault-detection/
|   run.py                      # Application entry point
|   config.py                   # Default configuration / thresholds
|   requirements.txt
|   grid_simulation/
|   |   __init__.py
|   |   topology.py             # Grid topology definition
|   |   simulator.py            # Core simulation + detection + isolation engine
|   backend/
|   |   __init__.py
|   |   app.py                  # Flask app factory + REST API
|   |   database.py             # SQLite layer (faults, events, config)
|   |   mqtt_client.py          # Optional MQTT publisher (paho-mqtt)
|   dashboard/
|   |   index.html
|   |   css/style.css
|   |   js/app.js               # Chart.js dashboard + SVG schematic
|   firmware/
|   |   esp32_grid_monitor/
|   |   |   esp32_grid_monitor.ino   # ESP32 Arduino firmware
|   tests/
|   |   test_simulation.py
|   |   test_fault_detection.py
|   |   test_api.py
|   scripts/
|   |   run_tests.py
```

---

## 3. Installation & Run

```bash
# 1. (Optional) virtual environment
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the system
python run.py
```

Open **http://127.0.0.1:5000** in a browser. The simulation ticks once per second.
Use the dashboard buttons to inject faults and watch detection -> isolation -> restoration.

### Run tests

```bash
python scripts/run_tests.py
# or
python -m unittest discover -s tests -v
```

---

## 4. REST API Reference

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/health` | Liveness probe |
| GET | `/api/status` | Full grid snapshot (sections, switches, thresholds) |
| GET | `/api/sections` | Section list with live measurements |
| GET | `/api/faults` | Fault history (also in `grid.db`) |
| GET | `/api/events` | Event log (`?limit=50`) |
| GET | `/api/telemetry?section=SEC1` | Recent measurement history for charts |
| POST | `/api/simulate/fault` | `{"section_id":"SEC2","fault_type":"SHORT_CIRCUIT"}` |
| POST | `/api/simulate/clear` | `{"section_id":"SEC2"}` — simulate repair |
| POST | `/api/simulate/sensor-failure` | `{"section_id":"SEC2","online":false}` |
| POST | `/api/simulate/comm-failure` | `{"online":false}` |
| POST | `/api/config` | Update thresholds (keys in `config.py`) |
| POST | `/api/telemetry` | ESP32 ingestion: `{"device_id":"...","section_id":"SEC1","voltage_kv":11.0,"current_a":40.0}` |

Fault types: `OVERCURRENT`, `UNDERVOLTAGE`, `OVERVOLTAGE`, `SHORT_CIRCUIT`.

### Example

```bash
curl -X POST http://127.0.0.1:5000/api/simulate/fault \
     -H "Content-Type: application/json" \
     -d '{"section_id": "SEC2", "fault_type": "SHORT_CIRCUIT"}'
```

---

## 5. How the Automation Logic Works

1. **Measurement** - each section gets simulated V/I every tick (noise included).
2. **Filtering + confirmation** - a raw threshold hit must persist for
   `confirmation_ticks` (default 3) before a fault is declared (debounce).
3. **Fault typing** - priority: short-circuit (I > 5xIn) -> overcurrent (I > 1.5xIn)
   -> undervoltage (V < 0.85xUn) -> overvoltage (V > 1.15xUn).
4. **Isolation** - the faulty section's switch opens after a simulated operating
   time; upstream healthy sections stay energized.
5. **Restoration** - the tie breaker closes **only after** the faulted section is
   confirmed isolated (interlock), then downstream healthy sections are fed from
   the alternate feeder (`RESTORING` -> `RESTORED`).
6. **Sensor failure** - frozen/offline sensors raise a communication warning event;
   affected sections are excluded from automated decisions.

---

## 6. ESP32 Firmware

1. Open `firmware/esp32_grid_monitor/esp32_grid_monitor.ino` in the Arduino IDE.
2. Libraries: **WiFi** (built-in), **HTTPClient** (built-in), **ArduinoJson** (install via Library Manager).
3. Edit `WIFI_SSID`, `WIFI_PASSWORD`, `SERVER_URL`.
4. With real sensors: wire SCT-013 (current) to GPIO34 via a burden resistor and
   ZMPT101B (voltage) to GPIO35. Without sensors the sketch runs in clearly-labeled
   **SIMULATION MODE** and transmits synthetic readings.

---

## 7. Optional MQTT

Uncomment `paho-mqtt` in `requirements.txt` and set `MQTT_ENABLED = True` in `config.py`.
Faults and events are then published to `grid/faults` and `grid/events`.

---

## 8. Viva / Demonstration Tips

- Show `GET /api/status` before and after a fault injection.
- Open the SQLite file `grid.db` (e.g. with DB Browser for SQLite) to prove logging.
- Explain the interlock: the tie breaker refuses to close until the faulted section is isolated.
- Explain why the confirmation delay prevents false trips from measurement noise.
