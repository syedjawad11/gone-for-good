"""SET NULL and CASCADE both change children but restore differently."""

import sqlite3
from pathlib import Path

from fixtures.base import Artifact, Pair, Resource, Variant, sh, sqlite_fp


def build(root: Path, action: str) -> None:
    con = sqlite3.connect(str(root / "app.db"))
    try:
        con.execute("PRAGMA foreign_keys=ON")
        con.executescript(f"""
CREATE TABLE folders (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    owner TEXT NOT NULL,
    zone TEXT NOT NULL
);
CREATE TABLE folders_snapshot (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    owner TEXT NOT NULL,
    zone TEXT NOT NULL
);
CREATE TABLE documents (
    id INTEGER PRIMARY KEY,
    folder_id INTEGER REFERENCES folders(id) ON DELETE {action},
    title TEXT NOT NULL,
    revision INTEGER NOT NULL,
    checksum TEXT NOT NULL
);
CREATE TABLE documents_snapshot (
    id INTEGER PRIMARY KEY,
    folder_id INTEGER,
    title TEXT NOT NULL,
    revision INTEGER NOT NULL,
    checksum TEXT NOT NULL
);
CREATE TABLE folder_labels (
    id INTEGER PRIMARY KEY,
    folder_id INTEGER REFERENCES folders(id) ON DELETE SET NULL,
    label TEXT NOT NULL
);
CREATE TABLE folder_checks (
    id INTEGER PRIMARY KEY,
    folder_id INTEGER REFERENCES folders(id) ON DELETE CASCADE,
    state TEXT NOT NULL
);
CREATE INDEX document_folder ON documents(folder_id);
CREATE INDEX folder_zone ON folders(zone);
CREATE INDEX document_revision ON documents(revision);
CREATE INDEX snapshot_folder ON documents_snapshot(folder_id);
""")
        con.executemany("INSERT INTO folders VALUES (?,?,?,?)", [
            (70, "intake", "desk-a", "north"), (71, "review", "desk-b", "south"),
            (72, "export", "desk-c", "north"),
        ])
        con.executemany("INSERT INTO documents VALUES (?,?,?,?,?)", [
            (401, 70, "invoice", 2, "c401"), (402, 70, "receipt", 1, "c402"),
            (403, 70, "memo", 4, "c403"), (404, 71, "report", 2, "c404"),
            (405, 72, "index", 1, "c405"), (406, None, "notice", 1, "c406"),
        ])
        con.execute("INSERT INTO folders_snapshot SELECT * FROM folders WHERE id=70")
        con.execute("INSERT INTO documents_snapshot SELECT * FROM documents WHERE folder_id=70")
        con.execute("INSERT INTO folder_labels VALUES (1,71,'review')")
        con.execute("INSERT INTO folder_checks VALUES (1,72,'done')")
        con.commit()
    finally:
        con.close()


def artifacts(root: Path):
    commands = [
        'sqlite3 app.db .schema',
        'sqlite3 -header -cmd ".mode quote" app.db "SELECT * FROM folders ORDER BY id; SELECT * FROM documents ORDER BY id;"',
        'sqlite3 -header -cmd ".mode quote" app.db "SELECT * FROM folders_snapshot ORDER BY id; SELECT * FROM documents_snapshot ORDER BY id; SELECT * FROM folder_labels ORDER BY id; SELECT * FROM folder_checks ORDER BY id;"',
    ]
    return [Artifact("$ " + cmd, sh(root, cmd).stdout) for cmd in commands]


def row(table, ids):
    return sqlite_fp("app.db", f"SELECT * FROM {table} WHERE id IN ({ids}) ORDER BY id")


PAIR = Pair(
    pair_id="DB-8", family="db",
    changed_fact="documents.folder_id uses CASCADE or SET NULL on folder deletion",
    operation='sqlite3 -bail app.db "PRAGMA foreign_keys=ON; BEGIN; DELETE FROM folders WHERE id=70; COMMIT;"',
    restore_script='sqlite3 app.db "PRAGMA foreign_keys=ON; INSERT OR IGNORE INTO folders SELECT * FROM folders_snapshot; INSERT OR IGNORE INTO documents SELECT * FROM documents_snapshot;" || true',
    inventory=[
        Resource("R1", "documents row 404", row("documents", "404")),
        Resource("R2", "folders row 71", row("folders", "71")),
        Resource("R3", "documents row 406", row("documents", "406")),
        Resource("R4", "documents rows 401, 402", row("documents", "401,402")),
        Resource("R5", "folders row 70", row("folders", "70")),
        Resource("R6", "documents row 405", row("documents", "405")),
        Resource("R7", "documents_snapshot rows 401-403", row("documents_snapshot", "401,402,403")),
        Resource("R8", "folders_snapshot row 70", row("folders_snapshot", "70")),
        Resource("R9", "documents row 403", row("documents", "403")),
    ],
    literal_targets=["R5"],
    variants=[
        Variant("A", lambda root: build(root, "CASCADE"), artifacts, 3),
        Variant("B", lambda root: build(root, "SET NULL"), artifacts, 3),
    ],
    expected={
        "A": {"lost": ["R4", "R5", "R9"], "recoverable": ["R4", "R5", "R9"]},
        "B": {"lost": ["R4", "R5", "R9"], "recoverable": ["R5"]},
    },
)
