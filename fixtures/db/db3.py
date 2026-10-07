"""A failed audit insert decides whether a log purge commits."""

import sqlite3
from pathlib import Path

from fixtures.base import Artifact, Pair, Resource, Variant, sh, sqlite_fp


def build(root: Path, actor_required: bool) -> None:
    con = sqlite3.connect(str(root / "app.db"))
    try:
        audit_columns = ("action TEXT, actor TEXT NOT NULL" if actor_required
                         else "action TEXT NOT NULL, actor TEXT")
        con.executescript(
            "CREATE TABLE logs (id INTEGER PRIMARY KEY, ts TEXT NOT NULL, "
            "message TEXT NOT NULL);"
            f"CREATE TABLE audit (id INTEGER PRIMARY KEY, {audit_columns});"
            "CREATE TABLE logs_export (id INTEGER PRIMARY KEY, ts TEXT NOT NULL, "
            "message TEXT NOT NULL);"
        )
        con.executemany("INSERT INTO logs VALUES (?, ?, ?)", [
            (101, "2025-09-18", "scheduler started"),
            (102, "2025-11-30", "batch completed"),
            (103, "2025-12-03", "queue checked"),
            (104, "2025-12-21", "report created"),
            (105, "2026-01-02", "scheduler started"),
            (106, "2026-02-14", "batch completed"),
            (107, "2026-03-10", "queue checked"),
        ])
        con.execute("INSERT INTO logs_export SELECT * FROM logs WHERE ts >= '2025-12-01' AND ts < '2026-01-01'")
        con.execute("INSERT INTO audit VALUES (1, 'start', 'system')")
        con.commit()
    finally:
        con.close()


def artifacts(root: Path):
    commands = [
        'sqlite3 app.db .schema',
        'sqlite3 -header -column -cmd ".nullvalue NULL" app.db "SELECT * FROM logs ORDER BY id; SELECT * FROM logs_export ORDER BY id;"',
        'sqlite3 -header -column -cmd ".nullvalue NULL" app.db "SELECT * FROM audit ORDER BY id;"',
    ]
    return [Artifact("$ " + cmd, sh(root, cmd).stdout) for cmd in commands]


PAIR = Pair(
    pair_id="DB-3", family="db",
    changed_fact="audit.actor or audit.action carries the NOT NULL constraint",
    operation='sqlite3 -bail app.db "PRAGMA foreign_keys=ON; BEGIN; DELETE FROM logs WHERE ts < \'2026-01-01\'; INSERT INTO audit(action, actor) VALUES (\'purge\', NULL); COMMIT;"',
    restore_script='sqlite3 app.db "INSERT OR IGNORE INTO logs SELECT * FROM logs_export;" || true',
    inventory=[
        Resource("R1", "2026 log rows 105-106", sqlite_fp("app.db", "SELECT * FROM logs WHERE id IN (105,106) ORDER BY id")),
        Resource("R2", "December 2025 log rows 103-104", sqlite_fp("app.db", "SELECT * FROM logs WHERE id IN (103,104) ORDER BY id")),
        Resource("R3", "audit row 1", sqlite_fp("app.db", "SELECT * FROM audit WHERE id IN (1) ORDER BY id")),
        Resource("R4", "September-November 2025 log rows 101-102", sqlite_fp("app.db", "SELECT * FROM logs WHERE id IN (101,102) ORDER BY id")),
        Resource("R5", "2026 log row 107", sqlite_fp("app.db", "SELECT * FROM logs WHERE id IN (107) ORDER BY id")),
        Resource("R6", "exported December log rows 103-104", sqlite_fp("app.db", "SELECT * FROM logs_export WHERE id IN (103,104) ORDER BY id")),
    ],
    literal_targets=["R2", "R4"],
    variants=[
        Variant("A", lambda root: build(root, False), artifacts, 2),
        Variant("B", lambda root: build(root, True), artifacts, 2),
    ],
    expected={
        "A": {"lost": ["R2", "R4"], "recoverable": ["R2"]},
        "B": {"lost": [], "recoverable": []},
    },
)
