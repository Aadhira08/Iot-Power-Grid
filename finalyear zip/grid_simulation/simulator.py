"""
Core simulation engine for the IoT-Based Intelligent Power Grid
Fault Detection and Automatic Restoration System.

Models: source, main feeder, distribution sections with loads, sectional
switches, an alternate feeder and a tie breaker. Implements measurement
generation, threshold-based fault detection with confirmation filtering,
automatic isolation with interlocks/timeouts, and restoration of healthy
sections through the alternate feeder.

ALL VALUES ARE SIMULATED and clearly labeled as such.
"""

import copy
import random
import threading
import time
import uuid
from collections import deque
from datetime import datetime
from enum import Enum

from .topology import DEFAULT_TOPOLOGY


class SectionState(str, Enum):
    HEALTHY = "HEALTHY"
    FAULTY = "FAULTY"
    ISOLATED = "ISOLATED"
    RESTORING = "RESTORING"
    RESTORED = "RESTORED"


class FaultType(str, Enum):
    NONE = "NONE"
    OVERCURRENT = "OVERCURRENT"
    UNDERVOLTAGE = "UNDERVOLTAGE"
    OVERVOLTAGE = "OVERVOLTAGE"
    SHORT_CIRCUIT = "SHORT_CIRCUIT"
    SENSOR_FAILURE = "SENSOR_FAILURE"


DEFAULT_THRESHOLDS = {
    "overcurrent_pu": 1.5,
    "short_circuit_pu": 5.0,
    "undervoltage_pu": 0.85,
    "overvoltage_pu": 1.15,
    "confirmation_ticks": 3,
    "switch_operation_ticks": 2,
    "restoration_delay_ticks": 4,
}


class Section:
    """One distribution section with its load, switch and sensors."""

    def __init__(self, spec):
        self.id = spec["id"]
        self.name = spec["name"]
        self.load_kw = spec["load_kw"]
        self.rated_current_a = spec["rated_current_a"]
        self.switch_id = spec["switch_id"]
        # Live state
        self.state = SectionState.HEALTHY
        self.switch_status = "CLOSED"       # CLOSED / OPEN
        self.voltage_kv = 0.0               # SIMULATED measurement
        self.current_a = 0.0                # SIMULATED measurement
        self.sensor_online = True
        self.supply_source = None           # "MAIN" / "ALTERNATE" / None
        # Protection internals
        self._confirm_ticks = 0
        self.fault_active = False           # physical fault present (simulated)
        self.fault_type = FaultType.NONE

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "load_kw": self.load_kw,
            "rated_current_a": self.rated_current_a,
            "switch_id": self.switch_id,
            "switch_status": self.switch_status,
            "state": self.state.value,
            "voltage_kv": round(self.voltage_kv, 3),
            "current_a": round(self.current_a, 2),
            "sensor_online": self.sensor_online,
            "supply_source": self.supply_source,
            "fault_active": self.fault_active,
            "fault_type": self.fault_type.value,
        }


