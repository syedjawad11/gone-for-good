"""Execute each filesystem fixture and check its authored gold labels."""
import re
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
