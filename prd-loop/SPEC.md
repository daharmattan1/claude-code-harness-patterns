# A plan file an agent can resume

A long task outlives the context window. The conversation that started it gets compacted,
the session ends, another agent picks it up next week. This spec makes the plan file the
only memory that matters: everything an agent needs to continue is written in the file,
and the file is updated after every action.

This document specifies the file format and the loop that runs it. `templates/` has a full
and a lite template that follow it.

## 1. The loop

Each iteration does exactly this:

1. Read the plan file.
2. Do ONE action toward the next unmet success criterion.
3. Update the file: state, log, learnings.
4. End with exactly one signal.

| Signal | Meaning |
|---|---|
| `<promise>CONTINUE</promise>` | More work. Run another iteration. |
| `<promise>TASK_COMPLETE</promise>` | Every success criterion is met and finalization is done. |
| `<promise>BLOCKED_NEED_HUMAN</promise>` | Stuck, or at a gate only a person can pass. The reason is in Blockers. |

The signal is the last line of the iteration's output and appears nowhere else in it. An
automated loop matches on the string, so an echo elsewhere can stop or restart it falsely.

One action per iteration is the rule that makes the file trustworthy. An agent that does
five things and then updates state loses all five to a compaction in the middle.

One action per iteration shrinks the uncertainty after an interruption to one action. It does
not remove it. A file updated after the action cannot tell an action that never happened from
one that succeeded just before the session died. For a local edit that is harmless: re-reading
the file shows whether the edit landed. For an action with an outside effect (a push, a
deploy, a sent message, a payment) it is not, so those follow the intent rule:

1. **Write the intent first.** Before acting, set Next Action to
   `IN FLIGHT: <action>; receipt: <how to check whether it happened>` and save the file.
2. **Act.**
3. **Record the receipt** (the commit SHA, the PR URL, the message id) and clear the IN FLIGHT
   line.

A fresh agent that finds an IN FLIGHT line checks the receipt before doing anything else. Each
outside action must therefore be either safe to repeat or have a receipt a fresh agent can look
up on its own. When neither is true, the action is a human gate: block, and let a person do it.

## 2. File layout

Sections, in this order:

| Section | Written | Purpose |
|---|---|---|
| Metadata | once | Sizing, quality bar, context mode, completion signal |
| Objective | once | One or two sentences: what and why |
| Success Criteria | once (boxes checked during the run) | The definition of done |
| Phases | once | The work, in order |
| State | every iteration | Where the run is |
| Iteration Log | every iteration | What each iteration did |
| Running Learnings | at phase boundaries | Reusable lessons, curated |
| Phase Handoff | at phase boundaries | What the next phase needs from the last one |
| Artifacts | as produced | Where outputs live |
| Escape Hatches | once | When to stop |
| Recovery | once | How a fresh agent resumes |

### Metadata

| Field | Value |
|---|---|
| Created | date |
| Completion Signal | `<promise>TASK_COMPLETE</promise>` |
| Max Iterations | from the sizing formula (section 10) |
| Deliverable Type | ops, infrastructure, content, page-build, consulting, research, analytics, or gtm-marketing |
| Quality Bar | structural, semantic, or adversarial (section 4) |
| Context Mode | direct, extract_then_assemble, or map_reduce (section 9) |
| Spec Version | 1 |
| Cross-model review | true for 10 or more phases: review the plan before the first iteration |

List any action that reaches outside the repository (a deploy, a production migration, a
public post) with who approves it. Decide that before the run, not when the agent reaches it.

## 3. Success criteria

Every criterion passes four tests:

- **Literal:** someone with no context can answer yes or no.
- **Quantified:** every adjective has a number.
- **Artifact:** it names a file, path, or command output.
- **Unambiguous:** two agents could not disagree about it.

Four types:

| Type | Shape | Example |
|---|---|---|
| Binary | `<artifact> <verb> <condition>` | `pytest tests/ reports 0 failures and >= 40 passed` |
| Threshold | `<check> <metric> <op> <number> on <artifact>` | `review score >= 85 on docs/guide.md` |
| Rubric | `<reviewer> scores <artifact> on <rubric> >= <n>, no dimension below <m>` | a weighted multi-dimension score with knockouts |
| Human gate | `<person> <action> <artifact>, evidence: <how to confirm>` | `owner approved the README, evidence: approval quoted in the log` |

**Every verifier needs a negative control.** A check that has never failed may be unable
to fail. Plant an input it must reject (a contaminated fixture, a known-bad file, a
deliberately broken implementation) and confirm it does. A test suite that passes on its
first run is the case to be most suspicious of.

## 4. Quality bar

The deliverable type sets the bar, and the bar sets what verification is enough:

| Bar | For | Verification |
|---|---|---|
| structural | configs, scripts, migrations, file moves | existence, grep, the script's own checks |
| semantic | documentation, research, content | an independent review score |
| adversarial | anything a buyer, client or public reader judges | an adversarial reader, plus the semantic review |

