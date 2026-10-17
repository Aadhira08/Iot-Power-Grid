"""Grid topology: source -> main breaker -> SEC1 -> SEC2 -> SEC3 (radial feeder).
An alternate feeder connects through a tie breaker downstream of SEC2."""

DEFAULT_TOPOLOGY = {
    "source": {"id": "SRC1", "name": "Main Grid Source", "voltage_kv": 11.0, "status": "ONLINE"},
    "alternate_source": {"id": "ALT1", "name": "Alternate Feeder Source", "voltage_kv": 11.0, "status": "ONLINE"},
    "main_breaker": {"id": "CB0", "status": "CLOSED"},
    "tie_breaker": {"id": "TIE1", "status": "OPEN", "connects_after_section": "SEC2"},
    "sections": [
        {"id": "SEC1", "name": "Distribution Section 1", "load_kw": 120, "rated_current_a": 63.0, "switch_id": "CB1"},
        {"id": "SEC2", "name": "Distribution Section 2", "load_kw": 150, "rated_current_a": 80.0, "switch_id": "CB2"},
        {"id": "SEC3", "name": "Distribution Section 3", "load_kw": 100, "rated_current_a": 50.0, "switch_id": "CB3"},
    ],
}
