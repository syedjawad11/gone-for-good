# W6: code fixes from the 7 Oct code review

Read `.agent/reviews/20261007-132243-gpt-6.1-sol.md` (the review) and `PLAN.md`. Use `.venv/bin/python`.
Files you own: `fixtures/base.py` (only `tree_fp` and `sh`), `scoring.py`, `tasks/build_task.py`,
`tests/test_scoring.py`, `tests/test_task_build.py`, new `tests/test_base.py`.
Do NOT touch fixtures/fs|db|recovery, harness/, data/ (another worker owns those).

## Fixes
1. **Per-item failure handling in the generated task** (review P1 #1, #3). In `gfg_item`, wrap the
   model call: on exception, retry once after 5 s; if it fails again, return a row with
   `format_ok=False, format_error="api_error"`, `api_error=<exception class + first 200 chars>`,
   and every correctness flag False. Never let one item abort the loop. `gone_for_good` must print
   `GFG_ITEM` per item and the aggregate, and add `n_api_errors` to the aggregate. If
   n_api_errors > 20% of items, still return pair_acc but print `GFG_WARNING incomplete run`.
   (We report such models as unscored in the post; that decision is ours, not the task's.)
   Per-item time budget: pass `timeout` through extra_api_params ONLY if the installed SDK's OpenAI /
   GoogleGenAI adapters accept it (read `.venv/lib/python3.12/site-packages/kaggle_benchmarks/actors/llms.py`);
   otherwise document in your report that the SDK transport timeout is what bounds a call.
2. **Token cap dispatch** (#6): use `isinstance(llm, kaggle_benchmarks.actors.llms.GoogleGenAI)` →
   `max_output_tokens`, `isinstance(..., OpenAI)` → `max_tokens`, else no cap. Raise the cap to 4096
   (thinking models spend output tokens before answering). Make the cap a build flag `--max-tokens`.
   If the provider rejects the cap param (exception mentioning max_tokens / max_output_tokens /
   unsupported parameter), the retry in fix 1 must drop the cap rather than repeat it.
3. **tree_fp** (#2): hash sorted, typed, length-prefixed entries: for every path under the dir
   (dirs incl. empty ones, files, symlinks — do not follow symlinked dirs) feed
   `type|len(relpath)|relpath|len(payload)|payload` where payload = file bytes, link target text, or
   empty for dirs. Return None if the dir is missing or is a symlink; an empty dir returns a hash (not
   None) — but keep `None` for missing. Regression tests in `tests/test_base.py` for the review's
   collision example, empty subdir, and symlink-in-dirnames.
4. **sh() timeout** (#3): `timeout=60` in `fixtures/base.py: sh`.
5. **Pair completeness** (#4): `aggregate` and `bootstrap` raise ValueError on duplicate item_ids;
   `aggregate(rows, expected_items=None)` — when given the full gold item list, any pair whose variants
   are not all present is counted as incorrect (missing items count as format_error "missing").
   The generated task passes the full RECORDS list. `build_task` rejects gold with duplicate ids or a
   pair with < 2 variants.
6. **Bootstrap in CLI** (#7): `scoring.py` CLI calls `bootstrap` once over all answer models
   (not baselines) and writes CIs + paired differences into `results/scores.json`; print pair_acc CI.

## Done =
`.venv/bin/python -m pytest -q` passes (whole suite; other worker's tests may be mid-edit — if a
failure is clearly in their files, say so). Add tests: stub LLM that raises on item 3 → remaining
items still run and the aggregate shows 1 api_error; stub that raises only when a cap param is passed
→ second attempt succeeds without cap. Report the SDK facts you confirmed.
