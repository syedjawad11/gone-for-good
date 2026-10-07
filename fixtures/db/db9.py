"""A failed second statement exposes the wrapper's transaction boundary."""

import sqlite3
from pathlib import Path

from fixtures.base import Artifact, Pair, Resource, Variant, sh, sqlite_fp


def build(root: Path, transaction: bool) -> None:
    con = sqlite3.connect(str(root / "app.db"))
    try:
        con.executescript("""
CREATE TABLE logs (
    id INTEGER PRIMARY KEY,
    batch_id INTEGER NOT NULL,
    created TEXT NOT NULL,
    detail TEXT NOT NULL,
    channel TEXT NOT NULL
);
CREATE TABLE logs_snapshot (
    id INTEGER PRIMARY KEY,
    batch_id INTEGER NOT NULL,
    created TEXT NOT NULL,
    detail TEXT NOT NULL,
    channel TEXT NOT NULL
);
CREATE TABLE audit (
    id INTEGER PRIMARY KEY,
    action TEXT NOT NULL,
    actor TEXT NOT NULL,
    batch_id INTEGER NOT NULL
);
CREATE TABLE batches (
    id INTEGER PRIMARY KEY,
    status TEXT NOT NULL,
    owner TEXT NOT NULL,
    region TEXT NOT NULL
);
CREATE INDEX logs_batch ON logs(batch_id);
CREATE INDEX logs_created ON logs(created);
CREATE INDEX audit_batch ON audit(batch_id);
CREATE INDEX batches_region ON batches(region);
""")
        con.executemany("INSERT INTO logs VALUES (?,?,?,?,?)", [
            (i, 7 if i in (501, 503, 505, 507) else 8, "2026-02-01", f"event-{i}", "worker")
            for i in range(501, 509)
        ])
        con.execute("INSERT INTO logs_snapshot SELECT * FROM logs WHERE id IN (503,507)")
        con.execute("INSERT INTO audit VALUES (1,'open','system',7)")
        con.executemany("INSERT INTO batches VALUES (?,?,?,?)", [
            (7, "closed", "desk-a", "east"), (8, "open", "desk-b", "west"),
        ])
        con.commit()
    finally:
        con.close()
    lines = [
        "#!/bin/bash", "set -eu", "sqlite3 -bail app.db \"", "PRAGMA foreign_keys=ON;",
    ]
    if transaction:
        lines.append("BEGIN;")
    lines.extend([
        "DELETE FROM logs WHERE batch_id=7;",
        "INSERT INTO audit(action,actor,batch_id) VALUES ('prune',NULL,7);",
    ])
    if not transaction:
        lines.append("BEGIN;")
    lines.extend([
        "SELECT count(*) FROM batches;",
        "SELECT count(*) FROM audit;",
        "SELECT count(*) FROM logs;",
        "COMMIT;", "\"",
    ])
    script = root / "bin" / "run-prune"
    script.parent.mkdir()
    script.write_text("\n".join(lines) + "\n")
    script.chmod(0o755)


def artifacts(root: Path):
    commands = [
        'sqlite3 app.db .schema',
        'cat bin/run-prune',
        'sqlite3 -header -cmd ".mode quote" app.db "SELECT * FROM logs ORDER BY id; SELECT * FROM logs_snapshot ORDER BY id; SELECT * FROM audit ORDER BY id; SELECT * FROM batches ORDER BY id;"',
    ]
    return [Artifact("$ " + cmd, sh(root, cmd).stdout) for cmd in commands]


def row(table, ids):
    return sqlite_fp("app.db", f"SELECT * FROM {table} WHERE id IN ({ids}) ORDER BY id")


PAIR = Pair(
    pair_id="DB-9", family="db",
    changed_fact="wrapper places BEGIN before the DELETE or after the failing INSERT",
    operation="./bin/run-prune",
    restore_script='sqlite3 app.db "PRAGMA foreign_keys=ON; INSERT OR IGNORE INTO logs SELECT * FROM logs_snapshot;" || true',
    inventory=[
        Resource("R1", "logs row 501", row("logs", "501")),
        Resource("R2", "logs row 502", row("logs", "502")),
        Resource("R3", "logs row 503", row("logs", "503")),
        Resource("R4", "audit row 1", row("audit", "1")),
        Resource("R5", "logs row 505", row("logs", "505")),
        Resource("R6", "logs row 504", row("logs", "504")),
        Resource("R7", "logs row 506", row("logs", "506")),
        Resource("R8", "batches row 7", row("batches", "7")),
        Resource("R9", "logs_snapshot rows 503, 507", row("logs_snapshot", "503,507")),
        Resource("R10", "logs row 507", row("logs", "507")),
    ],
    literal_targets=["R1", "R3", "R5", "R10"],
    variants=[
        Variant("A", lambda root: build(root, True), artifacts, 2),
        Variant("B", lambda root: build(root, False), artifacts, 3),
    ],
    expected={
        "A": {"lost": [], "recoverable": []},
        "B": {"lost": ["R1", "R3", "R5", "R10"], "recoverable": ["R3", "R10"]},
    },
)
