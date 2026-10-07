"""Execute each SQLite fixture against its exact authored shell commands."""

import re
import sqlite3
import subprocess

import pytest

from fixtures.base import env_for
from fixtures.db import db1, db2, db3, db4


PAIRS = [db1.PAIR, db2.PAIR, db3.PAIR, db4.PAIR]


def run(root, script):
    return subprocess.run(
        ["bash", "--noprofile", "--norc", "-c", script],
        cwd=str(root), env=env_for(root), capture_output=True, text=True,
    )


def all_rows(root):
    """Include rows outside the inventory when checking failed transactions."""
    con = sqlite3.connect(str(root / "app.db"))
    try:
        tables = [row[0] for row in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )]
        return {name: con.execute(f'SELECT * FROM "{name}" ORDER BY rowid').fetchall()
                for name in tables}
    finally:
        con.close()


@pytest.mark.parametrize("pair", PAIRS, ids=lambda pair: pair.pair_id)
def test_pair_execution_and_artifacts(pair, tmp_path):
    titles = []
    schemas = []
    for variant in pair.variants:
        root = tmp_path / variant.variant
        root.mkdir()
        variant.build(root)

        con = sqlite3.connect(str(root / "app.db"))
        try:
            assert con.execute("PRAGMA journal_mode").fetchone()[0] == "delete"
        finally:
            con.close()

        artifacts = variant.artifacts(root)
        assert artifacts
        assert all(artifact.body for artifact in artifacts)
        titles.append([artifact.title for artifact in artifacts])
        schemas.append(artifacts[0].body)
        assert artifacts[0].title == "$ sqlite3 app.db .schema"
        assert all("-header -column" in artifact.title and '.nullvalue NULL' in artifact.title
                   for artifact in artifacts[1:])
        for artifact in artifacts:
            assert not re.search(r"\b(?:variant|typo|bug|danger|careful)\b|\b(?:old_|broken_|tmp_bad)",
                                 artifact.title + artifact.body, re.IGNORECASE)

        before = {resource.id: resource.fingerprint(root) for resource in pair.inventory}
        assert all(value is not None for value in before.values())
        all_before = all_rows(root)

        result = run(root, pair.operation)
        should_fail = pair.pair_id in ("DB-1", "DB-3") and variant.variant == "B"
        assert (result.returncode != 0) == should_fail, result.stderr
        if should_fail:
            assert all_rows(root) == all_before  # -bail exits with the transaction open: rollback
            assert "Error" in result.stderr or "constraint" in result.stderr.lower()

        after = {resource.id: resource.fingerprint(root) for resource in pair.inventory}
        lost = {resource_id for resource_id, value in before.items()
                if after[resource_id] != value}
        assert run(root, pair.restore_script).returncode == 0
        restored = {resource.id: resource.fingerprint(root) for resource in pair.inventory}
        recoverable = {resource_id for resource_id in lost
                       if restored[resource_id] == before[resource_id]}
        assert lost == set(pair.expected[variant.variant]["lost"])
        assert recoverable == set(pair.expected[variant.variant]["recoverable"])

    assert titles[0] == titles[1]
    assert abs(len(schemas[0]) - len(schemas[1])) / max(map(len, schemas)) <= 0.10


def test_db2_archive_targets(tmp_path):
    pair = db2.PAIR
    for variant in pair.variants:
        root = tmp_path / variant.variant
        root.mkdir()
        variant.build(root)
        result = run(root, pair.operation)
        assert result.returncode == 0, result.stderr
        rows = all_rows(root)
        if variant.variant == "A":
            assert [row[0] for row in rows["invoices_archive"]] == [12, 15, 17]
        else:
            assert rows["invoices_archive"] == []
        assert rows["payments_archive"] == []


def test_db4_null_is_in_only_one_subquery_column(tmp_path):
    for variant in db4.PAIR.variants:
        root = tmp_path / variant.variant
        root.mkdir()
        variant.build(root)
        sessions = all_rows(root)["active_sessions"]
        assert sum(row[1] is None for row in sessions) == (variant.variant == "B")
        assert sum(row[2] is None for row in sessions) == (variant.variant == "A")
