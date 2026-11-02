#!/usr/bin/env python3
"""pre_read_token_estimate.py -- PreToolUse on Read: what a read will cost, before it happens.

Injects an estimated token count for large files and flags re-reads of the same file in
this session. It never blocks. A re-read is often fine; the third one usually means the
agent lost track of what it already has.

State lives in a per-session temp file, so nothing is written to the repo.
"""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))
import hook_io  # noqa: E402

CHARS_PER_TOKEN = 4
AVG_LINE_CHARS = 80
REPORT_FROM_TOKENS = 500


def tracker_path(session_id):
    safe = "".join(c for c in session_id if c.isalnum() or c in "-_")[:64] or "default"
    return os.path.join(tempfile.gettempdir(), "claude_reads_%s.json" % safe)


def load(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def as_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def handle(payload):
    if payload.get("tool_name") != "Read":
        return None
    ti = payload.get("tool_input") or {}
    fp = ti.get("file_path", "")
    if not fp or not os.path.isfile(fp):
        return None
    size = os.path.getsize(fp)
    est = size
    limit, offset = as_int(ti.get("limit")), as_int(ti.get("offset"))
    if limit:
        est = min(size, limit * AVG_LINE_CHARS)
    if offset:
        est = max(0, est - offset * AVG_LINE_CHARS)
    tokens = max(1, est // CHARS_PER_TOKEN)

    path = tracker_path(payload.get("session_id", "default"))
    reads = load(path)
    key = fp.replace("\\", "/")
    seen = reads.get(key, 0)
    reads[key] = seen + 1
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(reads, f)
    except OSError:
        pass

    parts = []
    if tokens >= REPORT_FROM_TOKENS:
        parts.append("~{:,} tokens ({:,} bytes)".format(tokens, size))
    if seen >= 1:
        parts.append("re-read #%d this session" % (seen + 1))
    if seen >= 2:
        parts.append("check whether you already have what you need")
    if not parts:
        return None
    return hook_io.context("PreToolUse", "[token-estimate] %s: %s" % (os.path.basename(fp), "; ".join(parts)))


if __name__ == "__main__":
    hook_io.run(handle)
