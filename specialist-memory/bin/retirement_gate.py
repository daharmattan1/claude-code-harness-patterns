#!/usr/bin/env python3
"""retirement_gate.py -- find promoted learnings that have stopped doing anything.

Memory that only grows rots. This gate reads a specialist's run history and reports:

  * RETIREMENT CANDIDATES: watched learnings with zero evidenced uses in the last N runs
    (default 20). Watched means the promoted ids, plus every rule in learning_rules.jsonl
    when --rules is given, minus anything a person already listed in retired.json.
    Each learning is judged only after it has been loaded for N runs of its own, counted
    from the run that added it (`added_run`, stamped by commit_return.py) or the run it was
    promoted in (`since_run` in promoted.json). A rule added yesterday is never a candidate,
    however long the history is. A learning with no recorded start counts from the first run.
  * four rolling metrics over the last N runs:
      recurrence_decay     early-half miss rate minus late-half miss rate (>0: the misses
                           these learnings guard against are fading)
      passes_to_approval   average review passes before approval (lower is better)
      utilization          share of watched learnings used at least once
      first_draft_quality  average recorded first-draft score

A use counts only when it is EVIDENCED: the run record cites the output text the learning
shaped (`output_span`). An unevidenced "fired" claim counts for nothing in either direction.
Otherwise an always-loaded rule reads as 100% used, and the gate goes blind to exactly the
layer most likely to rot.

The gate flags; it never deletes. Retiring a learning is a person's call (see
../docs/consolidation-ritual.md).

Inputs:
  run_history.jsonl     one row per run, as written by commit_return.py:
                        {"run": "...", "passes_to_approval": 2, "first_draft_quality": 78,
                         "learnings_fired": [{"learning_id": "L1", "output_span": "..."}],
                         "axis_missed": ["tone"]}
  promoted.json         a JSON list of ids, or of {"learning_id": "L4", "since_run": "..."}
  learning_rules.jsonl  rules, each {"id": ..., "added_run": ...}
  retired.json          a JSON list of ids a person has retired; the specialist skips them too

Usage:
  python retirement_gate.py --history run_history.jsonl [--promotions promoted.json]
      [--rules learning_rules.jsonl] [--retired retired.json] [--window 20] [--out DIR]
  (at least one of --promotions or --rules)
  python retirement_gate.py --synthetic        self-test on a generated 20-run history
Exit: 0 no candidates, 1 at least one retirement candidate, 2 usage or IO error.
"""
import argparse
import json
import os
import sys
from collections import defaultdict

DEFAULT_WINDOW = 20


def load_jsonl(path):
    """Rows of a JSONL file. Malformed lines are skipped and COUNTED: a silently shorter
    history would quietly keep the window from filling."""
    rows, skipped = [], 0
    with open(path, encoding="utf-8") as f:
        for ln in f:
            ln = ln.strip()
            if not ln or ln.startswith("//"):
                continue
            try:
                d = json.loads(ln)
            except ValueError:
                skipped += 1
                continue
            if isinstance(d, dict) and "_schema" not in d:
                rows.append(d)
            elif not isinstance(d, dict):
                skipped += 1
    if skipped:
        print("warning: %d malformed line(s) skipped in %s" % (skipped, path), file=sys.stderr)
    return rows


def evidenced_uses(run):
    return [f for f in run.get("learnings_fired", [])
            if isinstance(f, dict) and (f.get("output_span") or "").strip()]


def _watched(promoted, rules, retired):
    """Ordered, de-duplicated (id, start_run) pairs, minus retired ids. A duplicated id must
    not count twice; the first start run recorded for an id wins."""
    retired = set(retired or ())
    order, since = [], {}
    for p in promoted or []:
        lid, start = ((p.get("learning_id") or p.get("id"), p.get("since_run"))
                      if isinstance(p, dict) else (p, None))
        if lid is not None and lid not in since:
            order.append(lid)
            since[lid] = start
    for r in rules or []:
        lid = r.get("id")
        if lid is None:
            continue
        if lid not in since:
            order.append(lid)
            since[lid] = r.get("added_run")
        elif since[lid] is None:
            since[lid] = r.get("added_run")
    return [(lid, since[lid]) for lid in order if lid not in retired]


