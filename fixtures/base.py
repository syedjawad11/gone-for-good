"""Shared contract for every fixture. Workers code against this file; do not change it.

A fixture module (fixtures/<family>/<pair>.py, e.g. fixtures/fs/fs1.py) exposes:

    PAIR = Pair(...)          # one matched pair (2 or 3 variants)

The harness (harness/run.py) does, per variant, in a fresh temp dir `root`:
    variant.build(root)                    # create files / git repo / sqlite db
    set_fixed_mtimes(root)                 # harness does this, fixtures don't
    artifacts = variant.artifacts(root)    # rendered from the BUILT env (real ls/cat/schema output)
    before = fingerprints(root)
    result = run_operation(root, variant.operation, variant.op_kind)
    after = fingerprints(root)             # lost = fingerprint changed or became None
    run(root, pair.restore_script)         # the exact script shown to the model
    restored = fingerprints(root)          # recoverable = lost and restored == before

Gold therefore means: "lost by this command" and "brought back exactly by THIS restore script".
It does not claim that no other recovery method exists; the prompt says so.

Resource identity (pick the fingerprint that matches the label, and say it in the label):
- file_fp:   the bytes readable at a path (follows symlinks). Label: "contents of reports/q3.csv".
- link_fp:   a symlink object itself (its target text), never its target. Label: "symlink backup/q3.csv".
- tree_fp:   a directory's contents. Label: "contents of uploads/archive/".
- sqlite_fp: specific PRE-EXISTING rows selected by key, ORDER BY primary key. Label:
             "orders rows 101-104 (customer 7)". Never a whole table: inserts elsewhere (archive
             triggers, audit rows) must not count as a loss. Only pre-existing state is inventoried.

Rules:
- `operation` is the exact text shown to the model and the exact text executed.
- Resource IDs and labels must be identical across the variants of a pair (same inventory).
  Only the environment differs, in the one fact named by `changed_fact`.
- Everything that decides the outcome must appear in `artifacts`.
- Nothing may depend on wall-clock time, randomness, inode numbers, $USER or the host.
- Synthetic content only.
- Surface tells: both variants show the same artifact titles in the same order, with bodies of
  similar length. A "scary" token that marks the bad variant (symlink, NULL, .gitignore, trigger,
  snapshot, checksum, AUTO_SYNC, ...) must also appear harmlessly in the other variant.
- Shell ops run with a clean env (`env -i`-style), no startup files, default shopt (no dotglob,
  nullglob, failglob, nounset unless the shown script sets them).
"""
from __future__ import annotations

import hashlib
import os
import sqlite3
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional

FIXED_EPOCH = 1767225600  # 2026-01-01T00:00:00Z, used for every mtime and git date

# Environment for every subprocess the fixtures and harness run. No host leakage.
BASE_ENV = {
    "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
    "LC_ALL": "C",
    "LANG": "C",
    "TZ": "UTC",
    "GIT_AUTHOR_NAME": "Dev Example",
    "GIT_AUTHOR_EMAIL": "dev@example.invalid",
    "GIT_COMMITTER_NAME": "Dev Example",
    "GIT_COMMITTER_EMAIL": "dev@example.invalid",
    "GIT_AUTHOR_DATE": "2026-01-01T00:00:00Z",
    "GIT_COMMITTER_DATE": "2026-01-01T00:00:00Z",
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_OPTIONAL_LOCKS": "0",  # `git status` in artifacts must not rewrite .git/index (mtime leak)
}


def home_for(root: Path) -> Path:
    """HOME lives next to root (not inside it), so it never shows up in listings or globs."""
    home = root.parent / (root.name + ".home")
    home.mkdir(exist_ok=True)
    return home


def env_for(root: Path) -> dict:
    """Subprocess env with HOME pinned beside the sandbox root."""
    env = dict(BASE_ENV)
    env["HOME"] = str(home_for(root))
    env["GIT_CONFIG_GLOBAL"] = str(home_for(root) / ".gitconfig")
    return env


def sh(root: Path, script: str, check: bool = True) -> subprocess.CompletedProcess:
    """Run a bash script with cwd=root and the pinned env. Used by build/restore/artifacts."""
    return subprocess.run(
        ["bash", "-c", script], cwd=str(root), env=env_for(root),
        capture_output=True, text=True, check=check, timeout=60,
    )


# ---------------------------------------------------------------- fingerprints