The failure this prevents: a client deliverable whose 13 criteria were 12 structural checks
and one semantic one. Every check passed; the client could not use the output.

## 5. Phases

```markdown
### Phase 3: <name>

<!-- PHASE:3:short-slug -->

**Outcome:** <testable result>
**Context Budget:** LOW | MEDIUM | HIGH
**Source Manifest:** <files to read, with approximate line counts>
**Skill Gates:** <skills this phase must run, or none>
**Agent Gate:** <subagent type that does this phase's work> (optional)

**Actions:**
1. ... (at most five)

**Verification:**
- [ ] Output: <the check that proves the outcome>
- [ ] Completeness: <the check that nothing was skipped>
- [ ] Scope: <the check that nothing else was touched>
```

The marker `<!-- PHASE:<id>:<slug> -->` is what an executor parses. Ids may be integers,
decimals (`5.5`) or letters (`0a`).

**Do not mix work types in one phase.** Generation, validation, state updates and commits
each get their own phase. A phase that writes and also judges its own writing judges
leniently.

**Size phases with a score**, and split any phase over 2.0:

```
score = file_operations / 10 + actions / 5 + (1.5 if the actions say "for each")
      + source_lines / 3000 + (0.5 if it crosses directories) + (1.0 if it mixes work types)
```

A plan with fewer than ten phases for substantial work usually has phases that will not
fit in one context.

## 6. State

```markdown
### Current Phase
### Iteration Count
### Last Action          <- specific: what was done, to which file, with what result
### Next Action          <- specific enough that a fresh agent can start without reading anything else;
                            "IN FLIGHT: <action>; receipt: <check>" while an outside action runs (section 1)
### Blockers
### Failed Attempts on Current Action
### Working Branch       <- recorded on the first iteration, checked on every one
### Task IDs
### Pending Commit Paths <- every file changed since the last commit, appended as it changes
```

If the current branch ever differs from Working Branch, stop with BLOCKED. A different
branch means another session moved the tree.

Pending Commit Paths exists because the agent is stateless: a commit built from memory of
"what I touched" misses files after a compaction. The commit uses exactly this list.

## 7. Gates are checked on disk, never in the log

The Iteration Log has a Skills Invoked column. It is useful to a person reading the history.
**It is not a gate**, because the agent being checked writes it. A gate that trusts the
thing it polices manufactures false confidence: an agent can skip a step, type the step's
name in the column, and pass.

A skill gate is satisfied by an artifact on disk. Two classes:

- **Verdict-bearing**: a review that says the work is good enough. Accept only a record
  bound to the exact bytes reviewed (a sha256) and written by a principal other than the
  author. A review report the author wrote does not count, however good the score in it.
