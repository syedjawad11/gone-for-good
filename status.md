# Status: Kaggle Benchmarking Challenge (workspace memory)

Read this first when resuming. Update it at every milestone or break.
Last updated: Wed 7 Oct 2026 evening, Malta. ON BREAK. Pilot v2 built; local pilot shows a real spread. Nothing running.

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

- W6 (code fixes) + W7 (fixture fixes) done and verified by me: 54 tests pass; Docker gold regenerated,
  byte-identical across two runs, executed labels = all hypotheses, no date leaks. One Linux-only fix by me
  (R-3 artifact: GNU tar exits 2 on the empty archive; error text now shown).
- Task file `tasks/gone_for_good.py` builds, compiles, and ran end to end locally (per-item retry, 4096 cap).

## Local pilot v2 (7 Oct evening, 24 items, run from the Mac through the Model Proxy)
Logs: results/local/*.log (GFG_ITEM lines hold raw responses). Pair acc / item acc / format-fail rate:
| model | pair | item | fmt fail | notes |
|---|---|---|---|---|
| gemini-3-flash-preview | 1.00 | 1.00 | 0.00 | at ceiling |
| deepseek-r1-0528 | 0.67 | 0.83 | 0.04 | wrong: DB-3B, FS-1B, FS-4A |
| gemini-3.1-flash-lite-preview | 0.17 | 0.42 | 0.00 | 14 real reasoning errors, all families |
| qwen3-next-80b-a3b-instruct | 0.17 | 0.33 | 0.12 | mostly real errors |
| gpt-5.4-nano | 0.00 | 0.12 | 0.50 | format: answers bare numbers [2,3,5] instead of "R2"... (often right!) |
| granite-4.0-h-small | 0.00 | 0.00 | 0.96 | format: answers with row numbers (real confusion) |
| gpt-oss-120b | — | — | — | INCOMPLETE: api_error on every item, then hung at item 10; I killed it |
Earlier: gpt-5.5 (via Codex, blind, high effort) 24/24. Baselines: 0% pair acc.
CAUTION: an earlier batch of "7 models" was really Gemini 3 Flash 7 times (LLM_DEFAULT env does not
override .env). Fixed by selecting the model in code (scratch runner replaces the last line with
`gone_for_good.run(kbench.llms[os.environ["GFG_MODEL"]])`). Never trust a run without checking
the `*.run.json` filename shows the intended model.

## Next (in order) — decide with Jawad first
1. Scoring decision: accept bare integers n as "Rn"? Recommendation: NO silent fix; instead make the
   prompt say IDs are strings like "R2" and show an example answer, re-run, and report format errors
   separately (it is itself a finding: small models confuse resource IDs with row IDs).
2. gpt-oss-120b: read its api_error text in results/local/openai_gpt-oss-120b.log (likely the
   max_tokens param or temperature); fix in tasks/build_task.py.
3. Ceiling: frontier models (Gemini 3 Flash, GPT-5.5) are at 100%. Held-out set (18–24 pairs) must be
   harder: more hops, deciding fact buried in longer artifacts, subtler semantics (git index vs HEAD,
   INSERT OR IGNORE not overwriting changed rows, ON DELETE SET NULL, set -e inside && lists, rsync
   --delete, cp -r vs -a). Brief workers W8–W10 by family; red-team + blind audit before freezing.
4. Push task to Kaggle (`kaggle b t push gone-for-good -f tasks/gone_for_good.py --wait`) and run the
   main model set there (46 models available; pick 6–8 spanning vendors/sizes incl. open-weight).
5. Post draft Fri/Sat. Hook facts: docs/sources.md (two corrections).

## Notes
- HF26 week-2 challenge skipped this week (Jawad's call, 7 Oct).
- Previous challenge (HF26 Stock Diary) follow-ups live in that folder's status.md.
