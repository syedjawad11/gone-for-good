# Plan: "Gone for Good?" Kaggle benchmark

Design: `BENCHMARK_BRIEF.md` (the what). This file: scope, team, schedule, decisions (the how).
Deadline: Sun 11 Oct 2026 23:59 PDT = Mon 12 Oct 08:59 Malta.

## Scope (cut on Wed 7 Oct; we started building 2 days behind the brief's schedule)

- Pilot: the brief's 12 pairs (FS-1..4, DB-1..4, R-1..4) = 24 items. Development data.
- Main run: **18–24 frozen held-out pairs (36–48 items)**, written and gold-frozen before any model
  sees them. Include some mechanisms not in the pilot, so the claim is not only "renamed pilot items".
- Models: 6–8 on Kaggle, across vendors and sizes, incl. open-weight. Repeat run only if quota allows.
- HF26 week-2 challenge: skipped this week (Jawad, 7 Oct). Kaggle only.

## Team

| Role | Model | Call |
|---|---|---|
| Orchestrator | Claude Opus 5.5 | specs, integration, runs, labels' final say, post |
| Builder | gpt-6-sol | `scripts/codex-worker.sh <dir> <task.md>` |
| Lead reviewer | gpt-6.1-sol | `scripts/codex-review.sh` |
| Independent auditor | gpt-5.5 | `MODEL=gpt-5.5 scripts/codex-review.sh` or via panel |
| Red team | gpt-6.1-sol (astra dropped 8 Oct, token cost) | `scripts/codex-panel.sh --redteam` |
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
| Wed 7 | Plan + panel review. Source/prior-art check. Contract. Workers W1 harness+Docker, W2 FS, W3 DB, W4 R, W5 scorer+task. Kaggle CLI set up. |
| Thu 8 | Integrate, double-run gold in Docker. Label audit (gpt-5.5 blind, gpt-6-astra tells, Jawad). Push task, pilot on 3 models. Go/no-go. |
| Fri 9 | Held-out 18–24 pairs (3 workers by family), audit, freeze + commit gold. Main run 6–8 models. |
| Sat 10 | Analysis + charts, post draft, gpt-6.1-sol critique, publish task + repo + post. |
| Sun 11 | Buffer only. |

Kill-switch (Thu night, with Jawad): pilot at ceiling after one hardening round → publish the honest
null result. No ContractFlip pivot (no time to rebuild).

## Contract changes after the 7 Oct panel review (all three reviewers agreed)

Reviews: `.agent/reviews/20261007-130758-panel-*.md` (gpt-6.1-sol, gpt-5.5, gpt-6-astra).
Accepted:
- Gold = "lost by this command" + "restored exactly by THIS restore script". The restore script is
  shown verbatim in the prompt and executed. We never claim no other recovery exists.
- Resource identity is explicit: file bytes at a path (follows links) / symlink object / dir contents /
  specific pre-existing rows by key. No whole-table or db-file hashes (archive inserts are not losses).
- SQL runs via `sqlite3 -bail` with PRAGMA before BEGIN; -bail + exit rolls the transaction back.
- FS-1 expectation corrected (`.//*`; hidden files inside deleted dirs go too). FS-2 redesigned
  (direction of the symlink). FS-4 requires tree = index = HEAD. R-3 uses a really empty archive, not
  a checksum mismatch. R-4's operation is the wrapper script, source shown.
- Surface tells: the bad variant's distinctive token appears harmlessly in the good one; same artifact
  titles and similar lengths; no variant letters in prompts.
- Headline + Kaggle leaderboard metric = **pair accuracy**. Format failures count as wrong (and are
  reported separately). Baselines frozen in code before any model run. Bootstrap over pairs with the
  same draw across models.
- Scope: held-out 18–24 pairs, 6–8 models, no pivot.
Not accepted / deferred:
- Length/token-only ablation classifier: deferred; we report the naive-reader baseline and per-pair
  length ratios (`data/tell_report.txt`) instead.
- Proving a public Kaggle link on Wed: blocked on Jawad's Kaggle login; first thing once it exists.

Research (Sonnet subagent, `docs/sources.md`): positioning holds; two hook facts need rewording.

## Open questions

- Kaggle model list and daily quota (`kaggle b t models`, `kaggle b quota`) — needs Jawad's login.

## Decisions log

- 4 Oct: folder created; brief captured.
- 5 Oct: idea chosen: "Gone for Good?" (BENCHMARK_BRIEF.md). Fallback ContractFlip.
- 7 Oct: scope cut to 12 pilot + ~30 held-out pairs, 8–10 models. HF26 week 2 skipped.
  Codex team widened (auditor gpt-5.5, red team gpt-6-astra, helper gpt-6-luna). Kaggle CLI
  (`kaggle b ...`) replaces notebook-only runs if Jawad's login works.
- 7 Oct: panel review accepted (see above). Held-out cut further to 18–24 pairs, models 6–8.
  Workers W1 harness, W2 fs, W3 db, W4 recovery, W5 scorer+task launched in parallel.
- 7 Oct evening: W6/W7 fixes merged. Local pilot v2 on 6 models gives a real spread (Gemini 3 Flash 100%
  pair acc down to 0–17% for small models), so the benchmark is NOT flat overall, but frontier models are at
  ceiling on the pilot. Held-out set to be made harder. Open: integer-ID format failures, gpt-oss api errors.
