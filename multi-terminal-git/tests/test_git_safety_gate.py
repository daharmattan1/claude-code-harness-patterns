"""Tests for git_safety_gate.py. Run: pytest multi-terminal-git/tests

Each case named `bug_*` is a bypass or over-block found in an earlier version of this gate.
Each `allow_*` case is a negative control: a command the gate must let through.
"""
import json
import os
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "hooks"))
import git_safety_gate as gate  # noqa: E402

GATE = os.path.join(os.path.dirname(__file__), "..", "hooks", "git_safety_gate.py")


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    monkeypatch.delenv("ALLOW_NEW_WORKTREE", raising=False)
    monkeypatch.delenv("GIT_GATE_STRICT", raising=False)


def bash(cmd):
    return gate.check({"tool_name": "Bash", "tool_input": {"command": cmd}})


def pwsh(cmd):
    return gate.check({"tool_name": "PowerShell", "tool_input": {"command": cmd}})


def denied(out):
    return bool(out) and out["hookSpecificOutput"]["permissionDecision"] == "deny"


# ---- bypasses found in earlier versions -------------------------------------------------

@pytest.mark.parametrize("cmd", [
    "cd sub && git checkout main",             # bug: only commands starting with git were checked
    "git -C ../other checkout main",            # bug: -C hid the subcommand
    "git push -u origin main",                  # bug: regex missed flags before the remote
    "git push origin HEAD:main",                # bug: regex missed refspecs
    "git push origin +feature:refs/heads/main",
    'bash -c "git checkout main"',
    "FOO=1 git switch master",
    'git push origin main "oops',               # unbalanced quote must still be checked
])
def test_bug_bypasses_are_denied(cmd):
    assert denied(bash(cmd)), cmd


@pytest.mark.parametrize("cmd", [
    "git checkout main -- README.md",           # bug: file restore was treated as a switch
    "git checkout HEAD~1 -- src/app.py",
    "git commit -m 'never run git checkout main here'",   # bug: quoted text was matched
    "gh pr create --body 'step 1: git worktree add ../x'",
    "cat > note.md <<'EOF'\nrun git worktree add ../x, then git checkout main\nEOF",  # bug: heredoc body
    # A body line that IS a command in form must still be data: only stripping saves it.
    "cat > note.md <<'EOF'\ngit checkout main\ngit worktree add ../x\nEOF",
    "cat <<-EOF > note.md\n\tgit push origin main\n\tEOF",
])
def test_bug_over_blocks_are_allowed(cmd):
    assert bash(cmd) is None, cmd


# ---- worktrees -----------------------------------------------------------------------

@pytest.mark.parametrize("cmd", [
    "git worktree add ../wt -b work/x",
    "bash scripts/newwork.sh my-slug",          # bug: the gate looked for a flag newwork does not have
    "scripts/newwork.sh my-slug --sparse",
])
def test_worktree_creation_denied(cmd):
    assert denied(bash(cmd)), cmd


def test_newwork_without_slug_is_a_drift_report():
    assert bash("bash scripts/newwork.sh") is None


def test_allow_new_worktree_prefix():
    assert bash("ALLOW_NEW_WORKTREE=1 git worktree add ../wt") is None


def test_allow_new_worktree_env(monkeypatch):
    monkeypatch.setenv("ALLOW_NEW_WORKTREE", "1")
    assert bash("git worktree add ../wt") is None


def test_enter_worktree_tool_denied():
    assert denied(gate.check({"tool_name": "EnterWorktree", "tool_input": {}}))


def test_subagent_worktree_isolation_denied():
    assert denied(gate.check({"tool_name": "Agent", "tool_input": {"isolation": "worktree"}}))
    assert gate.check({"tool_name": "Agent", "tool_input": {"prompt": "x"}}) is None


# ---- PowerShell ----------------------------------------------------------------------

def test_powershell_switch_denied():
    assert denied(pwsh("Set-Location sub; git checkout main"))


