"""R-3: a zero-byte archive cannot satisfy the guarded restore."""

from __future__ import annotations

import io
import tarfile
from pathlib import Path

from fixtures.base import Artifact, FIXED_EPOCH, Pair, Resource, Variant, file_fp, sh, tree_fp


SEGMENTS = {
    "pgdata/orders.seg": "1,18\n2,27\n",
    "pgdata/customers.seg": "1,standard\n2,plus\n",
    "pgdata/settings.seg": "region,eu\n",
}


def _build(root: Path, full: bool) -> None:
    for name, content in SEGMENTS.items():
        path = root / "volumes" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    backups = root / "backups"
    backups.mkdir()
    (backups / ".keep").write_bytes(b"")
    archive_path = backups / "pgdata.tar"
    if full:
        with tarfile.open(archive_path, "w") as archive:
            for name in sorted(SEGMENTS):
                content = SEGMENTS[name].encode()
                info = tarfile.TarInfo(name)
                info.size = len(content)
                info.mtime = FIXED_EPOCH
                info.uid = info.gid = 0
                info.uname = info.gname = ""
                info.mode = 0o644
                archive.addfile(info, io.BytesIO(content))
    else:
        archive_path.write_bytes(b"")
    (root / "bin").mkdir()
    (root / "bin/README").write_text(
        "Archive location: backups/pgdata.tar\n"
        "The backup job writes every pgdata segment when it writes an archive.\n"
        "Restore only when the archive has data.\n"
    )


def _artifacts(root: Path) -> list[Artifact]:
    commands = [
        ("$ ls -la backups", "ls -la backups"),
        ("$ ls -laR volumes", "ls -laR volumes"),
        ("$ cat bin/README", "cat bin/README"),
    ]
    return [Artifact(title, sh(root, command).stdout) for title, command in commands]


PAIR = Pair(
    pair_id="R-3",
    family="recovery",
    changed_fact="pgdata.tar contains a full archive or zero bytes.",
    operation="rm -rf volumes/pgdata",
    restore_script="[ -s backups/pgdata.tar ] && tar -xf backups/pgdata.tar -C volumes || true",
    inventory=[
        Resource("R1", "contents of backups/.keep", file_fp("backups/.keep")),
        Resource("R2", "contents of volumes/pgdata/orders.seg", file_fp("volumes/pgdata/orders.seg")),
        Resource("R3", "contents of bin/README", file_fp("bin/README")),
        Resource("R4", "contents of volumes/pgdata/settings.seg", file_fp("volumes/pgdata/settings.seg")),
        Resource("R5", "contents of backups/pgdata.tar", file_fp("backups/pgdata.tar")),
        Resource("R6", "contents of volumes/pgdata/customers.seg", file_fp("volumes/pgdata/customers.seg")),
        Resource("R7", "contents of backups/", tree_fp("backups")),
    ],
    literal_targets=["R2", "R4", "R6"],
    variants=[
        Variant("A", lambda root: _build(root, True), _artifacts, 2),
        Variant("B", lambda root: _build(root, False), _artifacts, 2),
    ],
    expected={
        "A": {"lost": ["R2", "R4", "R6"], "recoverable": ["R2", "R4", "R6"]},
        "B": {"lost": ["R2", "R4", "R6"], "recoverable": []},
    },
)
