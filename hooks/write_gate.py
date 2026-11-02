#!/usr/bin/env python3
"""write_gate.py -- PreToolUse tripwire on Write | Edit | MultiEdit for final deliverables.

What it checks, on a write to a deliverable path (lib/paths.py):
  1. Placeholder markers left in the text.
  2. A long-form NEW deliverable written directly. A direct Write can never carry
     provenance: the sidecar is stamped by promote.py from the bytes it promoted. So the
     only legitimate route is draft in _workspace/, then promote.
And on any path:
  3. A drafter subagent writing a verdict or provenance artifact (a review report, a
     .review.json, a .provenance.json). The drafter grading its own work is the failure
     this whole folder exists to catch. Uses `agent_type` from the payload.

SHADOW by default: it logs what it would block to .claude/logs/write_gate_shadow.jsonl and
lets the write through. Set WRITE_GATE_ENFORCING=1 to deny instead. Run it in shadow,
read the log, then flip it.

What it does NOT cover (read ../docs/ before trusting it): a Bash `cp` or `python -c`
writing the same path never reaches this hook; a top-level agent can forge a sidecar; and
if `agent_type` is absent the drafter check does not fire. It is a tripwire, not a wall.
"""
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))
import hook_io  # noqa: E402
from paths import is_deliverable, repo_rel  # noqa: E402
from provenance import has_valid_provenance  # noqa: E402

LONGFORM_CHARS = 9000
PLACEHOLDER_RE = re.compile(r"\bTODO\b|\bFIXME\b|\{slot\}|\[PLACEHOLDER\]|\blorem ipsum\b", re.I)  # decontam:allow
VERDICT_BASENAMES = {"review_report.md", "review.md", "verdict.md"}
VERDICT_SUFFIXES = (".review.json", ".provenance.json")


def drafter_agents():
    raw = os.environ.get("HARNESS_DRAFTER_AGENTS", "drafter")
    return {a.strip() for a in raw.split(",") if a.strip()}


def project_dir(payload):
    return os.environ.get("CLAUDE_PROJECT_DIR") or payload.get("cwd") or os.getcwd()


def is_verdict_artifact(path):
    base = os.path.basename((path or "").replace("\\", "/")).lower()
    return base in VERDICT_BASENAMES or base.endswith(VERDICT_SUFFIXES)


def post_edit_text(tool_name, tool_input):
    """Text the file will hold after the call, or the edited region if the file is unreadable."""
    if tool_name == "Write":
        return tool_input.get("content", "")
    edits = tool_input.get("edits") if tool_name == "MultiEdit" else [tool_input]
    try:
        with open(tool_input.get("file_path", ""), encoding="utf-8", errors="replace") as f:
            text = f.read()
    except OSError:
        return "\n".join(e.get("new_string", "") for e in edits or [])
    for e in edits or []:
        old, new = e.get("old_string", ""), e.get("new_string", "")
        text = text.replace(old, new) if e.get("replace_all") else text.replace(old, new, 1)
    return text


def changed_text(tool_name, tool_input):
    if tool_name == "Write":
        return tool_input.get("content", "")
    edits = tool_input.get("edits") if tool_name == "MultiEdit" else [tool_input]
    return "\n".join(e.get("new_string", "") for e in edits or [])


def analyze(tool_name, tool_input, agent_type, proj):
    """Return a list of reasons this write would be blocked (empty list = clean)."""
    fp = tool_input.get("file_path", "")
    if agent_type and agent_type in drafter_agents() and is_verdict_artifact(fp):
        return ["drafter %r may not author a verdict or provenance artifact (%s); a reviewer "
                "that is not the drafter writes those" % (agent_type, os.path.basename(fp))]
    rel = repo_rel(fp, proj)
    if not is_deliverable(rel):
        return []
    reasons = []
    # Only markers this write ADDS count, for every tool: a typo fix next to a marker someone
    # else left, or an Edit whose replacement keeps a marker already in old_string, is not
    # what this check is for.
    marks = {m.group(0) for m in PLACEHOLDER_RE.finditer(changed_text(tool_name, tool_input))}
    if tool_name == "Write" and os.path.isfile(fp):
        try:
            with open(fp, encoding="utf-8", errors="replace") as f:
                marks -= {m.group(0) for m in PLACEHOLDER_RE.finditer(f.read())}
        except OSError:
            pass
    elif tool_name in ("Edit", "MultiEdit"):
        edits = tool_input.get("edits") if tool_name == "MultiEdit" else [tool_input]
        old = "\n".join(e.get("old_string", "") for e in edits or [])
        marks -= {m.group(0) for m in PLACEHOLDER_RE.finditer(old)}
    marks = sorted(marks)
    if marks:
        reasons.append("placeholder markers present: " + ", ".join(marks))

    exists = os.path.isfile(fp)
    if exists and has_valid_provenance(fp):
        # A promoted deliverable edited in place no longer matches its sidecar, so it silently
        # stops counting as reviewed. Change the draft and re-promote instead.
        reasons.append("in-place edit of a promoted deliverable (%s) breaks its provenance; edit "
                       "the draft under _workspace/ and re-run promote.py --overwrite" % rel)
    full = post_edit_text(tool_name, tool_input)
    if len(full) >= LONGFORM_CHARS and not exists:
        reasons.append("long-form new deliverable written directly (%s); draft under _workspace/ "
                       "and run promote.py, which stamps provenance" % rel)
    return reasons


def handle(payload):
    tool_name = payload.get("tool_name", "")
    if tool_name not in ("Write", "Edit", "MultiEdit"):
        return None
    tool_input = payload.get("tool_input") or {}
    agent_type = payload.get("agent_type", "") or ""
    proj = project_dir(payload)
    reasons = analyze(tool_name, tool_input, agent_type, proj)
    if not reasons:
        return None
    enforcing = os.environ.get("WRITE_GATE_ENFORCING") == "1"
    hook_io.append_log(proj, "write_gate_shadow.jsonl", {"tool_name": tool_name, "file_path": tool_input.get("file_path", ""),
                      "agent_type": agent_type, "reasons": reasons,
                      "mode": "enforcing" if enforcing else "shadow"})
    if enforcing:
        return hook_io.deny("write_gate: " + "; ".join(reasons))
    return None


if __name__ == "__main__":
    hook_io.run(handle)
