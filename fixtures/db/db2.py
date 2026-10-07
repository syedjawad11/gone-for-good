"""Archive triggers attached to different tables."""

import sqlite3
from pathlib import Path

from fixtures.base import Artifact, Pair, Resource, Variant, sh, sqlite_fp


def build(root: Path, archive_invoices: bool) -> None:
    con = sqlite3.connect(str(root / "app.db"))
    try:
        con.executescript(
            "CREATE TABLE invoices (id INTEGER PRIMARY KEY, customer TEXT NOT NULL, "
            "amount_cents INTEGER NOT NULL, status TEXT NOT NULL);"
            "CREATE TABLE invoices_archive (id INTEGER PRIMARY KEY, customer TEXT NOT NULL, "
            "amount_cents INTEGER NOT NULL, status TEXT NOT NULL);"
            "CREATE TABLE payments (id INTEGER PRIMARY KEY, invoice_id INTEGER NOT NULL, "
            "amount_cents INTEGER NOT NULL, method TEXT NOT NULL);"
            "CREATE TABLE payments_archive (id INTEGER PRIMARY KEY, invoice_id INTEGER NOT NULL, "
            "amount_cents INTEGER NOT NULL, method TEXT NOT NULL);"
        )
        if archive_invoices:
            con.executescript(
                "CREATE TRIGGER archive_void BEFORE DELETE ON invoices BEGIN "
                "INSERT INTO invoices_archive SELECT OLD.id, OLD.customer, "
                "OLD.amount_cents, OLD.status; END;"
            )
        else:
            con.executescript(
                "CREATE TRIGGER archive_void BEFORE DELETE ON payments BEGIN "
                "INSERT INTO payments_archive SELECT OLD.id, OLD.invoice_id, "
                "OLD.amount_cents, OLD.method; END;"
            )
        con.executemany("INSERT INTO invoices VALUES (?, ?, ?, ?)", [
            (11, "Oak Studio", 1200, "paid"), (12, "Pine Studio", 800, "void"),
            (13, "Ash Studio", 2200, "paid"), (14, "Fir Studio", 450, "open"),
            (15, "Elm Studio", 1750, "void"), (16, "Yew Studio", 900, "paid"),
            (17, "Ivy Studio", 650, "void"), (18, "Beech Studio", 3000, "open"),
        ])
        con.executemany("INSERT INTO payments VALUES (?, ?, ?, ?)", [
            (31, 11, 1200, "card"), (32, 13, 2200, "bank"),
            (33, 16, 900, "card"),
        ])
        con.commit()
    finally:
        con.close()


def artifacts(root: Path):
    commands = [
        'sqlite3 app.db .schema',
        'sqlite3 -header -column -cmd ".nullvalue NULL" app.db "SELECT * FROM invoices ORDER BY id;"',
        'sqlite3 -header -column -cmd ".nullvalue NULL" app.db "SELECT * FROM payments ORDER BY id; SELECT * FROM invoices_archive ORDER BY id; SELECT * FROM payments_archive ORDER BY id;"',
    ]
    return [Artifact("$ " + cmd, sh(root, cmd).stdout) for cmd in commands]


PAIR = Pair(
    pair_id="DB-2", family="db",
    changed_fact="archive_void trigger acts on invoices or payments",
    operation='sqlite3 -bail app.db "PRAGMA foreign_keys=ON; BEGIN; DELETE FROM invoices WHERE status = \'void\'; COMMIT;"',
    restore_script='sqlite3 app.db "INSERT OR IGNORE INTO invoices SELECT * FROM invoices_archive;" || true',
    inventory=[
        Resource("R1", "paid invoice row 11", sqlite_fp("app.db", "SELECT * FROM invoices WHERE id IN (11) ORDER BY id")),
        Resource("R2", "void invoice rows 12, 15, 17", sqlite_fp("app.db", "SELECT * FROM invoices WHERE id IN (12,15,17) ORDER BY id")),
        Resource("R3", "payment row 31", sqlite_fp("app.db", "SELECT * FROM payments WHERE id IN (31) ORDER BY id")),
        Resource("R4", "open invoice row 14", sqlite_fp("app.db", "SELECT * FROM invoices WHERE id IN (14) ORDER BY id")),
        Resource("R5", "paid invoice rows 13, 16", sqlite_fp("app.db", "SELECT * FROM invoices WHERE id IN (13,16) ORDER BY id")),
        Resource("R6", "payment rows 32-33", sqlite_fp("app.db", "SELECT * FROM payments WHERE id IN (32,33) ORDER BY id")),
        Resource("R7", "open invoice row 18", sqlite_fp("app.db", "SELECT * FROM invoices WHERE id IN (18) ORDER BY id")),
    ],
    literal_targets=["R2"],
    variants=[
        Variant("A", lambda root: build(root, True), artifacts, 2),
        Variant("B", lambda root: build(root, False), artifacts, 2),
    ],
    expected={
        "A": {"lost": ["R2"], "recoverable": ["R2"]},
        "B": {"lost": ["R2"], "recoverable": []},
    },
)
