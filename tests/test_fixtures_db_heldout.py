"""Execute every held-out SQLite operation and its authored restore script."""

import difflib
import math
import re
import sqlite3
import subprocess

import pytest

from fixtures.base import env_for
from fixtures.db import db5, db6, db7, db8, db9, db10


PAIRS = [db5.PAIR, db6.PAIR, db7.PAIR, db8.PAIR, db9.PAIR, db10.PAIR]
FORBIDDEN = re.compile(r"\b(?:variant|typo|bug|danger|careful|old_|broken_|tmp_bad)\b", re.I)


def test_set_balance():
    def permanent(pair, variant):
        gold = pair.expected[variant]
        return len(set(gold["lost"]) - set(gold["recoverable"]))

    assert sum(permanent(pair, "A") > permanent(pair, "B") for pair in PAIRS) == 3
    assert sum(permanent(pair, "B") > permanent(pair, "A") for pair in PAIRS) == 3
    assert sum(any(not pair.expected[v]["lost"] for v in ("A", "B")) for pair in PAIRS) >= 2
    assert sum(pair.expected["A"]["lost"] == pair.expected["B"]["lost"]
               and pair.expected["A"]["recoverable"] != pair.expected["B"]["recoverable"]
               for pair in PAIRS) >= 2
    nonempty_loss_sets = [frozenset(pair.expected[v]["lost"]) for pair in PAIRS
                          for v in ("A", "B") if pair.expected[v]["lost"]]
    assert len(nonempty_loss_sets) == len(set(nonempty_loss_sets)) + 2  # DB-8 and DB-10 match within pair.
    changed_positions = {}
    for pair in PAIRS:
        for resource_id in set(pair.expected["A"]["lost"] + pair.expected["A"]["recoverable"]
                               + pair.expected["B"]["lost"] + pair.expected["B"]["recoverable"]):
            answers = [(resource_id in pair.expected[v]["lost"],
                        resource_id in pair.expected[v]["recoverable"]) for v in ("A", "B")]
            if answers[0] != answers[1]:
                changed_positions[resource_id] = changed_positions.get(resource_id, 0) + 1
    assert max(changed_positions.values()) <= 2, changed_positions


def run(root, script):
    return subprocess.run(
        ["bash", "--noprofile", "--norc", "-c", script],
        cwd=str(root), env=env_for(root), capture_output=True, text=True,
    )


def rows(root, table):
    con = sqlite3.connect(str(root / "app.db"))
    try:
        return con.execute(f'SELECT * FROM "{table}" ORDER BY rowid').fetchall()
    finally:
        con.close()


@pytest.mark.parametrize("pair", PAIRS, ids=lambda p: p.pair_id)
def test_pair_gold_and_surface(pair, tmp_path):
    variants = {}
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
        assert 3 <= len(artifacts) <= 5
        assert 2 <= variant.hops <= len(artifacts)
        assert artifacts[0].title == "$ sqlite3 app.db .schema"
        assert all(a.body and not FORBIDDEN.search(a.title + a.body) for a in artifacts)
        assert any(len(a.body.splitlines()) >= 30 for a in artifacts)
        assert 1500 <= sum(len(a.body) for a in artifacts) <= 4000
        assert all('.mode quote' in a.title for a in artifacts[1:]
                   if a.title.startswith("$ sqlite3"))
        if pair.pair_id == "DB-6":
            assert all("typeof(day)" in a.title for a in artifacts[1:])
        if pair.pair_id == "DB-7":
            assert "'desk45@example.invalid'" in artifacts[1].body
        before = {r.id: r.fingerprint(root) for r in pair.inventory}
        assert 7 <= len(before) <= 12
        assert all(v is not None for v in before.values())
        result = run(root, pair.operation)
        assert (result.returncode != 0) == (pair.pair_id == "DB-9"), result.stderr
        after = {r.id: r.fingerprint(root) for r in pair.inventory}
        lost = {key for key, value in before.items() if after[key] != value}
        restore = run(root, pair.restore_script)
        assert restore.returncode == 0, restore.stderr
        restored = {r.id: r.fingerprint(root) for r in pair.inventory}
        recoverable = {key for key in lost if restored[key] == before[key]}
        assert lost == set(pair.expected[variant.variant]["lost"])
        assert recoverable == set(pair.expected[variant.variant]["recoverable"])
        variants[variant.variant] = artifacts

    a, b = variants["A"], variants["B"]
    assert [x.title for x in a] == [x.title for x in b]
    changed = sum(line[:2] in ("- ", "+ ") for line in difflib.ndiff(
        "\n".join(x.body for x in a).splitlines(),
        "\n".join(x.body for x in b).splitlines(),
    ))
    assert math.ceil(changed / 2) <= 8
    prompt_a = "\n".join(x.title + "\n" + x.body for x in a)
    prompt_b = "\n".join(x.title + "\n" + x.body for x in b)
    assert max(len(prompt_a), len(prompt_b)) / min(len(prompt_a), len(prompt_b)) <= 1.01


def test_db5_correlated_queue_is_nonempty(tmp_path):
    for variant in db5.PAIR.variants:
        root = tmp_path / variant.variant
        root.mkdir()
        variant.build(root)
        assert len(rows(root, "purge_queue")) == 1
        assert all(row[0] is not None for row in rows(root, "items"))


def test_db7_replace_cascades_only_with_email_index(tmp_path):
    for variant in db7.PAIR.variants:
        root = tmp_path / variant.variant
        root.mkdir()
        variant.build(root)
        assert run(root, db7.PAIR.operation).returncode == 0
        ids = [row[0] for row in rows(root, "assignments")]
        assert (301 in ids, 302 in ids) == ((False, False) if variant.variant == "A" else (True, True))


def test_db8_changed_rows_differ_after_restore(tmp_path):
    for variant in db8.PAIR.variants:
        root = tmp_path / variant.variant
        root.mkdir()
        variant.build(root)
        assert run(root, db8.PAIR.operation).returncode == 0
        assert run(root, db8.PAIR.restore_script).returncode == 0
        children = [row for row in rows(root, "documents") if row[0] in (401, 402, 403)]
        assert [row[1] for row in children] == ([70] * 3 if variant.variant == "A" else [None] * 3)


def test_db9_failed_insert_rolls_back_only_inside_begin(tmp_path):
    for variant in db9.PAIR.variants:
        root = tmp_path / variant.variant
        root.mkdir()
        variant.build(root)
        original = rows(root, "logs")
        result = run(root, db9.PAIR.operation)
        assert result.returncode != 0
        assert len(rows(root, "logs")) == (len(original) if variant.variant == "A" else 4)
        assert len(rows(root, "audit")) == 1


def test_db10_trigger_changes_surviving_base_rows(tmp_path):
    for variant in db10.PAIR.variants:
        root = tmp_path / variant.variant
        root.mkdir()
        variant.build(root)
        assert run(root, db10.PAIR.operation).returncode == 0
        selected = [row for row in rows(root, "tickets") if row[0] in (71, 74)]
        assert selected == ([] if variant.variant == "A" else [
            (71, "case-71", "desk-a", 1, 3), (74, "case-74", "desk-b", 1, 3),
        ])
        assert run(root, db10.PAIR.restore_script).returncode == 0
        restored = [row for row in rows(root, "tickets") if row[0] in (71, 74)]
        assert restored == ([] if variant.variant == "A" else [
            (71, "case-71", "desk-a", 0, 3), (74, "case-74", "desk-b", 1, 3),
        ])
