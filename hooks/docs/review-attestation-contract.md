# Review attestation contract

What `lib/review_attestation.py` and `promote.py` agree on.

## The problem it closes

"A review report exists next to the draft" and "a reviewer read these exact bytes and said
PASS" are different claims. The first is easy to satisfy by accident:

- the drafting agent writes its own `review_report.md` with a good score, or
- a clean review runs, and then someone edits the draft before it is promoted.

Either way, a check that trusts the report's existence promotes work nobody reviewed.

## The sidecar

The reviewer writes it, from the bytes it reviewed, through `write_attestation()`. The drafting
agent never writes it: `write_gate.py` denies a drafter-type agent writing any `.review.json`,
`.provenance.json` or review report (enforcing mode).

Location: `<draft>.review.json`, next to the draft.

```json
{
  "reviewed_file": "_workspace/memo/draft.md",
  "reviewed_sha256": "<sha256 of the reviewed bytes>",
  "reviewer": "independent-reviewer",
  "verdict": "PASS",
  "reviewed_at": "2026-10-22T13:58:02Z",
  "principal": "independent-reviewer",
  "notes": ""
}
```

`verdict` is `PASS` or `FAIL`. Recognized reviewers are listed in `KNOWN_REVIEWERS`; an unknown
name is not rejected on its own, and a caller can require a specific one.

## The predicate

`has_valid_review(draft, content=None, required_reviewer=None)` returns `(ok, reason)`. It is
ok only when the sidecar exists, names a reviewer, says PASS, and its `reviewed_sha256` matches
the bytes being promoted. Pass `content`, the exact string about to be promoted, so an edit made
after the review is caught even if the file on disk were swapped back.

Each failure has its own reason: no sidecar, no reviewer, no valid verdict, a FAIL verdict, or
STALE (the draft changed after the review).

## Where it is enforced

`promote.py` checks it for long-form drafts (9,000 characters or more). By default it only logs
the result to `.claude/logs/promote_review_shadow.jsonl` and promotes anyway. Set
`PROMOTE_REQUIRE_REVIEW=1` to refuse a long-form promotion without a valid attestation. When
the attestation is valid, the promoter copies it into the provenance sidecar so the audit trail
survives promotion.

## The tests

`tests/test_pattern_pack.py` covers: a self-written review report is refused, a stale
attestation is refused, the drafter cannot write the sidecar or a report, a reviewer can, and a
real attestation promotes (the over-block guard). The forgery tests were mutation-tested: with
a predicate that trusts any review file, both promotion forgery tests fail.

## What it does not prevent

Reviewer identity is procedural, not cryptographic. A top-level agent with a shell can write a
hash-matched PASS record itself. That is now a deliberate act, visible in review, rather than a
side effect of the normal flow; it is not impossible. And a PASS records a judgment, not that
the judgment was right.
