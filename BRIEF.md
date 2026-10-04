# Kaggle Benchmarking Challenge

Source: https://dev.to/challenges/kaggle-2026-09-23 (read 4 Oct 2026)
Launch post: https://dev.to/devteam/join-the-kaggle-benchmarking-challenge-2500-in-prizes-for-five-winners-18ml
Rules: https://dev.to/page/kaggle-2026-09-23-contest-rules and https://dev.to/page/official-hackathon-rules

## Dates

- Window opened: Wed 23 Sep 2026, 09:00 PDT
- **Submissions due: Sun 11 Oct 2026, 23:59 PDT = Mon 12 Oct 06:59 UTC = 08:59 Malta**
- Winners announced: Thu 5 Nov 2026

## Prompt

"Build a benchmark, run it against real models, and tell us what you found."
Build a benchmark on Kaggle (kaggle.com/benchmarks) that tests model behaviour:
multi-step reasoning, code generation, tool use, image recognition,
instruction following, or a novel failure mode you have hit yourself.
Launch post tip: "The best benchmarks usually come from a specific itch rather
than a general one."

## Rules that can disqualify

- **A public Kaggle benchmark link in the post is mandatory.** No link = ineligible.
- One submission per person. Teams up to four (one submission per team).
- DEV post from the official template (see `post.md`), tag `kagglechallenge`.
- English for prize eligibility. 18+. Void where prohibited.
- Plagiarism = ineligible (egregious: DEV suspension). Open-source code OK if
  significantly modified and credited. Credit non-trivial prior work.
- AI tools are allowed for building.
- Rules do not require new work, but we follow the workspace rule anyway:
  new repo, started inside the window. Any commit after the deadline is listed
  in the README.

## Judging (no stated weights; order as published)

1. **Insights shared**: do the findings teach something real?
2. Writing quality
3. Creativity in approach

Tie-break: most positive reactions on the DEV post. So share the post.

## Prizes

- Five winners: $500 + DEV++ + winner badge each. No partner categories.
- Completion badge for every valid entry.

## Submission must cover (template sections)

1. What I Benchmarked: the capability, and why it interested us
2. Models Tested: which, and why those
3. Findings: results, surprises, what we'd measure next
4. My Benchmark: the public Kaggle link (required)
Plus a cover image and extra fitting tags (max 4 total).

## Tooling facts (from Kaggle docs, 4 Oct)

- Library: https://github.com/Kaggle/kaggle-benchmarks (`import kaggle_benchmarks as kbench`).
  Docs: quick_start.md, user_guide.md, cookbook.md on the `ci` branch.
- Build in a Kaggle notebook: https://www.kaggle.com/benchmarks/tasks/new (deps preinstalled,
  models served through Kaggle; no API keys of ours).
- Local development with the model proxy is **Kaggle-internal only**. We prototype the
  task logic locally against stub/fake LLMs, then run the real models on Kaggle.
- Task: `@kbench.task(name=...)` function, first arg `llm`; `llm.prompt(...)`;
  assertions `kbench.assertions.assert_equal / assert_in / assert_contains_regex / assert_true ...`.
- Dataset runs: `task.evaluate(llm=[...], evaluation_data=df, n_jobs=..., timeout=...)`,
  `runs.as_dataframe()`. Cache with `kbench.client.enable_cache()`.
- Models: `kbench.llms["google/gemini-2.5-flash"]` etc. The exact list in the notebook must be
  checked on Kaggle (docs mention Gemini 2.5 Flash/Pro, Llama 3.1 70B, Claude Sonnet 4).
- One task per notebook feeds the leaderboard; `%choose main_task` selects it.
- Quotas/costs for model calls: not documented. Check on Kaggle before planning run sizes.
