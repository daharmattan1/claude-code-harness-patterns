#!/usr/bin/env python3
"""git_safety_gate.py -- PreToolUse on Bash | PowerShell (+ Agent | Task | EnterWorktree).

Several terminals building on one shared branch share one working tree and one index. In
that setup a few ordinary git commands destroy other people's work. This hook denies them:

  * switching to an existing branch (`git checkout main`, `git switch main`): the shared
    tree changes under every other terminal. Creating a branch (`-b`) and restoring a file
    (`git checkout <ref> -- <path>`) are allowed.
  * pushing to main or master in any form (`origin main`, `-u origin main`, `HEAD:main`,
    `+x:refs/heads/main`).
  * creating a worktree (`git worktree add`, `newwork.sh <slug>`, EnterWorktree, a subagent
    with isolation "worktree") unless ALLOW_NEW_WORKTREE=1 is set. Worktrees are full
    checkouts and nothing deletes them; see reap-worktrees.sh.
  * with GIT_GATE_STRICT=1, also the commands that discard work in place: `reset --hard`,
    `clean -f`, `stash` (push/save), `restore` of the working tree, `checkout -- .`.

How it reads a command: heredoc bodies (and PowerShell here-strings) are dropped as data,
the rest is tokenized with quotes respected and split on shell operators, and every simple
command is checked on its own. So `cd x && git checkout main` and `git -C x checkout main`
are caught, and text that merely mentions a command (a commit message, a PR body, a note
written through a heredoc) is not. `bash -c "..."` and `pwsh -Command "..."` are checked
recursively.

What it cannot see: a script, Makefile, alias or `python -c` that runs git internally.
It is a tripwire for agents, not a sandbox. It fails open on any internal error.
"""
import json
import os
import re
import shlex
import subprocess
import sys

PROTECTED = ("main", "master")
_SEP = "();<>|&\n`"
_PS_SEP = _SEP.replace("`", "")
_PWSH = {"pwsh", "pwsh.exe", "powershell", "powershell.exe"}
_SHELLS = {"bash", "sh", "zsh", "bash.exe", "sh.exe"}
_WRAPPERS = {"env", "command", "exec", "nohup", "sudo", "time", "builtin"}
_NEWWORK = re.compile(r"^newwork(?:\.sh|\.ps1)?$", re.I)
_HEREDOC = re.compile(r"(?<![<\w])<<(-?)\s*(['\"]?)([A-Za-z_][\w.-]*)\2")
_PS_HERESTRING = re.compile(r"@(['\"])[ \t]*\r?\n.*?\r?\n\1@", re.S)

WORKTREE_MSG = (
    "New worktree blocked. Each worktree is a full checkout and nothing removes them, so they "
    "pile up. Build in place on the shared checkout. If a new worktree is really wanted, run "
    "the command with ALLOW_NEW_WORKTREE=1 and plan its cleanup (reap-worktrees.sh).")
SWITCH_MSG = (
    "Branch switching blocked (target: %s). Every terminal shares this working tree, so a "
    "switch changes files under all of them. Create a branch with `git checkout -b <name>`, "
    "restore a file with `git checkout <ref> -- <path>`, or land with land-to-main.sh.")
PUSH_MSG = "Pushing to main/master blocked. Push a feature branch and open a PR."
STRICT_MSG = ("`%s` discards uncommitted work in a tree other terminals share "
              "(GIT_GATE_STRICT=1). Commit by pathspec instead, or do this in your own worktree.")


# ---- output ---------------------------------------------------------------------------

def deny(reason):
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                   "permissionDecision": "deny",
                                   "permissionDecisionReason": reason}}


# ---- parsing --------------------------------------------------------------------------

def strip_heredocs(command):
    out, pending = [], []
    for line in command.split("\n"):
        if pending:
            if line.strip() == pending[0]:
                pending.pop(0)
            continue
        out.append(line)
        pending = [m.group(3) for m in _HEREDOC.finditer(line)]
    return "\n".join(out)


