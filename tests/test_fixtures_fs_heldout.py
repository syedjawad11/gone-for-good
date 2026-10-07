"""Execute the held-out filesystem pairs against their authored outcomes."""
import difflib
import math
import re
import subprocess
import sys

import pytest

from fixtures.base import env_for
from fixtures.fs import fs5, fs6, fs7, fs8, fs9, fs10
from harness.render import render_prompt

PAIRS = (fs5.PAIR, fs6.PAIR, fs7.PAIR, fs8.PAIR, fs9.PAIR, fs10.PAIR)
FORBIDDEN = re.compile(r'\b(?:typo|bug|danger|careful)\b|old_|broken_|tmp_bad|\bvariant\s+[AB]\b', re.I)
VERSIONS = {'bash': 'bash 5.2', 'coreutils': 'coreutils 9.1',
            'git': 'git 2.39', 'sqlite': '3.40'}


def _run(root, command):
    return subprocess.run(['bash', '--noprofile', '--norc', '-c', command], cwd=root,
                          env=env_for(root), capture_output=True, text=True, check=True)


@pytest.mark.parametrize('pair', PAIRS, ids=lambda p: p.pair_id)
def test_pair(pair, tmp_path):
    titles = []
    bodies = []
    prompt_lengths = []
    directory_counts = []
    for variant in pair.variants:
        root = tmp_path / variant.variant
        root.mkdir()
        variant.build(root)
        artifacts = variant.artifacts(root)
        assert 3 <= len(artifacts) <= 5
        assert sum(len(a.title) + len(a.body) for a in artifacts) <= 4000
        assert variant.hops >= 2
        titles.append([a.title for a in artifacts])
        bodies.append('\n'.join(a.body for a in artifacts).splitlines())
        prompt_lengths.append(len(render_prompt(pair, artifacts, VERSIONS)))
        directory_counts.append(sum(p.is_dir() for p in root.iterdir()))
        if pair.pair_id == 'FS-5':
            assert any('notes.txt -> report.gz' in a.body for a in artifacts)
        if pair.pair_id == 'FS-7':
            assert any('new file mode' in a.body for a in artifacts)
        if pair.pair_id == 'FS-8':
            assert any('id,state\n1,open\n' in a.body for a in artifacts)
        if pair.pair_id == 'FS-10':
            stage_listing = next(a.body for a in artifacts if a.title == '$ find stage -print | sort')
            assert 'stage/src' not in stage_listing
            if variant.variant == 'B':
                assert stage_listing.splitlines() == ['stage', 'stage/notes.txt']
        for artifact in artifacts:
            assert not FORBIDDEN.search(artifact.title + '\n' + artifact.body)
        before = {r.id: r.fingerprint(root) for r in pair.inventory}
        assert all(fp is not None for fp in before.values())
        _run(root, pair.operation)
        after = {r.id: r.fingerprint(root) for r in pair.inventory}
        lost = {key for key in before if after[key] != before[key]}
        _run(root, pair.restore_script)
        restored = {r.id: r.fingerprint(root) for r in pair.inventory}
        recoverable = {key for key in lost if restored[key] == before[key]}
        assert lost == set(pair.expected[variant.variant]['lost'])
        assert recoverable == set(pair.expected[variant.variant]['recoverable'])
    assert titles[0] == titles[1]
    assert max(prompt_lengths) / min(prompt_lengths) <= 1.01
    if pair.pair_id == 'FS-10':
        assert directory_counts[0] == directory_counts[1]
    changed_lines = sum(line.startswith(('+ ', '- ')) for line in difflib.ndiff(*bodies))
    assert math.ceil(changed_lines / 2) <= 8


def test_family_balance():
    assert [pair.pair_id for pair in PAIRS] == [f'FS-{i}' for i in range(5, 11)]
    assert sum(pair.variants[0].hops == 3 for pair in PAIRS) >= 2
    assert sum(pair.operation.startswith('./bin/') for pair in PAIRS) >= 3
    assert sum('git ' in pair.operation for pair in PAIRS) >= 2
    assert sum(not pair.expected[v]['lost'] for pair in PAIRS for v in ('A', 'B')) >= 2
    assert sum(pair.expected['A']['lost'] == pair.expected['B']['lost'] and
               pair.expected['A']['recoverable'] != pair.expected['B']['recoverable']
               for pair in PAIRS) >= 2
    worse = []
    owners = {}
    changing_positions = {}
    for pair in PAIRS:
        counts = {v: len(set(pair.expected[v]['lost']) - set(pair.expected[v]['recoverable']))
                  for v in ('A', 'B')}
        assert counts['A'] != counts['B']
        worse.append(max(counts, key=counts.get))
        for v in ('A', 'B'):
            lost_set = frozenset(pair.expected[v]['lost'])
            if lost_set:
                assert owners.get(lost_set, pair.pair_id) == pair.pair_id
                owners[lost_set] = pair.pair_id
        for resource in pair.inventory:
            states = [(resource.id in pair.expected[v]['lost'],
                       resource.id in pair.expected[v]['recoverable']) for v in ('A', 'B')]
            if states[0] != states[1]:
                changing_positions.setdefault(resource.id, set()).add(pair.pair_id)
    assert worse.count('A') == worse.count('B') == 3
    assert max(map(len, changing_positions.values())) <= 2
