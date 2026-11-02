"""hook_io.py -- one place for the Claude Code hook I/O contract.

Every hook in this folder reads a JSON payload on stdin and answers on stdout. Doing that
by hand in each hook is how the shapes drift: one hook forgets `hookEventName`, another
pairs a JSON deny with exit 2, a third prints plain text the runtime throws away. This
module keeps the contract in one file.

Rules encoded here (from the Claude Code hooks reference):
  * `hookSpecificOutput` always carries `hookEventName`.
  * A PreToolUse decision goes in `hookSpecificOutput.permissionDecision`
    (allow | deny | ask) with `permissionDecisionReason`, and the hook exits 0.
  * `additionalContext` is only honored on some events (CONTEXT_EVENTS below).
    PreCompact and PostCompact are NOT among them; re-inject context after a
    compaction from SessionStart, whose `source` is "compact".
  * A hook fails open: if it crashes, the tool call proceeds. A gate that can take
    the whole session down is worse than a gate with a hole.
"""
import json
import os
import sys

CONTEXT_EVENTS = {
    "SessionStart", "SubagentStart", "UserPromptSubmit", "PreToolUse", "PostToolUse",
    "PostToolUseFailure", "Stop", "SubagentStop",
}


def read_payload(stream=None):
    """Return the hook payload as a dict, or {} if stdin is empty or not JSON."""
    try:
        raw = (stream or sys.stdin).read()
        data = json.loads(raw) if raw.strip() else {}
        return data if isinstance(data, dict) else {}
    except (ValueError, OSError):
        return {}


def emit(obj, stream=None):
    (stream or sys.stdout).write(json.dumps(obj))
    (stream or sys.stdout).flush()


def pretool_decision(decision, reason):
    """Build a PreToolUse decision. decision is 'allow', 'deny' or 'ask'."""
    if decision not in ("allow", "deny", "ask"):
        raise ValueError("decision must be allow, deny or ask")
    return {"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": decision,
        "permissionDecisionReason": reason,
    }}


def deny(reason):
    return pretool_decision("deny", reason)


def block(reason):
    """Top-level block for Stop, SubagentStop, PostToolUse, UserPromptSubmit and PreCompact.
    (PreToolUse uses deny() instead.)"""
    return {"decision": "block", "reason": reason}


def context(event, text):
    """Inject text into Claude's context. Raises if the event cannot carry context."""
    if event not in CONTEXT_EVENTS:
        raise ValueError("%s does not accept additionalContext" % event)
    return {"hookSpecificOutput": {"hookEventName": event, "additionalContext": text}}


def warn_user(text):
    """A message shown to the user only (top-level systemMessage)."""
    return {"systemMessage": text}


def append_log(proj, name, record):
    """Append one JSON line to <proj>/.claude/logs/<name>. Never raises."""
    try:
        d = os.path.join(proj, ".claude", "logs")
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, name), "a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(record) + "\n")
    except OSError:
        pass


def run(handler):
    """Run handler(payload) -> dict | None. Emit its answer; always exit 0 (fail open)."""
    try:
        result = handler(read_payload())
        if result:
            emit(result)
    except Exception as exc:  # fail open, but say so where the user can see it
        try:
            emit(warn_user("hook error (failed open): %s" % exc))
        except Exception:
            pass
    sys.exit(0)
