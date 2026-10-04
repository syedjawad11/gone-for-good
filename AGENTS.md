# Kaggle Benchmarking Challenge: instructions for Codex

Read `BRIEF.md` and `PLAN.md` first. The orchestrator (Claude Code) tells you
whether you are a worker or a reviewer.

- Worker: do only the task given, touch only the named files, do not commit,
  do not install packages (no network in your sandbox; report missing ones).
  End with: files changed, how verified, assumptions, anything not done.
- Reviewer: read-only. Lead with what would break the benchmark's validity or
  miss the deadline (Sun 11 Oct 2026, 23:59 PDT). Give file, problem, fix.
  End with a verdict.

Project rules:
- Every benchmark item has exactly one checkable gold answer. Flag any item
  that is ambiguous, has two defensible answers, or leaks its answer.
- Scorers are deterministic Python with pytest tests. No model calls in
  scorers unless the plan says so explicitly.
- Data is original and synthetic. No real customer, supplier, or employer data.
- Task code targets the `kaggle_benchmarks` API (`@kbench.task`, first arg
  `llm`, `llm.prompt`, `kbench.assertions.*`). Locally, test with a stub LLM;
  never assume a real model is reachable.
- Python 3.9+ compatible.
