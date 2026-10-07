"""FS-5: find's implicit -a binds more tightly than -o."""
from pathlib import Path
from fixtures.base import Artifact, Pair, Resource, Variant, file_fp, sh


def _build(root: Path, grouped: bool) -> None:
    (root / 'logs').mkdir()
    (root / 'bin').mkdir()
    (root / 'archive').mkdir()
    for i in range(32):
        (root / 'logs' / f'run-{i:02d}.log').write_text(f'run {i}\n')
    for name in ('midnight.tmp', 'nightly.gz', 'quarter.tmp', 'report.gz', 'summary.log'):
        (root / 'logs' / name).write_text(name + '\n')
    (root / 'logs/notes.txt').symlink_to('report.gz')
    (root / 'archive/quarter.tmp').write_text('quarter.tmp\n')
    (root / 'archive/report.gz').write_text('report.gz\n')
    (root / 'config.ini').write_text('retention=7\n')
    term = r"\( -name '*.tmp' -o -name '*.gz' \)" if grouped else "-name '*.tmp' -o -name '*.gz'"
    script = '#!/bin/bash\nset -u\ncd "$(dirname "$0")/.."\n[ -d logs ] || exit 1\nfind archive \\( -name "*.bak" -o -name "*.snap" \\) -print >/dev/null\nfind logs ' + term + ' -delete\n[ -d archive ] || exit 1\nprintf "rotation complete\\n"\nexit 0\n'
    (root / 'bin/rotate').write_text(script)
    (root / 'bin/rotate').chmod(0o755)


def _artifacts(root: Path):
    cmds = ('ls -la logs', 'cat bin/rotate',
            'ls -la archive; sha256sum logs/quarter.tmp logs/report.gz archive/quarter.tmp archive/report.gz')
    return [Artifact('$ ' + c, sh(root, c).stdout) for c in cmds]


PAIR = Pair('FS-5', 'fs', 'Parentheses group the two find name tests in B, but not A.',
    './bin/rotate',
    '[ -f archive/quarter.tmp ] && cp archive/quarter.tmp logs/quarter.tmp || true\n'
    '[ -f archive/report.gz ] && cp archive/report.gz logs/report.gz || true',
    [Resource('R1', 'contents of logs/midnight.tmp', file_fp('logs/midnight.tmp')),
     Resource('R2', 'contents of config.ini', file_fp('config.ini')),
     Resource('R3', 'contents of logs/nightly.gz', file_fp('logs/nightly.gz')),
     Resource('R4', 'contents of logs/notes.txt', file_fp('logs/notes.txt')),
     Resource('R5', 'contents of logs/quarter.tmp', file_fp('logs/quarter.tmp')),
     Resource('R6', 'contents of logs/report.gz', file_fp('logs/report.gz')),
     Resource('R7', 'contents of logs/summary.log', file_fp('logs/summary.log')),
     Resource('R8', 'contents of archive/quarter.tmp', file_fp('archive/quarter.tmp')),
     Resource('R9', 'contents of archive/report.gz', file_fp('archive/report.gz'))],
    ['R1', 'R3', 'R5', 'R6'],
    [Variant('A', lambda r: _build(r, False), _artifacts, 3), Variant('B', lambda r: _build(r, True), _artifacts, 3)],
    {'A': {'lost': ['R3', 'R4', 'R6'], 'recoverable': ['R4', 'R6']},
     'B': {'lost': ['R1', 'R3', 'R4', 'R5', 'R6'], 'recoverable': ['R4', 'R5', 'R6']}})
