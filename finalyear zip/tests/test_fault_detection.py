import unittest

from grid_simulation import GridSimulator, FaultType


class TestFaultDetection(unittest.TestCase):
    def setUp(self):
        self.sim = GridSimulator(seed=7)

    def _confirm(self, section_id, ftype, ticks=10):
        self.sim.inject_fault(section_id, ftype)
        for _ in range(ticks):
            self.sim.step()
        return self.sim.faults[-1] if self.sim.faults else None

    def test_short_circuit_detected(self):
        f = self._confirm("SEC1", "SHORT_CIRCUIT")
        self.assertIsNotNone(f)
        self.assertEqual(f["fault_type"], "SHORT_CIRCUIT")
        self.assertEqual(f["section_id"], "SEC1")
        self.assertGreater(f["current_a"], 5 * 63.0)

    def test_overcurrent_detected(self):
        f = self._confirm("SEC3", "OVERCURRENT")
        self.assertEqual(f["fault_type"], "OVERCURRENT")
        self.assertGreater(f["current_a"], 1.5 * 50.0)

    def test_undervoltage_detected(self):
        f = self._confirm("SEC2", "UNDERVOLTAGE")
        self.assertEqual(f["fault_type"], "UNDERVOLTAGE")
        self.assertLess(f["voltage_kv"], 0.85 * 11.0)

    def test_overvoltage_detected(self):
        f = self._confirm("SEC2", "OVERVOLTAGE")
        self.assertEqual(f["fault_type"], "OVERVOLTAGE")
        self.assertGreater(f["voltage_kv"], 1.15 * 11.0)

    def test_confirmation_delay_required(self):
        self.sim.inject_fault("SEC1", "OVERCURRENT")
        for _ in range(2):   # less than confirmation_ticks (3)
            self.sim.step()
        self.assertEqual(len(self.sim.faults), 0)
        for _ in range(2):
            self.sim.step()
        self.assertEqual(len(self.sim.faults), 1)

    def test_transient_noise_does_not_trip(self):
        # run 20 healthy ticks: noise stays within +-20% -> no faults
        for _ in range(20):
            self.sim.step()
        self.assertEqual(len(self.sim.faults), 0)

    def test_fault_log_fields_complete(self):
        f = self._confirm("SEC2", "SHORT_CIRCUIT")
        for key in ("fault_id", "timestamp", "section_id", "fault_type",
                    "voltage_kv", "current_a", "response"):
            self.assertIn(key, f)


if __name__ == "__main__":
    unittest.main()
