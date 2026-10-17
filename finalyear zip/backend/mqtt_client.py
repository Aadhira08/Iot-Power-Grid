"""Optional MQTT publisher (requires paho-mqtt). Disabled gracefully if absent."""

import json
import logging

log = logging.getLogger("mqtt")


class MqttPublisher:
    def __init__(self, broker, port=1883, topics=None):
        self.topics = topics or {}
        self.client = None
        try:
            import paho.mqtt.publish as publish
            self._publish = publish
            self.broker = broker
            self.port = port
            self.enabled = True
            log.info("MQTT enabled -> %s:%s", broker, port)
        except ImportError:
            self.enabled = False
            log.warning("paho-mqtt not installed; MQTT disabled.")

    def publish(self, kind, payload):
        if not self.enabled:
            return
        topic = self.topics.get(kind)
        if not topic:
            return
        try:
            self._publish.single(topic, json.dumps(payload),
                                 hostname=self.broker, port=self.port)
        except Exception as exc:  # broker unreachable, etc.
            log.warning("MQTT publish failed: %s", exc)
