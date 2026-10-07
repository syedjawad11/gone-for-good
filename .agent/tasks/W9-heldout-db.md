# W9: held-out SQLite fixtures DB-5..DB-10

Read `.agent/tasks/heldout-common.md` first and follow it, plus the general rules of
`.agent/tasks/W3-db.md` (sqlite3 CLI forms, sqlite_fp on pre-existing rows, `.nullvalue NULL` views,
schema artifact). Files you own: `fixtures/db/db5.py` .. `fixtures/db/db10.py`,
`tests/test_fixtures_db_heldout.py`. Touch nothing else. Family = "db". Pair IDs "DB-5" .. "DB-10". Six pairs.

Allowed operation forms (W3 required the first; here the others are allowed too):
- `sqlite3 -bail app.db "PRAGMA foreign_keys=ON; BEGIN; ...; COMMIT;"`
- a wrapper `./bin/<name>` shown as an artifact, which may run `sqlite3 app.db < sql/<file>.sql` with the
  SQL file also shown as an artifact (sqlite3 reading a script from stdin continues after errors unless
  `.bail on` is set — verify on 3.40 semantics; your local sqlite may differ).
Foreign keys are per connection: every sqlite3 invocation whose behaviour depends on FKs (operation,
wrapper, restore) states `PRAGMA foreign_keys=ON;` (or OFF) explicitly.
Restore scripts: sqlite3 commands reading only surviving tables, `|| true` at the end.

## Mechanism menu (pick at least 5; you may substitute others that meet the rules, say why)
Verify every claimed behaviour by execution and note anything sqlite-version-sensitive.
1. Subquery name resolution: `DELETE FROM items WHERE id IN (SELECT id FROM purge_queue)`. If
   purge_queue has no `id` column (it is `item_id`), `id` binds to the outer `items.id` and every row
   goes — provided purge_queue is non-empty and items.id is never NULL (show the queue rows). Deciding fact: one column name in a long schema.
2. Type affinity: `DELETE FROM events WHERE day < 20250101` behaves differently when `day` is declared
   TEXT vs DATE/NUMERIC with ISO strings stored ('2025-03-01'): text vs integer comparison rules.
3. `INSERT OR REPLACE` deletes any OTHER row that collides on a second UNIQUE column (and FK actions on
   that delete may follow). Deciding fact: a UNIQUE on email vs on another column.
4. ON DELETE SET NULL vs ON DELETE CASCADE with a restore of `INSERT OR IGNORE ... FROM snapshot`:
   CASCADE-deleted children are restored exactly; SET NULL children still exist with a changed column,
   so INSERT OR IGNORE skips them and they stay changed. The gentler-looking clause is worse.
5. Statements without BEGIN are autocommitted one by one: with `-bail` a later failure does not undo
   earlier statements; inside BEGIN..COMMIT it does. Deciding fact in a wrapper or SQL file.
6. `.bail on` present or not in a SQL script fed on stdin: without it, a statement that fails with a
   default-ABORT constraint error (NOT NULL / CHECK / UNIQUE with no ON CONFLICT clause, no OR ROLLBACK /
   OR FAIL) is undone alone and COMMIT still commits the rest. Use only that kind of failure.
7. `LIKE` is case-insensitive for ASCII and `_` matches any single character; `GLOB` is case-sensitive.
   Deciding fact: one row's name in a 30+ row table, or LIKE vs GLOB in the SQL file.
8. A view with an INSTEAD OF DELETE trigger that soft-deletes (UPDATE flag) vs one that deletes from the
   base table; operation deletes from the view.
9. Triggers with a WHEN clause or AFTER UPDATE trigger that deletes dependants.
10. Three-valued logic: `DELETE FROM t WHERE NOT (archived = 0)` leaves NULL rows; `WHERE archived != 0`
   vs `IS NOT 0`.
Mix hops 2 and 3. At least 2 pairs with a 30+ line schema where the deciding clause is mid-schema.