def tokens(command, ps=False):
    seps = _PS_SEP if ps else _SEP
    try:
        lex = shlex.shlex(command, posix=True, punctuation_chars=seps)
        lex.whitespace = " \t\r"  # newline separates commands, so it is punctuation here
        lex.whitespace_split = True
        lex.commenters = ""
        if ps:
            lex.escape = "`"  # PowerShell escape; backslash stays a path character
        return list(lex)
    except ValueError:
        # Unbalanced quotes. Fall back to a plain split rather than skipping the check:
        # a typo must not turn `git push origin main` into an unchecked command.
        pat = r"[;&|()<>\n]+|[^\s;&|()<>]+" if ps else r"[;&|()<>`\n]+|[^\s;&|()<>`]+"
        return re.findall(pat, command)


def segments(command, ps=False):
    """Simple commands as word lists, redirections removed."""
    seps = _PS_SEP if ps else _SEP
    text = _PS_HERESTRING.sub("''", command) if ps else strip_heredocs(command)
    segs, cur, skip = [], [], False
    for t in tokens(text, ps):
        if skip:
            skip = False
            continue
        if t and all(c in seps for c in t):
            if "<" in t or ">" in t:  # a redirection: drop it and its target
                if cur and cur[-1].isdigit():
                    cur.pop()
                skip = True
                continue
            if cur:
                segs.append(cur)
            cur = []
            continue
        cur.append(t)
    if cur:
        segs.append(cur)
    return segs


def base(tok):
    return re.split(r"[\\/]", tok)[-1].lower()


def strip_prefix(seg):
    """Drop VAR=val assignments and wrappers. Returns (rest, allow_new_worktree)."""
    i, allow = 0, False
    while i < len(seg):
        t = seg[i]
        if re.match(r"^[A-Za-z_]\w*=", t):
            allow = allow or t == "ALLOW_NEW_WORKTREE=1"
            i += 1
        elif t in _WRAPPERS:
            i += 1
        else:
            break
    return seg[i:], allow


def parse_git(seg):
    """(subcommand, args, -C dir or None) for a segment whose first word is git, else None."""
    if not seg or base(seg[0]) not in ("git", "git.exe"):
        return None
    i, n, repo = 1, len(seg), None
    while i < n:
        t = seg[i]
        if t == "-C" and i + 1 < n:
            repo = seg[i + 1]
            i += 2
        elif t in ("-c", "--git-dir", "--work-tree", "--namespace") and i + 1 < n:
            i += 2
        elif t.startswith("-"):
            i += 1
        else:
            break
    return (seg[i], seg[i + 1:], repo) if i < n else None


def current_branch(cwd):
    try:
        out = subprocess.run(["git", "branch", "--show-current"], capture_output=True,
                             text=True, timeout=5, cwd=cwd or None)
        return out.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def positionals(args):
    return [a for a in args if a == "-" or not a.startswith("-")]


# ---- rules ----------------------------------------------------------------------------

def checkout_target(sub, args):
    """The branch a checkout/switch would move the tree to, or None."""
    if sub == "checkout":
        if "--" in args or any(a in ("-b", "-B", "--orphan") for a in args):
            return None
    elif any(a in ("-c", "-C", "--create", "--force-create", "--orphan")
             or a.startswith(("--create=", "--force-create=")) for a in args):
        return None
    pos = positionals(args)
    if not pos or pos[0] == ".":  # `git checkout .` restores files; strict mode judges it
        return None
    return pos[0]


def pushes_to_protected(args, cwd=None):
    """True if this push would update main/master on the remote.

    Explicit refspecs are checked by destination. With no refspec, git pushes the current
    branch (push.default simple/current/upstream), so that branch is what matters. --all
    and --mirror push every branch, main included.
    """
    if any(a in ("--all", "--mirror", "--branches") for a in args):
        return True
    pos, i = [], 0
    while i < len(args):
        a = args[i]
        if a in ("-o", "--push-option", "--receive-pack", "--exec", "--repo"):
            i += 2
            continue
        if a == "-" or not a.startswith("-"):
            pos.append(a)
        i += 1
    if len(pos) <= 1:  # `git push` or `git push <remote>`: the current branch goes
        return current_branch(cwd) in PROTECTED
    for spec in pos[1:]:  # pos[0] is the remote
        src, _, dst = spec.lstrip("+").rpartition(":")
        dst = dst or src
        if dst in ("HEAD", "@"):
            dst = current_branch(cwd)
        if dst.startswith("refs/heads/"):
            dst = dst[len("refs/heads/"):]
        if dst in PROTECTED:
            return True
    return False


