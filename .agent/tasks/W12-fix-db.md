# W12: fix held-out DB-5..DB-10
Read `.agent/tasks/heldout-fixes-common.md` first. Files: `fixtures/db/db5.py`..`db10.py`,
`tests/test_fixtures_db_heldout.py`. Specific findings to close:
- All six: `-header -column` hides storage classes (TEXT vs BLOB vs INTEGER), so exact-restore and comparison
  claims are not provable. Render data views type-preserving: `sqlite3 -header -cmd ".mode quote" app.db "SELECT ..."`
  (quote mode shows 'text', integers bare, X'..' blobs, NULL). Keep `.schema`.
- DB-6: add `typeof(day)` to the relevant view; storage class is the mechanism.
- DB-7: make the email collision unambiguous under quote mode.
- DB-9: fix the bash/shebang wording the auditor flagged; neutralise bare `BEGIN` presence as a tell
  (e.g. both variants' wrappers contain a BEGIN-like line, only its scope differs).
- Hops per variant (DB-6A, DB-7B, DB-9B, DB-10B were overstated).
- DB-10 shares DB-8's "INSERT OR IGNORE skips existing changed rows" recovery trap; change DB-10's restore or
  scenario so its recovery hinges on something else (e.g. restore uses INSERT OR REPLACE, or the snapshot
  lacks a column), keeping the INSTEAD OF trigger mechanism.
- Position balance: R5 and R7 change in four pairs, R3 and R6 in three.
