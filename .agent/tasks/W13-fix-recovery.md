# W13: fix held-out R-5..R-10
Read `.agent/tasks/heldout-fixes-common.md` first. Files: `fixtures/recovery/r5.py`..`r10.py`,
`tests/test_fixtures_recovery_heldout.py`. Specific findings to close:
- R-5: show the COMPLETE typed member listing of the archive (`tar -tvf` is deterministic with fixed mtime/uid;
  verify) plus the content hashes; no filtered listing. Fix B's hops.
- R-6: show `git stash list` (empty). Add an inventoried tracked modification that the `git stash` really saves
  and `git stash pop` really restores, so stash semantics matter; drop the 71-line padding.
- R-7: prove the backups are independent files (regular-file metadata + generated `-ef` checks both ways).
- R-8: duplicates FS-6. Redesign around restore from HEAD with a STAGED edit: `git checkout HEAD -- <path>`
  overwrites index and worktree, so staging does not protect the edit (counterbalances FS-6, where staging
  protects). Equal-length, balanced evidence; drop the 71-line padding.
- R-9: rename `alpha-unavailable.tar` to a neutral, equal-length name; show complete member listings for BOTH
  archives (prove beta does not contain alpha paths); fix hops for B.
- R-10: prove no other inventoried file aliases the ledger (distinct hashes / negative `-ef` checks).
