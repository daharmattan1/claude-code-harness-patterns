#!/usr/bin/env python3
"""promote.py -- the only sanctioned way a draft becomes a final deliverable.

    python hooks/promote.py --draft _workspace/memo/draft.md --target deliverables/memo.md

It fails CLOSED (the write gate fails open; the two postures are opposite on purpose):
  * the draft must exist and live under _workspace/
  * the target must be a deliverable path (lib/paths.py)
  * placeholder markers refuse the promotion at any length
  * a long-form draft needs a valid review attestation (lib/review_attestation.py) bound to
    the exact bytes being promoted. Shadow by default: logged, not enforced, until
    PROMOTE_REQUIRE_REVIEW=1
  * an existing target is never overwritten without --overwrite
Then it replaces the target atomically and stamps a provenance sidecar from the promoted
bytes. The promoter is a different principal from the drafter: that separation is the
point.

Exit codes: 0 promoted, 2 bad invocation, 3 refused, 4 write failed.
"""
import argparse
import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))
import hook_io  # noqa: E402
import provenance as pv  # noqa: E402
import review_attestation as ra  # noqa: E402
from paths import is_deliverable, is_workspace, repo_rel  # noqa: E402
from write_gate import LONGFORM_CHARS, PLACEHOLDER_RE  # noqa: E402


def promote(draft, target, proj=None, overwrite=False, now=""):
    proj = proj or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    d_rel, t_rel = repo_rel(os.path.abspath(draft), proj), repo_rel(os.path.abspath(target), proj)
    if not os.path.isfile(draft):
        return 2, "draft not found: %s" % draft
    # A draft outside the project stays absolute after repo_rel: refuse it, so a file from
    # anywhere on disk cannot be stamped as if it came from this project's workspace.
    if os.path.isabs(d_rel) or not is_workspace(d_rel):
        return 2, "draft must live under a _workspace/ directory inside the project"
    if not is_deliverable(t_rel):
        return 2, "target is not a deliverable path: %s" % t_rel

    with open(draft, encoding="utf-8-sig", errors="replace") as f:
        content = f.read()

    marks = sorted({m.group(0) for m in PLACEHOLDER_RE.finditer(content)})
    if marks:
        return 3, "refused: placeholder markers present (%s)" % ", ".join(marks)

    review = None
    if len(content) >= LONGFORM_CHARS:
        ok, why = ra.has_valid_review(draft, content=content)
        enforcing = os.environ.get("PROMOTE_REQUIRE_REVIEW") == "1"
        hook_io.append_log(proj, "promote_review_shadow.jsonl", {"draft": d_rel, "target": t_rel, "review_valid": ok, "reason": why,
                    "mode": "enforcing" if enforcing else "shadow"})
        if enforcing and not ok:
            return 3, ("refused: long-form needs a valid review attestation, but %s. A review "
                       "report the drafter wrote is not a review." % why)
        if ok:
            review = ra.read_attestation(draft)

    if os.path.exists(target) and not overwrite:
        return 3, "refused: target exists (%s); pass --overwrite to republish" % t_rel

    os.makedirs(os.path.dirname(os.path.abspath(target)), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(os.path.abspath(target)), suffix=".tmp")
    try:
        # newline="" keeps the bytes identical to `content`, so the sidecar hash matches.
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            f.write(content)
        os.replace(tmp, target)
    except OSError as exc:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        return 4, "write failed: %s" % exc

    pv.write_sidecar(target, t_rel, content, d_rel, artifacts=[],
                     promoted_at=now or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                     review_attestation=review)
    return 0, "promoted %s -> %s (+ provenance sidecar)" % (d_rel, t_rel)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--draft", required=True)
    ap.add_argument("--target", required=True)
    ap.add_argument("--overwrite", action="store_true")
    a = ap.parse_args(argv)
    code, msg = promote(a.draft, a.target, overwrite=a.overwrite)
    print(msg, file=sys.stderr if code else sys.stdout)
    return code


if __name__ == "__main__":
    sys.exit(main())
