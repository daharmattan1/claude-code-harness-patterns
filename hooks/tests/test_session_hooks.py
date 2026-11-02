"""Tests for dispatch_guard, postcompact_verify and the token pair. Run: pytest hooks/tests

Each hook has at least one negative control: a payload it must let through untouched.
"""
import json
import os
import subprocess
import sys

import pytest

HOOKS = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, HOOKS)
sys.path.insert(0, os.path.join(HOOKS, "lib"))

import dispatch_guard  # noqa: E402
import post_read_token_ledger as ledger  # noqa: E402
import postcompact_verify  # noqa: E402
import pre_read_token_estimate as estimate  # noqa: E402


@pytest.fixture(autouse=True)
def clean_env(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    for var in ("DISPATCH_REQUIRE_MODEL", "DISPATCH_GUARD_SHADOW", "HARNESS_PLAN_GLOB"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr("tempfile.tempdir", str(tmp_path))


# ---- dispatch_guard ------------------------------------------------------------------

def dispatch(prompt, agent="general-purpose", model=None):
    ti = {"prompt": prompt, "subagent_type": agent}
    if model:
        ti["model"] = model
    return {"tool_name": "Agent", "tool_input": ti}


def ledger_rows(tmp_path):
    p = tmp_path / ".claude" / "logs" / "dispatch_ledger.jsonl"
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines()]


def test_dispatch_without_verifier_is_denied(tmp_path):
    out = dispatch_guard.handle(dispatch("Summarize the repo."))
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert ledger_rows(tmp_path)[-1]["verifier"] == "MISSING"


@pytest.mark.parametrize("prompt", [
    "Fix the parser. Your verifier: pytest exits 0.",
    "Count rows. Done when the CSV has 47 rows.",
    "Draft it. Acceptance criteria: under 300 words.",
])
def test_dispatch_with_verifier_passes(tmp_path, prompt):
    assert dispatch_guard.handle(dispatch(prompt)) is None
    assert ledger_rows(tmp_path)[-1]["status"] == "allowed"


def test_explicit_none_is_allowed_and_logged(tmp_path):
    assert dispatch_guard.handle(dispatch("Brainstorm names. verifier: none (taste call)")) is None
    assert ledger_rows(tmp_path)[-1]["verifier"] == "bypassed"


def test_model_floor_is_opt_in(monkeypatch):
    prompt = "Your verifier: tests pass."
    assert dispatch_guard.handle(dispatch(prompt)) is None
    monkeypatch.setenv("DISPATCH_REQUIRE_MODEL", "1")
    assert dispatch_guard.handle(dispatch(prompt))["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert dispatch_guard.handle(dispatch(prompt, model="sonnet")) is None
    assert dispatch_guard.handle(dispatch(prompt, agent="my-reviewer")) is None


def test_shadow_mode_never_denies(monkeypatch):
    monkeypatch.setenv("DISPATCH_GUARD_SHADOW", "1")
    assert dispatch_guard.handle(dispatch("no check named")) is None


def test_other_tools_ignored():
    assert dispatch_guard.handle({"tool_name": "Bash", "tool_input": {"command": "ls"}}) is None


# ---- postcompact_verify --------------------------------------------------------------

@pytest.fixture
def repo(tmp_path):
    (tmp_path / "plans").mkdir()
    for name in ("mine_active.md", "theirs_active.md"):
        (tmp_path / "plans" / name).write_text("plan", encoding="utf-8")
    return tmp_path


def compact_payload(repo, transcript_text, source="compact"):
    t = repo / "transcript.jsonl"
    t.write_text(transcript_text, encoding="utf-8")
    return {"hook_event_name": "SessionStart", "source": source, "cwd": str(repo),
            "transcript_path": str(t)}


def test_names_the_plan_from_this_sessions_transcript(repo):
    os.utime(repo / "plans" / "theirs_active.md", (2_000_000_000, 2_000_000_000))  # newest on disk
    out = postcompact_verify.handle(compact_payload(
        repo, '{"text": "working on plans/mine_active.md now"}\n'))
    ctx = out["hookSpecificOutput"]["additionalContext"]
    assert out["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    assert "plans/mine_active.md" in ctx and "theirs" not in ctx


def test_last_mention_wins(repo):
    out = postcompact_verify.handle(compact_payload(
        repo, "read plans/theirs_active.md earlier\nthen switched to plans/mine_active.md\n"))
    assert "plans/mine_active.md" in out["hookSpecificOutput"]["additionalContext"]


def test_windows_paths_in_transcript(repo):
    out = postcompact_verify.handle(compact_payload(repo, '"C:\\\\repo\\\\plans\\\\mine_active.md"'))
    assert "plans/mine_active.md" in out["hookSpecificOutput"]["additionalContext"]


def test_unknown_when_transcript_names_no_plan(repo):
    ctx = postcompact_verify.handle(compact_payload(repo, "no plan mentioned"))[
        "hookSpecificOutput"]["additionalContext"]
    assert "UNKNOWN" in ctx and "mine_active" not in ctx and "theirs_active" not in ctx


def test_ignores_startup_and_resume(repo):
    assert postcompact_verify.handle(compact_payload(repo, "plans/mine_active.md", source="startup")) is None
    assert postcompact_verify.handle(compact_payload(repo, "plans/mine_active.md", source="resume")) is None


def test_reads_branch_from_git(repo):
    if subprocess.run(["git", "--version"], capture_output=True).returncode != 0:
        pytest.skip("git not available")
    subprocess.run(["git", "init", "-q", "-b", "feature-x"], cwd=repo, check=True)
    ctx = postcompact_verify.handle(compact_payload(repo, "x"))["hookSpecificOutput"]["additionalContext"]
    assert "feature-x" in ctx


# ---- token pair ----------------------------------------------------------------------

def read_payload(path, session="s1", **extra):
    ti = {"file_path": str(path)}
    ti.update(extra)
    return {"tool_name": "Read", "session_id": session, "tool_input": ti}


def test_small_first_read_is_silent(tmp_path):
    f = tmp_path / "small.txt"
    f.write_text("tiny", encoding="utf-8")
    assert estimate.handle(read_payload(f)) is None


def test_large_read_reports_tokens(tmp_path):
    f = tmp_path / "big.txt"
    f.write_text("x" * 40_000, encoding="utf-8")
    ctx = estimate.handle(read_payload(f))["hookSpecificOutput"]["additionalContext"]
    assert "10,000 tokens" in ctx


def test_rereads_are_flagged(tmp_path):
    f = tmp_path / "small.txt"
    f.write_text("tiny", encoding="utf-8")
    estimate.handle(read_payload(f))
    second = estimate.handle(read_payload(f))["hookSpecificOutput"]["additionalContext"]
    third = estimate.handle(read_payload(f))["hookSpecificOutput"]["additionalContext"]
    assert "re-read #2" in second and "already have" in third


def test_sessions_are_tracked_separately(tmp_path):
    f = tmp_path / "small.txt"
    f.write_text("tiny", encoding="utf-8")
    estimate.handle(read_payload(f, session="a"))
    assert estimate.handle(read_payload(f, session="b")) is None


def test_ledger_counts_reads_and_writes(tmp_path):
    ledger.handle({"tool_name": "Read", "session_id": "s", "tool_input": {"file_path": "a.md"},
                   "tool_response": {"file": {"content": "x" * 400}}})
    ledger.handle({"tool_name": "Read", "session_id": "s", "tool_input": {"file_path": "b.md"},
                   "tool_response": {"file": {"numLines": 10}}})
    ledger.handle({"tool_name": "Write", "session_id": "s",
                   "tool_input": {"file_path": "c.md", "content": "y" * 80}})
    led = ledger.load(ledger.ledger_path("s"))
    assert led["total_read_chars"] == 800 and led["read_count"] == 2
    assert led["total_write_chars"] == 80 and led["write_count"] == 1
    assert "reads: 2" in ledger.report("s")


def test_ledger_ignores_other_tools(tmp_path):
    ledger.handle({"tool_name": "Bash", "session_id": "s", "tool_input": {"command": "ls"}})
    assert ledger.load(ledger.ledger_path("s"))["read_count"] == 0


# ---- regression tests for the 2026-10-22 code review --------------------------------

def test_recursive_plan_glob_does_not_swallow_two_paths(repo, monkeypatch):
    monkeypatch.setenv("HARNESS_PLAN_GLOB", "plans/**/*_active.md")
    (repo / "plans" / "q4").mkdir()
    (repo / "plans" / "q4" / "deep_active.md").write_text("plan", encoding="utf-8")
    text = "see plans/notes.md then plans/q4/deep_active.md"
    ctx = postcompact_verify.handle(compact_payload(repo, text))["hookSpecificOutput"]["additionalContext"]
    assert "plans/q4/deep_active.md" in ctx


@pytest.mark.parametrize("limit", [None, "fifty", ""])
def test_odd_limit_values_do_not_raise(tmp_path, limit):
    f = tmp_path / "big.txt"
    f.write_text("x" * 40_000, encoding="utf-8")
    out = estimate.handle(read_payload(f, limit=limit))
    assert "tokens" in out["hookSpecificOutput"]["additionalContext"]
