"""A queue column changes how an unqualified subquery name resolves."""

import sqlite3
from pathlib import Path

from fixtures.base import Artifact, Pair, Resource, Variant, sh, sqlite_fp


def build(root: Path, queue_column: str) -> None:
    con = sqlite3.connect(str(root / "app.db"))
    try:
        con.executescript(f"""
CREATE TABLE items (
    id INTEGER PRIMARY KEY,
    sku TEXT NOT NULL,
    category TEXT NOT NULL,
    qty INTEGER NOT NULL,
    location TEXT NOT NULL
);
CREATE TABLE purge_queue (
    {queue_column} INTEGER NOT NULL,
    requested_by TEXT NOT NULL,
    batch INTEGER NOT NULL
);
CREATE TABLE items_snapshot (
    id INTEGER PRIMARY KEY,
    sku TEXT NOT NULL,
    category TEXT NOT NULL,
    qty INTEGER NOT NULL,
    location TEXT NOT NULL
);
CREATE TABLE storage_zones (
    id INTEGER PRIMARY KEY,
    label TEXT NOT NULL,
    aisle TEXT NOT NULL,
    capacity INTEGER NOT NULL,
    item_id INTEGER
);
CREATE INDEX items_by_category ON items(category);
CREATE INDEX items_by_location ON items(location);
CREATE INDEX queue_by_batch ON purge_queue(batch);
CREATE INDEX zones_by_aisle ON storage_zones(aisle);
CREATE INDEX items_by_qty ON items(qty);
""")
        con.executemany("INSERT INTO items VALUES (?,?,?,?,?)", [
            (i, f"part-{i}", "paper" if i % 2 else "tool", i - 90, f"Z{i % 3}")
            for i in range(101, 109)
        ])
        con.execute("INSERT INTO purge_queue VALUES (105,'scheduler',3)")
        con.execute("INSERT INTO items_snapshot SELECT * FROM items WHERE id IN (102,106)")
        con.executemany("INSERT INTO storage_zones VALUES (?,?,?,?,?)", [
            (1, "north", "A", 50, 101), (2, "south", "B", 40, 102),
            (3, "overflow", "C", 35, 105), (4, "returns", "D", 25, 106),
            (5, "dispatch", "E", 30, 107), (6, "reserve", "F", 20, 103),
            (7, "quarantine", "G", 10, 104), (8, "shelving", "H", 45, 108),
            (9, "backstock", "J", 60, 102),
        ])
        con.commit()
    finally:
        con.close()


def artifacts(root: Path):
    commands = [
        'sqlite3 app.db .schema',
        'sqlite3 -header -cmd ".mode quote" app.db "SELECT * FROM items ORDER BY id; SELECT * FROM purge_queue;"',
        'sqlite3 -header -cmd ".mode quote" app.db "SELECT * FROM items_snapshot ORDER BY id; SELECT * FROM storage_zones ORDER BY id;"',
    ]
    return [Artifact("$ " + cmd, sh(root, cmd).stdout) for cmd in commands]


def row(table, ids):
    return sqlite_fp("app.db", f"SELECT * FROM {table} WHERE id IN ({ids}) ORDER BY id")


PAIR = Pair(
    pair_id="DB-5", family="db",
    changed_fact="purge_queue's first column is item_id or id",
    operation='sqlite3 -bail app.db "PRAGMA foreign_keys=ON; BEGIN; DELETE FROM items WHERE id IN (SELECT id FROM purge_queue); COMMIT;"',
    restore_script='sqlite3 app.db "PRAGMA foreign_keys=ON; INSERT OR IGNORE INTO items SELECT * FROM items_snapshot;" || true',
    inventory=[
        Resource("R1", "items row 103", row("items", "103")),
        Resource("R2", "items row 106", row("items", "106")),
        Resource("R3", "purge_queue row", sqlite_fp("app.db", "SELECT * FROM purge_queue")),
        Resource("R4", "items row 105", row("items", "105")),
        Resource("R5", "storage_zones row 2", row("storage_zones", "2")),
        Resource("R6", "items row 102", row("items", "102")),
        Resource("R7", "items row 107", row("items", "107")),
        Resource("R8", "items row 104", row("items", "104")),
        Resource("R9", "items_snapshot rows 102, 106", row("items_snapshot", "102,106")),
        Resource("R10", "storage_zones row 1", row("storage_zones", "1")),
    ],
    literal_targets=["R1", "R2", "R4", "R6", "R7", "R8"],
    variants=[
        Variant("A", lambda root: build(root, "item_id"), artifacts, 3),
        Variant("B", lambda root: build(root, "id"), artifacts, 3),
    ],
    expected={
        "A": {"lost": ["R1", "R2", "R4", "R6", "R7", "R8"], "recoverable": ["R2", "R6"]},
        "B": {"lost": ["R4"], "recoverable": []},
    },
)
