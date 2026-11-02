# Bundle format

One directory per specialist. Each file has one lifecycle.

| File | Lifecycle | Holds |
|---|---|---|
| `founding_profile.md` | frozen | Identity: role, standards, hard rules. Changing it means a new version, decided by a person. |
| `core_memory.md` | evolved, capped, always loaded | The few operating truths the specialist reasons from every run, plus pointers to required reading. |
| `evolution_log.md` | append-only, first person | "I learned X. I was wrong about Y." The file a person reads and corrects. |
| `learning_rules.jsonl` | append-only | Behavior-changing rules: `{"id", "rule", "source", "confidence", "added_run", "cross_agent"?}`. `commit_return.py` stamps `added_run`. |
| `run_history.jsonl` | append-only | One row per run; what the retirement gate reads. |
| `pending_promotions.jsonl` | append-only queue | Candidates for shared files, waiting for a person. |
| `promoted.json` | edited by a person | The ids of learnings promoted into core memory, optionally `{"learning_id", "since_run"}` so the gate counts from the promotion. |
| `retired.json` | edited by a person | Ids a person has retired. The specialist skips them when it loads its rules; the gate stops watching them. |
| `reflections/run_NN.md` | one file per run | Optional long-form reflection. |

## Rules that make it survive a shared branch

When several sessions append to the same bundle and branches merge, the format has to
survive a merge conflict without becoming unreadable:

- **JSONL, never a JSON array.** Two sessions appending to an array produce conflict markers
  inside one JSON value, and the specialist fails to load. Two sessions appending lines produce,
  at worst, one skippable bad line.
- **One file per run** for anything long. Concurrent runs then write different files.
- **Append-only logs.** A merge that duplicates an entry is harmless; a merge that corrupts a
  structured blob is not.

The invariant: a merge conflict never produces memory the specialist cannot read.

## What is portable and what is local

| The pattern (keep it anywhere) | Local plumbing (swap it) |
|---|---|
| Load on spawn; reflect on return | JSONL for merge safety (a single-user store may not need it) |
| A different principal commits than authored | git as the history of record |
| A capped core memory, consolidated by a person | Where the retirement backlog is shown |
| Retirement: evidenced use or out | The file layout |
| Shared memory changes only through human-approved promotion | The storage backend |

## Two stances worth stating

**Forgetting.** Append-only is an engineering convenience, never a reason to refuse "forget
that". Removing a record means removing it from the logs and re-deriving anything that cited
it: core memory, rules, promotions.

**Which direction gets the review.** This design auto-commits additions and asks a person
before anything is removed, which suits one operator who wants memory to grow quickly. For a
specialist that keeps notes about a person, invert it: what the agent adds about someone is
what needs review first.
