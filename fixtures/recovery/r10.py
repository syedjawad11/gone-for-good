"""R-10: a hard-linked snapshot shares writes with its source."""
from __future__ import annotations

import os
from pathlib import Path

from fixtures.base import Artifact, Pair, Resource, Variant, file_fp, sh

LEDGER = "id,amount,status\n01,000009,posted\n02,000018,posted\n"


def _build(root: Path, linked: bool) -> None:
    (root / "volumes/pgdata").mkdir(parents=True)
    (root / "snapshots/pgdata").mkdir(parents=True)
    live = root / "volumes/pgdata/ledger.seg"
    snapshot = root / "snapshots/pgdata/ledger.seg"
    live.write_text(LEDGER)
    if linked:
        os.link(live, snapshot)
    else:
        snapshot.write_text(LEDGER)
    for number in (1, 2, 3, 4, 5, 6, 7, 16, 25):
        (root / "volumes/pgdata" / f"catalog-{number:02}.seg").write_text(f"catalog,{number},ready\n")
    for number in range(1, 7):
        snapshot_catalog = root / "snapshots/pgdata" / f"catalog-{number:02}.seg"
        if number == 2:
            os.link(root / "volumes/pgdata" / f"catalog-{number:02}.seg", snapshot_catalog)
        else:
            snapshot_catalog.write_text(f"catalog,{number},ready\n")
    (root / "config.txt").write_text("snapshot=snapshots/pgdata/ledger.seg\n")
    (root / "notes.txt").write_text("Ledger rows are synthetic.\n")


def _artifacts(root: Path) -> list[Artifact]:
    names = "catalog-02.seg ledger.seg"
    identity = (f"for n in {names}; do if test snapshots/pgdata/\"$n\" -ef volumes/pgdata/\"$n\"; "
                "then echo \"$n same-file\"; else echo \"$n different-file\"; fi; done")
    others = ("config.txt notes.txt volumes/pgdata/catalog-02.seg "
              "volumes/pgdata/catalog-07.seg volumes/pgdata/catalog-16.seg "
              "volumes/pgdata/catalog-25.seg")
    cross = (f"for p in {others}; do if test volumes/pgdata/ledger.seg -ef \"$p\"; "
             "then echo \"$p same-file ledger\"; else echo \"$p different-file ledger\"; fi; done")
    return [
        Artifact("$ " + identity, sh(root, identity).stdout),
        Artifact("$ " + cross, sh(root, cross).stdout),
        Artifact("$ sha256sum volumes/pgdata/ledger.seg snapshots/pgdata/ledger.seg",
                 sh(root, "sha256sum volumes/pgdata/ledger.seg snapshots/pgdata/ledger.seg").stdout),
    ]


PAIR = Pair(
    pair_id="R-10", family="recovery",
    changed_fact="The snapshot is a hard link to the ledger or an independent byte copy.",
    operation=": > volumes/pgdata/ledger.seg",
    restore_script="cp snapshots/pgdata/ledger.seg volumes/pgdata/ledger.seg || true",
    inventory=[
        Resource("R1", "contents of config.txt", file_fp("config.txt")),
        Resource("R2", "contents of volumes/pgdata/catalog-02.seg", file_fp("volumes/pgdata/catalog-02.seg")),
        Resource("R3", "contents of snapshots/pgdata/ledger.seg", file_fp("snapshots/pgdata/ledger.seg")),
        Resource("R4", "contents of volumes/pgdata/ledger.seg", file_fp("volumes/pgdata/ledger.seg")),
        Resource("R5", "contents of volumes/pgdata/catalog-16.seg", file_fp("volumes/pgdata/catalog-16.seg")),
        Resource("R6", "contents of volumes/pgdata/catalog-07.seg", file_fp("volumes/pgdata/catalog-07.seg")),
        Resource("R7", "contents of volumes/pgdata/catalog-25.seg", file_fp("volumes/pgdata/catalog-25.seg")),
        Resource("R8", "contents of notes.txt", file_fp("notes.txt")),
    ], literal_targets=["R4"],
    variants=[Variant("A", lambda root: _build(root, True), _artifacts, 2),
              Variant("B", lambda root: _build(root, False), _artifacts, 3)],
    expected={"A": {"lost": ["R3", "R4"], "recoverable": []},
              "B": {"lost": ["R4"], "recoverable": ["R4"]}},
)