class GridSimulator:
    """Synchronous simulator. Call step() manually (tests) or start() to run
    a background loop at tick_seconds intervals."""

    def __init__(self, topology=None, thresholds=None, tick_seconds=1.0,
                 history_length=600, seed=None):
        self.topology = copy.deepcopy(topology or DEFAULT_TOPOLOGY)
        self.thr = dict(DEFAULT_THRESHOLDS)
        if thresholds:
            self.thr.update(thresholds)
        self.tick_seconds = tick_seconds
        self.rng = random.Random(seed)
        self.sections = [Section(s) for s in self.topology["sections"]]
        self.section_index = {s.id: i for i, s in enumerate(self.sections)}
        self.main_breaker = dict(self.topology["main_breaker"])
        self.tie_breaker = dict(self.topology["tie_breaker"])
        self.source = dict(self.topology["source"])
        self.alt_source = dict(self.topology["alternate_source"])
        self.tie_after_index = self.section_index[self.tie_breaker["connects_after_section"]]

        self.tick_count = 0
        self.events = deque(maxlen=1000)
        self.faults = deque(maxlen=500)
        self.history = deque(maxlen=history_length)
        self._timers = []          # [{"ticks": n, "action": name, "section": id, ...}]
        self.comm_online = True    # IoT communication link health
        self._stop = threading.Event()
        self._thread = None
        self.on_event = None       # optional callback(event_dict) for DB/MQTT
        self.on_fault = None       # optional callback(fault_dict)

    # ------------------------------------------------------------ loop
    def start(self):
        if self._thread is None:
            self._stop.clear()
            self._thread = threading.Thread(target=self._loop, daemon=True)
            self._thread.start()

    def stop(self):
        self._stop.set()

    def _loop(self):
        while not self._stop.is_set():
            self.step()
            time.sleep(self.tick_seconds)

    def step(self):
        """Advance the simulation by one tick."""
        self.tick_count += 1
        self._update_measurements()
        self._detect_faults()
        self._process_timers()
        self._record_history()

    # ------------------------------------------------------ measurement
    def _main_path_energized(self, idx):
        if self.source["status"] != "ONLINE" or self.main_breaker["status"] != "CLOSED":
            return False
        for i in range(idx + 1):
            if self.sections[i].switch_status != "CLOSED":
                return False
        return True

    def _alt_path_energized(self, idx):
        if idx <= self.tie_after_index:
            return False
        if self.alt_source["status"] != "ONLINE" or self.tie_breaker["status"] != "CLOSED":
            return False
        for i in range(self.tie_after_index + 1, idx + 1):
            if self.sections[i].switch_status != "CLOSED":
                return False
        return True

    def _update_measurements(self):
        for idx, sec in enumerate(self.sections):
            en_main = self._main_path_energized(idx)
            en_alt = self._alt_path_energized(idx)
            energized = (en_main or en_alt) and sec.switch_status == "CLOSED"
            sec.supply_source = "MAIN" if en_main else ("ALTERNATE" if en_alt else None)

            if not sec.sensor_online:
                continue  # frozen readings on a failed sensor

            rated = sec.rated_current_a
            v_nom = self.source["voltage_kv"]

            if sec.fault_active and energized:
                # fault signatures (clearly simulated)
                if sec.fault_type == FaultType.SHORT_CIRCUIT:
                    sec.current_a = rated * self.rng.uniform(6.0, 9.0)
                    sec.voltage_kv = v_nom * self.rng.uniform(0.10, 0.20)
                elif sec.fault_type == FaultType.OVERCURRENT:
                    sec.current_a = rated * self.rng.uniform(1.6, 2.2)
                    sec.voltage_kv = v_nom * self.rng.uniform(0.90, 0.96)
                elif sec.fault_type == FaultType.UNDERVOLTAGE:
                    sec.current_a = rated * self.rng.uniform(0.7, 0.85)
                    sec.voltage_kv = v_nom * self.rng.uniform(0.70, 0.82)
                elif sec.fault_type == FaultType.OVERVOLTAGE:
                    sec.current_a = rated * self.rng.uniform(0.9, 1.05)
                    sec.voltage_kv = v_nom * self.rng.uniform(1.18, 1.28)
            elif energized:
                sec.current_a = rated * self.rng.uniform(0.76, 0.84)
                sec.voltage_kv = v_nom * self.rng.uniform(0.99, 1.01)
            else:
                sec.current_a = 0.0
                sec.voltage_kv = 0.0

    # ------------------------------------------------------ detection
    def _classify(self, sec):
        """Return FaultType for current readings, or NONE."""
        rated = sec.rated_current_a
        v_nom = self.source["voltage_kv"]
        i_pu = sec.current_a / rated if rated else 0.0
        v_pu = sec.voltage_kv / v_nom if v_nom else 0.0
        if i_pu >= self.thr["short_circuit_pu"]:
            return FaultType.SHORT_CIRCUIT
        if i_pu >= self.thr["overcurrent_pu"]:
            return FaultType.OVERCURRENT
        if v_pu <= self.thr["undervoltage_pu"]:
            return FaultType.UNDERVOLTAGE
        if v_pu >= self.thr["overvoltage_pu"]:
            return FaultType.OVERVOLTAGE
        return FaultType.NONE

    def _detect_faults(self):
        for idx, sec in enumerate(self.sections):
            if sec.state == SectionState.FAULTY:
                continue
            if not sec.sensor_online:
                if sec._confirm_ticks != -1:
                    sec._confirm_ticks = -1
                    self._log_event("SENSOR_OFFLINE",
                                    "Sensor offline on %s; automated decisions suspended for this section." % sec.id)
                continue
            if sec._confirm_ticks == -1:
                sec._confirm_ticks = 0
                self._log_event("SENSOR_ONLINE", "Sensor back online on %s." % sec.id)

            energized = self._main_path_energized(idx) or self._alt_path_energized(idx)
            if not energized:
                sec._confirm_ticks = 0
                continue

            ftype = self._classify(sec)
            if ftype != FaultType.NONE:
                sec._confirm_ticks += 1
                if sec._confirm_ticks >= self.thr["confirmation_ticks"]:
                    self._confirm_fault(sec, ftype)
            else:
                sec._confirm_ticks = 0

    def _confirm_fault(self, sec, ftype):
        sec.state = SectionState.FAULTY
        sec.fault_active = True
        sec.fault_type = ftype
        sec._confirm_ticks = 0
        fault = {
            "fault_id": uuid.uuid4().hex[:12],
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "section_id": sec.id,
            "fault_type": ftype.value,
            "voltage_kv": round(sec.voltage_kv, 3),
            "current_a": round(sec.current_a, 2),
            "response": "ISOLATION_SCHEDULED",
        }
        self.faults.append(fault)
        self._log_event("FAULT_CONFIRMED",
                        "%s confirmed on %s (V=%skV, I=%sA). Isolation scheduled."
                        % (ftype.value, sec.id, fault["voltage_kv"], fault["current_a"]))
        self._timers.append({"ticks": self.thr["switch_operation_ticks"],
                             "action": "ISOLATE", "section": sec.id})
        if self.on_fault:
            self.on_fault(fault)

    # ---------------------------------------------- isolation / restoration
    def _process_timers(self):
        due = [t for t in self._timers if t["ticks"] <= 1]
        self._timers = [t for t in self._timers if t["ticks"] > 1]
        for t in self._timers:
            t["ticks"] -= 1
        for t in due:
            getattr(self, "_do_" + t["action"].lower())(t["section"])

    def _do_isolate(self, section_id):
        sec = self.sections[self.section_index[section_id]]
        if sec.switch_status != "CLOSED":
            return
        sec.switch_status = "OPEN"
        sec.state = SectionState.ISOLATED
        sec.supply_source = None
        self._log_event("SECTION_ISOLATED",
                        "%s isolated by opening %s." % (section_id, sec.switch_id))
        self._timers.append({"ticks": self.thr["switch_operation_ticks"],
                             "action": "ATTEMPT_RESTORE", "section": section_id})

    def _do_attempt_restore(self, section_id):
        fidx = self.section_index[section_id]
        downstream = [s for i, s in enumerate(self.sections) if i > fidx]
        if not downstream:
            return
        # INTERLOCK: alternate feeder must be healthy AND no confirmed fault on
        # any downstream section before closing the tie breaker.
        if self.alt_source["status"] != "ONLINE":
            for s in downstream:
                s.state = SectionState.ISOLATED
            self._log_event("RESTORE_SKIPPED",
                            "Alternate feeder unavailable; downstream sections remain isolated.")
            return
        if any(s.state == SectionState.FAULTY for s in downstream):
            for s in downstream:
                s.state = SectionState.ISOLATED
            self._log_event("RESTORE_BLOCKED",
                            "Interlock: fault present downstream; tie breaker NOT closed.")
            return
        if self.tie_breaker["status"] != "CLOSED":
            self.tie_breaker["status"] = "CLOSED"
            self._log_event("TIE_BREAKER_CLOSED",
                            "%s closed. Restoring downstream sections via alternate feeder."
                            % self.tie_breaker["id"])
        for s in downstream:
            if s.state in (SectionState.ISOLATED, SectionState.HEALTHY):
                s.state = SectionState.RESTORING
                self._timers.append({"ticks": self.thr["restoration_delay_ticks"],
                                     "action": "RESTORED", "section": s.id})

    def _do_restored(self, section_id):
        sec = self.sections[self.section_index[section_id]]
        if sec.state == SectionState.RESTORING:
            sec.state = SectionState.RESTORED
            self._log_event("SECTION_RESTORED",
                            "%s restored via alternate feeder %s."
                            % (section_id, self.alt_source["id"]))

    def _do_close_after_repair(self, section_id):
        sec = self.sections[self.section_index[section_id]]
        sec.switch_status = "CLOSED"
        sec.state = SectionState.HEALTHY
        self.tie_breaker["status"] = "OPEN"
        for s in self.sections:
            if s.state in (SectionState.RESTORING, SectionState.RESTORED,
                           SectionState.ISOLATED):
                s.state = SectionState.HEALTHY
        self._log_event("NORMAL_TOPOLOGY_RESTORED",
                        "%s reclosed after repair; tie breaker opened; grid back to normal radial operation."
                        % section_id)

    # ------------------------------------------------------ public controls
    def inject_fault(self, section_id, fault_type):
        """Simulate a physical fault appearing in a section."""
        if section_id not in self.section_index:
            raise KeyError("Unknown section %s" % section_id)
        sec = self.sections[self.section_index[section_id]]
        sec.fault_active = True
        sec.fault_type = FaultType(fault_type)
        self._log_event("FAULT_INJECTED",
                        "Simulated %s injected on %s." % (fault_type, section_id))

    def clear_fault(self, section_id):
        """Simulate repair / fault clearance."""
        sec = self.sections[self.section_index[section_id]]
        sec.fault_active = False
        sec.fault_type = FaultType.NONE
        self._log_event("FAULT_CLEARED",
                        "Fault cleared on %s; reclosing after checks." % section_id)
        self._timers.append({"ticks": self.thr["switch_operation_ticks"],
                             "action": "CLOSE_AFTER_REPAIR", "section": section_id})

    def set_sensor_online(self, section_id, online):
        sec = self.sections[self.section_index[section_id]]
        sec.sensor_online = bool(online)
        self._log_event("SENSOR_FAILURE_SIMULATED" if not online else "SENSOR_RECOVERED",
                        "Sensor on %s set %s." % (section_id, "ONLINE" if online else "OFFLINE"))

    def update_thresholds(self, new):
        for k, v in new.items():
            if k in self.thr:
                self.thr[k] = float(v) if isinstance(self.thr[k], float) else int(v)
        self._log_event("CONFIG_UPDATED", "Thresholds updated: %s" % new)

    def ingest_telemetry(self, section_id, voltage_kv, current_a):
        """Ingest an ESP32 reading (acknowledged; sim remains the data source
        of truth in this prototype)."""
        if not self.comm_online:
            raise ConnectionError("Communication link down")
        if section_id in self.section_index:
            sec = self.sections[self.section_index[section_id]]
            sec.sensor_online = True
        return {"accepted": True, "section_id": section_id,
                "note": "measurement acknowledged (simulation mode)"}

    # ------------------------------------------------------ logging / snapshot
    def _log_event(self, event_type, message):
        ev = {"timestamp": datetime.now().isoformat(timespec="seconds"),
              "type": event_type, "message": message}
        self.events.append(ev)
        if self.on_event:
            self.on_event(ev)

    def _record_history(self):
        for sec in self.sections:
            self.history.append({
                "tick": self.tick_count,
                "timestamp": datetime.now().isoformat(timespec="seconds"),
                "section_id": sec.id,
                "voltage_kv": round(sec.voltage_kv, 3),
                "current_a": round(sec.current_a, 2),
                "state": sec.state.value,
            })

    def snapshot(self):
        return {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "tick": self.tick_count,
            "communication_online": self.comm_online,
            "source": self.source,
            "alternate_source": self.alt_source,
            "main_breaker": self.main_breaker,
            "tie_breaker": self.tie_breaker,
            "sections": [s.to_dict() for s in self.sections],
            "thresholds": dict(self.thr),
            "faults_total": len(self.faults),
            "note": "All measurements are SIMULATED values for demonstration.",
        }

    def get_history(self, section_id=None, limit=200):
        data = list(self.history)
        if section_id:
            data = [h for h in data if h["section_id"] == section_id]
        return data[-limit:]
