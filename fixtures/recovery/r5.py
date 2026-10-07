"""R-5: archive member roots determine where extraction places the files."""
from __future__ import annotations

import io
import tarfile
from pathlib import Path

from fixtures.base import Artifact, FIXED_EPOCH, Pair, Resource, Variant, file_fp, sh

FILES = {f"base/seg-{n:02}.dat": f"segment,{n:02},epoch,2026-01-01\n" for n in range(1, 31)}
SELECTED = (1, 4, 9, 13, 18, 24, 29)


def archive(path: Path, members: dict[str, bytes]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(path, "w", format=tarfile.USTAR_FORMAT) as out:
        for name in sorted(members):
            content = members[name]
            info = tarfile.TarInfo(name)
            info.size = len(content)
            info.mtime = FIXED_EPOCH
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            info.mode = 0o644
            out.addfile(info, io.BytesIO(content))


def member_hash_command(archive_rel: str, names: list[str]) -> str:
    quoted = " ".join("'" + name + "'" for name in names)
    return (f"for m in {quoted}; do printf '%s ' \"$m\"; "
            f"tar -xOf {archive_rel} \"$m\" | sha256sum | cut -d' ' -f1; done")


def _build(root: Path, wrong_root: bool) -> None:
    for name, content in FILES.items():
        path = root / "volumes/pgdata" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    prefix = "backup/" if wrong_root else "pgdata/"
    members = {prefix + f"base/seg-{n:02}.dat": FILES[f"base/seg-{n:02}.dat"].encode()
               for n in SELECTED}
    archive(root / "backups/pg.tar", members)
    (root / "config").mkdir()
    (root / "config/restore.env").write_text("DESTINATION=volumes\nARCHIVE=backups/pg.tar\n")
    (root / "config/runbook.txt").write_text("The volume holds synthetic segment files.\n")


def _artifacts(root: Path) -> list[Artifact]:
    command = ("tar -tvf backups/pg.tar | while IFS= read -r line; do "
               "m=${line##* }; h=$(tar -xOf backups/pg.tar \"$m\" | sha256sum | cut -d' ' -f1); "
               "printf '%s sha256=%s\\n' \"$line\" \"$h\"; done")
    return [
        Artifact("$ cat config/restore.env", sh(root, "cat config/restore.env").stdout),
        Artifact("$ " + command, sh(root, command).stdout),
        Artifact("$ cd volumes/pgdata/base && sha256sum seg-{01,04,09,13,18,24,29}.dat",
                 sh(root, "cd volumes/pgdata/base && sha256sum seg-{01,04,09,13,18,24,29}.dat").stdout),
    ]


inventory = [Resource(f"R{i+1}", f"contents of volumes/pgdata/base/seg-{n:02}.dat",
                      file_fp(f"volumes/pgdata/base/seg-{n:02}.dat")) for i, n in enumerate(SELECTED)]
inventory += [Resource("R8", "contents of backups/pg.tar", file_fp("backups/pg.tar")),
              Resource("R9", "contents of config/runbook.txt", file_fp("config/runbook.txt"))]
PAIR = Pair(
    pair_id="R-5", family="recovery",
    changed_fact="Archive member paths have pgdata/ or backup/ as their root.",
    operation="rm -rf volumes/pgdata",
    restore_script='source config/restore.env\n[ -f "$ARCHIVE" ] && tar -xf "$ARCHIVE" -C "$DESTINATION" || true',
    inventory=inventory, literal_targets=[f"R{i}" for i in range(1, 8)],
    variants=[Variant("A", lambda root: _build(root, False), _artifacts, 3),
              Variant("B", lambda root: _build(root, True), _artifacts, 2)],
    expected={"A": {"lost": [f"R{i}" for i in range(1, 8)], "recoverable": [f"R{i}" for i in range(1, 8)]},
              "B": {"lost": [f"R{i}" for i in range(1, 8)], "recoverable": []}},
)
