"""paths.py -- which paths are final deliverables, and which are drafts.

The table is deliberately tiny. Point it at your own layout with the environment variable
HARNESS_DELIVERABLES (comma-separated globs, repo-relative).

Why not fnmatch: Python's fnmatch has no recursive `**`, so "a/**/b/*.md" never matches the
way you expect. Here `**` matches across directories and `*` stays inside one.

The trap this module also handles: `**` compiles to `.*` and the `/` before the tail is
literal, so `deliverables/**/*.md` needs at least one subdirectory and silently misses
`deliverables/memo.md`. Every `/**/` pattern therefore also gets its direct-child form.
"""
import os
import re

DEFAULT_DELIVERABLES = ["deliverables/**/*.md"]
WORKSPACE_DIR = "_workspace"


def glob_to_regex(pattern):
    out, i = [], 0
    while i < len(pattern):
        if pattern.startswith("**", i):
            out.append(".*")
            i += 2
        elif pattern[i] == "*":
            out.append("[^/]*")
            i += 1
        else:
            out.append(re.escape(pattern[i]))
            i += 1
    return re.compile("^" + "".join(out) + "$", re.IGNORECASE)


def expand_recursive_tails(patterns):
    out = []
    for p in patterns:
        out.append(p)
        if "/**/" in p:
            direct = p.replace("/**/", "/", 1)
            if direct not in patterns and direct not in out:
                out.append(direct)
    return out


def deliverable_patterns():
    raw = os.environ.get("HARNESS_DELIVERABLES", "")
    pats = [p.strip() for p in raw.split(",") if p.strip()] or DEFAULT_DELIVERABLES
    return [glob_to_regex(p) for p in expand_recursive_tails(pats)]


def repo_rel(path, project_dir):
    """Repo-relative, forward-slash path. Absolute paths outside the project stay absolute."""
    p = (path or "").replace("\\", "/")
    root = (project_dir or "").replace("\\", "/").rstrip("/")
    if root and p.lower().startswith(root.lower() + "/"):
        p = p[len(root) + 1:]
    while p.startswith("./"):
        p = p[2:]
    return p


def is_workspace(rel):
    return ("/" + rel.replace("\\", "/") + "/").find("/" + WORKSPACE_DIR + "/") != -1


def is_deliverable(rel):
    rel = rel.replace("\\", "/")
    if is_workspace(rel):
        return False
    return any(rx.match(rel) for rx in deliverable_patterns())
