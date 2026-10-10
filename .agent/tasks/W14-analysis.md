# W14: results analysis script (tables + plots)

## Goal
One script that turns the Kaggle main-run logs into the tables and charts used in the DEV post.
Deterministic, no network, no model calls.

## Files you write (only these)
- `analysis/analyze.py` (new; also create empty `analysis/__init__.py`)
- `tests/test_analyze.py` (new)
- Do NOT touch anything else: not `data/`, `scoring.py`, `harness/`, `tasks/`, `results/kaggle/`.
  The script writes its outputs to `results/analysis/` at run time; do not commit-stage anything.

## Inputs
1. `results/kaggle/logs/*.log`: one file per model run. Relevant lines start with `GFG_ITEM ` followed by
   one JSON object (one per item, 36 per complete run). Ignore every other line. Fields used:
   `item_id, pair_id, family (db|fs|recovery), hops (int), item_correct, format_ok, format_error
   ("" | "api_error" | "no_json" | "not_subset" | ...), api_error (only present on API failures),
   raw_response (absent on API failures), gold_permanent, pred_permanent, missed_permanent,
   lost_exact, rec_exact, missed_losses, phantom_losses, false_alarm, false_assurance`.
   If an item_id appears more than once in one file, keep the LAST occurrence.
2. `analysis/models.json` (YOU create it with exactly this content; the script reads it; a log whose stem
   is not listed gets display=stem, open_weight=null, note=""):
```json
{
  "gemini-3.7-flash":               {"display": "Gemini 3.7 Flash",        "vendor": "Google",    "open_weight": false},
  "gemini-3-flash-preview":         {"display": "Gemini 3 Flash",          "vendor": "Google",    "open_weight": false},
  "gemini-3.1-flash-lite-preview":  {"display": "Gemini 3.1 Flash-Lite",   "vendor": "Google",    "open_weight": false},
  "claude-sonnet-5-default":        {"display": "Claude Sonnet 5",         "vendor": "Anthropic", "open_weight": false},
  "gpt-5.4-2026-03-05":             {"display": "GPT-5.4",                 "vendor": "OpenAI",    "open_weight": false, "note": "default settings; 39 s for 36 items suggests no extended reasoning"},
  "gpt-5.4-nano-2026-03-17":        {"display": "GPT-5.4 nano",            "vendor": "OpenAI",    "open_weight": false},
  "glm-5":                          {"display": "GLM-5",                   "vendor": "Zhipu",     "open_weight": true},
  "gemma-4-31b-it":                 {"display": "Gemma 4 31B",             "vendor": "Google",    "open_weight": true},
  "deepseek-r1-0528":               {"display": "DeepSeek R1",             "vendor": "DeepSeek",  "open_weight": true},
  "qwen3-next-80b-a3b-thinking":    {"display": "Qwen3-Next 80B Thinking", "vendor": "Alibaba",   "open_weight": true}
}
```
3. `data/heldout/gold.jsonl`: one JSON per item with `item_id, pair_id, family, hops, changed_fact,
   lost, recoverable, permanent_loss, inventory_labels` (dict R-id -> human label).

## CLI
`python -m analysis.analyze [--logs results/kaggle/logs] [--gold data/heldout/gold.jsonl] [--out results/analysis] [--models analysis/models.json]`
Defaults as shown. Must run with the project `.venv` (pandas, numpy, matplotlib 3.11 available; use
`matplotlib.use("Agg")`). Python 3.9+ syntax.

## Definitions (implement exactly)
- Item outcome class, first match wins:
  1. `infra`: `api_error` key present, OR `raw_response` is "" (empty reply from the provider).
  2. `format`: `format_ok` is false.
  3. `correct`: `item_correct` true.
  4. `wrong`: everything else (a well-formed answer that is wrong = a reasoning error).
- For `wrong` items, also tag (non-exclusive) error types:
  `false_assurance` = gold_permanent true and pred_permanent false (said "safe", data actually gone);
  `false_alarm_perm` = gold_permanent false and pred_permanent true;
  `lost_wrong` = lost_exact false; `rec_wrong` = rec_exact false.
- Pair correct = both items of the pair correct. Pair accuracy = correct pairs / 18 (raw).
- "Clean" metrics: same, but excluding items of class `infra` (clean item acc) and pairs containing any
  `infra` item (clean pair acc). Report n alongside.
- A run is "complete" if it has 36 items.

## Outputs (in --out, create dir)
1. `leaderboard.md`: markdown table sorted by raw pair acc desc, then item acc desc. Columns:
   Model | Open weight (yes/no/?) | Pair acc | Item acc | Infra fails | Format fails | Reasoning errors |
   False assurance (items) | Clean pair acc (n pairs) | Note. Accuracies as 0.00 with two decimals.
   Below the table: one line with the 0-guess baselines? NO: skip baselines. Just the table.
2. `by_family.md` and `by_hops.md`: rows = models (same order), columns = pair acc per family
   (db, fs, recovery) / per hops (2, 3, 4), with n pairs in the header, e.g. `db (6 pairs)`.
3. `items_matrix.md`: rows = item_id (sorted by family, then pair, then A/B), columns = models (short
   display names), cells `✓` correct, `✗` wrong, `F` format, `—` infra. Last column: number of models
   correct. Then a section "Hardest items" listing items with ≤ 3 models correct, each with its
   `changed_fact` from gold.
4. `error_types.md`: per model, counts of wrong items with each tag; plus a totals row. Plus one
   sentence-free table of "false assurance" items: item_id | models that said safe | gold lost ids with labels.
5. `failures.jsonl`: one line per (model, wrong-or-format item): model, item_id, class, tags, gold lost,
   gold recoverable, gold permanent_loss, raw_response (truncated to 2000 chars).
6. `summary.json`: per model the metrics above, machine-readable.
7. Plots (PNG, 150 dpi, white background, readable at 700 px wide, no seaborn, no titles with emoji):
   - `leaderboard.png`: horizontal bars of raw pair accuracy per model, sorted, open-weight bars
     hatched or distinctly coloured with a legend; item acc as a dot marker on the same axis; x from 0 to 1.
   - `by_family.png`: grouped horizontal or vertical bars, pair acc per family per model.
   - `items_heatmap.png`: models (rows, leaderboard order) x items (columns, family-grouped) grid,
     green correct / red wrong / grey infra / amber format; family separators and labels.
   Use the colorblind-friendly palette: correct #1b9e77, wrong #d95f02, infra #bdbdbd, format #e6ab02,
   closed-weight bars #4c78a8, open-weight bars #f58518.

## Tests (`tests/test_analyze.py`, pytest)
Build small synthetic log files in tmp_path (2 models, 2 pairs = 4 items, plus a minimal gold.jsonl) and
check: outcome classification order (infra beats format beats correct), duplicate item_id keeps last,
raw vs clean pair acc, false_assurance tagging, leaderboard sort order, that all output files are created.
Existing suite must still pass: `.venv/bin/python -m pytest -q`.

## Done when
- `.venv/bin/python -m analysis.analyze` runs on the real logs without error and writes all files.
- `.venv/bin/python -m pytest -q` passes.
- Reply with: files written, the leaderboard.md content, and anything in the data that surprised you.
