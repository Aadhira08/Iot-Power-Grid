import os
import tempfile
import unittest

try:
    from backend.app import create_app
    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False

from grid_simulation import GridSimulator


@unittest.skipUnless(FLASK_AVAILABLE, "Flask not installed (pip install Flask)")


class TestApi(unittest.TestCase):  # noqa: E303
    def setUp(self):
        self.db = os.path.join(tempfile.mkdtemp(), "test.db")
        self.sim = GridSimulator(seed=1)
        self.app = create_app(self.sim, db_path=self.db).test_client()

    def test_health(self):
        r = self.app.get("/api/health")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["status"], "ok")

    def test_status_shape(self):
        r = self.app.get("/api/status")
        j = r.get_json()
        self.assertIn("sections", j)
        self.assertEqual(len(j["sections"]), 3)
        self.assertIn("thresholds", j)

    def test_inject_fault_and_logged(self):
        r = self.app.post("/api/simulate/fault",
                          json={"section_id": "SEC1",
                                "fault_type": "SHORT_CIRCUIT"})
        self.assertTrue(r.get_json()["ok"])
        for _ in range(6):
            self.sim.step()
        r = self.app.get("/api/faults")
        faults = r.get_json()["faults"]
        self.assertEqual(len(faults), 1)
        self.assertEqual(faults[0]["section_id"], "SEC1")

    def test_bad_fault_request(self):
        r = self.app.post("/api/simulate/fault",
                          json={"section_id": "NOPE",
                                "fault_type": "SHORT_CIRCUIT"})
        self.assertEqual(r.status_code, 400)

    def test_sensor_failure_endpoint(self):
        r = self.app.post("/api/simulate/sensor-failure",
                          json={"section_id": "SEC2", "online": False})
        self.assertTrue(r.get_json()["ok"])
        self.assertFalse(self.sim.sections[1].sensor_online)

    def test_comm_failure_rejects_telemetry(self):
        self.app.post("/api/simulate/comm-failure", json={"online": False})
        r = self.app.post("/api/telemetry",
                          json={"section_id": "SEC1", "voltage_kv": 11.0,
                                "current_a": 40.0})
        self.assertEqual(r.status_code, 503)

    def test_telemetry_ingest_ok(self):
        r = self.app.post("/api/telemetry",
                          json={"device_id": "n1", "section_id": "SEC3",
                                "voltage_kv": 10.9, "current_a": 41.2})
        self.assertTrue(r.get_json()["accepted"])

    def test_config_update(self):
        r = self.app.post("/api/config", json={"overcurrent_pu": 1.8})
        self.assertEqual(r.get_json()["thresholds"]["overcurrent_pu"], 1.8)

    def test_events_logged_to_db(self):
        self.app.post("/api/simulate/fault",
                      json={"section_id": "SEC2", "fault_type": "OVERCURRENT"})
        self.sim.step()
        r = self.app.get("/api/events")
        types = [e["type"] for e in r.get_json()["events"]]
        self.assertIn("FAULT_INJECTED", types)


if __name__ == "__main__":
    unittest.main()
