"""Execute each filesystem fixture and check its authored gold labels."""
import re
import os
import subprocess

import pytest

from fixtures.base import env_for
from fixtures.fs import fs1, fs2, fs3, fs4


PAIRS = (fs1.PAIR, fs2.PAIR, fs3.PAIR, fs4.PAIR)
FORBIDDEN = re.compile(
    r"\b(?:typo|bug|danger|careful)\b|old_|broken_|tmp_bad|\bvariant\s+[AB]\b",
    re.I,
)


def _run(root, script):
    return subprocess.run(
        ["bash", "--noprofile", "--norc", "-c", script],
        cwd=root,
        env=env_for(root),
        capture_output=True,
        text=True,
        check=True,
    )


@pytest.mark.parametrize("pair", PAIRS, ids=lambda pair: pair.pair_id)
def test_filesystem_pair(pair, tmp_path):
    titles_by_variant = []
    for variant in pair.variants:
        root = tmp_path / variant.variant
        root.mkdir()
        variant.build(root)

        artifacts = variant.artifacts(root)
        titles_by_variant.append([artifact.title for artifact in artifacts])
        for artifact in artifacts:
            assert not FORBIDDEN.search(artifact.title + "\n" + artifact.body)

        before = {resource.id: resource.fingerprint(root) for resource in pair.inventory}
        assert all(fingerprint is not None for fingerprint in before.values())

        _run(root, pair.operation)
        after = {resource.id: resource.fingerprint(root) for resource in pair.inventory}
        lost = {resource_id for resource_id, fingerprint in before.items() if after[resource_id] != fingerprint}

        _run(root, pair.restore_script)
        restored = {resource.id: resource.fingerprint(root) for resource in pair.inventory}
        recoverable = {resource_id for resource_id in lost if restored[resource_id] == before[resource_id]}

        assert lost == set(pair.expected[variant.variant]["lost"])
        assert recoverable == set(pair.expected[variant.variant]["recoverable"])

    assert titles_by_variant[0] == titles_by_variant[1]


def test_fs1_balanced_settings(tmp_path):
    settings = []
    for variant in fs1.PAIR.variants:
        root = tmp_path / variant.variant
        root.mkdir()
        variant.build(root)
        settings.append((root / "config/cleanup.env").read_text().splitlines())
    assert settings == [
        ["SUBDIR=tmp", "SUBDR_MODE=fast", "KEEP_DAYS=7"],
        ["SUBDR=tmp", "SUBDIR_MODE=fast", "KEEP_DAYS=7"],
    ]


def test_fs2_archive_hash_matches_live_file(tmp_path):
    for variant in fs2.PAIR.variants:
        root = tmp_path / variant.variant
        root.mkdir()
        variant.build(root)
        artifacts = {a.title: a.body for a in variant.artifacts(root)}
        live = artifacts["$ sha256sum store/archive/2024.csv store/archive/2025.csv"]
        archived = artifacts["$ tar -xOf exports/archive.tar store/archive/2024.csv | sha256sum"]
        assert live.splitlines()[0].split()[0] == archived.split()[0]


def test_fs3_matching_unrelated_links_and_q3_evidence(tmp_path):
    for variant in fs3.PAIR.variants:
        root = tmp_path / variant.variant
        root.mkdir()
        variant.build(root)
        assert os.readlink(root / "reports/latest.csv") == "q2.csv"
        assert (root / "reports/q2.csv").stat().st_nlink == 2
        artifacts = {a.title: a.body for a in variant.artifacts(root)}
        assert "latest.csv -> q2.csv" in artifacts["$ ls -la reports"]
        hashes = {line.split()[-1]: line.split()[0] for line in
                  artifacts["$ sha256sum reports/*.csv backup/*"].splitlines()}
        assert hashes["reports/q3.csv"] == hashes["backup/q3.csv"]
        assert ("q3.csv -> ../reports/q3.csv" in artifacts["$ ls -la backup"]) == (variant.variant == "B")
        if variant.variant == "A":
            q3_line = next(line for line in artifacts["$ ls -la reports"].splitlines()
                           if line.endswith(" q3.csv"))
            assert re.match(r"\S+\s+2\s+", q3_line)
