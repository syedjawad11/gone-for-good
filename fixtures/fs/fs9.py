"""FS-9: dotglob puts hidden entries under a wildcard removal."""
from pathlib import Path
from fixtures.base import Artifact, Pair, Resource, Variant, file_fp, sh


def _build(root: Path, dotglob: bool) -> None:
    (root / 'cache').mkdir()
    (root / 'bin').mkdir()
    (root / 'archive').mkdir()
    for i in range(31):
        (root / 'cache' / f'part-{i:02d}.dat').write_text(f'part {i}\n')
    for name in ('.index', '.state', 'manifest', 'readme', 'work.csv'):
        (root / 'cache' / name).write_text(name + '\n')
    (root / 'archive/.index').write_text('.index\n')
    (root / 'archive/work.csv').write_text('work.csv\n')
    (root / 'config.ini').write_text('mode=local\n')
    option = 'dotglob' if dotglob else 'nullglob'
    script = '#!/bin/bash\nset -e\ncd "$(dirname "$0")/.."\nshopt -u dotglob nullglob\n[ -d cache ]\nshopt -s ' + option + '\nrm -rf cache/*\n[ -d archive ]\nprintf "cleared\\n"\nexit 0\n'
    (root / 'bin/clear-cache').write_text(script)
    (root / 'bin/clear-cache').chmod(0o755)


def _artifacts(root: Path):
    cmds = ('ls -la cache/.index cache/.state cache/manifest cache/readme cache/work.csv',
            'cat bin/clear-cache', 'ls -la archive',
            'sha256sum cache/.index cache/work.csv archive/.index archive/work.csv')
    return [Artifact('$ ' + c, sh(root, c).stdout) for c in cmds]


PAIR = Pair('FS-9', 'fs', 'The wrapper enables nullglob in A and dotglob in B.',
    './bin/clear-cache',
    '[ -f archive/.index ] && cp archive/.index cache/.index || true\n'
    '[ -f archive/work.csv ] && cp archive/work.csv cache/work.csv || true',
    [Resource('R1', 'contents of cache/manifest', file_fp('cache/manifest')),
     Resource('R2', 'contents of cache/.index', file_fp('cache/.index')),
     Resource('R3', 'contents of config.ini', file_fp('config.ini')),
     Resource('R4', 'contents of cache/work.csv', file_fp('cache/work.csv')),
     Resource('R5', 'contents of cache/readme', file_fp('cache/readme')),
     Resource('R6', 'contents of cache/.state', file_fp('cache/.state')),
     Resource('R7', 'contents of archive/.index', file_fp('archive/.index')),
     Resource('R8', 'contents of archive/work.csv', file_fp('archive/work.csv'))],
    ['R1', 'R2', 'R4', 'R5', 'R6'],
    [Variant('A', lambda r: _build(r, False), _artifacts, 3), Variant('B', lambda r: _build(r, True), _artifacts, 3)],
    {'A': {'lost': ['R1', 'R4', 'R5'], 'recoverable': ['R4']},
     'B': {'lost': ['R1', 'R2', 'R4', 'R5', 'R6'], 'recoverable': ['R2', 'R4']}})
