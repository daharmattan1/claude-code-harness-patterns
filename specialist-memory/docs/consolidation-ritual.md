# Consolidation ritual

The retirement gate flags learnings that have stopped being used. This is where a person acts
on the flags. The automated loop only ever adds; only this pass merges or retires.

**Who:** the operator, a different principal from the loop.
**When:** quarterly, or sooner when the gate lists more than about five candidates, or when
utilization stays under about 0.5 for a full window (most learnings not firing means the
memory is rotting).
**How safe:** every change is a commit. Nothing is hard-deleted; a retired learning can come
back if the miss it guarded against returns.

The ritual only works if it actually happens. Put the retirement backlog somewhere you look
anyway (a daily brief, a weekly review), not in a file you have to remember to open.

## The pass

1. **Read the candidates:**
   `python bin/retirement_gate.py --history memory/<name>/run_history.jsonl --promotions memory/<name>/promoted.json --rules memory/<name>/learning_rules.jsonl --retired memory/<name>/retired.json`.
   Candidates are learnings, promoted or not, with no evidenced use in the last 20 runs. Each
   one is judged only after it has been loaded for 20 runs of its own, so a rule added or
   promoted last week is listed as too new to judge, not as a candidate.
2. **Read the four metrics** for context. Zero uses with flat metrics is a clean retire. Zero
   uses while first-draft quality is rising may be a measurement gap: the rule may be working
   without being cited.
3. **Decide each candidate:**
   - **Retire:** add its id to `retired.json` and remove it from `core_memory.md` and
     `promoted.json`. The specialist skips retired ids when it loads its rules, so a retired
     rule stops shaping its work. The rule itself stays in `learning_rules.jsonl` and in git
     history, and taking the id out of `retired.json` brings it back.
   - **Merge:** fold it into a broader truth that covers it.
   - **Keep:** record why (`human_verdict: right`), so the next pass does not relitigate it.
4. **Consolidate core memory** if `commit_return.py` reported it over the cap: merge or drop
   the least-used truths.
5. **Commit once:** `chore(memory): consolidation, retired N, merged M`.

## Rules

- The loop adds; people remove.
- Never hard-delete. Demote and commit.
- Record a verdict for every candidate you looked at, including the ones you kept. Those
  verdicts are the only labeled data on whether the memory is working.
