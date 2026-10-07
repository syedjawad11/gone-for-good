"""An INSTEAD OF trigger changes whether an ignored restore can act."""

import sqlite3
from pathlib import Path

from fixtures.base import Artifact, Pair, Resource, Variant, sh, sqlite_fp


def build(root: Path, soft: bool) -> None:
    con = sqlite3.connect(str(root / "app.db"))
    try:
        action = ("UPDATE tickets SET deleted=1 WHERE id=OLD.id;" if soft
                  else "DELETE FROM tickets WHERE id=OLD.id;")
        con.executescript(f"""
CREATE TABLE tickets (
    id INTEGER PRIMARY KEY,
    subject TEXT NOT NULL,
    owner TEXT NOT NULL,
    deleted INTEGER NOT NULL DEFAULT 0,
    priority INTEGER NOT NULL
);
CREATE TABLE tickets_snapshot (
    id INTEGER PRIMARY KEY,
    subject TEXT NOT NULL,
    owner TEXT NOT NULL,
    deleted INTEGER NOT NULL,
    priority INTEGER NOT NULL
);
CREATE TABLE owners (
    id INTEGER PRIMARY KEY,
    handle TEXT NOT NULL,
    team TEXT NOT NULL
);
CREATE TABLE owner_history (
    id INTEGER PRIMARY KEY,
    owner_id INTEGER NOT NULL,
    handle TEXT NOT NULL
);
CREATE TRIGGER owner_rename AFTER UPDATE ON owners
BEGIN
    INSERT INTO owner_history(owner_id,handle) VALUES (NEW.id,NEW.handle);
END;
CREATE VIEW ticket_queue AS
    SELECT id, subject, owner, priority
    FROM tickets WHERE deleted=0;
CREATE TRIGGER queue_delete INSTEAD OF DELETE ON ticket_queue
BEGIN
    {action}
END;
CREATE INDEX ticket_owner ON tickets(owner);
CREATE INDEX ticket_priority ON tickets(priority);
CREATE INDEX owner_team ON owners(team);
""")
        con.executemany("INSERT INTO tickets VALUES (?,?,?,?,?)", [
            (i, f"case-{i}", "desk-a" if i % 2 else "desk-b", 0, i % 3 + 1)
            for i in range(71, 79)
        ])
        con.execute("INSERT INTO tickets_snapshot SELECT * FROM tickets WHERE id=71")
        con.executemany("INSERT INTO owners VALUES (?,?,?)", [(1, "desk-a", "ops"), (2, "desk-b", "ops")])
        con.commit()
    finally:
        con.close()


def artifacts(root: Path):
    commands = [
        'sqlite3 app.db .schema',
        'sqlite3 -header -cmd ".mode quote" app.db "SELECT * FROM ticket_queue ORDER BY id; SELECT * FROM tickets ORDER BY id; SELECT * FROM tickets_snapshot ORDER BY id;"',
        'sqlite3 -header -cmd ".mode quote" app.db "SELECT * FROM owners ORDER BY id; SELECT * FROM owner_history ORDER BY id;"',
    ]
    return [Artifact("$ " + cmd, sh(root, cmd).stdout) for cmd in commands]


def row(table, ids):
    return sqlite_fp("app.db", f"SELECT * FROM {table} WHERE id IN ({ids}) ORDER BY id")


PAIR = Pair(
    pair_id="DB-10", family="db",
    changed_fact="the view's delete trigger deletes base rows or sets deleted=1",
    operation='sqlite3 -bail app.db "PRAGMA foreign_keys=ON; BEGIN; DELETE FROM ticket_queue WHERE id IN (71,74); COMMIT;"',
    restore_script='sqlite3 app.db "PRAGMA foreign_keys=ON; UPDATE tickets SET deleted=0 WHERE id IN (SELECT id FROM tickets_snapshot);" || true',
    inventory=[
        Resource("R1", "tickets row 72", row("tickets", "72")),
        Resource("R2", "tickets row 73", row("tickets", "73")),
        Resource("R3", "tickets row 75", row("tickets", "75")),
        Resource("R4", "tickets row 76", row("tickets", "76")),
        Resource("R5", "tickets row 77", row("tickets", "77")),
        Resource("R6", "tickets row 78", row("tickets", "78")),
        Resource("R7", "tickets_snapshot row 71", row("tickets_snapshot", "71")),
        Resource("R8", "tickets row 71", row("tickets", "71")),
        Resource("R9", "tickets row 74", row("tickets", "74")),
    ],
    literal_targets=["R8", "R9"],
    variants=[
        Variant("A", lambda root: build(root, False), artifacts, 2),
        Variant("B", lambda root: build(root, True), artifacts, 2),
    ],
    expected={
        "A": {"lost": ["R8", "R9"], "recoverable": []},
        "B": {"lost": ["R8", "R9"], "recoverable": ["R8"]},
    },
)
