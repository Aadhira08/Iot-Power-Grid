#!/usr/bin/env python3
"""Entry point: builds the simulator, wires DB/MQTT, runs the Flask server."""

import config
from backend.app import create_app
from backend.mqtt_client import MqttPublisher
from grid_simulation import GridSimulator


def main():
    sim = GridSimulator(thresholds=config.DEFAULT_THRESHOLDS,
                        tick_seconds=config.TICK_SECONDS,
                        history_length=config.HISTORY_LENGTH)
    mqtt = None
    if config.MQTT_ENABLED:
        mqtt = MqttPublisher(config.MQTT_BROKER, config.MQTT_PORT,
                             config.MQTT_TOPICS)
    app = create_app(sim, db_path=config.DB_PATH, mqtt=mqtt)
    sim.start()
    print("=" * 60)
    print("  IoT Power Grid Fault Detection & Restoration System")
    print("  Dashboard: http://127.0.0.1:%d" % config.PORT)
    print("=" * 60)
    app.run(host=config.HOST, port=config.PORT, debug=config.DEBUG,
            threaded=True)


if __name__ == "__main__":
    main()
