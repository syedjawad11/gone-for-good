# Status: Kaggle Benchmarking Challenge (workspace memory)

Read this first when resuming. Update it at every milestone or break.
Last updated: Wed 7 Oct 2026 afternoon, Malta. Pilot built + gold frozen-candidate; audits back; waiting on Kaggle login.

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

- Pilot built by 5 gpt-6-sol workers, verified by me: 37 tests pass; Docker gold (24 items) byte-identical
  across runs; executed labels = all hypotheses; date leaks fixed. Committed e039f13.
- Baselines: all three 0% pair accuracy.
- Audits: gpt-5.5 blind (high reasoning) scored 24/24 = labels unambiguous BUT ceiling risk.
  Red team (.agent/reviews/*redteam-tells.md): 5 items lack proof of exact restore (hashes), every
  pair has a shallow cue, a hand-made shortcut gets 3/12 pairs. Code review (*-gpt-6.1-sol.md):
  per-item error handling, tree_fp collision, timeouts, "same shell" wording, token-cap dispatch.

## Next (in order)
1. Fix code-review P1/P2s and red-team "breaks" (W6 worker), regenerate gold.
2. Kaggle pilot on 3 models (needs login) BEFORE hardening: tells us whether Kaggle's models spread out.
3. If at ceiling: harden held-out set (more hops, noise, counterbalanced cues, permuted IDs).
4. Jawad: `cd challenges/kaggle-benchmarking-2026 && .venv/bin/kaggle auth login` (browser OAuth).
   Then I run `kaggle b init -y`, `kaggle b t models`, `kaggle b quota`, push + pilot on 3 models.

## Notes
- HF26 week-2 challenge skipped this week (Jawad's call, 7 Oct).
- Previous challenge (HF26 Stock Diary) follow-ups live in that folder's status.md.
