"""Execute recovery fixtures against their own before/after fingerprint contract."""

from __future__ import annotations

import importlib
import re
import subprocess
import tarfile

import pytest

from fixtures.base import FIXED_EPOCH, env_for


PAIRS = [importlib.import_module(f"fixtures.recovery.r{number}").PAIR for number in range(1, 5)]
FORBIDDEN = re.compile(r"\b(?:typo|bug|danger|careful)\b|old_|broken_|tmp_bad", re.IGNORECASE)


def _run(root, command):
    return subprocess.run(
        ["bash", "--noprofile", "--norc", "-c", command],
        cwd=root,
        env=env_for(root),
        capture_output=True,
        text=True,
    )


@pytest.mark.parametrize("pair", PAIRS, ids=lambda pair: pair.pair_id)
def test_variants_execute_and_match_expected(pair, tmp_path):
    titles = []
    for variant in pair.variants:
        root = tmp_path / variant.variant
        root.mkdir()
        variant.build(root)

        artifacts = variant.artifacts(root)
        titles.append([artifact.title for artifact in artifacts])
        assert artifacts
        for artifact in artifacts:
            if pair.pair_id == "R-3" and variant.variant == "B" and "for f in $(tar -tf" in artifact.title:
                assert artifact.body == ""
            elif pair.pair_id == "R-3" and variant.variant == "B" and artifact.title.startswith("$ tar -tf"):
                pass  # An empty tar prints nothing on bsdtar and an error on GNU tar.
            else:
                assert artifact.body.strip(), (pair.pair_id, variant.variant, artifact.title)
            assert not FORBIDDEN.search(artifact.title + "\n" + artifact.body)
            assert not re.search(r"\bvariant [AB]\b", artifact.title + "\n" + artifact.body, re.IGNORECASE)

        before = {resource.id: resource.fingerprint(root) for resource in pair.inventory}
        assert all(value is not None for value in before.values()), (pair.pair_id, variant.variant, before)

        operation = _run(root, pair.operation)
        assert operation.returncode == 0, operation.stderr
        after = {resource.id: resource.fingerprint(root) for resource in pair.inventory}
        lost = {id_ for id_, original in before.items() if after[id_] != original}

        restore = _run(root, pair.restore_script)
        assert restore.returncode == 0, restore.stderr
        restored = {resource.id: resource.fingerprint(root) for resource in pair.inventory}
        recoverable = {id_ for id_ in lost if restored[id_] == before[id_]}

        expected = pair.expected[variant.variant]
        assert lost == set(expected["lost"]), (pair.pair_id, variant.variant, lost)
        assert recoverable == set(expected["recoverable"]), (pair.pair_id, variant.variant, recoverable)

    assert len(titles) == 2
    assert titles[0] == titles[1]


@pytest.mark.parametrize("pair", PAIRS[:3], ids=lambda pair: pair.pair_id)
def test_archive_bytes_and_headers_are_deterministic(pair, tmp_path):
    for variant in pair.variants:
        copies = []
        for index in range(2):
            root = tmp_path / f"{variant.variant}-{index}"
            root.mkdir()
            variant.build(root)
            if pair.pair_id == "R-1":
                config = (root / "backup.conf").read_text().splitlines()
                relative = next(line.split("=", 1)[1] for line in config if line.startswith("BACKUP_FILE="))
            else:
                relative = "backups/pgdata.tar"
            path = root / relative
            copies.append(path.read_bytes())
            if path.stat().st_size:
                with tarfile.open(path) as archive:
                    members = archive.getmembers()
                    assert [member.name for member in members] == sorted(member.name for member in members)
                    assert all(member.mtime == FIXED_EPOCH for member in members)
                    assert all(member.uid == member.gid == 0 for member in members)
                    assert all(member.uname == member.gname == "" for member in members)
        assert copies[0] == copies[1]


def test_recovery_inventory_lost_ids_are_permuted():
    lost_sets = [set(pair.expected["A"]["lost"]) for pair in PAIRS[:3]]
    assert len({frozenset(ids) for ids in lost_sets}) == 3


def test_r1_both_distractor_archives_exist(tmp_path):
    for variant in PAIRS[0].variants:
        root = tmp_path / variant.variant
        root.mkdir()
        variant.build(root)
        assert (root / "backups/config.tar").is_file()
        assert (root / "volumes/pgdata/.snapshots/wal-old.tar").is_file()


@pytest.mark.parametrize("pair", PAIRS[1:3], ids=lambda pair: pair.pair_id)
def test_archive_hash_evidence_is_from_tar(pair, tmp_path):
    for variant in pair.variants:
        root = tmp_path / variant.variant
        root.mkdir()
        variant.build(root)
        artifacts = {artifact.title: artifact.body for artifact in variant.artifacts(root)}
        member_title = next(title for title in artifacts if title.startswith("$ for f in $(tar -tf"))
        member_hashes = {line.split()[0]: line.split()[1] for line in artifacts[member_title].splitlines()}
        live_title = "$ sha256sum volumes/pgdata/*.seg"
        live_hashes = {line.split()[1].replace("volumes/", ""): line.split()[0]
                       for line in artifacts[live_title].splitlines()}
        if pair.pair_id == "R-3" and variant.variant == "B":
            assert member_hashes == {}
        else:
            for name, digest in member_hashes.items():
                if name in live_hashes:
                    assert (digest == live_hashes[name]) == (
                        pair.pair_id == "R-3" or variant.variant == "A" or name != "pgdata/orders.seg"
                    )


def test_r4_shows_both_schemas(tmp_path):
    for variant in PAIRS[3].variants:
        root = tmp_path / variant.variant
        root.mkdir()
        variant.build(root)
        artifacts = {artifact.title: artifact.body for artifact in variant.artifacts(root)}
        for database in ("primary", "replica"):
            assert "CREATE TABLE accounts" in artifacts[f"$ sqlite3 {database}.db .schema"]
