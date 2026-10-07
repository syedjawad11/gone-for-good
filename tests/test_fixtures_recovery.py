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