def strict_violation(sub, args):
    """Commands that discard uncommitted work in place. Checked only with GIT_GATE_STRICT=1."""
    if sub == "reset" and "--hard" in args:
        return "git reset --hard"
    if sub == "clean" and any(a.startswith("-") and "f" in a.lstrip("-") and not a.startswith("--")
                              or a == "--force" for a in args):
        return "git clean -f"
    # Allowlist, not denylist: any stash form that is not read-only or a re-apply saves and
    # clears working-tree changes (`stash -m wip`, `stash -p`, `stash --keep-index` ...).
    if sub == "stash" and (not args or args[0] not in ("list", "show", "apply", "pop", "branch",
                                                       "drop", "clear", "create", "store")):
        return "git stash"
    if sub == "restore" and "--staged" not in args and "-S" not in args:
        return "git restore"
    if sub == "restore" and any(a in ("--worktree", "-W") for a in args):
        return "git restore --worktree"
    if sub == "checkout" and "--" in args and "." in args[args.index("--") + 1:]:
        return "git checkout -- ."
    if sub == "checkout" and args in (["."], ["-f"], ["--force"]):
        return "git checkout " + " ".join(args)
    return None


def newwork_creates_worktree(seg):
    if not seg:
        return False
    first = base(seg[0])
    if _NEWWORK.match(first):
        idx = 0
    elif first in _SHELLS | _PWSH | {"&", "."}:
        idx = next((k for k, t in enumerate(seg) if _NEWWORK.match(base(t))), None)
        if idx is None:
            return False
    else:
        return False
    return any(not a.startswith("-") or a.lower().startswith("-slug") for a in seg[idx + 1:])


def check_segment(seg, depth=0, cwd=None):
    seg, allow_wt = strip_prefix(seg)
    if not seg:
        return None
    allow_wt = allow_wt or os.environ.get("ALLOW_NEW_WORKTREE") == "1"

    first = base(seg[0])
    if depth < 3 and first in _SHELLS | _PWSH:
        for flag in ("-c", "-Command", "-command"):
            if flag in seg[1:-1]:
                inner = seg[seg.index(flag, 1) + 1]
                for s in segments(inner, ps=first in _PWSH):
                    r = check_segment(s, depth + 1, cwd)
                    if r:
                        return r

    if not allow_wt and newwork_creates_worktree(seg):
        return WORKTREE_MSG
    parsed = parse_git(seg)
    if not parsed:
        return None
    sub, args, repo = parsed
    if repo:
        cwd = repo if os.path.isabs(repo) or not cwd else os.path.join(cwd, repo)
    if sub == "worktree" and args[:1] == ["add"] and not allow_wt:
        return WORKTREE_MSG
    if sub in ("checkout", "switch"):
        target = checkout_target(sub, args)
        if target:
            return SWITCH_MSG % target
    if sub == "push" and pushes_to_protected(args, cwd):
        return PUSH_MSG
    if os.environ.get("GIT_GATE_STRICT") == "1":
        what = strict_violation(sub, args)
        if what:
            return STRICT_MSG % what
    return None


def check(payload):
    """Return a deny dict, or None to allow."""
    tool = payload.get("tool_name", "")
    ti = payload.get("tool_input") or {}
    allow_wt = os.environ.get("ALLOW_NEW_WORKTREE") == "1"
    if tool == "EnterWorktree" and not allow_wt:
        return deny(WORKTREE_MSG)
    if tool in ("Agent", "Task") and str(ti.get("isolation", "")).lower() == "worktree" and not allow_wt:
        return deny(WORKTREE_MSG + " For a subagent: drop isolation \"worktree\" and give it "
                    "files no other agent is touching.")
    if tool not in ("Bash", "PowerShell"):
        return None
    ps = tool == "PowerShell"
    cwd = payload.get("cwd") or None
    for seg in segments(ti.get("command", "") or "", ps):
        reason = check_segment(seg, cwd=cwd)
        if reason:
            return deny(reason)
    return None


def main():
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
        out = check(payload if isinstance(payload, dict) else {})
        if out:
            sys.stdout.write(json.dumps(out))
    except Exception:
        pass  # fail open: a broken gate must not take the session down
    sys.exit(0)


if __name__ == "__main__":
    main()
