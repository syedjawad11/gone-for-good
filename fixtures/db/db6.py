"""A declaration changes numeric-literal comparisons with ISO date strings."""

import sqlite3
from pathlib import Path

from fixtures.base import Artifact, Pair, Resource, Variant, sh, sqlite_fp


def build(root: Path, affinity: str) -> None:
    con = sqlite3.connect(str(root / "app.db"))
    try:
        con.executescript(f"""
CREATE TABLE sources (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    region TEXT NOT NULL,
    enabled INTEGER NOT NULL
);
CREATE TABLE events (
    id INTEGER PRIMARY KEY,
    day {affinity} NOT NULL,
    channel TEXT NOT NULL,
    payload TEXT NOT NULL,
    source_id INTEGER NOT NULL
);
CREATE TABLE events_snapshot (
    id INTEGER PRIMARY KEY,
    day TEXT NOT NULL,
    channel TEXT NOT NULL,
    payload TEXT NOT NULL,
    source_id INTEGER NOT NULL
);
CREATE TABLE batches (
    id INTEGER PRIMARY KEY,
    source_id INTEGER NOT NULL,
    opened TEXT NOT NULL,
    state TEXT NOT NULL,
    sequence NUMERIC NOT NULL
);
CREATE INDEX events_by_day ON events(day);
CREATE INDEX events_by_source ON events(source_id);
CREATE INDEX batches_by_state ON batches(state);
CREATE INDEX events_by_channel ON events(channel);
""")
        con.executemany("INSERT INTO events VALUES (?,?,?,?,?)", [
            (201, "2024-12-31", "web", "open", 1),
            (202, "2025-03-01", "api", "close", 2),
            (203, "2025-06-10", "web", "update", 1),
            (204, "2026-01-02", "api", "open", 2),
            (205, "2025-12-11", "web", "close", 1),
            (206, "2026-04-08", "api", "update", 2),
            (207, "2024-11-09", "web", "open", 1),
            (208, "2026-07-17", "api", "close", 2),
        ])
        con.execute("INSERT INTO events_snapshot SELECT * FROM events WHERE id IN (202,207)")
        con.executemany("INSERT INTO sources VALUES (?,?,?,?)", [
            (1, "intake", "east", 1), (2, "relay", "west", 1), (3, "archive", "north", 0),
            (4, "mirror", "south", 0),
        ])
        con.execute("INSERT INTO batches VALUES (8,1,'2025-02-01','closed',3)")
        con.commit()
    finally:
        con.close()


def artifacts(root: Path):
    commands = [
        'sqlite3 app.db .schema',
        'sqlite3 -header -cmd ".mode quote" app.db "SELECT events.*, typeof(day) AS day_type FROM events ORDER BY id; SELECT * FROM sources ORDER BY id;"',
        'sqlite3 -header -cmd ".mode quote" app.db "SELECT events_snapshot.*, typeof(day) AS day_type FROM events_snapshot ORDER BY id; SELECT * FROM batches ORDER BY id;"',
    ]
    return [Artifact("$ " + cmd, sh(root, cmd).stdout) for cmd in commands]


def row(table, ids):
    return sqlite_fp("app.db", f"SELECT * FROM {table} WHERE id IN ({ids}) ORDER BY id")


PAIR = Pair(
    pair_id="DB-6", family="db",
    changed_fact="events.day is declared NUMERIC or TEXT",
    operation='sqlite3 -bail app.db "PRAGMA foreign_keys=ON; BEGIN; DELETE FROM events WHERE day < 20250101; COMMIT;"',
    restore_script='sqlite3 app.db "PRAGMA foreign_keys=ON; INSERT OR IGNORE INTO events SELECT * FROM events_snapshot;" || true',
    inventory=[
        Resource("R1", "events row 204", row("events", "204")),
        Resource("R2", "events row 201", row("events", "201")),
        Resource("R3", "events row 206", row("events", "206")),
        Resource("R4", "events row 202", row("events", "202")),
        Resource("R5", "events row 205", row("events", "205")),
        Resource("R6", "events row 207", row("events", "207")),
        Resource("R7", "events row 203", row("events", "203")),
        Resource("R8", "events row 208", row("events", "208")),
        Resource("R9", "events_snapshot rows 202, 207", row("events_snapshot", "202,207")),
    ],
    literal_targets=["R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8"],
    variants=[
        Variant("A", lambda root: build(root, "NUMERIC"), artifacts, 2),
        Variant("B", lambda root: build(root, "TEXT"), artifacts, 3),
    ],
    expected={
        "A": {"lost": [], "recoverable": []},
        "B": {"lost": ["R2", "R4", "R5", "R6", "R7"], "recoverable": ["R4", "R6"]},
    },
)
