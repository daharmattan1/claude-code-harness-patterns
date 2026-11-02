#!/usr/bin/env python3
"""post_read_token_ledger.py -- PostToolUse on Read | Edit | Write: what the session actually read.

Adds up the characters each Read returned and each Edit or Write sent, per session, in a
temp file. Print a session's totals with:

    python hooks/post_read_token_ledger.py --report <session_id>

Payload note: the Read result arrives as tool_response.file.content. Older keys
(tool_output, tool_response.text) are kept as fallbacks; if the payload shape changes and
none match, the ledger records 0 for that read rather than guessing.
"""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))
import hook_io  # noqa: E402

CHARS_PER_TOKEN = 4
AVG_LINE_CHARS = 40  # only when a large Read reports a line count but elides the content


def ledger_path(session_id):
    safe = "".join(c for c in session_id if c.isalnum() or c in "-_")[:64] or "default"
    return os.path.join(tempfile.gettempdir(), "claude_token_ledger_%s.json" % safe)


def load(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {"total_read_chars": 0, "total_write_chars": 0, "read_count": 0,
                "write_count": 0, "files_read": {}}


def read_chars(payload):
    resp = payload.get("tool_response")
    if isinstance(resp, dict):
        f = resp.get("file")
        if isinstance(f, dict):
            if isinstance(f.get("content"), str) and f["content"]:
                return len(f["content"])
            lines = f.get("numLines") or f.get("totalLines")
            if isinstance(lines, int) and lines > 0:
                return lines * AVG_LINE_CHARS
        for key in ("content", "text", "output", "stdout"):
            if isinstance(resp.get(key), str) and resp[key]:
                return len(resp[key])
    elif isinstance(resp, str):
        return len(resp)
    legacy = payload.get("tool_output")
    return len(legacy) if isinstance(legacy, str) else 0


def handle(payload):
    tool = payload.get("tool_name", "")
    if tool not in ("Read", "Edit", "Write"):
        return None
    path = ledger_path(payload.get("session_id", "default"))
    led = load(path)
    ti = payload.get("tool_input") or {}
    fp = (ti.get("file_path", "") or "").replace("\\", "/")
    if tool == "Read":
        n = read_chars(payload)
        led["total_read_chars"] += n
        led["read_count"] += 1
        led["files_read"][fp] = led["files_read"].get(fp, 0) + n
    else:
        led["total_write_chars"] += len(ti.get("new_string", "") or ti.get("content", "") or "")
        led["write_count"] += 1
    with open(path, "w", encoding="utf-8") as f:
        json.dump(led, f)
    return None


def report(session_id):
    led = load(ledger_path(session_id))
    top = sorted(led["files_read"].items(), key=lambda kv: -kv[1])[:10]
    lines = ["reads: %d (~%s tokens)  writes: %d (~%s tokens)" % (
        led["read_count"], "{:,}".format(led["total_read_chars"] // CHARS_PER_TOKEN),
        led["write_count"], "{:,}".format(led["total_write_chars"] // CHARS_PER_TOKEN))]
    lines += ["  ~{:>8,} tok  {}".format(n // CHARS_PER_TOKEN, p) for p, n in top]
    return "\n".join(lines)


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--report":
        print(report(sys.argv[2]))
        sys.exit(0)
    hook_io.run(handle)
