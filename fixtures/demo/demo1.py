"""Copy versus dangling symlink recovery demo."""

from pathlib import Path

from fixtures.base import Artifact, Pair, Resource, Variant, file_fp, sh


def build(root: Path, symlink: bool) -> None:
    (root / "notes").mkdir()
    (root / "backup").mkdir()
    (root / "notes/a.txt").write_text("alpha\n", encoding="utf-8")
    (root / "notes/b.txt").write_text("beta\n", encoding="utf-8")
    if symlink:
        (root / "backup/a.txt").symlink_to("../notes/a.txt")
    else:
        (root / "backup/a.txt").write_text("alpha\n", encoding="utf-8")


def artifacts(root: Path) -> list[Artifact]:
    return [Artifact("$ ls -lR", sh(root, "ls -lR").stdout)]


PAIR = Pair(
    pair_id="DEMO-1", family="demo", changed_fact="backup/a.txt copy versus symlink",
    operation="rm -f notes/a.txt",
    restore_script="[ -f backup/a.txt ] && cp backup/a.txt notes/a.txt || true",
    inventory=[
        Resource("R1", "contents of notes/a.txt", file_fp("notes/a.txt")),
        Resource("R2", "contents of notes/b.txt", file_fp("notes/b.txt")),
        Resource("R3", "contents of backup/a.txt", file_fp("backup/a.txt")),
    ],
    literal_targets=["R1"],
    variants=[
        Variant("A", lambda root: build(root, False), artifacts, 1),
        Variant("B", lambda root: build(root, True), artifacts, 1),
    ],
    expected={
        "A": {"lost": ["R1"], "recoverable": ["R1"]},
        "B": {"lost": ["R1", "R3"], "recoverable": []},
    },
)