def test_powershell_herestring_is_data():
    assert pwsh("$m = @'\ngit checkout main\n'@\ngit commit -m $m") is None


def test_powershell_windows_paths_survive():
    assert pwsh(r"git -C C:\repo\sub status") is None


# ---- strict mode -----------------------------------------------------------------------

STRICT = ["git reset --hard", "git clean -fd", "git stash", "git stash push -m wip",
          "git stash -m wip", "git stash --patch", "git stash --keep-index",
          "git restore src/a.py", "git restore --staged --worktree a.py", "git checkout -- .",
          "git checkout ."]


@pytest.mark.parametrize("cmd", STRICT)
def test_strict_off_by_default(cmd):
    assert bash(cmd) is None, cmd


@pytest.mark.parametrize("cmd", STRICT)
def test_strict_on_denies(monkeypatch, cmd):
    monkeypatch.setenv("GIT_GATE_STRICT", "1")
    assert denied(bash(cmd)), cmd


@pytest.mark.parametrize("cmd", ["git stash list", "git stash show -p", "git stash pop", "git restore --staged a.py",
                                 "git reset --soft HEAD~1", "git clean -n"])
def test_strict_allows_non_destructive(monkeypatch, cmd):
    monkeypatch.setenv("GIT_GATE_STRICT", "1")
    assert bash(cmd) is None, cmd


# ---- negative controls ---------------------------------------------------------------

@pytest.mark.parametrize("cmd", [
    "git status", "git checkout -b feature/x", "git switch -c feature/x",
    "git push origin feature/x", "git log --oneline main",
    "git diff main...HEAD", "git commit -m 'msg' -- a.py b.py", "ls && git fetch origin",
])
def test_ordinary_commands_allowed(cmd):
    assert bash(cmd) is None, cmd


def test_other_tools_ignored():
    assert gate.check({"tool_name": "Read", "tool_input": {"file_path": "x"}}) is None


# ---- the real process ----------------------------------------------------------------

def run_gate(stdin):
    return subprocess.run([sys.executable, GATE], input=stdin, capture_output=True, text=True)


def test_subprocess_deny_shape():
    p = run_gate(json.dumps({"tool_name": "Bash", "tool_input": {"command": "git checkout main"}}))
    assert p.returncode == 0
    assert json.loads(p.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"


@pytest.mark.parametrize("stdin", ["", "not json", "[1,2]"])
def test_subprocess_fails_open(stdin):
    p = run_gate(stdin)
    assert p.returncode == 0 and p.stdout == ""


# ---- pushes with no refspec push the CURRENT branch -------------------------------------

def git_repo(path, branch):
    subprocess.run(["git", "init", "-q", "-b", branch, str(path)], check=True)
    return str(path)


def bash_in(cmd, cwd):
    return gate.check({"tool_name": "Bash", "cwd": cwd, "tool_input": {"command": cmd}})


@pytest.mark.parametrize("cmd", ["git push", "git push origin", "git push -u origin HEAD", "git push origin @"])
def test_bare_push_from_main_denied(tmp_path, cmd):
    assert denied(bash_in(cmd, git_repo(tmp_path / "r", "main"))), cmd


@pytest.mark.parametrize("cmd", ["git push", "git push origin", "git push -u origin HEAD"])
def test_bare_push_from_feature_allowed(tmp_path, cmd):
    assert bash_in(cmd, git_repo(tmp_path / "r", "feature-x")) is None, cmd


@pytest.mark.parametrize("cmd", ["git push --all origin", "git push --mirror origin"])
def test_push_all_and_mirror_denied(tmp_path, cmd):
    assert denied(bash_in(cmd, git_repo(tmp_path / "r", "feature-x"))), cmd


def test_dash_c_points_the_branch_lookup(tmp_path):
    feature = git_repo(tmp_path / "f", "feature-x")
    main_repo = git_repo(tmp_path / "m", "main")
    assert denied(bash_in("git -C %s push" % main_repo.replace("\\", "/"), feature))
