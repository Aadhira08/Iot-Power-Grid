"""Central configuration for the Power Grid Fault Detection System."""

# --- Server ---
HOST = "0.0.0.0"
PORT = 5000
DEBUG = False
DB_PATH = "grid.db"

# --- Simulation ---
TICK_SECONDS = 1.0          # one simulation tick per second
HISTORY_LENGTH = 600        # telemetry samples kept in memory (per section)

# --- Default protection thresholds (per-unit of rated values) ---
DEFAULT_THRESHOLDS = {
    "overcurrent_pu": 1.5,        # I > 1.5 x In  -> overcurrent
    "short_circuit_pu": 5.0,      # I > 5.0 x In  -> short-circuit-like
    "undervoltage_pu": 0.85,      # V < 0.85 x Un -> undervoltage
    "overvoltage_pu": 1.15,       # V > 1.15 x Un -> overvoltage
    "confirmation_ticks": 3,      # fault must persist N ticks (filtering)
    "switch_operation_ticks": 2,  # simulated breaker operating time
    "restoration_delay_ticks": 4, # time to re-energize via alternate feeder
}

# --- MQTT (optional) ---
MQTT_ENABLED = False
MQTT_BROKER = "127.0.0.1"
MQTT_PORT = 1883
MQTT_TOPICS = {"faults": "grid/faults", "events": "grid/events", "status": "grid/status"}
