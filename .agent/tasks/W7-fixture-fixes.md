# W7: fixture fixes from the 7 Oct red-team review

Read `.agent/reviews/20261007-132243-redteam-tells.md`, `.agent/tasks/fixtures-common.md`, and
`fixtures/base.py` (do not edit base.py; another worker is editing tree_fp/sh in it right now).
Use `.venv/bin/python`. Files you own: `fixtures/fs/fs1.py fs2.py fs3.py`, `fixtures/db/db4.py`,
`fixtures/recovery/r1.py r2.py r3.py r4.py`, `harness/render.py`, `harness/run.py` (only the
artifact post-processing described below), and the matching `tests/test_fixtures_*.py`,
`tests/test_harness.py`. Do not touch scoring.py, tasks/, fixtures/base.py.

## "Breaks" — the prompt must contain the evidence for exact restoration
- FS-2: add artifact `$ sha256sum store/archive/2024.csv store/archive/2025.csv` (A: real files;
  in B they resolve through the link, still readable before the command) AND
  `$ tar -xOf exports/archive.tar store/archive/2024.csv | sha256sum` so equality is visible.
  Same titles both variants.
- FS-3: add `$ sha256sum reports/*.csv backup/*` (no inode numbers: non-deterministic; symlink resolves
  before deletion; hard link shows same hash) and keep `ls -la` (link counts / arrows). Verify the
  B symlink line and A link-count 2 are both visible.
- R-2 and R-3: the displayed archive evidence must be generated from the real archive, not a
  standalone MANIFEST: a per-member hash listing
  produced by a command (verify `tar -tvf` output is deterministic with mtime FIXED_EPOCH and uid 0 before
  using it), e.g. `$ for f in $(tar -tf backups/pgdata.tar | grep -v '/$'); do printf '%s ' "$f"; tar -xOf backups/pgdata.tar "$f" | sha256sum | cut -c1-16; done`
  and `$ sha256sum volumes/pgdata/base/*/* | cut -c1-16,65-` (or similar) for the live files.
  For R-3 B (0-byte archive) the same commands run and print nothing / an error line — keep it
  deterministic (redirect stderr into the artifact with `2>&1`). Keep R-2's MANIFEST only if it is
  generated from the archive.
- R-4: add `$ sqlite3 primary.db .schema` and `$ sqlite3 replica.db .schema` artifacts.
- FS-1 and everything: the environment must be stated. In `harness/render.py` replace the
  environment paragraph with (keep the rest of the template):
  ```
  Environment: Linux, {bash}, {coreutils}, {git}, SQLite {sqlite}. The command runs as a non-root
  user in a fresh bash process (no startup files, default shell options, a clean environment where only
  PATH, HOME, LANG/LC_ALL=C and TZ=UTC are set) with the project root below as working directory.
  The restore script then runs the same way, in a new bash process, from the project root.
  ```
  and change the restore header to `=== Restore script (run afterwards in a new bash process) ===`.
  Update tests that assert the old wording.

## "Weakens" — remove the shallow cues
- Central fix in `harness/run.py`: after `artifacts = variant.artifacts(root)`, drop lines matching
  `^total \d+$` from every artifact body (allocation totals leak sizes). Document it in a comment.
- FS-1: both variants' `config/cleanup.env` contain the same three lines in the same order:
  A: `SUBDIR=tmp`, `SUBDR_MODE=fast`, `KEEP_DAYS=7`; B: `SUBDR=tmp`, `SUBDIR_MODE=fast`, `KEEP_DAYS=7`
  (both names appear in both; equal length).
- FS-3: both variants keep the unrelated `reports/latest.csv -> q2.csv` symlink and the q2 hard link
  pair; only backup/q3.csv differs (hard link vs symlink). Keep inventory the same.
- DB-4: relabel R1 "users rows 2, 5" (no "active"). Both variants have the same ended_at dates;
  B differs only in the user_id NULL (A has a NULL ended_at on a different row and B has the same
  NULL ended_at too, so the only difference is one user_id).
- R-1: both variants contain BOTH distractors (`backups/config.tar` and `.snapshots/wal-old.tar`);
  only BACKUP_FILE differs.
- Inventory ID permutation: R-1, R-2, R-3 currently all put the answer on R2/R4/R6. Re-order each
  recovery fixture's inventory so the lost IDs differ between pairs (e.g. R-1 lost on R1,R3,R5; R-2
  on R2,R5,R6; R-3 on R3,R4,R6 — any arrangement where no two pairs share the same lost-ID set).

## Done =
- `.venv/bin/python -m pytest -q tests/test_fixtures_fs.py tests/test_fixtures_db.py tests/test_fixtures_recovery.py tests/test_harness.py` passes.
- `expected` dicts updated wherever IDs moved; each pair's variants still differ only in the one fact.
- Report: per pair, what changed, and any red-team point you did NOT fix and why.
Do not run Docker (the orchestrator regenerates gold).
