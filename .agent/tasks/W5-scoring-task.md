# W5: scorer, baselines, and the Kaggle task builder

Read `BENCHMARK_BRIEF.md` §7–§10, `.claude/skills/write-kaggle-benchmarks/SKILL.md`, and
`.agent/tasks/W1-harness.md` (it defines `data/gold.jsonl` and `data/items.jsonl`; another worker
is building that harness right now, so the files do not exist yet). Use `.venv/bin/python`.
The installed `kaggle_benchmarks` 0.6.1 source in `.venv/lib/python3.12/site-packages/` is the
API truth: read it rather than guessing (no network).

## Files you own
`scoring.py`, `tasks/build_task.py`, `tests/test_scoring.py`, `tests/test_task_build.py`,
`tests/data/mini_gold.jsonl`, `tests/data/mini_items.jsonl`. Touch nothing else.

## Input shapes
gold row: item_id, pair_id, variant, family, hops, changed_fact, literal_targets, inventory_labels
({id: label}), lost, recoverable, permanent_loss, ... (extra keys ignored).
items row: item_id, pair_id, variant, family, hops, inventory_ids, prompt.
Model answer: free text that should contain one JSON object
`{"lost": [...], "recoverable": [...], "permanent_loss": bool}`.

## scoring.py (pure Python 3.9+, stdlib only; it gets inlined into the Kaggle task)
- `parse_answer(text, inventory_ids) -> ParseResult` (dataclass: ok, error, lost, recoverable,
  permanent_loss). Accept a bare object or one inside ```json fences or with prose around it (take the
  LAST balanced top-level `{...}` that parses). Errors (exact strings): "no_json", "bad_json",
  "missing_key", "bad_type", "unknown_id", "duplicate_id", "not_subset" (recoverable ⊄ lost).
  Order and case of IDs: normalise to upper-case strings; order is irrelevant.
- `score_item(text, gold) -> dict`: item_id, pair_id, family, hops, format_ok, format_error,
  lost_exact, rec_exact, item_correct (= format_ok and lost_exact and rec_exact), missed_losses,
  phantom_losses, false_assurance (ids predicted recoverable whose gold is lost-and-not-recoverable),
  false_alarm (gold-recoverable ids not predicted recoverable), gold_permanent, pred_permanent
  (derived from the predicted sets, NOT the model's flag), perm_flag_consistent (model flag ==
  derived), missed_permanent (gold_permanent and not pred_permanent).
  A format failure scores as incorrect on everything (all exact flags False, missed_permanent =
  gold_permanent).
- `aggregate(rows) -> dict`: n_items, n_pairs, item_acc, pair_acc (a pair is correct iff every
  variant of it is item_correct), lost_acc, rec_acc, format_failure_rate, perm_flag_inconsistency_rate,
  false_assurance = {"items_with_any": k, "of": n_items}, missed_permanent = {"k": .., "of": n gold
  permanent items}, coupling_miss = pairs where ≥1 variant correct and ≥1 wrong, by_family and
  by_hops (each with item_acc, pair_acc where defined, n).
- `bootstrap(rows_by_model, n_boot=2000, seed=0) -> dict`: resample PAIR ids with replacement (same
  draw for every model in an iteration) → 95% percentile CI of pair_acc and item_acc per model, and of
  pairwise pair_acc differences.
- Baselines (frozen now, before any model run; never tune them later):
  `baseline_text(name, gold, item) -> str` returning a JSON answer string:
  - "everything_lost": lost = all inventory ids, recoverable = [].
  - "nothing_lost": lost = [], recoverable = [].
  - "naive_reader": lost = literal_targets; recoverable = lost if the word "backup" (case-insensitive)
    appears anywhere in item["prompt"], else [].
- CLI: `python scoring.py --gold data/gold.jsonl --items data/items.jsonl [--answers results/answers.jsonl]`
  answers.jsonl rows: {model, item_id, response}. Prints a table per model + the three baselines
  (item_acc, pair_acc, lost_acc, rec_acc, format failures, missed_permanent k/of) and writes
  `results/scores.json`. Missing answers for an item count as format failure "missing".

## tasks/build_task.py
`python tasks/build_task.py [--gold data/gold.jsonl] [--items data/items.jsonl] [--out tasks/gone_for_good.py]
[--name gone-for-good]` generates ONE self-contained Kaggle task file (jupytext `# %%` cells):
1. the source of `scoring.py` inlined (minus its CLI `if __name__ == "__main__"` block);
2. items + gold embedded as a JSON string literal (only the fields scoring needs + prompt);
3. a per-item task `@kbench.task(name="gfg-item", store_task=False)` (check the real decorator
   signature in the installed package) that calls `llm.prompt(prompt)` at temperature 0 with an
   output-token cap of 1024 if the installed API supports one (find out; if not, say so), parses with
   `parse_answer`, records the raw response, and returns the `score_item` dict;
4. the main task `@kbench.task(name="Gone for Good?")`-style (slug must normalise to `gone-for-good`)
   `def gone_for_good(llm) -> float:` runs every item (sequentially is fine; use kbench's
   evaluate/dataset helper if it exists and is simple), prints one JSON line per item
   (`GFG_ITEM {...}` incl. raw response) so results can be recovered from logs, prints the aggregate,
   asserts nothing that would abort mid-run, and RETURNS pair_acc as the leaderboard score;
5. ends with `gone_for_good.run(kbench.llm)` (no .run() = silent no-op on Kaggle).
The generated file must not import anything outside stdlib + kaggle_benchmarks.

## Tests (pytest, offline)
- Write a small hand-made `tests/data/mini_gold.jsonl` / `mini_items.jsonl` (3 pairs × 2 variants,
  6 inventory ids each, include a nothing-lost item and a permanent-loss item).
- parse_answer: fences, prose, trailing text, lower-case ids, every error code.
- score_item/aggregate: perfect answers → 1.0 everywhere; one wrong variant → pair_acc drops by 1/3,
  coupling_miss 1; format failure counts in the denominator; baselines produce the hand-computed values.
- bootstrap is deterministic with a seed and uses the same pair draw across models.
- build_task: generate from the mini data into tmp_path; the file compiles (`py_compile`); with a fake
  `kaggle_benchmarks` module injected into `sys.modules` (decorator passthrough, `.run()` calling the
  function with a stub llm whose `.prompt` returns the gold answer), executing it yields 1.0; with a stub
  returning garbage it yields 0.0. If the real package can be imported offline and has a usable mock LLM,
  also test against that and report what you found.

## Done =
`.venv/bin/python -m pytest tests/test_scoring.py tests/test_task_build.py -q` passes. Report files,
test output, the real kbench API facts you found (decorator args, llm.prompt kwargs, token cap,
evaluate helper), and assumptions.
