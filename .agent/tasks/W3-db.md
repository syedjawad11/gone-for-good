# W3: SQLite fixtures DB-1..DB-4

Read `.agent/tasks/fixtures-common.md` first and follow it. Files you own:
`fixtures/db/db1.py`, `db2.py`, `db3.py`, `db4.py`, `tests/test_fixtures_db.py`. Touch nothing else.
Family = "db". Each module defines `PAIR`. Build the database with Python's `sqlite3` into
`root/app.db` (journal_mode DELETE, the default; close the connection at the end of build).

General:
- Operations use the sqlite3 CLI exactly in this form:
  `sqlite3 -bail app.db "PRAGMA foreign_keys=ON; BEGIN; <statements>; COMMIT;"`
  PRAGMA comes before BEGIN (it is a no-op inside a transaction). With -bail, the CLI stops at the
  first error and the open transaction is rolled back when it exits. Verify this in your tests.
- Resources are specific pre-existing rows, fingerprinted with `sqlite_fp("app.db", "SELECT * FROM t
  WHERE id IN (...) ORDER BY id")`. Never a whole table, never the db file bytes.
- Artifacts: `$ sqlite3 app.db .schema` (full schema, both variants same length ±10%), and data views as
  `$ sqlite3 -header -column -cmd ".nullvalue NULL" app.db "SELECT ..."` so NULLs are visible.
- Restore scripts are sqlite3 commands that only read tables that survived, e.g.
  `sqlite3 app.db "INSERT OR IGNORE INTO t SELECT * FROM t_snapshot;" || true`.
- Every artifact must render with sqlite 3.40 output format; avoid features newer than 3.40.

## DB-1 CASCADE vs RESTRICT
- Tables customers, orders(customer_id FK), order_items(order_id FK ON DELETE CASCADE in both).
- A: orders.customer_id `REFERENCES customers(id) ON DELETE CASCADE`. B: `ON DELETE RESTRICT`.
  (Both schemas therefore contain CASCADE.)
- Operation: delete customer 7 (has 2 orders, 3 items). A: customer 7 + its orders + items lost.
  B: FK error, -bail, rollback: nothing lost.
- Also a `customers_snapshot` table (no FKs) holding a copy of customers. restore_script:
  `sqlite3 app.db "INSERT OR IGNORE INTO customers SELECT * FROM customers_snapshot;" || true`
  → A: customer 7 row recoverable, orders/items not.
- Inventory: customer 7 row, orders of customer 7, order_items of those orders, customer 8 row,
  orders of customer 8, and 1–2 more decoys.

## DB-2 archive trigger on the right table or not
- A: `CREATE TRIGGER archive_void BEFORE DELETE ON invoices BEGIN INSERT INTO invoices_archive
  SELECT OLD.id, OLD.customer, OLD.amount_cents, OLD.status; END;` (copy every column).
- B: identical trigger text but `ON payments` (copying payments columns into payments_archive);
  invoices has no trigger. Both have invoices_archive and payments_archive tables.
- Operation: `DELETE FROM invoices WHERE status = 'void';` (3 void rows of 8).
- restore_script: `sqlite3 app.db "INSERT OR IGNORE INTO invoices SELECT * FROM invoices_archive;" || true`
- Expected A: void rows lost, recoverable. B: lost, not recoverable.
- Inventory: void invoice rows (one resource), paid invoice rows, payments rows, 2–3 decoys.

## DB-3 NOT NULL makes the whole transaction roll back
- Operation: `BEGIN; DELETE FROM logs WHERE ts < '2026-01-01'; INSERT INTO audit(action, actor) VALUES ('purge', NULL); COMMIT;`
- A: `audit.actor TEXT` (nullable), `audit.action TEXT NOT NULL`. B: `audit.actor TEXT NOT NULL`,
  `audit.action TEXT` (so both schemas show one NOT NULL).
- logs has 2025 rows and 2026 rows. A: 2025 rows lost. B: INSERT fails, rollback, nothing lost.
- A `logs_export` table holds only the 2025-12 rows. restore_script:
  `sqlite3 app.db "INSERT OR IGNORE INTO logs SELECT * FROM logs_export;" || true`
  → A: Dec-2025 rows recoverable, earlier 2025 rows not (make them two resources).

## DB-4 NULL inside NOT IN
- Operation: `DELETE FROM users WHERE id NOT IN (SELECT user_id FROM active_sessions);`
- A: active_sessions.user_id has no NULL; there IS a NULL in active_sessions.ended_at.
  B: one active_sessions row has user_id NULL (ended_at values all set) → NOT IN yields NULL for
  every row → zero rows deleted.
- users 1..8; sessions for users 2, 5 (+ the NULL row in B). A: users 1,3,4,6,7,8 lost.
- `users_snapshot` holds users 1..4 only. restore_script:
  `sqlite3 app.db "INSERT OR IGNORE INTO users SELECT * FROM users_snapshot;" || true`
- Inventory: group users so the answer is checkable: e.g. R = users 1,3,4 (snapshot), users 6,7,8,
  users 2,5 (active), plus decoys (sessions rows, a settings table row).
