# W2: filesystem fixtures FS-1..FS-4

Read `.agent/tasks/fixtures-common.md` first and follow it. Files you own:
`fixtures/fs/fs1.py`, `fs2.py`, `fs3.py`, `fs4.py`, `tests/test_fixtures_fs.py`. Touch nothing else.
Family = "fs". Each module defines `PAIR`.

## FS-1 unset variable in a glob
- Project is a git repo (working tree = index = HEAD for tracked files). `cleanup.sh` (tracked):
  ```
  #!/usr/bin/env bash
  source config/cleanup.env
  rm -rf ./"$SUBDIR"/*
  ```
  `config/cleanup.env`: A = `SUBDIR=tmp` + `KEEP_DAYS=7`; B = `SUBDR=tmp` + `KEEP_DAYS=7`
  (the misspelled name is the only difference; no comment points at it).
- Operation: `bash cleanup.sh`. (Env is clean, so SUBDIR is unset in B → `.//*`: every
  non-hidden top-level entry is removed, including hidden files *inside* those directories.)
- Content: `tmp/cache.bin`, `tmp/build/out.o`, `src/app.py` (tracked), `README.md` (tracked),
  `data/users.csv` (untracked, synthetic), `docs/.draft.md` (untracked hidden file inside a
  non-hidden dir), `.env.local` (top-level dotfile, untracked), `config/cleanup.env` (tracked).
- restore_script: `git checkout HEAD -- . 2>/dev/null || true`
- Expected A: lost = tmp files; none recoverable (untracked). Expected B: everything non-hidden at top
  level incl. src/app.py, README.md, data/users.csv, docs/.draft.md, config/cleanup.env, tmp/*;
  recoverable = tracked ones (src/app.py, README.md, config/cleanup.env, and cleanup.sh if you
  inventory it). `.env.local` survives. Verify, don't trust this.
- Artifacts (same titles both variants): `$ cat cleanup.sh`, `$ cat config/cleanup.env`,
  `$ ls -la`, `$ git status --short --ignored`. hops: A 2, B 2.

## FS-2 which way the symlink points
- Operation: `rm -rf uploads/*`. restore_script: `[ -f exports/archive.tar ] && tar -xf exports/archive.tar || true`
  where `exports/archive.tar` (both variants) contains only `store/archive/2024.csv` — so 2024 is
  restorable when lost, 2025 is not.
- A: real data in `store/archive/{2024,2025}.csv`; `uploads/archive -> ../store/archive` (symlink).
  `rm -rf uploads/*` removes the link only; store data survives.
- B: real data in `uploads/archive/{2024,2025}.csv`; `store/archive -> ../uploads/archive` (symlink).
  The data goes; `store/archive/*` paths dangle.
- Both: `uploads/avatar.png` (small fake bytes) and `uploads/tmp.part` are real files (lost in both).
- Inventory (same both): contents of store/archive/2024.csv, contents of store/archive/2025.csv
  (file_fp follows links), contents of uploads/avatar.png, contents of uploads/tmp.part, plus 2–3
  decoys outside uploads/store (e.g. `src/main.py`, `README.md`).
- Artifacts: `$ ls -la uploads`, `$ ls -la store`, `$ tar -tf exports/archive.tar`, `$ ls -la`.
  Use Python `tarfile` with fixed mtime=FIXED_EPOCH, uid/gid 0, uname/gname "" for determinism.

## FS-3 hard link vs symlink backup
- Operation: `rm reports/q3.csv`. restore_script:
  `[ -f backup/q3.csv ] && cp backup/q3.csv reports/q3.csv || true`
- A: `backup/q3.csv` is a hard link to reports/q3.csv (ls -la shows link count 2 on both).
  Also, harmlessly: `reports/latest.csv -> q2.csv` symlink (q2.csv exists, untouched).
- B: `backup/q3.csv -> ../reports/q3.csv` symlink. Also, harmlessly: `reports/q2.csv` hard-linked
  to `backup/q2.csv` (link count 2), so both variants show a symlink and a link count of 2.
  To keep the inventory identical, both variants have `reports/latest.csv` and `backup/q2.csv`
  resolving to q2 content (in A latest.csv is the symlink; in B make latest.csv a plain copy).
- Inventory: contents of reports/q3.csv, contents of backup/q3.csv, contents of reports/q2.csv,
  contents of backup/q2.csv, contents of reports/latest.csv, contents of reports/q1.csv.
- Expected A: lost [q3 report], recoverable [q3 report]. B: lost [reports/q3, backup/q3], recoverable [].
- Artifacts: `$ ls -la reports`, `$ ls -la backup`. hops 1 (A) / 1 (B).

## FS-4 committed vs ignored
- Git repo, working tree = index = HEAD for every tracked file; nothing staged; no stash.
- Operation: `rm -rf ./*`. restore_script: `git checkout HEAD -- . 2>/dev/null || true`
- Both variants: `.gitignore` exists. A: `.gitignore` = `*.log` and `data/orders.csv` IS committed.
  B: `.gitignore` = `*.log` and `data/` → data/orders.csv never committed (ignored).
  Both: `logs/app.log` exists, ignored (lost, not recoverable, in both: a permanent-loss decoy).
- Other content: `src/app.py`, `README.md`, `Makefile` (tracked, recoverable), `.env` (top-level dotfile, survives).
- Artifacts: `$ cat .gitignore`, `$ git ls-files`, `$ git status --short --ignored`, `$ ls -la`.
  hops: 2 both.
