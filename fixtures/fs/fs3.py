"""FS-3: a backup name may share bytes or follow a removed name."""
import os
from pathlib import Path

from fixtures.base import Artifact, Pair, Resource, Variant, file_fp, sh


def _build(root: Path, backup_is_link: bool) -> None:
    (root / "reports").mkdir()
    (root / "backup").mkdir()
    (root / "reports/q1.csv").write_text("quarter,total\n1,14\n")
    (root / "reports/q2.csv").write_text("quarter,total\n2,18\n")
    (root / "reports/q3.csv").write_text("quarter,total\n3,21\n")
    if backup_is_link:
        (root / "backup/q3.csv").symlink_to("../reports/q3.csv")
        os.link(root / "reports/q2.csv", root / "backup/q2.csv")
        (root / "reports/latest.csv").write_bytes((root / "reports/q2.csv").read_bytes())
    else:
        os.link(root / "reports/q3.csv", root / "backup/q3.csv")
        (root / "backup/q2.csv").write_bytes((root / "reports/q2.csv").read_bytes())
        (root / "reports/latest.csv").symlink_to("q2.csv")


def _artifacts(root: Path):
    commands = ("ls -la reports", "ls -la backup")
    return [Artifact("$ " + command, sh(root, command).stdout) for command in commands]


PAIR = Pair(
    pair_id="FS-3",
    family="fs",
    changed_fact="The q3 backup is a hard link in A and a symlink in B.",
    operation="rm reports/q3.csv",
    restore_script="[ -f backup/q3.csv ] && cp backup/q3.csv reports/q3.csv || true",
    inventory=[
        Resource("R1", "contents of reports/q2.csv", file_fp("reports/q2.csv")),
        Resource("R2", "contents of backup/q3.csv", file_fp("backup/q3.csv")),
        Resource("R3", "contents of reports/q1.csv", file_fp("reports/q1.csv")),
        Resource("R4", "contents of reports/q3.csv", file_fp("reports/q3.csv")),
        Resource("R5", "contents of reports/latest.csv", file_fp("reports/latest.csv")),
        Resource("R6", "contents of backup/q2.csv", file_fp("backup/q2.csv")),
    ],
    literal_targets=["R4"],
    variants=[
        Variant("A", lambda root: _build(root, False), _artifacts, 1),
        Variant("B", lambda root: _build(root, True), _artifacts, 1),
    ],
    expected={
        "A": {"lost": ["R4"], "recoverable": ["R4"]},
        "B": {"lost": ["R2", "R4"], "recoverable": []},
    },
)