def compute(history, promoted, window=DEFAULT_WINDOW, rules=None, retired=()):
    watched = _watched(promoted, rules, retired)
    win = history[-window:]
    n = len(win)
    uses = defaultdict(int)
    for run in win:
        for f in evidenced_uses(run):
            uses[f.get("learning_id")] += 1

    position = {}
    for i, run in enumerate(history):
        position.setdefault(run.get("run"), i)

    def loaded_for(start):
        """Runs since the learning arrived. The run that adds a rule never loaded it, so it
        does not count. An unknown start counts from the first run."""
        i = position.get(start) if start is not None else None
        return len(history) if i is None else len(history) - i - 1

    def avg(key):
        vals = [r[key] for r in win if isinstance(r.get(key), (int, float))]
        return round(sum(vals) / len(vals), 2) if vals else None

    def miss_rate(rows):
        return sum(len(r.get("axis_missed", [])) for r in rows) / max(1, len(rows))

    half = max(1, n // 2)
    ids = [lid for lid, _ in watched]
    metrics = {
        "recurrence_decay": round(miss_rate(win[:half]) - miss_rate(win[half:]), 3) if n >= 2 else None,
        "passes_to_approval": avg("passes_to_approval"),
        "utilization": (round(sum(1 for lid in ids if uses[lid]) / len(ids), 3)
                        if ids else None),
        "first_draft_quality": avg("first_draft_quality"),
    }
    candidates, too_new = [], []
    for lid, start in watched:
        if loaded_for(start) < window:
            too_new.append(lid)
        elif uses[lid] == 0:
            candidates.append({"learning_id": lid, "evidenced_uses": 0})
    return {"window": n, "window_full": n >= window, "metrics": metrics,
            "watched": len(ids), "too_new_to_judge": too_new,
            "retirement_candidates": candidates, "uses": dict(uses)}


def synthetic_history():
    """20 runs. L1 is used every run, L2 every other run, L3 only ever claimed WITHOUT evidence."""
    hist = []
    for i in range(1, 21):
        fired = [{"learning_id": "L1", "output_span": "span %d a" % i}]
        if i % 2 == 0:
            fired.append({"learning_id": "L2", "output_span": "span %d b" % i})
        fired.append({"learning_id": "L3"})  # claimed, no evidence: must not save it
        hist.append({"run": "r%d" % i, "passes_to_approval": 3 if i <= 10 else 2,
                     "first_draft_quality": 70 + i // 2, "learnings_fired": fired,
                     "axis_missed": ["angle"] if i <= 10 else []})
    return hist, ["L1", "L2", "L3"]


def _load_list(path):
    with open(path, encoding="utf-8") as f:
        val = json.load(f)
    if not isinstance(val, list):
        raise ValueError("%s must be a JSON list" % path)
    return val


def main(argv=None):
    ap = argparse.ArgumentParser(description="Flag learnings with no evidenced use.")
    ap.add_argument("--history")
    ap.add_argument("--promotions", help="JSON list of promoted learning ids")
    ap.add_argument("--rules", help="learning_rules.jsonl: watch every rule, not only promoted ones")
    ap.add_argument("--retired", help="JSON list of ids a person has already retired")
    ap.add_argument("--window", type=int, default=DEFAULT_WINDOW)
    ap.add_argument("--out", help="directory to write retirement_candidates.json into")
    ap.add_argument("--synthetic", action="store_true")
    a = ap.parse_args(argv)

    rules, retired = None, []
    if a.synthetic:
        history, promoted = synthetic_history()
    else:
        if not a.history or not (a.promotions or a.rules):
            ap.print_usage(sys.stderr)
            print("--history and at least one of --promotions or --rules are required",
                  file=sys.stderr)
            return 2
        try:
            history = load_jsonl(a.history)
            promoted = _load_list(a.promotions) if a.promotions else []
            rules = load_jsonl(a.rules) if a.rules else None
            retired = _load_list(a.retired) if a.retired else []
        except (OSError, ValueError) as exc:
            print("cannot read input: %s" % exc, file=sys.stderr)
            return 2

    res = compute(history, promoted, a.window, rules=rules, retired=retired)
    print(json.dumps(res, indent=2, ensure_ascii=False))
    if a.out:
        os.makedirs(a.out, exist_ok=True)
        with open(os.path.join(a.out, "retirement_candidates.json"), "w", encoding="utf-8") as f:
            json.dump({"retirement_candidates": res["retirement_candidates"],
                       "metrics": res["metrics"], "window": res["window"]}, f, indent=2)
    if not res["window_full"]:
        print("window not full (%d of %d runs): retirement is not decidable yet"
              % (res["window"], a.window), file=sys.stderr)
    return 1 if res["retirement_candidates"] else 0


if __name__ == "__main__":
    sys.exit(main())