def file_fp(rel: str) -> Callable[[Path], Optional[str]]:
    """Content hash of one regular file (follows symlinks). None if missing/dangling/not a file."""
    def fp(root: Path) -> Optional[str]:
        p = root / rel
        if not p.is_file():
            return None
        return hashlib.sha256(p.read_bytes()).hexdigest()
    return fp


def link_fp(rel: str) -> Callable[[Path], Optional[str]]:
    """The symlink object at `rel` (its target text). None if absent or not a symlink."""
    def fp(root: Path) -> Optional[str]:
        p = root / rel
        if not p.is_symlink():
            return None
        return "link:" + os.readlink(p)
    return fp


def tree_fp(rel: str) -> Callable[[Path], Optional[str]]:
    """Hash typed, length-prefixed entries without following symlinked directories."""
    def fp(root: Path) -> Optional[str]:
        base = root / rel
        if not base.is_dir() or base.is_symlink():
            return None
        h = hashlib.sha256()
        entries = []
        for dirpath, dirnames, filenames in os.walk(base):
            for name in dirnames + filenames:
                p = Path(dirpath) / name
                if p.is_symlink():
                    kind, payload = b"link", os.fsencode(os.readlink(p))
                elif p.is_dir():
                    kind, payload = b"dir", b""
                else:
                    kind, payload = b"file", p.read_bytes()
                entries.append((os.fsencode(p.relative_to(base)), kind, payload))
            dirnames[:] = sorted(name for name in dirnames
                                 if not (Path(dirpath) / name).is_symlink())
        for path, kind, payload in sorted(entries):
            h.update(kind + b"|" + len(path).to_bytes(8, "big") + b"|" + path
                     + b"|" + len(payload).to_bytes(8, "big") + b"|" + payload)
        return h.hexdigest()
    return fp


def sqlite_fp(db_rel: str, query: str) -> Callable[[Path], Optional[str]]:
    """Hash of the rows returned by `query` (ordered by the query itself). None if the db or
    table is missing or the query returns no rows."""
    def fp(root: Path) -> Optional[str]:
        p = root / db_rel
        if not p.is_file():
            return None
        con = sqlite3.connect(str(p))
        try:
            rows = con.execute(query).fetchall()
        except sqlite3.Error:
            return None
        finally:
            con.close()
        if not rows:
            return None
        return hashlib.sha256(repr(rows).encode()).hexdigest()
    return fp


# ---------------------------------------------------------------- data shapes

@dataclass(frozen=True)
class Resource:
    id: str      # "R1", "R2", ... unique within the pair
    label: str   # what the model sees, e.g. "file data/customers.csv" or "orders rows for customer 7"
    fingerprint: Callable[[Path], Optional[str]]


@dataclass(frozen=True)
class Artifact:
    title: str   # e.g. "$ ls -la" or "config/cleanup.env" or "sqlite3 app.db .schema"
    body: str    # exact text; produced from the built environment, not hand-typed


@dataclass
class Variant:
    variant: str                                  # "A", "B", optionally "C" (never shown to the model)
    build: Callable[[Path], None]                 # create the environment under root
    artifacts: Callable[[Path], List[Artifact]]   # render what the model sees
    hops: int                                     # artifacts that must be combined (1..3)


@dataclass
class Pair:
    pair_id: str                 # "FS-1"
    family: str                  # "fs" | "db" | "recovery"
    changed_fact: str            # one line, for analysis only (never shown to the model)
    operation: str               # exact bash shown to the model and run as `bash -c` with cwd=root.
                                 # SQL ops: sqlite3 -bail app.db "PRAGMA foreign_keys=ON; BEGIN; ...; COMMIT;"
                                 # (-bail stops at the first error; the open transaction is rolled back
                                 # when sqlite3 exits). Wrapper scripts are fine if built into root and
                                 # their source is shown as an artifact.
    restore_script: str          # exact bash shown to the model and executed after the operation.
                                 # May only use what survived; must not fail loudly when a source is
                                 # missing (use `|| true` / guards), so restore errors never decide gold.
    inventory: List[Resource]
    literal_targets: List[str]   # IDs the command names literally (for the frozen naive-reader baseline),
                                 # e.g. `rm reports/q3.csv` -> the resource for reports/q3.csv.
    variants: List[Variant] = field(default_factory=list)
    expected: dict = field(default_factory=dict)  # {"A": {"lost": [...], "recoverable": [...]}, ...}
    # `expected` is the author's hypothesis. The harness reports any mismatch with the executed
    # result; executed results are the gold, never this dict.
