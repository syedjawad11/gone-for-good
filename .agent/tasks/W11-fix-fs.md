# W11: fix held-out FS-5..FS-10
Read `.agent/tasks/heldout-fixes-common.md` first. Files: `fixtures/fs/fs5.py`..`fs10.py`,
`tests/test_fixtures_fs_heldout.py`. Specific findings to close:
- FS-5: third hop overstated — either make the log listing necessary or set hops honestly.
- FS-7: A is longer and alone has a cached diff / `new file mode`. Balance HEAD/index/worktree evidence
  (both variants show comparable diff sections for relevant and harmless files), equal length.
- FS-8: show the ledger contents (generated `cat`), so the substitution's effect is provable.
- FS-10: show the destination's contents (prove `stage/src` absent in B); remove the parent-link-count /
  `ls` padding tell (Debian diff was 40 lines). Keep directory counts constant across variants.
- Position balance: R2 currently changes in four pairs.
