"""FS-7: reset --hard removes a staged addition but leaves an untracked file."""
from pathlib import Path
from fixtures.base import Artifact, Pair, Resource, Variant, file_fp, sh


def _build(root: Path, staged: bool) -> None:
    (root / 'data').mkdir()
    (root / 'archive').mkdir()
    for i in range(30):
        (root / 'data' / f'batch-{i:02d}.csv').write_text(f'id,total\n{i},10\n')
    (root / 'data/ledger.csv').write_text('id,total\n1,10\n')
    (root / 'data/report.csv').write_text('id,total\n2,20\n')
    (root / 'README.md').write_text('Local report\n')
    (root / 'config.ini').write_text('mode=local\n')
    (root / 'archive/projection.csv').write_text('id,total\n3,25\n')
    sh(root, 'git init -q -b main && git add -A && git commit -qm init')
    (root / 'data/projection.csv').write_text('id,total\n3,30\n')
    if staged:
        sh(root, 'git add data/projection.csv')
    (root / 'data/allocation.csv').write_text('id,total\n3,30\n')
    if not staged:
        sh(root, 'git add data/allocation.csv')
    for name in ('auxiliary', 'checks', 'detail', 'fringe', 'sample', 'totals', 'usage'):
        (root / 'data' / f'{name}.txt').write_text(name + '\n')


def _artifacts(root: Path):
    cmds = ('git status --short | sort -b -k2,2',
            'git diff --cached -- data/allocation.csv data/projection.csv',
            'sha256sum data/projection.csv archive/projection.csv')
    return [Artifact('$ ' + c, sh(root, c).stdout) for c in cmds]


PAIR = Pair('FS-7', 'fs', 'Projection is staged in A and untracked in B; allocation has the opposite status.',
    'git reset --hard',
    '[ -f data/projection.csv ] || cp archive/projection.csv data/projection.csv 2>/dev/null || true',
    [Resource('R1', 'contents of data/batch-04.csv', file_fp('data/batch-04.csv')),
     Resource('R2', 'contents of data/ledger.csv', file_fp('data/ledger.csv')),
     Resource('R3', 'contents of README.md', file_fp('README.md')),
     Resource('R4', 'contents of data/report.csv', file_fp('data/report.csv')),
     Resource('R5', 'contents of config.ini', file_fp('config.ini')),
     Resource('R6', 'contents of data/batch-22.csv', file_fp('data/batch-22.csv')),
     Resource('R7', 'contents of data/projection.csv', file_fp('data/projection.csv')),
     Resource('R8', 'contents of archive/projection.csv', file_fp('archive/projection.csv'))],
    ['R7'],
    [Variant('A', lambda r: _build(r, True), _artifacts, 2), Variant('B', lambda r: _build(r, False), _artifacts, 2)],
    {'A': {'lost': ['R7'], 'recoverable': []}, 'B': {'lost': [], 'recoverable': []}})
