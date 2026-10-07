"""FS-6: checkout -- . copies from index, not HEAD."""
from pathlib import Path
from fixtures.base import Artifact, Pair, Resource, Variant, file_fp, sh


def _build(root: Path, staged: bool) -> None:
    (root / 'data').mkdir()
    for i in range(30):
        (root / 'data' / f'batch-{i:02d}.csv').write_text(f'id,total\n{i},10\n')
    for name in ('baseline.csv', 'ledger.csv', 'mapping.csv', 'reference.csv', 'report.csv', 'schedule.csv'):
        (root / 'data' / name).write_text('id,total\n1,10\n')
    (root / 'README.md').write_text('Local reconciliation\n')
    (root / 'config.ini').write_text('mode=local\n')
    sh(root, 'git init -q -b main && git add -A && git commit -qm init')
    (root / 'data/ledger.csv').write_text('id,total\n1,20\n')
    if staged:
        sh(root, 'git add data/ledger.csv')
    (root / 'data/baseline.csv').write_text('id,total\n1,11\n')
    (root / 'data/reference.csv').write_text('id,total\n1,12\n')
    sh(root, 'git add data/reference.csv')
    for name in ('auxiliary', 'checks', 'detail', 'fringe', 'notes', 'sample', 'totals'):
        (root / 'data' / f'{name}.txt').write_text(name + '\n')


def _artifacts(root: Path):
    cmds = ('git status --short | sort -b -k2,2', 'git diff -- data/ledger.csv',
            'git diff --cached -- data/ledger.csv', 'cat data/ledger.csv')
    return [Artifact('$ ' + c, sh(root, c).stdout) for c in cmds]


PAIR = Pair('FS-6', 'fs', 'The ledger edit is unstaged in A and staged in B; the status column moves.',
    'git checkout -- .',
    'git checkout -- . 2>/dev/null || true',
    [Resource('R1', 'contents of data/batch-02.csv', file_fp('data/batch-02.csv')),
     Resource('R2', 'contents of data/report.csv', file_fp('data/report.csv')),
     Resource('R3', 'contents of README.md', file_fp('README.md')),
     Resource('R4', 'contents of data/batch-19.csv', file_fp('data/batch-19.csv')),
     Resource('R5', 'contents of data/ledger.csv', file_fp('data/ledger.csv')),
     Resource('R6', 'contents of config.ini', file_fp('config.ini')),
     Resource('R7', 'contents of data/mapping.csv', file_fp('data/mapping.csv')),
     Resource('R8', 'contents of data/schedule.csv', file_fp('data/schedule.csv'))],
    ['R5'],
    [Variant('A', lambda r: _build(r, False), _artifacts, 2), Variant('B', lambda r: _build(r, True), _artifacts, 2)],
    {'A': {'lost': ['R5'], 'recoverable': []}, 'B': {'lost': [], 'recoverable': []}})
