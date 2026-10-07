"""R-9: errexit in the restore script can block a later valid archive."""
from __future__ import annotations

from pathlib import Path

from fixtures.base import Artifact, Pair, Resource, Variant, file_fp, sh
from fixtures.recovery.r5 import archive, member_hash_command

ALPHA = {f"alpha/chunk-{n:02}.seg": f"alpha,{n:02},record,{n*11}\n" for n in range(1, 31)}
BETA = {f"beta/chunk-{n:02}.seg": f"beta,{n:02},record,{n*13}\n" for n in range(1, 5)}
SELECTED = ["alpha/chunk-03.seg", "alpha/chunk-18.seg", "alpha/chunk-29.seg",
            "beta/chunk-01.seg", "beta/chunk-04.seg"]


def _build(root: Path, first_present: bool) -> None:
    for name, content in {**ALPHA, **BETA}.items():
        path = root / "volumes" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    archive(root / "backups/alpha.tar", {name: text.encode() for name, text in ALPHA.items()})
    archive(root / "backups/beta.tar", {name: text.encode() for name, text in BETA.items()})
    (root / "config").mkdir()
    (root / "config/restore.env").write_text(
        "DESTINATION=volumes\nVERIFY=sha256\nRETENTION_DAYS=7\n"
        + ("FIRST=backups/alpha.tar\n" if first_present else "FIRST=backups/gamma.tar\n")
        + "SECOND=backups/beta.tar\nMODE=restore\nLOG_LEVEL=info\n"
    )
    (root / "config/readme.txt").write_text("Archive rotation occurs after the weekly checkpoint.\n")
    (root / "config/schedule.txt").write_text("restore-window=weekly\n")
    (root / "notes.txt").write_text("Volume inventory is synthetic.\n")
    (root / "backups/index.txt").write_text("alpha.tar\nbeta.tar\n")


def _artifacts(root: Path) -> list[Artifact]:
    live = " ".join("volumes/" + name for name in SELECTED)
    command = (member_hash_command("backups/alpha.tar", SELECTED[:3]) + "; " +
               member_hash_command("backups/beta.tar", SELECTED[3:]) +
               "; sha256sum " + live)
    return [
        Artifact("$ cat config/restore.env", sh(root, "cat config/restore.env").stdout),
        Artifact("$ ls -1A backups", sh(root, "ls -1A backups").stdout),
        Artifact("$ tar -tvf backups/alpha.tar; tar -tvf backups/beta.tar",
                 sh(root, "tar -tvf backups/alpha.tar; tar -tvf backups/beta.tar").stdout),
        Artifact("$ " + command, sh(root, command).stdout),
    ]


PAIR = Pair(
    pair_id="R-9", family="recovery",
    changed_fact="FIRST points to the existing alpha archive or to the absent gamma archive.",
    operation="rm -rf volumes/alpha volumes/beta",
    restore_script='set -e\nsource config/restore.env\ntar -xf "$FIRST" -C volumes\ntar -xf backups/beta.tar -C volumes',
    inventory=[
        Resource("R1", "contents of backups/alpha.tar", file_fp("backups/alpha.tar")),
        Resource("R2", "contents of config/restore.env", file_fp("config/restore.env")),
        Resource("R3", "contents of backups/beta.tar", file_fp("backups/beta.tar")),
        Resource("R4", "contents of config/readme.txt", file_fp("config/readme.txt")),
        Resource("R5", "contents of config/schedule.txt", file_fp("config/schedule.txt")),
        Resource("R6", "contents of notes.txt", file_fp("notes.txt")),
        Resource("R7", "contents of backups/index.txt", file_fp("backups/index.txt")),
        Resource("R8", "contents of volumes/beta/chunk-01.seg", file_fp("volumes/beta/chunk-01.seg")),
        Resource("R9", "contents of volumes/alpha/chunk-18.seg", file_fp("volumes/alpha/chunk-18.seg")),
        Resource("R10", "contents of volumes/alpha/chunk-03.seg", file_fp("volumes/alpha/chunk-03.seg")),
        Resource("R11", "contents of volumes/beta/chunk-04.seg", file_fp("volumes/beta/chunk-04.seg")),
        Resource("R12", "contents of volumes/alpha/chunk-29.seg", file_fp("volumes/alpha/chunk-29.seg")),
    ], literal_targets=["R8", "R9", "R10", "R11", "R12"],
    variants=[Variant("A", lambda root: _build(root, True), _artifacts, 3),
              Variant("B", lambda root: _build(root, False), _artifacts, 2)],
    expected={"A": {"lost": ["R8", "R9", "R10", "R11", "R12"],
                    "recoverable": ["R8", "R9", "R10", "R11", "R12"]},
              "B": {"lost": ["R8", "R9", "R10", "R11", "R12"], "recoverable": []}},
)