- **Ran-only**: a trace that a step happened (an imitation-sample file, an editor's backup).
  Existence is accepted for exactly what it is: evidence the step ran, not that it went well.

See `../hooks/` for a working implementation of both, including the test that rejects a
forged review.

### Validate before you advance

When a phase looks complete, hold its identity (call it the executing phase) and, in order:

1. Check its outcome against its Verification block.
2. Check the quality bar and the gate artifacts for that same phase.
3. If anything fails, do not advance. Record the failure against the executing phase, leave
   Current Phase where it is, and retry differently or block.
4. Only when everything passes: advance Current Phase, close the phase's task, write the
   handoff, commit.

The order matters. If the agent advances first and validates second, an interruption in
between leaves the file pointing at the next phase with the failed one marked done, and
recovery never returns to it.

## 8. Learnings and handoff

**Running Learnings** is the only place a lesson survives into the next plan. At every phase
boundary, ask of each non-trivial event: would this help a different plan? If yes, write one
line, prefixed with the iteration number. Tag it `[CROSS-POLLINATE]` when it is a failure
mode, a sizing surprise, or a platform workaround others will hit. Merge entries at twenty;
never delete.

**Phase Handoff** is overwritten at each boundary with what the next phase needs: what was
produced and where, decisions that constrain the next phase, the facts and paths it needs.
A fresh context reads the handoff instead of re-reading the last phase's sources.

## 9. Context modes

Set at planning time from the total lines the plan will read, and re-checked at the start
of each phase from its Source Manifest:

| Lines to read | Mode | What it means |
|---|---|---|
| under 3,000 | direct | Read sources as needed. |
| 3,000 to 6,000 | extract_then_assemble | Extract key facts from each source into a notes file (under 500 lines), then work from the notes only. |
| over 6,000 | map_reduce | Mandatory. MAP sub-phases each write their notes to disk; the REDUCE phase reads only those notes. It may reopen one source to verify or repair a note; reopening several means the notes are bad, so redo the MAP step. |

Several overlapping sources on one topic warrant map_reduce even under 3,000 lines: reading
them in one pass biases the result toward whichever was read last.

## 10. Sizing

```
Max Iterations = (Phases x 2) + 5
                 + 50% if the plan has recursive synthesis or multi-pass quality gates
                 + 25% if it covers more than three independent items
               then x 1.15, rounded up
Creative or content work: at least 60.
```

The result is a ceiling, not an estimate. Observed burn is far below it (section 13).

## 11. Escape hatches

| Trigger | Action |
|---|---|
| The same action fails 3 times | Stop repeating it. Split it, change approach, or block. |
| 5 iterations without phase progress | `BLOCKED_NEED_HUMAN` with the specific question |
| Max iterations reached | Stop and summarize |
| A quality threshold missed after 2 revision cycles | Surface the best version with its review instead of looping |

**These limits are advisory, and the reason is structural.** Every counter above is kept by
the agent it is meant to stop, in a file that agent writes. In the history behind this spec,
one plan ran 157 iterations against a cap of 45 without halting. (Most plans' Failed Attempts
counter read 0 when they finished, but that field resets on every action, so a final zero
says nothing either way.) A hard limit needs something outside the worker to own
the count. Treat these as prompts to stop and think.

That sets the division of labor. The plan file is for resuming: what was decided, what is
done, what comes next. Anything that must hold whether or not the agent cooperates belongs
outside it: a runner that counts iterations, a hook that blocks a write, git itself recording
what a commit contained. The fields the file does keep are checked against those outside
records (a commit's file list, a sidecar's hash), never trusted on their own.

## 12. Completion

Completion is three states, recorded as the run passes through them:

1. **Deliverables verified.** Every criterion is checked, every named artifact exists and is
   non-empty, every gate artifact passes. Nothing outside the file has been touched yet.
2. **Finalization pending.** Rename the plan (`_active` to `_complete`), close its task,
   score the run, commit. Each sub-step is recorded as it succeeds, so an interrupted
   finalization resumes the missing steps instead of repeating the done ones.
3. **Complete.** The receipts are verified (the renamed file, the closed task, the commit
   in the log). Only then is `TASK_COMPLETE` emitted.

**Score every completed plan** on a few fixed dimensions (fit of the criteria, sizing
accuracy, how often gates caught something, learning density, rework) and feed the scores
back into planning. That loop is where the calibration below came from.

**Lineage.** When a new plan depends on a finished one, read the finished one's criteria and
flag any left unchecked. A plan that says fix, repair or improve measures a baseline in
its first phase. On completion, look for plans that listed this one as a prerequisite.

## 13. Calibration

Measured across 85 of the author's executed plans that were analyzed for sizing; each table
covers the plans with complete data for it. (The escape-hatch figures in section 11 come
from a later scan of all 329 plan files.)

**Iterations used per phase, by category** (82 plans):

| Category | Min | Median | Max | n |
|---|---|---|---|---|
| Page build | 0.2 | 0.5 | 0.7 | 14 |
| Infrastructure | 0.07 | 0.5 | 1.0 | 15 |
| Skill upgrade | 0.2 | 0.8 | 2.0 | 8 |
| Consulting deliverable | 0.1 | 0.7 | 1.0 | 9 |
| Content | 0.14 | 1.0 | 2.1 | 7 |
| Data pipeline | 0.6 | 0.8 | 1.0 | 6 |
| Research and analysis | 0.13 | 0.9 | 1.5 | 7 |
| Newsletter | 0.07 | 0.5 | 1.0 | 3 |
| Batch orchestration | 0.15 | 0.6 | 1.0 | 4 |
| Campaign | 0.86 | 0.9 | 1.0 | 3 |
| Migration | 0.4 | 0.7 | 1.1 | 6 |

**Share of the iteration cap actually used** (80 plans): 0-10% in 28, 10-20% in 18, 20-40% in
22, 40-60% in 12, over 60% in none.

**What went wrong, by frequency:**

| Failure | Plans | Mitigation |
|---|---|---|
| Dependence on a UI or API the agent cannot drive | 14 | Verify access in a pre-flight phase; block for the human step |
| Context exhausted mid-phase | 10 | extract_then_assemble or map_reduce |
| A subagent's output never reached disk | 8 | Require the file write; check the file exists after |
| Quality score under threshold | 7 | Stop after two revision cycles and surface the best version |
| External API errors | 6 | A fallback named in the plan |
| Windows platform quirks | 6 | Platform notes in the plan; test on the target platform |
| Corrupted YAML frontmatter from a batch script | 3 | Run the script on one file and read the output before the batch |

Three patterns cut across categories:

- **Breadth overruns.** Plans covering more than three independent items overran their
  estimates, which is where the +25% in section 10 comes from.
- **Named risks are the cheap ones.** 42% of the risks written into plans materialized, and
  their planned mitigations worked. The damage came from risks nobody named, mostly context
  exhaustion and platform quirks, so name those two in every plan.
- **Some plans collapse.** Twelve plans scoped as several phases finished in a single pass.
  The cap exists for the ones that do not.
