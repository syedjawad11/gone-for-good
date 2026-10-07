"""R-6: stash excludes an untracked file, while clean is scoped by config."""
from __future__ import annotations

from pathlib import Path

from fixtures.base import Artifact, Pair, Resource, Variant, file_fp, sh


def _build(root: Path, clean_data: bool) -> None:
    (root / "data").mkdir()
    (root / "notes").mkdir()
    (root / "config").mkdir()
    for number in (3, 5, 17, 29, 31, 51):
        (root / "notes" / f"check-{number:02}.txt").write_text(f"review,{number:02},2026-01-01\n")
    (root / ".gitignore").write_text("*.cache\n")
    (root / "data/ledger.csv").write_text("id,amount\n1,12\n2,24\n")
    (root / "config/clean.env").write_text(
        "REPOSITORY=.\nSTASH_MODE=tracked\nREPORT=short\n"
        + ("CLEAN_PATH=data/\n" if clean_data else "CLEAN_PATH=notes/\n")
        + "CLEAN_FLAGS=-fd\nRESTORE=stash\nLOG_LEVEL=info\n"
    )
    sh(root, "git init -q -b main && git add .gitignore notes data/ledger.csv config && git commit -qm initial")
    (root / "data/ledger.csv").write_text("id,amount\n1,12\n2,27\n")
    (root / "data/queue.csv").write_text("id,amount\n1,7\n2,14\n")


def _artifacts(root: Path) -> list[Artifact]:
    return [
        Artifact("$ cat config/clean.env", sh(root, "cat config/clean.env").stdout),
        Artifact("$ git status --short", sh(root, "git status --short").stdout),
        Artifact("$ git diff -- data/ledger.csv", sh(root, "git diff -- data/ledger.csv").stdout),
        Artifact("$ git stash list", sh(root, "git stash list").stdout),
    ]


PAIR = Pair(
    pair_id="R-6", family="recovery",
    changed_fact="CLEAN_PATH selects notes/ or data/; stash saves the tracked ledger edit but not the untracked queue.",
    operation='source config/clean.env\ngit stash\ngit clean -fd "$CLEAN_PATH"',
    restore_script="git stash pop >/dev/null 2>&1 || true",
    inventory=[
        Resource("R1", "contents of notes/check-03.txt", file_fp("notes/check-03.txt")),
        Resource("R2", "contents of notes/check-05.txt", file_fp("notes/check-05.txt")),
        Resource("R3", "contents of notes/check-17.txt", file_fp("notes/check-17.txt")),
        Resource("R4", "contents of .gitignore", file_fp(".gitignore")),
        Resource("R5", "contents of config/clean.env", file_fp("config/clean.env")),
        Resource("R6", "contents of notes/check-29.txt", file_fp("notes/check-29.txt")),
        Resource("R7", "contents of notes/check-31.txt", file_fp("notes/check-31.txt")),
        Resource("R8", "contents of notes/check-51.txt", file_fp("notes/check-51.txt")),
        Resource("R9", "contents of data/queue.csv", file_fp("data/queue.csv")),
        Resource("R10", "contents of data/ledger.csv", file_fp("data/ledger.csv")),
    ], literal_targets=[],
    variants=[Variant("A", lambda root: _build(root, False), _artifacts, 4),
              Variant("B", lambda root: _build(root, True), _artifacts, 4)],
    expected={"A": {"lost": ["R10"], "recoverable": ["R10"]},
              "B": {"lost": ["R9", "R10"], "recoverable": ["R10"]}},
)
