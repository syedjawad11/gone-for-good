# W15: "same answer to both variants" metric in analysis/analyze.py

Files you may edit: analysis/analyze.py, tests/test_analyze.py. Nothing else.

Every gold pair has different answers for its A and B items (by design: one changed fact changes the
outcome). So a model that gives the SAME parsed answer to both items of a pair is guaranteed to get one
wrong: it read the command, not the environment. Add this metric.

- Parse a model answer from `raw_response`: take the LAST substring matching a flat JSON object that
  contains the key "lost" (regex `\{[^{}]*"lost"[^{}]*\}`), json.loads it; the canonical answer is
  (sorted lost, sorted recoverable, permanent_loss). Unparseable / missing / infra -> None.
- Per model: `same_answer_pairs` = number of pairs where both A and B parse and are equal;
  `same_answer_of` = number of pairs where both parse.
- Add both to summary.json per model, add a column "Same answer A=B (pairs)" to leaderboard.md formatted
  `k/n` (insert it right after "False assurance (items)").
- Tests: extend tests/test_analyze.py with a case where one model answers both variants identically
  (count 1) and one where a code-fenced answer ```json {...}``` parses. Keep existing tests passing.
Done when `.venv/bin/python -m analysis.analyze` runs and `.venv/bin/python -m pytest -q tests/test_analyze.py` passes.
Expected on the real logs: GPT-5.4 9/18, Gemini 3.1 Flash-Lite 9/18, GPT-5.4 nano 6/18, Gemini 3.7 Flash 0/18.
