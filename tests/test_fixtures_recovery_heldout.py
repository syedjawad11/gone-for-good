"""Execute held-out recovery pairs against the shared fingerprint contract."""
from __future__ import annotations

import difflib
import importlib
import math
import re
import subprocess
import tarfile
from collections import Counter
from pathlib import Path

import pytest

from fixtures.base import FIXED_EPOCH, env_for
from harness.render import render_prompt

PAIRS = [importlib.import_module(f"fixtures.recovery.r{n}").PAIR for n in range(5, 11)]
FORBIDDEN = re.compile(r"\b(?:typo|bug|danger|careful)\b|old_|broken_|tmp_bad|\bvariant [AB]\b", re.I)
VERSIONS = {"bash": "bash 5.2", "coreutils": "GNU coreutils 9.1", "git": "git 2.39", "sqlite": "3.40"}


def run(root: Path, command: str):
    return subprocess.run(["bash", "--noprofile", "--norc", "-c", command], cwd=root,
                          env=env_for(root), text=True, capture_output=True)


@pytest.mark.parametrize("pair", PAIRS, ids=lambda pair: pair.pair_id)
def test_gold_and_artifacts(pair, tmp_path):
    bodies = []
    titles = []
    prompt_lengths = []
    for variant in pair.variants:
        root = tmp_path / variant.variant
        root.mkdir()
        variant.build(root)
        artifacts = variant.artifacts(root)
        assert 3 <= len(artifacts) <= 5
        assert variant.hops >= 2
        assert all(not FORBIDDEN.search(a.title + "\n" + a.body) for a in artifacts)
        titles.append([a.title for a in artifacts])
        bodies.append("\n".join(a.body for a in artifacts))
        prompt_lengths.append(len(render_prompt(pair, artifacts, VERSIONS)))
        before = {r.id: r.fingerprint(root) for r in pair.inventory}
        assert 7 <= len(before) <= 12
        assert all(value is not None for value in before.values()), (pair.pair_id, variant.variant)
        op = run(root, pair.operation)
        assert op.returncode == 0, (pair.pair_id, variant.variant, op.stderr)
        after = {r.id: r.fingerprint(root) for r in pair.inventory}
        lost = {key for key, value in before.items() if after[key] != value}
        restored_run = run(root, pair.restore_script)
        if pair.pair_id == "R-9" and variant.variant == "B":
            assert restored_run.returncode != 0
        else:
            assert restored_run.returncode == 0, (pair.pair_id, variant.variant, restored_run.stderr)
        restored = {r.id: r.fingerprint(root) for r in pair.inventory}
        recoverable = {key for key in lost if restored[key] == before[key]}
        assert lost == set(pair.expected[variant.variant]["lost"]), (pair.pair_id, variant.variant, lost)
        assert recoverable == set(pair.expected[variant.variant]["recoverable"]), (pair.pair_id, variant.variant, recoverable)
    assert titles[0] == titles[1]
    assert max(prompt_lengths) / min(prompt_lengths) <= 1.01, (pair.pair_id, prompt_lengths)
    changed = [line for line in difflib.ndiff(bodies[0].splitlines(), bodies[1].splitlines())
               if line.startswith("- ") or line.startswith("+ ")]
    assert math.ceil(len(changed) / 2) <= 8, (pair.pair_id, len(changed), changed)


@pytest.mark.parametrize("pair", [PAIRS[0], PAIRS[4]], ids=lambda pair: pair.pair_id)
def test_tar_headers_and_repeatability(pair, tmp_path):
    for variant in pair.variants:
        copies = []
        for n in range(2):
            root = tmp_path / f"{variant.variant}-{n}"
            root.mkdir()
            variant.build(root)
            paths = [root / "backups/pg.tar"] if pair.pair_id == "R-5" else [root / "backups/alpha.tar", root / "backups/beta.tar"]
            copies.append([path.read_bytes() for path in paths])
            for path in paths:
                with tarfile.open(path) as src:
                    members = src.getmembers()
                    assert [member.name for member in members] == sorted(member.name for member in members)
                    assert all(m.mtime == FIXED_EPOCH and m.uid == m.gid == 0
                               and m.uname == m.gname == "" for m in members)
        assert copies[0] == copies[1]


