# Kaggle Benchmarking Challenge: instructions for Claude Code

Workspace rules in `../../CLAUDE.md` apply. This file adds what is specific here.

## Start of every session

Read `status.md`, then `BRIEF.md`, then `PLAN.md`. Update `status.md` at every
milestone and before every break.

## Other work running alongside

The HF26 weekend challenge (Stock Diary) is submitted. The next Hacktoberfest weekly
challenge has not launched yet; it gets its own folder when it does. Check the
workspace CLAUDE.md "Challenges" section for what's active.

## What we are making

A benchmark on Kaggle Benchmarks, run against several real models, plus a DEV
post about what we found. Deadline Sun 11 Oct 2026 23:59 PDT (Mon 12 Oct 08:59 Malta).
The deliverable is **insight**, not an app: a small, sharp dataset, a scorer we
trust, results across models, and a post that teaches something.

## Differences from the Hacktoberfest challenge

- The open-source-AI runtime rule does NOT apply. Closed models are fine to test;
  the benchmark runs on Kaggle's hosted models.
- No partner categories. Judging: insights, writing, creativity. Tie-break is
  reactions, so the post gets shared.
- No app to host. The public Kaggle benchmark link is mandatory.

## Roles

See the workspace CLAUDE.md roles table and this folder's PLAN.md "Team". In short:
Claude orchestrates; gpt-6-sol builds; gpt-6.1-sol + gpt-5.5 (+ gpt-6-astra red team)
review via `../../scripts/codex-panel.sh`. Jawad owns the Kaggle account, publishes the
task and the post.

## Benchmark rules we hold ourselves to

- Every item has one checkable gold answer, decided before any model is run.
  Ambiguous items are fixed or dropped, never scored by vibes.
- Scoring is deterministic Python where possible (exact match, parsing, regex) with
  pytest tests. LLM-as-judge only if unavoidable, and then validated against hand labels.
- Dataset is original and synthetic (or properly licensed and credited). No real
  customer, supplier or employer data. Label synthetic data as such.
- Keep a held-out split or a frozen version; don't tune items on the models' answers
  and then report those as findings without saying so.
- Report what we actually measured: n items, models, dates, settings, failure examples.
  No numbers in the post that the notebook can't reproduce.
- Small and sharp beats big and generic: ~100–300 items in one clear capability.

## Layout

- `fixtures/`: one module per matched pair (contract in `fixtures/base.py`).
- `harness/`: executes fixtures in Docker and writes `data/gold.jsonl`, `data/items.jsonl`.
- `scoring.py`: deterministic scorer + frozen baselines.
- `tasks/`: `build_task.py` generates the self-contained Kaggle task file `gone_for_good.py`.
- `data/`: gold and rendered items (generated; frozen before model runs).
- `results/`: exported run dataframes and plots (from Kaggle).
- `tests/`: pytest for scorers and data validation (runs locally with a fake `llm`).
- `docs/`: cover image and figures for the post.
- `.agent/tasks/`, `.agent/reviews/`: worker briefs and reviewer notes (kept as a record).

## Local vs Kaggle

Kaggle CLI 2.2.4 + kaggle-benchmarks are in `.venv`. Once Jawad has logged in
(`kaggle auth login`), `kaggle b init -y` writes Model Proxy creds to `.env` (gitignored)
and tasks are pushed/run/downloaded from here: see `.claude/skills/write-kaggle-benchmarks/`.
Gold is generated in Docker (`harness/run_in_docker.sh`), never on macOS.
