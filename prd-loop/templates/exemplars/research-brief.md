# Exemplar card: write a research brief

Synthetic, like `cli-tool.md`: the task is invented to show the shape of a good plan in a
category where quality is a judgment, not a test result.

## Category signals

The plan mentions: sources, synthesis, citations, a comparison, a recommendation.

## Recommended parameters

| Parameter | Value |
|---|---|
| Deliverable type | research |
| Quality bar | semantic (adversarial if a buyer or client will read it) |
| Context mode | map_reduce once sources exceed 6,000 lines; otherwise extract_then_assemble |
| Typical phases | 8 to 15 |
| Iterations per phase (expect) | about 0.9 |

## Success criteria that worked

1. `research/vendors/brief.md` covers all 6 vendors listed in `research/vendors/scope.md`,
   one H2 each.
2. Every factual claim in the brief carries an inline source link; `grep -c "](http"` is at
   least the number of claims counted in the review.
3. Each vendor section has a pricing row; an unknown price says "not published", never blank.
4. An independent review scores the brief at least 80, and its report sits beside the brief.
5. The recommendation names one vendor and the two facts that decided it.
6. The person who asked for the brief approves it; the approval is quoted in the log.

## Phase skeleton

```
1. Scope: the vendor list and the questions, approved before research starts
2-7. MAP: one phase per vendor (or per batch of 2-3), notes written to disk
8. REDUCE: comparison table from the notes only
9. Draft the brief
10. Independent review (a different reviewer from the drafter)
11. Revise against the review
12. Approval gate
```

## Failure modes

| Failure | Mitigation |
|---|---|
| Context runs out mid-synthesis | MAP notes on disk; REDUCE reads notes, not sources |
| The last source read dominates the conclusion | Map-reduce even below the line threshold when sources overlap |
| The drafter's own review passes the draft | The review is run by a different principal and bound to the draft's bytes |
| Citations point at pages that do not say the claim | Spot-check five citations in the review phase |
