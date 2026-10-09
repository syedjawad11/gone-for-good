"""FS-8: replacing an inode preserves hard-linked source bytes."""
import os
from pathlib import Path
from fixtures.base import Artifact, Pair, Resource, Variant, file_fp, sh


def _build(root: Path, replace: bool) -> None:
    for d in ('data', 'hold', 'bin', 'config'):
        (root / d).mkdir()
    for i in range(31):
        (root / 'data' / f'batch-{i:02d}.csv').write_text(f'id,state\n{i},open\n')
    (root / 'data/ledger.csv').write_text('id,state\n1,open\n')
    os.link(root / 'data/ledger.csv', root / 'hold/ledger.csv')
    (root / 'data/report.csv').write_text('id,state\n2,open\n')
    (root / 'data/schedule.csv').write_text('id,state\n3,open\n')
    (root / 'hold/notes.txt').write_text('cycle=1\n')
    (root / 'hold/summary.txt').write_text('period=1\n')
    mode = 'replace' if replace else 'stream'
    (root / 'config/update.env').write_text('INPUT=data/ledger.csv\nFIELD=state\nVALUE=closed\nMODE=' + mode + '\nCYCLE=1\nOWNER=ops\nFORMAT=csv\nQUEUE=local\n')
    script = ('#!/bin/bash\nset -e\ncd "$(dirname "$0")/.."\n'
              'source config/update.env\n[ -f "$INPUT" ]\n'
              'if [ "$MODE" = replace ]; then\n'
              '  sed -i -e "s/open/$VALUE/" "$INPUT"\n'
              'else\n'
              '  sed "s/open/$VALUE/" "$INPUT" > data/ledger.next\n'
              '  cat data/ledger.next > "$INPUT"\nfi\nprintf "updated\\n"\n')
    (root / 'bin/update').write_text(script)
    (root / 'bin/update').chmod(0o755)


def _artifacts(root: Path):
    cmds = ('cat bin/update', 'cat config/update.env',
            'for f in data/ledger.csv hold/ledger.csv; do [ "$f" -ef data/ledger.csv ] && echo "$f same-file data/ledger.csv" || echo "$f different-file data/ledger.csv"; done; stat -c "%n: %F, %h links" data hold data/ledger.csv hold/ledger.csv; cat data/ledger.csv hold/ledger.csv')
    return [Artifact('$ ' + c, sh(root, c).stdout) for c in cmds]


PAIR = Pair('FS-8', 'fs', 'The update mode is replace in A and stream in B.',
    './bin/update',
    '[ -f hold/ledger.csv ] && cp hold/ledger.csv data/ledger.csv 2>/dev/null || true',
    [Resource('R1', 'contents of data/batch-05.csv', file_fp('data/batch-05.csv')),
     Resource('R2', 'contents of data/ledger.csv', file_fp('data/ledger.csv')),
     Resource('R3', 'contents of data/report.csv', file_fp('data/report.csv')),
     Resource('R4', 'contents of hold/notes.txt', file_fp('hold/notes.txt')),
     Resource('R5', 'contents of data/batch-26.csv', file_fp('data/batch-26.csv')),
     Resource('R6', 'contents of data/schedule.csv', file_fp('data/schedule.csv')),
     Resource('R7', 'contents of hold/summary.txt', file_fp('hold/summary.txt'))],
    ['R2'],
    [Variant('A', lambda r: _build(r, True), _artifacts, 3), Variant('B', lambda r: _build(r, False), _artifacts, 3)],
    {'A': {'lost': ['R2'], 'recoverable': ['R2']},
     'B': {'lost': ['R2'], 'recoverable': []}})
