# Status: Kaggle Benchmarking Challenge (workspace memory)

Read this first when resuming. Update it at every milestone or break.
Last updated: Wed 7 Oct 2026 afternoon, Malta. Contract fixed after panel review; 5 workers building.

## Deadline
- Submissions close Sun 11 Oct 2026, 23:59 PDT = Mon 12 Oct 06:59 UTC = 08:59 Malta.
- Schedule in PLAN.md (we are ~2 days behind the brief's original schedule; scope cut accordingly).

## Where things are
- Idea: "Gone for Good?" (BENCHMARK_BRIEF.md). Plan, team, scope: PLAN.md.
- Codex team scripts: ../../scripts/codex-{worker,review,panel}.sh, models in ../../scripts/models.env.
- No GitHub repo, no Kaggle task yet.

## Done (7 Oct)
- Panel review (gpt-6.1-sol, gpt-5.5, gpt-6-astra) → contract fixes, recorded in PLAN.md.
- Sources + prior art verified (docs/sources.md). Docker running, base image pulled.
- Kaggle CLI 2.2.4 + kaggle-benchmarks 0.6.1 in .venv; Kaggle's official skill in .claude/skills.

## In progress
- Workers (gpt-6-sol), briefs in .agent/tasks/: W1 harness+Docker, W2 fs, W3 db, W4 recovery,
  W5 scorer+task builder. Logs: .agent/W*.out and .agent/logs/.

## Next (in order)
1. Verify each worker's output myself (pytest), integrate, run gold twice in Docker, compare.
2. Label audit: gpt-5.5 blind predictions vs gold; gpt-6-astra surface-tell attack; Jawad reads labels.
3. Jawad: `cd challenges/kaggle-benchmarking-2026 && .venv/bin/kaggle auth login` (browser OAuth).
   Then I run `kaggle b init -y`, `kaggle b t models`, `kaggle b quota`, push + pilot on 3 models.

## Notes
- HF26 week-2 challenge skipped this week (Jawad's call, 7 Oct).
- Previous challenge (HF26 Stock Diary) follow-ups live in that folder's status.md.
