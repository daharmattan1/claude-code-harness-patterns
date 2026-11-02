#!/usr/bin/env python3
"""commit_return.py -- write a specialist's returned reflection into its memory bundle.

A specialist agent never writes its own memory. It does its work, then RETURNS a manifest:

    {"author": "toy-specialist", "run": "2026-10-22-review-1",
     "evolution_entry": "first-person note on what happened",
     "learning_rules": [{"id": "L4", "rule": "...", "source": "...", "confidence": "medium"}],
     "passes_to_approval": 2, "first_draft_quality": 78,
     "learnings_fired": [{"learning_id": "L1", "output_span": "the exact text it shaped"}],
     "axis_missed": ["tone"],
     "promotion_candidates": [{"learning_id": "L4", "why": "..."}]}

The orchestrator (a different principal) runs this script to commit it:
  * appends the entry to evolution_log.md and the rules to learning_rules.jsonl (JSONL:
    append-only, so two runs never clobber each other in a merge), each stamped with the
    run that added it (`added_run`)
  * logs one row to run_history.jsonl, the record the retirement gate reads
  * queues promotion candidates in pending_promotions.jsonl. Nothing is ever promoted to a
    shared file automatically; a person approves promotions
  * refuses to write any protected path (shared files several agents read)
  * refuses a manifest whose declared author equals the declared committer

Honest scope of that last check: a command-line script cannot see who called it, so it
compares two declared names. It catches the mistake of an agent committing its own return.
It does not stop a determined caller. The real wall is that the specialist's tool list has no
shell, so it cannot run this script at all.

Usage:
  python commit_return.py --bundle memory/toy-specialist --manifest return.json \\
      [--committer orchestrator] [--protect path ...] [--core-cap 12]
Exit: 0 committed, 1 refused, 2 bad input.
"""
import argparse
import json
import os
import re
import sys
from datetime import date

CORE_CAP_DEFAULT = 12
PROTECT_FILE = "protected_paths.txt"   # optional, in the bundle's parent dir: one path per line


def _norm(path):
    """One spelling per file: resolves symlinks, and folds case where the OS does."""
    return os.path.normcase(os.path.realpath(os.path.abspath(path)))


def _protected(bundle, extra):
    paths = list(extra or [])
    pf = os.path.join(os.path.dirname(os.path.abspath(bundle)), PROTECT_FILE)
    if os.path.isfile(pf):
        with open(pf, encoding="utf-8") as f:
            paths += [ln.strip() for ln in f if ln.strip() and not ln.startswith("#")]
    return {_norm(p) for p in paths}


def _validate(manifest):
    """Reject a malformed manifest before anything is written."""
    if not isinstance(manifest, dict):
        raise ValueError("manifest must be a JSON object")
    for key in ("learning_rules", "learnings_fired", "promotion_candidates"):
        val = manifest.get(key)
        if val is not None and not (isinstance(val, list) and all(isinstance(x, dict) for x in val)):
            raise ValueError("%s must be a list of objects" % key)
    axis = manifest.get("axis_missed")
    if axis is not None and not (isinstance(axis, list) and all(isinstance(x, str) for x in axis)):
        raise ValueError("axis_missed must be a list of strings")
    entry = manifest.get("evolution_entry")
    if entry is not None and not isinstance(entry, str):
        raise ValueError("evolution_entry must be a string")


def core_truths(bundle):
    """Operating-truth bullets in core_memory.md (lines starting with '- **')."""
    p = os.path.join(bundle, "core_memory.md")
    if not os.path.isfile(p):
        return []
    with open(p, encoding="utf-8") as f:
        return [ln for ln in f if re.match(r"^\s*-\s+\*\*", ln)]


def commit_return(bundle, manifest, committer="orchestrator", protect=None,
                  core_cap=CORE_CAP_DEFAULT, today=None):
    """Commit a returned manifest. Returns a summary dict; raises ValueError / PermissionError."""
    author = (manifest.get("author") or "").strip()
    if not author:
        raise ValueError("manifest has no 'author'; the specialist must name itself")
    if author == committer:
        raise PermissionError("refused: author %r is also the committer; a specialist does not "
                              "commit its own memory" % author)
    if not os.path.isdir(bundle):
        raise ValueError("bundle not found: %s" % bundle)
    _validate(manifest)
    protected = _protected(bundle, protect)
    today = today or date.today().isoformat()
    run = manifest.get("run") or today

    # Build every write first, check every target, then write: a refusal never leaves a
    # half-committed return behind (a retry would otherwise append the reflection twice).
    writes = []
    entry = (manifest.get("evolution_entry") or "").strip()
    if entry:
        writes.append(("evolution_log.md", "\n### %s: %s\n%s\n" % (today, run, entry)))
    # Stamp each rule with the run that added it, so the retirement gate can wait until a
    # rule has had a full window to fire before judging it.
    rules = [dict(r, added_run=r.get("added_run") or run)
             for r in (manifest.get("learning_rules") or [])]
    if rules:
        writes.append(("learning_rules.jsonl",
                       "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rules)))
    row = {
        "run": run,
        "committed_by": committer,
        "passes_to_approval": manifest.get("passes_to_approval"),
        "first_draft_quality": manifest.get("first_draft_quality"),
        "learnings_fired": manifest.get("learnings_fired") or [],
        "axis_missed": manifest.get("axis_missed") or [],
        "logged": today,
    }
    writes.append(("run_history.jsonl", json.dumps(row, ensure_ascii=False) + "\n"))
    candidates = manifest.get("promotion_candidates") or []
    if candidates:
        recs = [dict(c, author=author, status="pending human approval", captured=today)
                for c in candidates]
        writes.append(("pending_promotions.jsonl",
                       "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in recs)))

    targets = [(os.path.join(bundle, name), text) for name, text in writes]
    for path, _ in targets:
        if _norm(path) in protected:
            raise PermissionError("refused: %s is a protected shared file; nothing was written" % path)
    for path, text in targets:
        with open(path, "a", encoding="utf-8", newline="\n") as f:
            f.write(text)

    truths = len(core_truths(bundle))
    return {"run": run, "rules_added": len(rules), "candidates_queued": len(candidates),
            "core_truths": truths, "core_over_cap": truths > core_cap}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Commit a specialist's returned reflection.")
    ap.add_argument("--bundle", required=True, help="the specialist's memory directory")
    ap.add_argument("--manifest", required=True, help="the returned JSON manifest")
    ap.add_argument("--committer", default=os.environ.get("HARNESS_COMMITTER", "orchestrator"))
    ap.add_argument("--protect", action="append", default=[], help="a shared path never to write")
    ap.add_argument("--core-cap", type=int, default=CORE_CAP_DEFAULT)
    a = ap.parse_args(argv)
    try:
        with open(a.manifest, encoding="utf-8") as f:
            manifest = json.load(f)
    except (OSError, ValueError) as exc:
        print("bad manifest: %s" % exc, file=sys.stderr)
        return 2
    try:
        res = commit_return(a.bundle, manifest, a.committer, a.protect, a.core_cap)
    except PermissionError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps(res))
    if res["core_over_cap"]:
        print("core_memory.md holds %d operating truths (cap %d): time for the consolidation "
              "ritual. Nothing was trimmed." % (res["core_truths"], a.core_cap), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
