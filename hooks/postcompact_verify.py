#!/usr/bin/env python3
"""postcompact_verify.py -- after a compaction, tell the session which plan it was on.

Register on SessionStart with matcher "compact". (PostCompact cannot inject context; the
hooks reference lists the events that honor additionalContext and it is not one of them.)

The rule this hook exists for: recovery is bound to THIS session. With several terminals
on one working tree, "the plan file modified most recently" is routinely another
terminal's plan. So the hook reads the tail of this session's own transcript and takes
the last plan path it mentions. If the transcript names none, it says so and does not
guess: an honest "unknown" is recoverable, a confident wrong answer is an instruction to
work on someone else's plan.

HARNESS_PLAN_GLOB sets which files count as active plans (default plans/*_active.md).
"""
import glob
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))
import hook_io  # noqa: E402
from paths import glob_to_regex  # noqa: E402

TAIL_BYTES = 1_000_000  # transcripts reach hundreds of MB; the plan in play is named near the end


def plan_glob():
    return os.environ.get("HARNESS_PLAN_GLOB", "plans/*_active.md")


def plan_from_transcript(transcript_path, proj):
    if not transcript_path or not os.path.isfile(transcript_path):
        return None
    try:
        size = os.path.getsize(transcript_path)
        with open(transcript_path, "rb") as fh:
            if size > TAIL_BYTES:
                fh.seek(size - TAIL_BYTES)
            tail = fh.read().decode("utf-8", errors="replace")
    except OSError:
        return None
    tail = tail.replace("\\\\", "/").replace("\\", "/")
    # A transcript is free text: keep `*` and `**` from running across spaces, quotes or
    # brackets, or one match could swallow two paths.
    stop = "\\s\"'`()<>|,"
    body = (glob_to_regex(plan_glob()).pattern.strip("^$")
            .replace("[^/]*", "[^/" + stop + "]*")
            .replace(".*", "[^" + stop + "]*"))
    for rel in reversed(re.findall("(" + body + ")", tail, re.I)):
        if os.path.isfile(os.path.join(proj, rel)):
            return rel
    return None


def current_branch(proj):
    try:
        out = subprocess.run(["git", "branch", "--show-current"], capture_output=True,
                             text=True, timeout=5, cwd=proj)
        return out.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def handle(payload):
    if payload.get("hook_event_name") not in (None, "SessionStart"):
        return None
    if payload.get("source") != "compact":
        return None
    proj = payload.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    parts = []
    branch = current_branch(proj)
    if branch:
        parts.append("Current branch: %s" % branch)
    plan = plan_from_transcript(payload.get("transcript_path"), proj)
    if plan:
        parts.append("Active plan for THIS session: %s (read from this session's transcript, "
                     "not file times). Re-read its state before continuing." % plan)
    else:
        n = len(glob.glob(os.path.join(proj, plan_glob())))
        parts.append("Active plan: UNKNOWN. This session's transcript names none, and %d active "
                     "plans exist in a tree other terminals may share. Ask which plan before "
                     "resuming plan work." % n)
    return hook_io.context("SessionStart", "AFTER COMPACTION: " + " ".join(parts))


if __name__ == "__main__":
    hook_io.run(handle)
