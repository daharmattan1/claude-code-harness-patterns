# Plan: [task name]

<!--
Plan file (see ../SPEC.md). The file is the memory: an agent reads it, does
ONE action, updates it, and ends with one signal. Fill every [bracket]. Delete this comment.
Save as plans/YYYY-MM-DD_[slug]_active.md; rename to _complete.md when done.
-->

## Metadata

| Field | Value |
|---|---|
| Created | [YYYY-MM-DD] |
| Completion Signal | `<promise>TASK_COMPLETE</promise>` |
| Max Iterations | [(phases x 2) + 5, +50% recursive, +25% if >3 independent items, x 1.15; show the arithmetic] |
| Deliverable Type | [ops / infrastructure / content / page-build / consulting / research / analytics / gtm-marketing] |
| Quality Bar | [structural / semantic / adversarial] |
| Context Mode | [direct / extract_then_assemble / map_reduce] |
| Spec Version | 1 |
| Cross-model review | [true if 10+ phases: review this plan before iteration 1] |

### Actions outside the repository

| Action | Phase | Who approves |
|---|---|---|
| [deploy, migration, public post, payment] | [n] | [person, or "PR + green checks"] |

## Objective

[One or two sentences: what is being built and why.]

## Success Criteria

All must be true for completion. Each passes: literal, quantified, names an artifact, unambiguous.

- [ ] **[Binary]** [artifact at path] [verb] [condition]
- [ ] **[Threshold]** [check] [metric] [op] [number] on [artifact]
- [ ] **[Negative control]** [verifier] fails on [planted bad input at path]
- [ ] **[Human gate]** [person] [action] [artifact], evidence: [where it is recorded]

## Phases

### Phase 1: [name]

<!-- PHASE:1:[slug] -->

**Outcome:** [testable result]
**Context Budget:** [LOW / MEDIUM / HIGH]
**Source Manifest:** [files to read, ~line counts]
**Skill Gates:** [skills this phase must run, or none]

**Actions:**
1. [specific action, naming the file it produces]
2. [at most five]

**Verification:**
- [ ] Output: [the command or check that proves the outcome]
- [ ] Completeness: [the check that nothing was skipped]
- [ ] Scope: [the check that nothing else changed]

---

### Phase 2: [name]

<!-- PHASE:2:[slug] -->

[same fields]

---

## State

### Current Phase
0

### Iteration Count
0

### Last Action
Not started.

### Next Action
Phase 1, action 1: [exact first step].
<!-- Before any action with an outside effect: "IN FLIGHT: <action>; receipt: <how to check>",
save, act, record the receipt, clear the line. See SPEC section 1. -->



### Blockers
None.

### Failed Attempts on Current Action
0

### Working Branch
[recorded on the first iteration]

### Task IDs
[phase -> task id, if a task tracker is used]

### Pending Commit Paths
[appended as files change; cleared after each verified commit]

## Iteration Log

| # | Date | Phase | Action | Result | Skills Invoked | Notes |
|---|---|---|---|---|---|---|

<!-- Skills Invoked is for people reading the history. Gates are checked on disk, never here. -->

## Running Learnings

<!-- One line per reusable lesson, prefixed [Iter N]. Tag [CROSS-POLLINATE] when another plan
will hit it. Merge at 20 entries; never delete. -->

## Phase Handoff

### Completed Phase
### Key Outputs
### Decisions That Affect the Next Phase
### Context Carried Forward
### Source Material Summary

## Artifacts

| Type | Location | Status | Notes |
|---|---|---|---|

## Escape Hatches

- The same action fails 3 times: stop repeating it; split it, change approach, or block.
- 5 iterations without phase progress: `<promise>BLOCKED_NEED_HUMAN</promise>` with the specific question.
- [Max Iterations] reached: stop and summarize.
- A quality threshold missed after 2 revision cycles: surface the best version with its review.

These counters are kept by the agent they are meant to stop. Treat them as prompts to think.

## Completion

1. Deliverables verified: every box above checked, every artifact present, every gate passed.
2. Finalization (record each step as it succeeds): rename to `_complete.md`, close the task,
   score the run, commit.
3. Emit `<promise>TASK_COMPLETE</promise>` only after the receipts are verified.

## Recovery

A fresh agent: read State, then Phase Handoff, then Running Learnings, then the last five
Iteration Log rows. Do the Next Action. Update State. One signal.
