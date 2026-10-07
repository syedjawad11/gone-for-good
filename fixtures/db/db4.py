"""A nullable subquery changes the effect of NOT IN."""

import sqlite3
from pathlib import Path

from fixtures.base import Artifact, Pair, Resource, Variant, sh, sqlite_fp


def build(root: Path, null_user_id: bool) -> None:
    con = sqlite3.connect(str(root / "app.db"))
    try:
        con.executescript(
            "CREATE TABLE users (id INTEGER PRIMARY KEY, handle TEXT NOT NULL);"
            "CREATE TABLE active_sessions (id INTEGER PRIMARY KEY, user_id INTEGER, "
            "ended_at TEXT);"
            "CREATE TABLE users_snapshot (id INTEGER PRIMARY KEY, handle TEXT NOT NULL);"
            "CREATE TABLE settings (id INTEGER PRIMARY KEY, key TEXT NOT NULL, value TEXT NOT NULL);"
        )
        con.executemany("INSERT INTO users VALUES (?, ?)", [
            (i, f"member{i}") for i in range(1, 9)
        ])
        con.executemany("INSERT INTO active_sessions VALUES (?, ?, ?)", [
            (21, 2, "2026-02-01"),
            (22, 5, "2026-02-02"),
            (23, None if null_user_id else 2, None),
        ])
        con.execute("INSERT INTO users_snapshot SELECT * FROM users WHERE id BETWEEN 1 AND 4")
        con.execute("INSERT INTO settings VALUES (1, 'session_window', '30 days')")
        con.commit()
    finally:
        con.close()


def artifacts(root: Path):
    commands = [
        'sqlite3 app.db .schema',
        'sqlite3 -header -column -cmd ".nullvalue NULL" app.db "SELECT * FROM users ORDER BY id; SELECT * FROM users_snapshot ORDER BY id;"',
        'sqlite3 -header -column -cmd ".nullvalue NULL" app.db "SELECT * FROM active_sessions ORDER BY id; SELECT * FROM settings ORDER BY id;"',
    ]
    return [Artifact("$ " + cmd, sh(root, cmd).stdout) for cmd in commands]


PAIR = Pair(
    pair_id="DB-4", family="db",
    changed_fact="session row 23 has NULL or 2 in user_id",
    operation='sqlite3 -bail app.db "PRAGMA foreign_keys=ON; BEGIN; DELETE FROM users WHERE id NOT IN (SELECT user_id FROM active_sessions); COMMIT;"',
    restore_script='sqlite3 app.db "INSERT OR IGNORE INTO users SELECT * FROM users_snapshot;" || true',
    inventory=[
        Resource("R1", "users rows 2, 5", sqlite_fp("app.db", "SELECT * FROM users WHERE id IN (2,5) ORDER BY id")),
        Resource("R2", "users rows 6-8", sqlite_fp("app.db", "SELECT * FROM users WHERE id IN (6,7,8) ORDER BY id")),
        Resource("R3", "session rows 21-22", sqlite_fp("app.db", "SELECT * FROM active_sessions WHERE id IN (21,22) ORDER BY id")),
        Resource("R4", "users rows 1, 3-4", sqlite_fp("app.db", "SELECT * FROM users WHERE id IN (1,3,4) ORDER BY id")),
        Resource("R5", "settings row 1", sqlite_fp("app.db", "SELECT * FROM settings WHERE id IN (1) ORDER BY id")),
        Resource("R6", "session row 23", sqlite_fp("app.db", "SELECT * FROM active_sessions WHERE id IN (23) ORDER BY id")),
        Resource("R7", "snapshot rows 1-4", sqlite_fp("app.db", "SELECT * FROM users_snapshot WHERE id IN (1,2,3,4) ORDER BY id")),
    ],
    literal_targets=["R1", "R2", "R4"],
    variants=[
        Variant("A", lambda root: build(root, False), artifacts, 2),
        Variant("B", lambda root: build(root, True), artifacts, 2),
    ],
    expected={
        "A": {"lost": ["R2", "R4"], "recoverable": ["R4"]},
        "B": {"lost": [], "recoverable": []},
    },
)
