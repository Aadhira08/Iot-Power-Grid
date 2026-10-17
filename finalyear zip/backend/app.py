"""Flask application factory + REST API for the grid system."""

import os

from flask import Flask, jsonify, request, send_from_directory

from .database import get_faults, get_events, log_event, log_fault
from .mqtt_client import MqttPublisher


def create_app(simulator, db_path="grid.db", mqtt=None):
    app = Flask(__name__, static_folder=None)
    sim = simulator

    BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    DASH = os.path.join(BASE, "dashboard")

    # ---------------- DB + MQTT wiring ----------------
    def on_fault(fault):
        log_fault(db_path, fault)
        if mqtt:
            mqtt.publish("faults", fault)

    def on_event(event):
        log_event(db_path, event)
        if mqtt:
            mqtt.publish("events", event)

    sim.on_fault = on_fault
    sim.on_event = on_event

    # ---------------- CORS (allow ESP32 / local dashboard) ----------------
    @app.after_request
    def add_cors(resp):
        resp.headers["Access-Control-Allow-Origin"] = "*"
        resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
        resp.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
        return resp

    # ---------------- Dashboard ----------------
    @app.route("/")
    def index():
        return send_from_directory(DASH, "index.html")

    @app.route("/css/<path:f>")
    def css(f):
        return send_from_directory(os.path.join(DASH, "css"), f)

    @app.route("/js/<path:f>")
    def js(f):
        return send_from_directory(os.path.join(DASH, "js"), f)

    # ---------------- API ----------------
    @app.get("/api/health")
    def health():
        return jsonify({"status": "ok", "tick": sim.tick_count,
                        "communication_online": sim.comm_online})

    @app.get("/api/status")
    def status():
        return jsonify(sim.snapshot())

    @app.get("/api/sections")
    def sections():
        return jsonify({"sections": [s.to_dict() for s in sim.sections]})

    @app.get("/api/faults")
    def faults():
        return jsonify({"faults": get_faults(db_path, 100)})

    @app.get("/api/events")
    def events():
        limit = request.args.get("limit", 50, type=int)
        return jsonify({"events": get_events(db_path, limit)})

    @app.get("/api/telemetry")
    def telemetry():
        sec = request.args.get("section")
        limit = request.args.get("limit", 200, type=int)
        return jsonify({"telemetry": sim.get_history(sec, limit)})

    @app.post("/api/simulate/fault")
    def simulate_fault():
        body = request.get_json(force=True) or {}
        try:
            sim.inject_fault(body["section_id"], body["fault_type"])
            return jsonify({"ok": True})
        except KeyError as e:
            return jsonify({"ok": False, "error": str(e)}), 400

    @app.post("/api/simulate/clear")
    def simulate_clear():
        body = request.get_json(force=True) or {}
        try:
            sim.clear_fault(body["section_id"])
            return jsonify({"ok": True})
        except KeyError as e:
            return jsonify({"ok": False, "error": str(e)}), 400

    @app.post("/api/simulate/sensor-failure")
    def sensor_failure():
        body = request.get_json(force=True) or {}
        try:
            sim.set_sensor_online(body["section_id"], body.get("online", False))
            return jsonify({"ok": True})
        except KeyError as e:
            return jsonify({"ok": False, "error": str(e)}), 400

    @app.post("/api/simulate/comm-failure")
    def comm_failure():
        body = request.get_json(force=True) or {}
        sim.comm_online = bool(body.get("online", True))
        return jsonify({"ok": True, "communication_online": sim.comm_online})

    @app.post("/api/config")
    def config():
        body = request.get_json(force=True) or {}
        sim.update_thresholds(body)
        return jsonify({"ok": True, "thresholds": sim.thr})

    @app.post("/api/telemetry")
    def ingest():
        """ESP32 telemetry ingestion endpoint."""
        if not sim.comm_online:
            return jsonify({"accepted": False,
                            "error": "communication link down"}), 503
        body = request.get_json(force=True) or {}
        try:
            return jsonify(sim.ingest_telemetry(
                body["section_id"], float(body["voltage_kv"]),
                float(body["current_a"])))
        except (KeyError, ValueError) as e:
            return jsonify({"accepted": False, "error": str(e)}), 400

    return app
