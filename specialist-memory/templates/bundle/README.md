# Bundle template

Copy this directory to `memory/<specialist-name>/` and fill in `founding_profile.md` and a
short seed for `core_memory.md`. Leave the rest empty; they accrete.

| File | Lifecycle | Written by |
|---|---|---|
| `founding_profile.md` | frozen | a person, once |
| `core_memory.md` | evolved, capped, always loaded | a person, at consolidation |
| `evolution_log.md` | append-only, first person | `commit_return.py`, from the returned manifest |
| `learning_rules.jsonl` | append-only, one JSON object per line | `commit_return.py` |
| `run_history.jsonl` | append-only, one row per run | `commit_return.py` |
| `pending_promotions.jsonl` | append-only queue | `commit_return.py`; a person approves |
| `promoted.json` | edited by a person | a person, when approving a promotion |
| `retired.json` | edited by a person | a person, at consolidation; the specialist skips these ids |
| `reflections/run_NN.md` | one file per run | optional, the orchestrator |

The full format is in `docs/bundle-format.md` in the specialist-memory folder. Delete this
README from your copy once you've read it.
