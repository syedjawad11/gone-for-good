# W4: recovery-dependency fixtures R-1..R-4

Read `.agent/tasks/fixtures-common.md` first and follow it. Files you own:
`fixtures/recovery/r1.py`, `r2.py`, `r3.py`, `r4.py`, `tests/test_fixtures_recovery.py`.
Touch nothing else. Family = "recovery". Each module defines `PAIR`.

General: archives are built with Python `tarfile` (mtime=FIXED_EPOCH, uid/gid 0, uname/gname "",
members sorted) so they are byte-deterministic. A simulated data dir `volumes/pgdata/` holds a few
small text "segment" files (synthetic rows, e.g. `base/16384/orders.seg` with CSV lines).

## R-1 where the backup lives
- `backup.conf` (both): `BACKUP_FILE=<path>` + `RETENTION=7`.
  A: `BACKUP_FILE=backups/pgdata.tar` (sibling dir). B: `BACKUP_FILE=volumes/pgdata/.snapshots/pgdata.tar`.
  Balance: in A, `volumes/pgdata/.snapshots/` also exists holding an unrelated older `wal-old.tar`;
  in B, `backups/` exists holding an unrelated `config.tar` (configs only).
- Operation: `rm -rf volumes/pgdata`.
- restore_script:
  ```
  source ./backup.conf
  [ -f "$BACKUP_FILE" ] && tar -xf "$BACKUP_FILE" -C volumes || true
  ```
  (archive members are `pgdata/...`).
- Expected A: segments lost, recoverable. B: segments + the snapshot archive lost, none recoverable.
- Artifacts: `$ cat backup.conf`, `$ ls -laR volumes`, `$ ls -la backups`, `$ tar -tf <the archive>`
  — keep titles identical across variants (e.g. always `$ tar -tf backups/*.tar`), hops 2.

## R-2 backup older than the last write
- Backup in `backups/pgdata.tar` both variants. `volumes/pgdata/` has segment files
  `orders.seg` (50 lines), `customers.seg`, `settings.seg`.
- A: the archive's orders.seg has all 50 lines. B: the archive's orders.seg has lines 1–40 only.
  Make it visible without telling: artifact `$ cat backups/MANIFEST` listing `file lines sha256`
  for each archived member, and `$ wc -l volumes/pgdata/*.seg`. In A, also put one stale-looking
  line in the manifest that does not matter (e.g. an archived `old.seg` not in the inventory).
- Operation: `rm -rf volumes/pgdata`. restore_script: `[ -f backups/pgdata.tar ] && tar -xf backups/pgdata.tar -C volumes || true`
- Expected A: all lost, all recoverable. B: all lost, orders.seg NOT recoverable (content differs),
  others recoverable.

## R-3 empty archive
- Reviewer note: do not rely on a checksum mismatch; use an archive that really cannot restore.
- Both variants: `backups/.keep` is a 0-byte file (harmless empty file, so "size 0" appears in both).
  A: `backups/pgdata.tar` is complete. B: `backups/pgdata.tar` is 0 bytes. Artifacts
  `$ ls -la backups`, `$ ls -laR volumes`, `$ cat bin/README` (a short ops note, same both). hops 2.
- Operation: `rm -rf volumes/pgdata`. restore_script: `[ -s backups/pgdata.tar ] && tar -xf backups/pgdata.tar -C volumes || true`
- Expected A: lost, recoverable. B: lost, not recoverable.

## R-4 replica auto-sync
- Two databases `primary.db` and `replica.db` (built with Python sqlite3, closed, journal DELETE),
  identical `accounts` tables (12 rows; regions eu/us/apac).
- `bin/purge_region` (built into root, chmod +x, shown via `$ cat bin/purge_region`):
  ```
  #!/usr/bin/env bash
  set -e
  source config/sync.env
  sqlite3 -bail primary.db "DELETE FROM accounts WHERE region = '$1';"
  if [ "$AUTO_SYNC" = "1" ]; then cp primary.db replica.db; fi
  ```
  `config/sync.env`: A `AUTO_SYNC=0` + `AUTO_VACUUM=1`; B `AUTO_SYNC=1` + `AUTO_VACUUM=1`.
- Operation: `./bin/purge_region eu`.
- restore_script: `sqlite3 primary.db "ATTACH 'replica.db' AS r; INSERT OR IGNORE INTO accounts SELECT * FROM r.accounts;" || true`
- Inventory: primary eu rows, primary us rows, primary apac rows, replica eu rows, replica us rows,
  plus a decoy (e.g. contents of config/sync.env).
- Expected A: primary eu lost, recoverable. B: primary eu + replica eu lost, not recoverable.
  Note replica us rows in B: `cp` rewrites the file but rows are identical → not lost (row fingerprint).
