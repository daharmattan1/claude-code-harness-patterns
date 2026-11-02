"""review_attestation.py -- a review verdict bound to the exact bytes it reviewed.

See ../docs/review-attestation-contract.md for the contract.

"A review file exists" and "a reviewer read THESE bytes and said PASS" are different claims.
The first is easy to fake by accident: a drafter can write its own review report, or edit
the draft after a clean review. This module records the second.

  provenance.py         written AFTER promotion, from the promoted bytes, by the promoter.
  review_attestation.py written BEFORE promotion, from the draft bytes, by a reviewer that
                        is not the drafter.

Honest limit: reviewer identity is procedural, not cryptographic. The hash binding catches
edits after review; it cannot prove who wrote the record.
"""
import json
import time

from provenance import sha256_bytes, sha256_file  # one hashing implementation for both sidecars

SIDECAR_SUFFIX = ".review.json"

# Reviewer names this repo recognizes. An unknown name is not rejected on its own (a typo
# should not hard-fail a promotion), but callers can require a specific reviewer.
KNOWN_REVIEWERS = {
    "independent-reviewer",
    "cross-model-review",
    "buyer-review",
    "editor",
}

VALID_VERDICTS = {"PASS", "FAIL"}


def sidecar_path(draft_path):
    return draft_path + SIDECAR_SUFFIX


def read_attestation(draft_path):
    try:
        with open(sidecar_path(draft_path), "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def has_valid_review(draft_path, content=None, required_reviewer=None):
    """Return (ok, reason).

    ok is True iff an attestation exists, names a reviewer, says PASS, and its
    reviewed_sha256 matches the bytes being promoted. Pass `content` (the exact string
    about to be promoted) so an edit made after the review is caught even if the file
    on disk was swapped back.
    """
    att = read_attestation(draft_path)
    if not att:
        return False, "no review attestation sidecar found"
    reviewer = att.get("reviewer", "")
    verdict = att.get("verdict", "")
    if not reviewer:
        return False, "attestation missing 'reviewer' field"
    if required_reviewer and reviewer != required_reviewer:
        return False, "attestation reviewer %r != required %r" % (reviewer, required_reviewer)
    if verdict not in VALID_VERDICTS:
        return False, "attestation has no valid verdict (got: %r)" % (verdict,)
    if verdict != "PASS":
        return False, "attestation verdict is %s, not PASS" % verdict
    cur = sha256_bytes(content) if content is not None else sha256_file(draft_path)
    if not cur:
        return False, "could not hash the current bytes"
    if att.get("reviewed_sha256", "") != cur:
        return False, ("attestation is STALE: the draft changed after the review ran; "
                       "re-review required")
    return True, "valid"


def write_attestation(draft_path, reviewed_content, reviewer, verdict,
                      principal="", notes="", reviewed_at=None):
    """Write the attestation from the exact bytes reviewed. Called by the reviewer, never the drafter."""
    if verdict not in VALID_VERDICTS:
        raise ValueError("verdict must be one of %s, got %r" % (sorted(VALID_VERDICTS), verdict))
    record = {
        "reviewed_file": draft_path.replace("\\", "/"),
        "reviewed_sha256": sha256_bytes(reviewed_content),
        "reviewer": reviewer,
        "verdict": verdict,
        "reviewed_at": reviewed_at or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "principal": principal or reviewer,
        "notes": notes,
    }
    with open(sidecar_path(draft_path), "w", encoding="utf-8") as f:
        json.dump(record, f, indent=2)
    return record
