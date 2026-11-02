# Plan: [task name]

<!-- Lite plan file, for 3 to 7 phases (see ../SPEC.md). One action per iteration;
the file is the memory. For 8 or more phases use prd_full.md. -->

## Metadata

| Created | Max Iterations | Quality Bar | Context Mode | Spec Version |
|---|---|---|---|---|
| [YYYY-MM-DD] | [(phases x 2) + 5, x 1.15] | [structural / semantic / adversarial] | [direct / extract_then_assemble] | 1 |

## Objective

[One or two sentences.]

## Success Criteria

- [ ] [artifact] [verb] [condition]
- [ ] [verifier] fails on [planted bad input]   <!-- negative control -->

## Phases

### Phase 1: [name]
<!-- PHASE:1:[slug] -->
**Outcome:** [testable result]  **Skill Gates:** [or none]
**Actions:** 1. [...] 2. [...]
**Verification:** [command or check]

### Phase 2: [name]
<!-- PHASE:2:[slug] -->
[same fields]

## State

### Current Phase
0
### Iteration Count
0
### Last Action
Not started.
### Next Action
Phase 1, action 1: [exact first step].
### Blockers
None.
### Failed Attempts on Current Action
0
### Working Branch
[recorded on the first iteration]
### Pending Commit Paths

## Iteration Log

| # | Date | Phase | Action | Result | Skills Invoked | Notes |
|---|---|---|---|---|---|---|

## Running Learnings

## Escape Hatches

Same action fails 3 times: change approach. 5 iterations without progress:
`<promise>BLOCKED_NEED_HUMAN</promise>`. Max iterations: stop and summarize.

## Completion

On every box checked and verified: rename to `_complete.md`, score the run, commit, then
emit `<promise>TASK_COMPLETE</promise>`.
