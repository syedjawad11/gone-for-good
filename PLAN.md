# Plan: "Gone for Good?" Kaggle benchmark

Design: `BENCHMARK_BRIEF.md` (the what). This file: scope, team, schedule, decisions (the how).
Deadline: Sun 11 Oct 2026 23:59 PDT = Mon 12 Oct 08:59 Malta.

## Scope (cut on Wed 7 Oct; we started building 2 days behind the brief's schedule)

- Pilot: the brief's 12 pairs (FS-1..4, DB-1..4, R-1..4) = 24 items. Development data.
- Main run: **~30 frozen held-out pairs (~60 items)**, written and gold-frozen before any model sees them.
- Models: 8–10 on Kaggle, across vendors and sizes, incl. open-weight; one repeat run on 2 models.
- HF26 week-2 challenge: skipped this week (Jawad, 7 Oct). Kaggle only.

## Team

| Role | Model | Call |
|---|---|---|
| Orchestrator | Claude Opus 5.5 | specs, integration, runs, labels' final say, post |
| Builder | gpt-6-sol | `scripts/codex-worker.sh <dir> <task.md>` |
| Lead reviewer | gpt-6.1-sol | `scripts/codex-review.sh` |
| Independent auditor | gpt-5.5 | `MODEL=gpt-5.5 scripts/codex-review.sh` or via panel |
| Red team | gpt-6-astra | `scripts/codex-panel.sh --redteam` |
| Cheap helper | gpt-6-luna | `MODEL=gpt-6-luna EFFORT=low scripts/codex-worker.sh` |
| Research | Claude Sonnet 5 subagent | source checks, prior art |

Worker briefs live in `.agent/tasks/`, reviews in `.agent/reviews/`, worker logs in `.agent/logs/`.

## Code layout (interface contract, set before workers start)

- `fixtures/{fs,db,recovery}/<id>.py`: one module per pair. Contract in `.agent/tasks/CONTRACT.md`.
- `harness/run.py`: builds each variant in a temp dir, runs the authored operation, runs the restore,
  hashes, writes `data/gold.jsonl` + `data/items.jsonl` (rendered prompts). `harness/Dockerfile` pins Linux.
- `scoring.py` + `tests/`: deterministic scorer, baselines, stub LLMs.
- `tasks/gone_for_good.py`: the kbench task pushed with `kaggle b t push`.

## Schedule

| Day | Work |
|---|---|
| Wed 7 | Plan + brief review (panel). Source/prior-art check. Contract. Workers W1 harness+Docker, W2 FS, W3 DB, W4 R. Kaggle CLI set up. |
| Thu 8 | Integrate, double-run gold. W5 scorer+tests, W6 kbench task. Label audit (gpt-5.5 blind, gpt-6-astra tells, Jawad). Pilot on 3 models. Go/no-go. |
| Fri 9 | Held-out ~30 pairs (3 workers by family), audit, freeze + commit gold. Main run 8–10 models. |
| Sat 10 | Analysis + charts, post draft, gpt-6.1-sol critique, publish task + repo + post. |
| Sun 11 | Buffer only. |

Kill-switch (Thu night, with Jawad): pilot at ceiling after one hardening round → honest null result
or ContractFlip.

## Open questions

- Kaggle model list and daily quota (`kaggle b t models`, `kaggle b quota`) — needs Jawad's login.
- Docker Desktop must be running for gold generation; fallback is a Kaggle notebook.

## Decisions log

- 4 Oct: folder created; brief captured.
- 5 Oct: idea chosen: "Gone for Good?" (BENCHMARK_BRIEF.md). Fallback ContractFlip.
- 7 Oct: scope cut to 12 pilot + ~30 held-out pairs, 8–10 models. HF26 week 2 skipped.
  Codex team widened (auditor gpt-5.5, red team gpt-6-astra, helper gpt-6-luna). Kaggle CLI
  (`kaggle b ...`) replaces notebook-only runs if Jawad's login works.
