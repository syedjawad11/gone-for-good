# Held-out fix round (W11 fs, W12 db, W13 recovery) — common rules

You built (or are taking over) six held-out pairs. Three reviewers attacked them. Read, in full:
`.agent/reviews/20261007-185319-panel-gpt-6.1-sol.md` (lead), `...-panel-gpt-6-astra.md` (red team),
`...-panel-gpt-5.5.md` (auditor). Also re-read `.agent/tasks/heldout-common.md` (all rules still hold) and
`fixtures/base.py`. Executed Debian gold + rendered prompts for the current version are in
`.agent/heldout-check/{fs,db,rec}/` — note GNU `ls` output can differ from your macOS output.
Use `.venv/bin/python`. Do not run Docker, do not commit, touch only your files.

Apply to every pair you own:
1. **No alternative world.** For each pair, list every fact the gold depends on and make sure a generated
   artifact proves it. If a reviewer gave a counterexample environment consistent with the prompt, add the
   evidence that rules it out (contents, complete member listings, `-ef` identity checks both ways, empty
   `git stash list`, etc.).
2. **Honest hops, per variant.** `Variant.hops` = the number of artifacts actually needed for THAT variant's
   answer (artifact-removal test). It is fine for a "nothing lost" variant to have hops 2. Do not pad.
   Keep `hops >= 2` per variant; if a variant falls to 1, add a genuinely needed dependency or say so.
   Remove long listings that carry no needed fact (or make them carry one); we no longer require a 30-line artifact.
3. **No cheap cue.** Kill each shortcut the reviewers scored on your pairs. The worse variant must not be the
   longer prompt (keep A/B total prompt length within 1%, either direction), must not be identifiable by
   column padding, a giveaway word, or the mere presence of a diff/section. Count the A/B differing lines on
   the Debian rendering logic (avoid width-dependent `ls -la` columns that change when counts change; prefer
   `stat -c '%n %F links=%h size=%s'` or `find ... -printf '%y %p\n'` where a listing is needed).
4. **Position balance.** Across your 6 pairs, no inventory position may be one whose answer changes between
   variants in more than 2 pairs. Permute IDs (update `expected`, `literal_targets`) as needed.
5. Keep each pair's mechanism unless your brief says otherwise. Keep tests (`tests/test_fixtures_<family>_heldout.py`)
   passing and extend them: prompt-length ratio <= 1.01, differing-lines cap 8, position-balance check.

Report: per pair, what changed and which reviewer finding it closes; per variant hops with the needed fact per
artifact; anything you did not fix and why; pytest output.
