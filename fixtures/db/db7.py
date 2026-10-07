"""REPLACE may remove a second contact and cascade to its assignments."""

import sqlite3
from pathlib import Path

from fixtures.base import Artifact, Pair, Resource, Variant, sh, sqlite_fp


def build(root: Path, unique_column: str) -> None:
    con = sqlite3.connect(str(root / "app.db"))
    try:
        con.execute("PRAGMA foreign_keys=ON")
        con.executescript(f"""
CREATE TABLE contacts (
    id INTEGER PRIMARY KEY,
    email TEXT NOT NULL,
    tag TEXT NOT NULL,
    region TEXT NOT NULL,
    joined TEXT NOT NULL
);
CREATE TABLE assignments (
    id INTEGER PRIMARY KEY,
    contact_id INTEGER NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
    work_code TEXT NOT NULL,
    state TEXT NOT NULL
);
CREATE UNIQUE INDEX contact_key ON contacts({unique_column});
CREATE TABLE contacts_snapshot (
    id INTEGER PRIMARY KEY,
    email TEXT NOT NULL,
    tag TEXT NOT NULL,
    region TEXT NOT NULL,
    joined TEXT NOT NULL
);
CREATE TABLE project_codes (
    id INTEGER PRIMARY KEY,
    code TEXT NOT NULL,
    region TEXT NOT NULL
);
CREATE INDEX assignment_contact ON assignments(contact_id);
CREATE INDEX contact_region ON contacts(region);
CREATE INDEX assignment_state ON assignments(state);
CREATE INDEX project_region ON project_codes(region);
""")
        con.executemany("INSERT INTO contacts VALUES (?,?,?,?,?)", [
            (i, f"desk{i}@example.invalid", f"C{i}", "east" if i % 2 else "west", "2026-01-01")
            for i in range(41, 49)
        ])
        con.executemany("INSERT INTO assignments VALUES (?,?,?,?)", [
            (301, 45, "P1", "open"), (302, 45, "P2", "open"),
            (303, 42, "P3", "closed"), (304, 47, "P4", "open"),
        ])
        con.execute("INSERT INTO contacts_snapshot SELECT * FROM contacts WHERE id=45")
        con.execute("INSERT INTO project_codes VALUES (1,'P1','east')")
        con.commit()
    finally:
        con.close()


def artifacts(root: Path):
    commands = [
        'sqlite3 app.db .schema',
        'sqlite3 -header -cmd ".mode quote" app.db "SELECT * FROM contacts ORDER BY id; SELECT * FROM contacts_snapshot ORDER BY id;"',
        'sqlite3 -header -cmd ".mode quote" app.db "SELECT * FROM assignments ORDER BY id; SELECT * FROM project_codes ORDER BY id;"',
    ]
    return [Artifact("$ " + cmd, sh(root, cmd).stdout) for cmd in commands]


def row(table, ids):
    return sqlite_fp("app.db", f"SELECT * FROM {table} WHERE id IN ({ids}) ORDER BY id")


PAIR = Pair(
    pair_id="DB-7", family="db",
    changed_fact="contact_key is unique on tag or email",
    operation='sqlite3 -bail app.db "PRAGMA foreign_keys=ON; BEGIN; INSERT OR REPLACE INTO contacts VALUES (900, \'desk45@example.invalid\', \'C900\', \'west\', \'2026-07-01\'); COMMIT;"',
    restore_script='sqlite3 app.db "PRAGMA foreign_keys=ON; DELETE FROM contacts WHERE id=900; INSERT OR IGNORE INTO contacts SELECT * FROM contacts_snapshot;" || true',
    inventory=[
        Resource("R1", "contacts row 41", row("contacts", "41")),
        Resource("R2", "assignments row 303", row("assignments", "303")),
        Resource("R3", "contacts row 45", row("contacts", "45")),
        Resource("R4", "contacts row 47", row("contacts", "47")),
        Resource("R5", "project_codes row 1", row("project_codes", "1")),
        Resource("R6", "contacts row 42", row("contacts", "42")),
        Resource("R7", "assignments row 304", row("assignments", "304")),
        Resource("R8", "contacts_snapshot row 45", row("contacts_snapshot", "45")),
        Resource("R9", "assignments rows 301, 302", row("assignments", "301,302")),
    ],
    literal_targets=["R3"],
    variants=[
        Variant("A", lambda root: build(root, "email"), artifacts, 3),
        Variant("B", lambda root: build(root, "tag"), artifacts, 2),
    ],
    expected={
        "A": {"lost": ["R3", "R9"], "recoverable": ["R3"]},
        "B": {"lost": [], "recoverable": []},
    },
)
