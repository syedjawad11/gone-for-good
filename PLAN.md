# Plan: Kaggle benchmark (not started)

Status: no idea chosen yet. Next session: pick the benchmark, then a Sol review of this plan.

## Candidate ideas (to decide with Jawad)

1. **Roman Urdu shop notes** (strongest itch): from Stock Diary we saw models read
   mixed Roman Urdu / Urdu script / English stock notes. Measure: extract
   product, qty, unit, in/out; refuse to guess when ambiguous ("chawal 10 aaye"
   with two rices). Gold answers are exact; scoring is deterministic. Novel
   language angle few benchmarks cover. Must be NEW items (not Stock Diary's 12
   spike sentences reused), and credit Stock Diary as the origin.
2. Instruction-following under unit/number traps (e.g. integers vs decimals,
   mixed units, dozen/carton conversions).
3. "Knows when not to guess": abstention on underspecified questions.

## Open questions

- Which models does the Kaggle notebook expose, and what are the quotas?
- Dataset size we can afford to run across ~4–6 models.
- Scoring: exact match per field + overall item accuracy + abstention rate?

## Decisions log

- 4 Oct: folder created; brief captured.
