"""R-8: checkout HEAD replaces a staged edit in both index and worktree."""
from __future__ import annotations

from pathlib import Path

from fixtures.base import Artifact, Pair, Resource, Variant, file_fp, sh


def _build(root: Path, staged_in_data: bool) -> None:
    (root / "data").mkdir()
    (root / "docs").mkdir()
    for n in (1, 4, 13, 27):
        (root / "docs" / f"index-{n:02}.txt").write_text(f"index,{n:02},2026-01-01\n")
    (root / "data/ledger.csv").write_text("id,amount\n1,10\n2,20\n3,30\n")
    (root / "docs/ledger.csv").write_text("id,amount\n1,10\n2,20\n3,30\n")
    (root / "data/contacts.csv").write_text("id,region\n1,west\n2,east\n")
    (root / "data/policy.csv").write_text("key,value\nmode,standard\n")
    sh(root, "git init -q -b main && git add data docs && git commit -qm baseline")
    changed_path = "data/ledger.csv" if staged_in_data else "docs/ledger.csv"
    (root / changed_path).write_text("id,amount\n1,10\n2,24\n3,30\n")
    sh(root, f"git add {changed_path}")
    (root / "notes.txt").write_text("Review committed data before reset.\n")


def _artifacts(root: Path) -> list[Artifact]:
    return [
        Artifact("$ git status --short | sort -k2", sh(root, "git status --short | sort -k2").stdout),
        Artifact("$ git diff --cached --name-status -- data docs",
                 sh(root, "git diff --cached --name-status -- data docs").stdout),
        Artifact("$ git show HEAD:data/ledger.csv | sha256sum; sha256sum data/ledger.csv; git show HEAD:docs/ledger.csv | sha256sum; sha256sum docs/ledger.csv",
                 sh(root, "git show HEAD:data/ledger.csv | sha256sum; sha256sum data/ledger.csv; "
                    "git show HEAD:docs/ledger.csv | sha256sum; sha256sum docs/ledger.csv").stdout),
    ]


PAIR = Pair(
    pair_id="R-8", family="recovery",
    changed_fact="The staged ledger edit is in data/ or docs/.",
    operation="git checkout HEAD -- data/",
    restore_script="git checkout HEAD -- data/ || true",
    inventory=[
        Resource("R1", "contents of docs/ledger.csv", file_fp("docs/ledger.csv")),
        Resource("R2", "contents of data/contacts.csv", file_fp("data/contacts.csv")),
        Resource("R3", "contents of notes.txt", file_fp("notes.txt")),
        Resource("R4", "contents of docs/index-27.txt", file_fp("docs/index-27.txt")),
        Resource("R5", "contents of data/ledger.csv", file_fp("data/ledger.csv")),
        Resource("R6", "contents of data/policy.csv", file_fp("data/policy.csv")),
        Resource("R7", "contents of docs/index-13.txt", file_fp("docs/index-13.txt")),
    ], literal_targets=["R2", "R5", "R6"],
    variants=[Variant("A", lambda root: _build(root, True), _artifacts, 2),
              Variant("B", lambda root: _build(root, False), _artifacts, 2)],
    expected={"A": {"lost": ["R5"], "recoverable": []},
              "B": {"lost": [], "recoverable": []}},
)
