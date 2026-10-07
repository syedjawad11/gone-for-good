# W10: held-out recovery-dependency fixtures R-5..R-10

Read `.agent/tasks/heldout-common.md` first and follow it, plus the general rules of
`.agent/tasks/W4-recovery.md` (deterministic tar via Python `tarfile`, synthetic data dirs).
Files you own: `fixtures/recovery/r5.py` .. `fixtures/recovery/r10.py`,
`tests/test_fixtures_recovery_heldout.py`. Touch nothing else. Family = "recovery". Pair IDs "R-5" .. "R-10". Six pairs.

Evidence rule from the red team: whenever exact restoration depends on archive content, the prompt must
show evidence generated from the real archive (e.g. `tar -tvf` or a per-member hash listing produced by a
command) AND hashes of the live files, so equality is visible; see heldout-common.md.

## Mechanism menu (pick at least 5; you may substitute others that meet the rules, say why)
1. tar member prefix: members `pgdata/...` vs `volumes/pgdata/...` with restore
   `tar -xf backups/pg.tar -C volumes` (second case extracts to the wrong place). Or `--strip-components`.
2. Rotation by lexical order: a wrapper keeps "the newest 2" with
   `cd backups && ls | sort | head -n -2 | xargs rm --` style logic (run inside backups/); `backup-9.tar` sorts after `backup-10.tar` without zero padding, so the newest go.
   Deciding fact: zero-padded names vs not. (Do NOT use `ls -t`: mtimes are all equal.)
3. Restore with `cp -n` (no clobber; `--update=none` does not exist in coreutils 9.1) after an operation that truncates files instead
   of deleting them: the truncated files block the restore.
4. `git stash` (without `-u`) then `git clean -fd`, restore `git stash pop`: an untracked file (`??`) is
   not stashed and is gone; a modified tracked file (` M`) comes back.
5. Restore from git `git checkout HEAD -- data/`: exact only for files unmodified since the commit
   (`git status --short` shows ` M` or not).
6. Restore script that starts with `set -e`: an earlier step failing (a missing first archive in the
   listing) stops later steps that would have worked.
7. Hard-linked snapshot (`cp -al` style, link count 2 visible) vs a real copy, with an operation that
   writes through the inode (`truncate`, `>`) rather than unlinking.
8. Backup script with an `--exclude` pattern that also matches the critical file (e.g. `--exclude='*.db-*'`
   vs `--exclude='*.db-wal'`), with the real `tar -tf` listing shown.
9. Two-step dependency: the backup is only restorable if a key/config file that the operation also
   deleted survived (e.g. restore reads the archive path from a config the operation removed).
Mix hops 2 and 3; vary which resources are lost so lost-ID sets differ from the pilot's R-1..R-4.