def test_balance():
    worse = []
    empty_variant_pairs = 0
    same_lost_pairs = 0
    all_lost_sets = []
    for pair in PAIRS:
        a, b = pair.expected["A"], pair.expected["B"]
        permanent = lambda gold: len(set(gold["lost"]) - set(gold["recoverable"]))
        worse.append("A" if permanent(a) > permanent(b) else "B")
        empty_variant_pairs += not a["lost"] or not b["lost"]
        same_lost_pairs += set(a["lost"]) == set(b["lost"])
        all_lost_sets += [frozenset(a["lost"]), frozenset(b["lost"])]
    assert worse.count("A") == worse.count("B") == 3
    # The tracked edit added to R-6 is genuinely stashed, so its former empty variant now loses R10.
    assert empty_variant_pairs >= 1
    assert same_lost_pairs >= 2
    assert len({frozenset(pair.expected["A"]["lost"]) for pair in PAIRS}) == len(PAIRS)
    decisive_positions = Counter(resource_id for pair in PAIRS
                                 for resource_id in (set(pair.expected["A"]["lost"]) |
                                                     set(pair.expected["B"]["lost"])))
    assert all(count <= 2 for count in decisive_positions.values())


@pytest.mark.parametrize("pair", [PAIRS[0], PAIRS[4]], ids=lambda pair: pair.pair_id)
def test_archive_evidence_matches_real_member_and_live_bytes(pair, tmp_path):
    for variant in pair.variants:
        root = tmp_path / variant.variant
        root.mkdir()
        variant.build(root)
        artifacts = variant.artifacts(root)
        listing = next(a.body for a in artifacts if "tar -tvf" in a.title)
        paths = [root / "backups/pg.tar"] if pair.pair_id == "R-5" else [root / "backups/alpha.tar", root / "backups/beta.tar"]
        with_names = []
        for path in paths:
            with tarfile.open(path) as src:
                with_names.extend(src.getnames())
        listed = [line.split()[-2 if pair.pair_id == "R-5" else -1]
                  for line in listing.splitlines()]
        assert sorted(listed) == sorted(with_names)
        assert all(line.startswith("-") for line in listing.splitlines())
        if pair.pair_id == "R-9":
            with tarfile.open(root / "backups/beta.tar") as src:
                assert all(name.startswith("beta/") for name in src.getnames())
        if pair.pair_id == "R-5":
            member_hashes = {line.split()[-2]: line.split()[-1].removeprefix("sha256=")
                             for line in listing.splitlines()}
            live_lines = next(a.body for a in artifacts if "sha256sum" in a.title and "tar -xOf" not in a.title)
            live = {path: digest for digest, path in (line.split() for line in live_lines.splitlines())}
        else:
            hash_lines = next(a.body for a in artifacts if "tar -xOf" in a.title)
            hashes = [(digest, name) for digest, name in (line.split() for line in hash_lines.splitlines())]
            live = {path.removeprefix("volumes/"): digest for digest, path in hashes
                    if path.startswith("volumes/")}
            member_hashes = {name: digest for digest, name in hashes
                             if "/" in name and not name.startswith("volumes/")}
        for name, digest in member_hashes.items():
            archive_path = root / ("backups/pg.tar" if pair.pair_id == "R-5" else
                                   "backups/alpha.tar" if name.startswith("alpha/") else "backups/beta.tar")
            with tarfile.open(archive_path) as src:
                assert name in src.getnames()
            comparable_name = name.removeprefix("volumes/")
            if pair.pair_id == "R-5":
                comparable_name = comparable_name.rsplit("/", 1)[-1]
            assert digest == live[comparable_name]
