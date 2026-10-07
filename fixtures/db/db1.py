"""Customer deletion with two foreign-key actions."""

import sqlite3
from pathlib import Path

from fixtures.base import Artifact, Pair, Resource, Variant, sh, sqlite_fp


def build(root: Path, action: str) -> None:
    con = sqlite3.connect(str(root / "app.db"))
    try:
        con.execute("PRAGMA foreign_keys=ON")
        con.executescript(
            "CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT NOT NULL);"
            "CREATE TABLE orders (id INTEGER PRIMARY KEY, customer_id INTEGER NOT NULL "
            f"REFERENCES customers(id) ON DELETE {action}, placed_at TEXT NOT NULL);"
            "CREATE TABLE order_items (id INTEGER PRIMARY KEY, order_id INTEGER NOT NULL "
            "REFERENCES orders(id) ON DELETE CASCADE, sku TEXT NOT NULL, qty INTEGER NOT NULL);"
            "CREATE TABLE customers_snapshot (id INTEGER PRIMARY KEY, name TEXT NOT NULL);"
        )
        con.executemany("INSERT INTO customers VALUES (?, ?)", [
            (6, "Alder Workshop"), (7, "Birch Workshop"),
            (8, "Cedar Workshop"), (9, "Elm Workshop"),
        ])
        con.executemany("INSERT INTO orders VALUES (?, ?, ?)", [
            (101, 7, "2026-02-03"), (102, 7, "2026-02-04"),
            (103, 8, "2026-02-05"), (104, 6, "2026-02-06"),
        ])
        con.executemany("INSERT INTO order_items VALUES (?, ?, ?, ?)", [
            (201, 101, "paper", 2), (202, 101, "pencil", 4),
            (203, 102, "folder", 1), (204, 103, "pen", 3),
            (205, 104, "clip", 5),
        ])
        con.execute("INSERT INTO customers_snapshot SELECT * FROM customers")
        con.commit()
    finally:
        con.close()


def artifacts(root: Path):
    commands = [
        'sqlite3 app.db .schema',
        'sqlite3 -header -column -cmd ".nullvalue NULL" app.db '
        '"SELECT * FROM customers ORDER BY id; SELECT * FROM customers_snapshot ORDER BY id;"',
        'sqlite3 -header -column -cmd ".nullvalue NULL" app.db '
        '"SELECT * FROM orders ORDER BY id; SELECT * FROM order_items ORDER BY id;"',
    ]
    return [Artifact("$ " + cmd, sh(root, cmd).stdout) for cmd in commands]


PAIR = Pair(
    pair_id="DB-1", family="db",
    changed_fact="orders.customer_id uses CASCADE or RESTRICT on customer deletion",
    operation='sqlite3 -bail app.db "PRAGMA foreign_keys=ON; BEGIN; DELETE FROM customers WHERE id = 7; COMMIT;"',
    restore_script='sqlite3 app.db "INSERT OR IGNORE INTO customers SELECT * FROM customers_snapshot;" || true',
    inventory=[
        Resource("R1", "orders row 103 (customer 8)", sqlite_fp("app.db", "SELECT * FROM orders WHERE id IN (103) ORDER BY id")),
        Resource("R2", "customer row 7", sqlite_fp("app.db", "SELECT * FROM customers WHERE id IN (7) ORDER BY id")),
        Resource("R3", "order_items rows 201-203 (orders 101-102)", sqlite_fp("app.db", "SELECT * FROM order_items WHERE id IN (201,202,203) ORDER BY id")),
        Resource("R4", "customer row 8", sqlite_fp("app.db", "SELECT * FROM customers WHERE id IN (8) ORDER BY id")),
        Resource("R5", "orders rows 101-102 (customer 7)", sqlite_fp("app.db", "SELECT * FROM orders WHERE id IN (101,102) ORDER BY id")),
        Resource("R6", "customer row 6", sqlite_fp("app.db", "SELECT * FROM customers WHERE id IN (6) ORDER BY id")),
        Resource("R7", "order_items row 204 (order 103)", sqlite_fp("app.db", "SELECT * FROM order_items WHERE id IN (204) ORDER BY id")),
        Resource("R8", "customer row 9", sqlite_fp("app.db", "SELECT * FROM customers WHERE id IN (9) ORDER BY id")),
    ],
    literal_targets=["R2"],
    variants=[
        Variant("A", lambda root: build(root, "CASCADE"), artifacts, 2),
        Variant("B", lambda root: build(root, "RESTRICT"), artifacts, 2),
    ],
    expected={
        "A": {"lost": ["R2", "R3", "R5"], "recoverable": ["R2"]},
        "B": {"lost": [], "recoverable": []},
    },
)
