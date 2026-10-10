# W16: post charts + cover image

## Goal
Publication-quality charts for the DEV post, one per finding, each with a title that STATES the finding,
plus a cover image. Deterministic, no network, no model calls. Style reference: clean, light, modern
(think a well-designed blog chart, not default matplotlib): no top/right spines, light grey gridlines on the
value axis only, generous padding, direct value labels on bars, a small grey footnote line under the plot.

## Files you write (only these)
- `analysis/charts.py` (new)
- `tests/test_charts.py` (new)
- Do NOT touch anything else (not `analysis/analyze.py`, `models.json`, `data/`, `scoring.py`, `results/kaggle/`,
  `post.md`, `README.md`). Outputs go to `results/charts/` at run time.

## Inputs
- `results/analysis/summary.json` (dict keyed by log stem; fields: display, open_weight, pair_accuracy,
  item_accuracy, correct_pairs, n_pairs, error_tags.false_assurance, same_answer_pairs, same_answer_of,
  by_family.{db,fs,recovery}.{accuracy,correct_pairs,n_pairs}).
- Per-item outcomes for the heatmap: reuse functions from `analysis/analyze.py` (`read_log`, `outcome`,
  `item_sort_key`, etc.) on `results/kaggle/logs/*.log` and `data/heldout/gold.jsonl`. Read analyze.py first.
- EXCLUDE the stem `qwen3-next-80b-a3b-thinking` (run 1) from every chart. Show run 2's display name as
  `Qwen3-Next 80B Thinking` (strip " (run 2)") and mark it with a trailing `‡` in labels.
  GPT-5.4 (`gpt-5.4-2026-03-05`) label gets a trailing `†`.
- Model order everywhere: pair accuracy desc, then item accuracy desc (same as leaderboard.md).

## CLI
`python -m analysis.charts [--summary results/analysis/summary.json] [--logs results/kaggle/logs]
[--gold data/heldout/gold.jsonl] [--out results/charts]`. Python 3.9+, `matplotlib.use("Agg")`, project
`.venv` (matplotlib 3.11, numpy, pandas). Font: DejaVu Sans (matplotlib's bundled font; bold weight for titles),
DejaVu Sans Mono for code text. PNG at dpi 200, figure width 8 in (1600 px), white background.

## Palette
text #1f2430, muted text #6b7280, grid #e5e7eb, closed-weight #4c78a8, open-weight #f58518,
bad/red #d64545, correct #1b9e77, wrong #d95f02, infra #bdbdbd, format #e6ab02, accent blue #1f6feb.

## Charts (exact titles; subtitle = one muted line under the title; footnote = small muted line at bottom)
1. `01_leaderboard.png`
   Title: "From 18 of 18 pairs to 1 of 18"
   Subtitle: "Pair accuracy: both variants of a matched pair exactly right"
   Horizontal bars = pair accuracy in % (x axis 0–100, ticks every 20, "%" labels). Bar colour closed/open
   (legend: "Closed weight", "Open weight"). Item accuracy as a small dark dot on the same row (legend "Item accuracy").
   Right of each bar, a label like `100%  18/18` (pair % and correct_pairs/n_pairs).
   Footnote: "18 matched pairs (36 items), one response per item, temperature 0. Scored in Python, no LLM judge.
   † default reasoning config  ‡ run 2, 4 empty replies counted wrong"
2. `02_false_assurance.png`
   Title: "25 answers said nothing was permanently lost. Data was."
   (compute the 25 as the sum of error_tags.false_assurance over included models; put the computed number in
   the title, and assert it equals 25 in the test against the real summary.json)
   Subtitle: "Answers claiming no permanent loss on the 22 items where the restore script leaves data unrestored"
   Horizontal bars, count per model, colour #d64545; zero rows show a muted "0" label and no bar.
   Labels `11` at bar end. Footnote: "Bottom three models: 22 of 25. Empty or unparseable replies not counted."
   (compute the bottom-three sum = last three models in order; put it in the footnote, don't hard-code)
3. `03_same_answer.png`
   Title: "Same answer to both variants, wrong on at least one"
   Subtitle: "Pairs where a model gave identical answers to A and B. Gold answers always differ."
   Horizontal bars of same_answer_pairs / same_answer_of as %, label `9 of 18`. Colour #d95f02.
   Footnote: "Denominator: pairs where both replies parsed (Qwen: 15)." — compute Qwen's denominator from data.
4. `04_by_family.png`
   Title: "SQLite pairs were the hardest"
   Three small-multiple panels side by side (shared y = models in leaderboard order, y labels only on the
   first panel): "Recovery", "Filesystem", "SQLite". Panel subtitle "median 92%" etc., computed as the median of
   per-model family accuracy over included models. Bars in % (0–100), label `5/6` at bar end. Colours by
   closed/open as in chart 1. Footnote: "6 pairs per family. Recovery: hard links, archives, git stash, cp -n.
   Filesystem: find precedence, globs, the git index. SQLite: type affinity, name resolution, REPLACE and foreign keys, transactions, triggers."
5. `05_items_heatmap.png`
   Title: "Every model on every item"
   Grid models (rows, leaderboard order) × 36 items (columns grouped Recovery | Filesystem | SQLite with
   visible separators and group labels above). Cell colours: correct #1b9e77, wrong #d95f02, infra/empty #bdbdbd,
   format #e6ab02. Item ids as small rotated x labels. Legend below: Correct, Wrong, Empty reply, Unparseable.
   Figure width 10 in for this one.
6. `cover.png` — EXACTLY 2000×840 px (DEV cover 1000×420 at 2×). Light background #fafbfc with a faint dot grid
   (#d9dee5 dots, ~40 px spacing). Left half: line 1 big bold accent-blue "18 of 18" then dark " to 1 of 18" on the
   same baseline (or 2 lines if it won't fit); line 2–3 bold dark: "Can AI tell which deleted data" /
   "comes back?"; a muted line: "A Kaggle benchmark of 10 models · Gone for Good?". Right half: a terminal-window
   card (white, rounded corners, soft shadow imitation via a slightly offset light-grey rounded rect, three dots
   red/yellow/green in a title bar) containing monospace lines:
       $ sha256sum live/ledger.seg snap/ledger.seg
       f90d93cc…d920  live/ledger.seg
       f90d93cc…d920  snap/ledger.seg
       $ test -ef live/ledger.seg snap/ledger.seg && echo same-file
       same-file
   with the last line highlighted (pale red background #fde8e8, red text) and a small red round badge with "!"
   near it, plus a caption under the card in muted text: "Matching checksums. Same file. One truncate, both gone."
   All text must fit inside the canvas with ≥ 60 px margins; verify by rendering and checking text bounding boxes
   (renderer.get_window_extent) — fail loudly if anything overflows.

## Tests (`tests/test_charts.py`)
- Run `main([...])` (make main accept argv) on the real repo inputs into tmp_path; assert all 6 files exist, are
  PNG, cover is exactly 2000×840 (read via matplotlib.image or PIL if available — PIL ships with matplotlib).
- Assert the computed false-assurance total is 25 and bottom-three sum is 22 for the real data, and that run 1
  is excluded.
- Existing suite must still pass: `.venv/bin/python -m pytest -q`.

## Done when
`.venv/bin/python -m analysis.charts` writes the 6 files, pytest passes. Reply with the files written, the
computed numbers in titles/footnotes, and any label that you had to shorten.
