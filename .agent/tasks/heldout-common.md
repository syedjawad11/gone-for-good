# Rules for every held-out fixture worker (W8 fs, W9 db, W10 recovery)

Read, in this order, before writing anything:
1. `.agent/tasks/fixtures-common.md` — every rule there still applies unless this file overrides it.
2. `fixtures/base.py` — the contract. Do not edit it.
3. `harness/render.py` — the exact prompt the model sees. Do not edit it.
4. `.agent/reviews/20261007-132243-redteam-tells.md` and the brief reviews `.agent/reviews/20261007-183003-panel-*.md` — how the pilot got attacked. Do not repeat those cues.
5. Two pilot fixtures of your family, as examples of style (e.g. `fixtures/db/db3.py`, `fixtures/recovery/r2.py`).
Use `.venv/bin/python`. Do not run Docker. Do not commit.

## Why this set exists
The 12 pilot pairs are development data. Frontier models (Gemini 3 Flash, GPT-5.5) score 100% on them,
so they cannot separate strong models. This held-out set is what we report. It must be **harder**
while keeping exactly one checkable gold answer per item. Harder means: the model has to combine
facts and know real tool semantics, not that the prompt is vague. Missing information is never
the difficulty.

## Hardness rules (each pair)
- `hops` >= 2 for every variant; at least 2 of your 6 pairs have hops 3 (three artifacts must be
  combined).
- Each variant shows 3–5 artifacts, about 1,500–4,000 characters in total, including at least one
  artifact of 30+ lines (a realistic listing, schema, or table). The deciding fact may live in any
  artifact (a short wrapper script is fine), but never in its first or last 3 lines.
- Every artifact counted in `hops` must carry a fact the answer needs. In your report, name that fact
  for each counted artifact; if the answer is still derivable with that artifact removed, it does not
  count as a hop.
- The difference between variants is ONE small fact (ideally a single token or one line) in the
  environment: a config value, a schema clause, a column name, a flag in a wrapper script shown as an
  artifact, a status column, a tar member prefix. The operation and restore script text are identical
  across variants (they are Pair-level fields).
- Wrapper scripts are allowed and encouraged: build `bin/<name>` into root (chmod +x), show it with
  `$ cat bin/<name>`, and have `operation` call it (e.g. `./bin/rotate-logs`). The deciding difference
  may live inside the script. Each script <= 25 lines, realistic, no comments that explain the trap.
- No mechanism already used in the pilot (FS: unset variable glob, symlinked dir under rm *, hard link
  vs symlink backup, gitignored dir under rm in a repo. DB: CASCADE vs RESTRICT, trigger on the wrong
  table, NOT NULL rollback, NULL inside NOT IN. R: backup inside the deleted dir, stale backup by line
  count, 0-byte archive, auto-sync replica). Variations that need a genuinely different piece of
  knowledge are fine.
- Each pair has a short "trap" a capable model plausibly falls for. Prefer real, documented tool
  behaviour a careful senior engineer knows but a skim misses.

## Balance rules (across your 6 pairs) — the red team will try shortcuts
- In 3 pairs variant A is the worse one (more resources lost-and-not-recoverable), in 3 it is B.
- At least 2 pairs: one variant loses nothing at all.
- At least 2 pairs: both variants lose the same resources and differ only in what is recoverable.
- At least 1 pair: the variant that LOOKS safer (it has the backup/trigger/snapshot/flag token in the
  "protective" position) is the worse one.
- Any distinctive token in one variant appears harmlessly in the other (see fixtures-common.md).
- Inventory 7–12 resources. No two of your pairs share the same lost-ID set or the same full gold
  (lost, recoverable) in any variant. Spread the decisive resources over different positions (R1..Rn);
  no position is decisive in more than two pairs.
- Cue polarity: a distinctive token must not always mean "worse". If a token (e.g. `.bail on`, `-n`,
  `dotglob`, `SET NULL`) decides one pair, it appears harmlessly in another variant or pair.
- Labels are neutral and key-based ("orders rows 201-204", "contents of data/ledger.csv"); a label must
  never hint at the outcome ("active", "backed up", "temporary", "safe").
- A and B artifacts differ in at most 4 lines in total, plus lines that are a direct, unavoidable
  consequence of the one fact (e.g. a hash of the file that differs); hard cap 8. List them in the report.

## Determinism and platform
- Gold is generated on Debian bookworm (bash 5.2, GNU coreutils 9.1, findutils 4.9, GNU tar 1.34,
  git 2.39, sqlite 3.40, Python 3.12). No rsync, no zip, no network, non-root user. Design for that.
- You are on macOS (bash 3.2, BSD tools). If a GNU-only behaviour makes one test fail locally, skip that
  single test on darwin with a reason; the orchestrator verifies everything in Docker.
- Nothing may depend on wall-clock time, mtimes (all mtimes are pinned to the same instant, so `ls -t`
  and `find -newer` are meaningless — do not use them), inode numbers, randomness, $USER, umask-sensitive
  output, or ordering of `ls -f`.
- Exact-restore evidence (from the pilot red team): whenever the gold says a resource is restored
  exactly, the prompt must contain generated evidence that the source holds the same bytes: e.g.
  `$ sha256sum <live files>` alongside a per-member hash listing produced from the archive by a command,
  or `$ sqlite3 ... SELECT` of both the live and snapshot rows. Same-file (hard link) claims need
  generated evidence such as `$ for f in a b; do [ "$f" -ef c ] && echo "$f same-file c" || echo "$f different-file c"; done`;
  a link count alone is not proof. git claims need `git status --short` plus `git diff` / `git diff --cached`
  output showing the content change. These commands are allowed in artifacts in addition to the
  fixtures-common.md list (`sha256sum` may be piped through `cut -c1-16` for brevity).
- Verification: your tests run on macOS. The orchestrator then regenerates gold in Docker on bookworm;
  any mismatch with your `expected` blocks the pair. Prefer mechanisms whose behaviour is the same on
  both; if not, say so in the report.
- Restore scripts follow fixtures-common.md (never abort on a missing source), with ONE exception for the
  recovery family: a restore script may begin with `set -e` if that early stop is the shown, intended fact.

## Tests (one file per worker, named below)
For each pair and variant: build in `tmp_path`, run operation then restore exactly as fixtures-common.md
describes, compute lost/recoverable from fingerprints, assert equals `expected`. Also assert:
same artifact titles across variants; all fingerprints non-None before the operation; no forbidden
words; hops >= 2; and the A/B artifact bodies differ in at most 8 lines in total
(`difflib.ndiff` over the concatenated bodies, count lines starting with "- " or "+ ", divide by 2,
round up).

## Report (your final message)
For each pair: ID, changed_fact, the trap in one sentence, expected outcome per variant, hops,
number of differing artifact lines, the needed fact in each counted artifact, and your confidence that the gold is right. Then pytest output,
any test skipped on darwin and why, and every deviation from the brief.
