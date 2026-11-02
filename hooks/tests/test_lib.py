"""Tests for hooks/lib: hook_io, provenance, review_attestation. Run: pytest hooks/tests"""
import io
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lib"))

import hook_io  # noqa: E402
import provenance as pv  # noqa: E402
import review_attestation as ra  # noqa: E402


# ---- hook_io -------------------------------------------------------------------------

def test_read_payload_parses_json():
    assert hook_io.read_payload(io.StringIO('{"tool_name": "Bash"}')) == {"tool_name": "Bash"}


@pytest.mark.parametrize("raw", ["", "   ", "not json", "[1, 2]"])
def test_read_payload_fails_open_to_empty_dict(raw):
    assert hook_io.read_payload(io.StringIO(raw)) == {}


@pytest.mark.parametrize("decision", ["allow", "deny", "ask"])
def test_pretool_decision_shape(decision):
    out = hook_io.pretool_decision(decision, "why")["hookSpecificOutput"]
    assert out == {"hookEventName": "PreToolUse", "permissionDecision": decision,
                   "permissionDecisionReason": "why"}


def test_pretool_decision_rejects_unknown_value():
    with pytest.raises(ValueError):
        hook_io.pretool_decision("block", "why")


def test_block_is_top_level():
    assert hook_io.block("tests must pass") == {"decision": "block", "reason": "tests must pass"}


def test_warn_user_is_system_message():
    assert hook_io.warn_user("heads up") == {"systemMessage": "heads up"}


def test_context_carries_event_name():
    out = hook_io.context("SessionStart", "hello")
    assert out["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    assert out["hookSpecificOutput"]["additionalContext"] == "hello"


@pytest.mark.parametrize("event", ["PreCompact", "PostCompact", "SessionEnd"])
def test_context_refuses_events_that_drop_it(event):
    with pytest.raises(ValueError):
        hook_io.context(event, "would be silently discarded")


def test_run_fails_open_and_exits_zero(monkeypatch, capsys):
    monkeypatch.setattr(sys, "stdin", io.StringIO("{}"))

    def boom(_):
        raise RuntimeError("bad")

    with pytest.raises(SystemExit) as exc:
        hook_io.run(boom)
    assert exc.value.code == 0
    assert "failed open" in json.loads(capsys.readouterr().out)["systemMessage"]


# ---- provenance ----------------------------------------------------------------------

def test_provenance_valid_then_stale_after_edit(tmp_path):
    f = tmp_path / "doc.md"
    f.write_text("final text", encoding="utf-8")
    pv.write_sidecar(str(f), "doc.md", "final text", "_workspace/doc.md")
    assert pv.has_valid_provenance(str(f))
    f.write_text("final text, edited after promotion", encoding="utf-8")
    assert not pv.has_valid_provenance(str(f))


def test_provenance_rejects_wrong_promoter(tmp_path):
    f = tmp_path / "doc.md"
    f.write_text("x", encoding="utf-8")
    sc = {"promoter": "someone-else", "target_sha256": pv.sha256_bytes("x")}
    (tmp_path / "doc.md.provenance.json").write_text(json.dumps(sc), encoding="utf-8")
    assert not pv.has_valid_provenance(str(f))


def test_provenance_missing_sidecar(tmp_path):
    f = tmp_path / "doc.md"
    f.write_text("x", encoding="utf-8")
    assert not pv.has_valid_provenance(str(f))


# ---- review_attestation --------------------------------------------------------------

def test_review_valid_pass(tmp_path):
    d = tmp_path / "draft.md"
    d.write_text("reviewed body", encoding="utf-8")
    ra.write_attestation(str(d), "reviewed body", reviewer="independent-reviewer", verdict="PASS")
    ok, reason = ra.has_valid_review(str(d), content="reviewed body")
    assert ok, reason


def test_review_stale_after_hand_edit(tmp_path):
    d = tmp_path / "draft.md"
    ra.write_attestation(str(d), "original", reviewer="independent-reviewer", verdict="PASS")
    d.write_text("original plus a sentence added after review", encoding="utf-8")
    ok, reason = ra.has_valid_review(str(d))
    assert not ok and "STALE" in reason


def test_review_fail_verdict_is_not_a_pass(tmp_path):
    d = tmp_path / "draft.md"
    ra.write_attestation(str(d), "body", reviewer="independent-reviewer", verdict="FAIL")
    ok, reason = ra.has_valid_review(str(d), content="body")
    assert not ok and "FAIL" in reason


def test_review_required_reviewer(tmp_path):
    d = tmp_path / "draft.md"
    ra.write_attestation(str(d), "body", reviewer="editor", verdict="PASS")
    ok, _ = ra.has_valid_review(str(d), content="body", required_reviewer="cross-model-review")
    assert not ok


def test_review_missing_sidecar(tmp_path):
    ok, reason = ra.has_valid_review(str(tmp_path / "nothing.md"), content="x")
    assert not ok and "no review attestation" in reason


def test_write_attestation_rejects_bad_verdict(tmp_path):
    with pytest.raises(ValueError):
        ra.write_attestation(str(tmp_path / "d.md"), "x", reviewer="editor", verdict="LGTM")
