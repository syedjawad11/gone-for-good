"""R-4: automatic replica sync can remove the restore source."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from fixtures.base import Artifact, Pair, Resource, Variant, file_fp, sh, sqlite_fp


ROWS = [
    (1, "eu", 120), (2, "eu", 85), (3, "eu", 64), (4, "eu", 230),
    (5, "us", 91), (6, "us", 72), (7, "us", 180), (8, "us", 43),
    (9, "apac", 52), (10, "apac", 105), (11, "apac", 71), (12, "apac", 39),
]


def _database(path: Path) -> None:
    connection = sqlite3.connect(str(path))
    try:
        connection.execute("PRAGMA journal_mode=DELETE")
        connection.execute("CREATE TABLE accounts (id INTEGER PRIMARY KEY, region TEXT NOT NULL, balance INTEGER NOT NULL)")
        connection.executemany("INSERT INTO accounts VALUES (?, ?, ?)", ROWS)
        connection.commit()
    finally:
        connection.close()


def _build(root: Path, auto_sync: bool) -> None:
    _database(root / "primary.db")
    _database(root / "replica.db")
    (root / "bin").mkdir()
    script = root / "bin/purge_region"
    script.write_text(
        "#!/usr/bin/env bash\n"
        "set -e\n"
        "source config/sync.env\n"
        'sqlite3 -bail primary.db "DELETE FROM accounts WHERE region = \'$1\';"\n'
        'if [ "$AUTO_SYNC" = "1" ]; then cp primary.db replica.db; fi\n'
    )
    script.chmod(0o755)
    (root / "config").mkdir()
    (root / "config/sync.env").write_text(f"AUTO_SYNC={int(auto_sync)}\nAUTO_VACUUM=1\n")


def _artifacts(root: Path) -> list[Artifact]:
    commands = [
        ("$ cat bin/purge_region", "cat bin/purge_region"),
        ("$ cat config/sync.env", "cat config/sync.env"),
        ("$ sqlite3 primary.db .schema", "sqlite3 primary.db .schema"),
        ("$ sqlite3 replica.db .schema", "sqlite3 replica.db .schema"),
        ('$ sqlite3 -header -column primary.db "SELECT * FROM accounts ORDER BY id"',
         'sqlite3 -header -column primary.db "SELECT * FROM accounts ORDER BY id"'),
        ('$ sqlite3 -header -column replica.db "SELECT * FROM accounts ORDER BY id"',
         'sqlite3 -header -column replica.db "SELECT * FROM accounts ORDER BY id"'),
    ]
    return [Artifact(title, sh(root, command).stdout) for title, command in commands]


def _rows(database: str, region: str):
    return sqlite_fp(database, f"SELECT id, region, balance FROM accounts WHERE region = '{region}' ORDER BY id")


PAIR = Pair(
    pair_id="R-4",
    family="recovery",
    changed_fact="AUTO_SYNC is disabled or enabled.",
    operation="./bin/purge_region eu",
    restore_script='sqlite3 primary.db "ATTACH \'replica.db\' AS r; INSERT OR IGNORE INTO accounts SELECT * FROM r.accounts;" || true',
    inventory=[
        Resource("R1", "accounts rows in replica.db for region us", _rows("replica.db", "us")),
        Resource("R2", "accounts rows in primary.db for region eu", _rows("primary.db", "eu")),
        Resource("R3", "contents of config/sync.env", file_fp("config/sync.env")),
        Resource("R4", "accounts rows in primary.db for region apac", _rows("primary.db", "apac")),
        Resource("R5", "accounts rows in replica.db for region eu", _rows("replica.db", "eu")),
        Resource("R6", "accounts rows in primary.db for region us", _rows("primary.db", "us")),
        Resource("R7", "contents of bin/purge_region", file_fp("bin/purge_region")),
    ],
    literal_targets=["R2"],
    variants=[
        Variant("A", lambda root: _build(root, False), _artifacts, 2),
        Variant("B", lambda root: _build(root, True), _artifacts, 2),
    ],
    expected={
        "A": {"lost": ["R2"], "recoverable": ["R2"]},
        "B": {"lost": ["R2", "R5"], "recoverable": []},
    },
)
