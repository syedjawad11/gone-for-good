"""FS-10: recursive copy nests under an existing destination directory."""
from pathlib import Path
from fixtures.base import Artifact, Pair, Resource, Variant, file_fp, sh


def _build(root: Path, destination_dir: bool) -> None:
    for d in ('src', 'bin', 'docs'):
        (root / d).mkdir()
    for i in range(31):
        (root / 'src' / f'batch-{i:02d}.csv').write_text(f'id,total\n{i},10\n')
    for name in ('ledger.csv', 'mapping.csv', 'report.csv'):
        (root / 'src' / name).write_text(name + '\n')
    (root / 'docs/notes.txt').write_text('cycle=1\n')
    (root / 'config.ini').write_text('mode=local\n')
    for d in ('z_archive', 'z_output', 'z_store'):
        (root / d).mkdir()
    if destination_dir:
        (root / 'stage').mkdir()
        (root / 'stage/notes.txt').write_text('stage=ready\n')
        (root / 'z_notes').write_text('stage=ready\n')
    else:
        (root / 'stage').write_text('stage=ready\n')
        (root / 'z_notes').mkdir()
        (root / 'z_notes/notes.txt').write_text('stage=ready\n')
    script = '#!/bin/bash\nset -u\ncd "$(dirname "$0")/.."\n[ -e stage ] || exit 1\ncp -r src stage || true\nrm -rf src\nprintf "finished\\n"\n'
    (root / 'bin/archive').write_text(script)
    (root / 'bin/archive').chmod(0o755)


def _artifacts(root: Path):
    cmds = ("python3 -c 'import hashlib; from pathlib import Path; [print(hashlib.sha256(p.read_bytes()).hexdigest(), p) for p in sorted(Path(\"src\").iterdir())]'",
            "python3 -c 'from pathlib import Path; [print(p, \"directory\" if p.is_dir() else \"file\") for p in (Path(\"stage\"), Path(\"z_notes\"))]'",
            'cat bin/archive', 'cat src/ledger.csv src/mapping.csv src/report.csv',
            'find stage -print | sort')
    return [Artifact('$ ' + c, sh(root, c).stdout) for c in cmds]


PAIR = Pair('FS-10', 'fs', 'Stage and z_notes swap file and directory roles between variants.',
    './bin/archive',
    '[ -d stage/src ] && cp -r stage/src src || true',
    [Resource('R1', 'contents of src/batch-03.csv', file_fp('src/batch-03.csv')),
     Resource('R2', 'contents of config.ini', file_fp('config.ini')),
     Resource('R3', 'contents of src/ledger.csv', file_fp('src/ledger.csv')),
     Resource('R4', 'contents of src/mapping.csv', file_fp('src/mapping.csv')),
     Resource('R5', 'contents of docs/notes.txt', file_fp('docs/notes.txt')),
     Resource('R6', 'contents of src/report.csv', file_fp('src/report.csv')),
     Resource('R7', 'contents of src/batch-24.csv', file_fp('src/batch-24.csv'))],
    ['R1', 'R3', 'R4', 'R6', 'R7'],
    [Variant('A', lambda r: _build(r, False), _artifacts, 2), Variant('B', lambda r: _build(r, True), _artifacts, 2)],
    {'A': {'lost': ['R1', 'R3', 'R4', 'R6', 'R7'], 'recoverable': []},
     'B': {'lost': ['R1', 'R3', 'R4', 'R6', 'R7'], 'recoverable': ['R1', 'R3', 'R4', 'R6', 'R7']}})
