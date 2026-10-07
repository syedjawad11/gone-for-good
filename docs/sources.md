# Sources for the post's hook and prior art (checked 7 Oct 2026 by a research subagent)

Quote nothing that is not CONFIRMED here. X/Twitter pages returned HTTP 402 to our fetcher;
where marked "secondary capture", re-open the X post in a browser before quoting.

## PocketOS / Railway (April 2026)
| Claim | Status | Source |
|---|---|---|
| Cursor agent running Claude Opus 4.6 | Confirmed (Crane's words, secondary capture) | https://x.com/lifeofjer/status/2048103471019434248 |
| Token found "in a file completely unrelated to the task" | Confirmed (same) | same |
| `volumeDelete` GraphQL mutation; "9 seconds" | Confirmed (same) | same |
| "most recent recoverable backup was three months old" | Confirmed (same) | same |
| Volume backups live with the volume | Confirmed, but from Railway's **docs**, not the blog: "Wiping a volume deletes all of its backups" | https://docs.railway.com/guides/postgres-backups-restores |
| Restored from offsite disaster backups | Confirmed ("back up with all their data") | https://blog.railway.com/p/your-ai-wants-to-nuke-your-database |
| "~2.5 days" to restore | NOT stated by Railway; derived from dates. Do not quote a duration. | — |
| 48-hour soft delete for API volume deletes, 1 May | Confirmed | https://railway.com/changelog/2026-05-01-undoable-deletes |

## 700 GB home directory (Aug 2026, Sebastien Guillemot)
| Claim | Status | Source |
|---|---|---|
| Model named by the developer: "Fable" ("Bad news: Fable nuked my entire dev machine") | Confirmed via search capture of his post | https://x.com/SebastienGllmt/status/2092634841863123047 |
| Mechanism: cleanup reused the variable holding the home path | Secondary only (Tom's Hardware + others agree) | Tom's Hardware, 28 Aug 2026 |
| Mid-task downgrade to "Opus 4.8" | Secondary only, unverified. Do not quote. | Tom's Hardware |
| ~90% recovered from an old drive, rest from GitHub | Secondary consensus, unverified against his own text | — |

## Prior art (none does exact loss + tested recoverability on one-fact matched pairs)
| Work | Overlap |
|---|---|
| SABER, arXiv 2606.01317: agents in stateful workspaces, final-state safety scoring | Partial (closest; behavioural, multi-step, not prediction) |
| PreAct-Bench, arXiv 2606.09890: 1,000 paired trajectories, predict unethical endings | Partial (paired design, different target) |
| CARE, arXiv 2607.21642: pre-execution shell command verifier | None |
| Look Before You Leap, arXiv 2609.11957: pre-action verification | None |
| edgedelta/blast-radius-bench: SRE root-cause chains | None |
| DEV entry "Undo Only Yours" (dev.to/aqeelabbas3972): selective undo of shared edits | Partial theme, different mechanism |
