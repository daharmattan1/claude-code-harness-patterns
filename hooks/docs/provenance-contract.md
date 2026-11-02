# Provenance contract

What `lib/provenance.py`, `promote.py` and `write_gate.py` agree on.

## The sidecar

`promote.py` writes it, after it has replaced the target, from the exact bytes it promoted.
The drafting agent never writes it: a sidecar the author writes for itself proves nothing.

Location: `<deliverable>.provenance.json`, next to the deliverable.

```json
{
  "target_file": "deliverables/memo.md",
  "target_sha256": "<sha256 of the promoted bytes>",
  "promoted_at": "2026-10-22T14:03:11Z",
  "promoter": "promote.py",
  "workspace_draft": "_workspace/memo/draft.md",
  "artifacts": [],
  "review_attestation": { "...": "copied from the draft's .review.json, when there was one" }
}
```

## The predicate

`has_valid_provenance(path)` is true when all three hold:

1. `<path>.provenance.json` exists and parses.
2. Its `promoter` is the trusted promoter (`promote.py`).
3. Its `target_sha256` equals the sha256 of the file's current bytes.

The link between draft and deliverable is the explicit `workspace_draft` and `target_file`
pair the promoter was given. Nothing guesses it from folder names.

## Freshness

Any edit to the deliverable changes its bytes and invalidates the sidecar until the draft is
changed and promoted again (`promote.py --overwrite`). `write_gate.py` reports an in-place edit
of a promoted deliverable for exactly this reason: the edit would leave the file looking
reviewed when the reviewed bytes are gone.

## What it proves, and what it does not

It proves the trusted promoter stamped these exact bytes, and that nobody has changed them since.

It does not prove:

- **Who wrote the sidecar.** It is a plain JSON file. Anything holding a Write tool or a shell can
  compute a hash and write `"promoter": "promote.py"`. The field is a convention, not a signature.
  What it buys is that drift is caught, and that a forgery has to be a deliberate, visible act
  rather than an accident. An unforgeable version needs the promoter to sign with a key the
  drafting agent cannot read; that is not built here.
- **That the work is good.** A sidecar says a step ran. Whether its judgment was right is still a
  person's call.
- **Anything about files written by a shell command.** A `cp` onto a deliverable path never passes
  through the write gate. The defense there is the promotion boundary: the drafting agent's tool
  list has no shell.
