import unittest

from grid_simulation import GridSimulator, SectionState, FaultType


class TestGridSimulation(unittest.TestCase):
    def setUp(self):
        self.sim = GridSimulator(seed=42)

    def test_initial_state_all_healthy(self):
        self.sim.step()
        for s in self.sim.sections:
            self.assertEqual(s.state, SectionState.HEALTHY)
            self.assertAlmostEqual(s.voltage_kv, 11.0, delta=0.5)
            self.assertGreater(s.current_a, 0)

    def test_measurements_are_labeled_simulated(self):
        snap = self.sim.snapshot()
        self.assertIn("SIMULATED", snap["note"])

    def test_isolation_opens_switch_and_section(self):
        self.sim.inject_fault("SEC2", "SHORT_CIRCUIT")
        # confirmation_ticks (3) + isolation timer (2)
        for _ in range(6):
            self.sim.step()
        sec2 = self.sim.sections[1]
        self.assertEqual(sec2.state, SectionState.ISOLATED)
        self.assertEqual(sec2.switch_status, "OPEN")

    def test_downstream_restored_via_alternate_feeder(self):
        self.sim.inject_fault("SEC2", "SHORT_CIRCUIT")
        # 6 ticks to isolate+attempt restore + 4 restoration delay
        for _ in range(12):
            self.sim.step()
        sec3 = self.sim.sections[2]
        self.assertEqual(sec3.state, SectionState.RESTORED)
        self.assertEqual(self.sim.tie_breaker["status"], "CLOSED")
        self.assertEqual(sec3.supply_source, "ALTERNATE")

    def test_upstream_stays_healthy(self):
        self.sim.inject_fault("SEC2", "OVERCURRENT")
        for _ in range(6):
            self.sim.step()
        self.assertEqual(self.sim.sections[0].state, SectionState.HEALTHY)

    def test_clear_fault_restores_normal_topology(self):
        self.sim.inject_fault("SEC2", "SHORT_CIRCUIT")
        for _ in range(6):
            self.sim.step()
        self.sim.clear_fault("SEC2")
        for _ in range(4):
            self.sim.step()
        self.assertEqual(self.sim.tie_breaker["status"], "OPEN")
        for s in self.sim.sections:
            self.assertEqual(s.state, SectionState.HEALTHY)

    def test_sensor_failure_suspends_detection(self):
        self.sim.set_sensor_online("SEC1", False)
        self.sim.inject_fault("SEC1", "SHORT_CIRCUIT")
        for _ in range(10):
            self.sim.step()
        # sensor offline -> no fault should be confirmed automatically
        self.assertNotEqual(self.sim.sections[0].state, SectionState.FAULTY)


if __name__ == "__main__":
    unittest.main()
