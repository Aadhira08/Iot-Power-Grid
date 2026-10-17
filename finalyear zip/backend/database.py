"""SQLite persistence layer (faults and events)."""

import json
import sqlite3
import threading

_local = threading.local()


def get_conn(db_path):
    if not hasattr(_local, "conn") or _local.db_path != db_path:
        _local.conn = sqlite3.connect(db_path, check_same_thread=False)
        _local.conn.row_factory = sqlite3.Row
        _local.db_path = db_path
        _init_schema(_local.conn)
    return _local.conn


def _init_schema(conn):
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS faults (
            fault_id TEXT PRIMARY KEY,
            timestamp TEXT NOT NULL,
            section_id TEXT NOT NULL,
            fault_type TEXT NOT NULL,
            voltage_kv REAL,
            current_a REAL,
            response TEXT
        );
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            type TEXT NOT NULL,
            message TEXT
        );
        CREATE TABLE IF NOT EXISTS config (
            key TEXT PRIMARY KEY,
            value TEXT
        );
        """
    )
    conn.commit()


def log_fault(db_path, fault):
    conn = get_conn(db_path)
    conn.execute(
        "INSERT OR REPLACE INTO faults VALUES (?,?,?,?,?,?,?)",
        (fault["fault_id"], fault["timestamp"], fault["section_id"],
         fault["fault_type"], fault.get("voltage_kv"), fault.get("current_a"),
         fault.get("response")),
    )
    conn.commit()


def log_event(db_path, event):
    conn = get_conn(db_path)
    conn.execute("INSERT INTO events (timestamp, type, message) VALUES (?,?,?)",
                 (event["timestamp"], event["type"], event.get("message")))
    conn.commit()


def get_faults(db_path, limit=100):
    conn = get_conn(db_path)
    rows = conn.execute(
        "SELECT * FROM faults ORDER BY timestamp DESC LIMIT ?", (limit,)
    ).fetchall()
    return [dict(r) for r in rows]


def get_events(db_path, limit=100):
    conn = get_conn(db_path)
    rows = conn.execute(
        "SELECT * FROM events ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    return [dict(r) for r in rows]


def save_config(db_path, cfg):
    conn = get_conn(db_path)
    for k, v in cfg.items():
        conn.execute("INSERT OR REPLACE INTO config VALUES (?,?)",
                     (k, json.dumps(v)))
    conn.commit()
