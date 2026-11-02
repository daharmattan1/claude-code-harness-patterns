#!/usr/bin/env python3
"""dispatch_guard.py -- PreToolUse on Agent | Task: every dispatch names its verifier.

A subagent that is not told how its work will be checked will pick the easiest check it
can pass. So a dispatch prompt must say what decides success: "Your verifier: the script
exits 0 and the CSV has 47 rows." If none applies, write `verifier: none (reason)`; that
is allowed, and it lands in the ledger, so the exception is visible later.

Every dispatch, allowed or denied, appends one row to .claude/logs/dispatch_ledger.jsonl:
the route, the verifier state and the model. That row survives a compaction; the
conversation that launched the subagent may not.

Optional cost floor: with DISPATCH_REQUIRE_MODEL=1, a dispatch to a generic built-in type
(general-purpose, Explore, Plan) must pass an explicit model, so its tier is a choice
rather than whatever the parent session runs.

DISPATCH_GUARD_SHADOW=1 logs denials without enforcing them. The hook fails open.
"""
import hashlib
import os
import re
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))
import hook_io  # noqa: E402

DISPATCH_TOOLS = {"Agent", "Task"}
GENERIC_TYPES = {"general-purpose", "Explore", "Plan", ""}
VERIFIER_RE = re.compile(
    r"your\s+verifier|verifier\s*[:=]|verified\s+by|verification\s*[:=]"
    r"|success\s+(?:is|criteri)|acceptance\s+criteri|must\s+exit\s+0|done\s+when|passes?\s+when",
    re.I)
BYPASS_RE = re.compile(r"verifier\s*:\s*none", re.I)

NO_VERIFIER = (
    "This dispatch names no verifier. Say what decides whether the work worked, so the "
    "subagent cannot swap in an easier check. Add one line, for example:\n"
    "  Your verifier: the script exits 0 and the CSV has 47 rows.\n"
    "If no check applies, write 'verifier: none (reason)'; it is allowed and logged.")
NO_MODEL = (
    "subagent_type %r carries no model of its own, so this dispatch would inherit the "
    "parent session's model. Pass an explicit model, or use an agent definition that "
    "pins one.")


def handle(payload):
    if payload.get("tool_name", "") not in DISPATCH_TOOLS:
        return None
    ti = payload.get("tool_input") or {}
    prompt = str(ti.get("prompt", "") or "")
    agent = ti.get("subagent_type") or ""
    model = ti.get("model") or ""
    bypassed = bool(BYPASS_RE.search(prompt))
    named = bypassed or bool(VERIFIER_RE.search(prompt))
    untiered = (os.environ.get("DISPATCH_REQUIRE_MODEL") == "1"
                and agent in GENERIC_TYPES and not model)
    allowed = named and not untiered
    now = datetime.now(timezone.utc)
    proj = os.environ.get("CLAUDE_PROJECT_DIR") or payload.get("cwd") or os.getcwd()
    hook_io.append_log(proj, "dispatch_ledger.jsonl", {
        "id": now.strftime("%Y%m%dT%H%M%S") + "-" + hashlib.sha1(prompt.encode("utf-8")).hexdigest()[:8],
        "ts": now.isoformat(),
        "agent": agent or "(unnamed)",
        "model": model or "(inherited)",
        "verifier": "bypassed" if bypassed else ("named" if named else "MISSING"),
        "status": "allowed" if allowed else "denied",
    })
    if allowed or os.environ.get("DISPATCH_GUARD_SHADOW") == "1":
        return None
    return hook_io.deny(NO_MODEL % (agent or "(none)") if untiered else NO_VERIFIER)


if __name__ == "__main__":
    hook_io.run(handle)
