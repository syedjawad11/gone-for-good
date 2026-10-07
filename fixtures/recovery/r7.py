"""R-7: a no-clobber copy cannot fill a truncated destination."""
from __future__ import annotations

from pathlib import Path

from fixtures.base import Artifact, Pair, Resource, Variant, file_fp, sh

FILES = {f"part-{n:02}.seg": f"partition,{n:02},rows,{n*13}\n" for n in range(1, 31)}
TARGETS = (5, 21)


def _build(root: Path, truncate: bool) -> None:
    data = root / "volumes/pgdata"
    data.mkdir(parents=True)
    (root / "backups/pgdata").mkdir(parents=True)
    (root / "config").mkdir()
    (root / "bin").mkdir()
    for name, content in FILES.items():
        (data / name).write_text(content)
    for number in TARGETS:
        name = f"part-{number:02}.seg"
        (root / "backups/pgdata" / name).write_text(FILES[name])
    (root / "config/purge.env").write_text(
        "SEGMENT_ROOT=volumes/pgdata\nRETENTION_DAYS=7\nCHECKPOINT=complete\n"
        + ("METHOD=truncate\n" if truncate else "METHOD=remove\n")
        + "VERIFY=sha256\nOWNER=storage\nLOG_LEVEL=info\n"
    )
    script = ("#!/usr/bin/env bash\n"
              "set -e\n"
              "source config/purge.env\n"
              "for n in 05 21; do\n"
              "  file=volumes/pgdata/part-$n.seg\n"
              "  if [ \"$METHOD\" = truncate ]; then\n"
              "    : > \"$file\"\n"
              "  else\n"
              "    rm -f \"$file\"\n"
              "  fi\n"
              "done\n")
    (root / "bin/purge_segments").write_text(script)
    (root / "bin/purge_segments").chmod(0o755)
    (root / "notes.txt").write_text("Segment rotation runs after checkpoint.\n")


def _artifacts(root: Path) -> list[Artifact]:
    identity = ("for n in 05 21; do "
                "a=volumes/pgdata/part-$n.seg; b=backups/pgdata/part-$n.seg; "
                "if test \"$a\" -ef \"$b\"; then echo \"$a same-file $b\"; "
                "else echo \"$a different-file $b\"; fi; "
                "if test \"$b\" -ef \"$a\"; then echo \"$b same-file $a\"; "
                "else echo \"$b different-file $a\"; fi; done")
    return [
        Artifact("$ cat bin/purge_segments", sh(root, "cat bin/purge_segments").stdout),
        Artifact("$ cat config/purge.env", sh(root, "cat config/purge.env").stdout),
        Artifact("$ ls -l volumes/pgdata/part-{05,21}.seg backups/pgdata/part-{05,21}.seg; " + identity,
                 sh(root, "ls -l volumes/pgdata/part-{05,21}.seg backups/pgdata/part-{05,21}.seg; " + identity).stdout),
        Artifact("$ sha256sum volumes/pgdata/part-{05,21}.seg backups/pgdata/part-{05,21}.seg",
                 sh(root, "sha256sum volumes/pgdata/part-{05,21}.seg backups/pgdata/part-{05,21}.seg").stdout),
    ]


PAIR = Pair(
    pair_id="R-7", family="recovery",
    changed_fact="Purge method truncates or removes the destination files before cp -n.",
    operation="./bin/purge_segments",
    restore_script="cp -n backups/pgdata/*.seg volumes/pgdata/ || true",
    inventory=[
        Resource("R1", "contents of notes.txt", file_fp("notes.txt")),
        Resource("R2", "contents of volumes/pgdata/part-21.seg", file_fp("volumes/pgdata/part-21.seg")),
        Resource("R3", "contents of volumes/pgdata/part-07.seg", file_fp("volumes/pgdata/part-07.seg")),
        Resource("R4", "contents of backups/pgdata/part-05.seg", file_fp("backups/pgdata/part-05.seg")),
        Resource("R5", "contents of volumes/pgdata/part-12.seg", file_fp("volumes/pgdata/part-12.seg")),
        Resource("R6", "contents of config/purge.env", file_fp("config/purge.env")),
        Resource("R7", "contents of volumes/pgdata/part-05.seg", file_fp("volumes/pgdata/part-05.seg")),
        Resource("R8", "contents of backups/pgdata/part-21.seg", file_fp("backups/pgdata/part-21.seg")),
    ], literal_targets=[],
    variants=[Variant("A", lambda root: _build(root, True), _artifacts, 4),
              Variant("B", lambda root: _build(root, False), _artifacts, 4)],
    expected={"A": {"lost": ["R2", "R7"], "recoverable": []},
              "B": {"lost": ["R2", "R7"], "recoverable": ["R2", "R7"]}},
)
