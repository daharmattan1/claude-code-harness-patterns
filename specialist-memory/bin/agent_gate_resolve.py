#!/usr/bin/env python3
"""agent_gate_resolve.py -- check that every `**Agent Gate:** <type>` in a plan names a real agent.

A plan phase can say which persistent specialist does its work:

    **Agent Gate:** toy-specialist

The executor spawns that subagent type. If the name has a typo, the spawn fails late, or a
generic agent quietly does the work instead and the specialist's memory never grows. This
script resolves each gate against the agent definitions directory before the run starts.

It checks resolution only. It does not spawn anything.

Usage:
  python agent_gate_resolve.py <plan.md> [--agents-dir .claude/agents] [--assert <type>]
Exit: 0 every gate resolves (and --assert matched), 1 a gate does not resolve, 2 bad input.
"""
import argparse
import os
import re
import sys

GATE = re.compile(r"\*\*Agent Gate:\*\*\s*([A-Za-z0-9_-]+)")


def resolve(plan_path, agents_dir):
    """[(type, resolved)] for every Agent Gate line in the plan."""
    out = []
    with open(plan_path, encoding="utf-8") as f:
        for line in f:
            m = GATE.search(line)
            if m:
                t = m.group(1)
                out.append((t, os.path.isfile(os.path.join(agents_dir, t + ".md"))))
    return out


def find_agents_dir(plan_path):
    """The nearest .claude/agents above the plan, so the check works from any directory."""
    d = os.path.dirname(os.path.abspath(plan_path))
    while True:
        cand = os.path.join(d, ".claude", "agents")
        if os.path.isdir(cand):
            return cand
        parent = os.path.dirname(d)
        if parent == d:
            return os.path.join(".claude", "agents")
        d = parent


def main(argv=None):
    ap = argparse.ArgumentParser(description="Resolve Agent Gate lines against agent definitions.")
    ap.add_argument("plan")
    ap.add_argument("--agents-dir", default=os.environ.get("HARNESS_AGENTS_DIR"),
                    help="default: the nearest .claude/agents above the plan")
    ap.add_argument("--assert", dest="expect")
    a = ap.parse_args(argv)
    if not os.path.isfile(a.plan):
        print("plan not found: %s" % a.plan, file=sys.stderr)
        return 2
    a.agents_dir = a.agents_dir or find_agents_dir(a.plan)
    gates = resolve(a.plan, a.agents_dir)
    if not gates:
        print("no Agent Gate lines in %s" % os.path.basename(a.plan))
        return 1 if a.expect else 0
    bad = False
    for t, ok in gates:
        if ok:
            print("RESOLVED  %s -> %s" % (t, os.path.join(a.agents_dir, t + ".md")))
        else:
            print("MISSING   %s (no %s.md in %s)" % (t, t, a.agents_dir))
            bad = True
    if a.expect and a.expect not in [t for t, ok in gates if ok]:
        print("ASSERT FAIL: %s did not resolve" % a.expect)
        return 1
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
