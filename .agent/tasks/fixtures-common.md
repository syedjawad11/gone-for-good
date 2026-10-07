# Rules for every fixture worker (W2 fs, W3 db, W4 recovery)

Read `fixtures/base.py` in full first: it is the contract. Do not edit it. Read
`BENCHMARK_BRIEF.md` §5 for the idea. Use `.venv/bin/python`.

## What one fixture module looks like
`fixtures/<family>/<id>.py` defines `PAIR = Pair(...)` with 2 variants ("A", "B").
- `build(root)` creates everything with Python (`pathlib`, `os.symlink`, `os.link`, `sqlite3`) or
  `sh(root, ...)`. git repos: `sh(root, "git init -q -b main && git add -A && git commit -qm init")`
  (env is pinned by `sh`).
- `artifacts(root)` returns real command output from the built env, via `sh(root, cmd).stdout`.
  Allowed commands: `ls -la <dir>`, `ls -laR`, `cat <file>`, `git status --short`,
  `git ls-files`, `sqlite3 app.db .schema`, `sqlite3 -header -column app.db "SELECT ..."`,
  `stat -c '%n %F links=%h' <paths>` (GNU form; for links use `ls -la`, which shows `-> target`).
  NO inode numbers (`ls -i`), no sizes in blocks, no timestamps other than the fixed mtime the
  harness sets (`ls -la` dates are fine: they will all read Jan 1 2026).
  Prefer `ls -la` over `ls -l` so hard-link counts and symlink targets are visible.
- The artifact title is the command line shown, e.g. `$ ls -la uploads` or `$ cat config/cleanup.env`.
- Every variant returns the SAME titles in the SAME order. Bodies should be similar in length.
- `operation` and `restore_script` are bash, shown verbatim and executed verbatim. Keep each under
  ~6 lines. Restore scripts must never abort on a missing source: guard with `[ -f x ] && ... || true`.
- Inventory: 6–10 resources, IDs R1..Rn, identical across variants. Include decoys that survive in
  both variants. Labels say exactly what is fingerprinted ("contents of X", "symlink X",
  "contents of dir/", "orders rows 101-104"). Shuffle so the interesting resource is not always R1.
- `literal_targets`: IDs the operation names directly (glob targets count when the glob is literal,
  e.g. `rm -rf uploads/*` targets everything under uploads/).
- `hops`: number of artifacts that must be combined to get the answer right.
- `expected`: your hypothesis for each variant ({"A": {"lost": [...], "recoverable": [...]}, ...}).
  The harness checks it against execution. If your test shows a mismatch, fix the fixture or the
  hypothesis and SAY SO in your report; never fudge a fingerprint to make it match.

## Surface-tell rules (reviewers will attack these)
- The variant letter, the word "typo", "bug", "danger", "careful", comments that explain the trap,
  and names like `old_`, `broken_`, `tmp_bad` are forbidden.
- If the bad variant contains a distinctive token (symlink, NULL, .gitignore, trigger, .snapshots,
  CASCADE, AUTO_SYNC=1, empty file), the good variant must contain the same kind of token harmlessly
  (an unrelated symlink, a NULL in an irrelevant column, a .gitignore for a different path, a trigger
  on a different table, ...). Balance A and B: sometimes A is the "nothing lost" one, sometimes B.
- Synthetic, boring, realistic content: small CSVs, notes, configs. No real people or companies.

## Tests
Write `tests/test_fixtures_<family>.py`: for each pair and variant, build in `tmp_path`, apply fixed
mtimes is NOT needed, run operation and restore via `subprocess.run(["bash","--noprofile","--norc","-c", ...],
cwd=root, env=env_for(root))`, compute lost/recoverable from the inventory fingerprints exactly as
`fixtures/base.py` describes, and assert they equal `expected`. Also assert: same artifact titles
across variants; every fingerprint non-None before the operation; no forbidden words in any artifact.
You are on macOS (bash 3.2, BSD coreutils): if a GNU-only behaviour makes a test fail locally,
mark that single test `pytest.mark.skipif(sys.platform == "darwin", reason=...)` and explain it
in your report. Final gold is produced on Debian bookworm (bash 5.2, GNU coreutils 9.1, git 2.39,
sqlite 3.40); design for that.

## Report
Files created, pytest output, every place you deviated from the brief and why, and any pair where
you are not sure the expected outcome is right.
