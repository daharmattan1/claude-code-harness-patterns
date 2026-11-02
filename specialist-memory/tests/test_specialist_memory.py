"""Tests for commit_return, retirement_gate and agent_gate_resolve. Run: pytest specialist-memory/tests"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "bin"))
import agent_gate_resolve as agr  # noqa: E402
import commit_return as cr  # noqa: E402
import retirement_gate as rg  # noqa: E402


@pytest.fixture
def bundle(tmp_path):
    b = tmp_path / "memory" / "toy-specialist"
    b.mkdir(parents=True)
    (b / "core_memory.md").write_text("# Core\n- **Truth one.**\n- **Truth two.**\n", encoding="utf-8")
    for name in ("evolution_log.md", "learning_rules.jsonl", "run_history.jsonl"):
        (b / name).write_text("", encoding="utf-8")
    return b


def manifest(**over):
    m = {"author": "toy-specialist", "run": "r1", "evolution_entry": "I missed the tone twice.",
         "learning_rules": [{"id": "L4", "rule": "Read the brief's audience line first."}],
         "passes_to_approval": 2, "first_draft_quality": 78,
         "learnings_fired": [{"learning_id": "L1", "output_span": "the opening sentence"}],
         "axis_missed": ["tone"]}
    m.update(over)
    return m


# ---- commit_return -------------------------------------------------------------------

def test_commit_appends_log_rules_and_one_run_row(bundle):
    res = cr.commit_return(str(bundle), manifest(), today="2026-10-22")
    assert res["rules_added"] == 1
    assert "I missed the tone" in (bundle / "evolution_log.md").read_text(encoding="utf-8")
    rows = (bundle / "run_history.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(rows) == 1 and json.loads(rows[0])["committed_by"] == "orchestrator"


def test_appends_never_overwrite(bundle):
    cr.commit_return(str(bundle), manifest(run="r1"))
    cr.commit_return(str(bundle), manifest(run="r2"))
    rows = (bundle / "run_history.jsonl").read_text(encoding="utf-8").splitlines()
    assert [json.loads(r)["run"] for r in rows] == ["r1", "r2"]
    assert len((bundle / "learning_rules.jsonl").read_text(encoding="utf-8").splitlines()) == 2


def test_author_cannot_commit_its_own_return(bundle):
    with pytest.raises(PermissionError):
        cr.commit_return(str(bundle), manifest(), committer="toy-specialist")
    assert (bundle / "run_history.jsonl").read_text(encoding="utf-8") == ""


def test_manifest_must_name_its_author(bundle):
    with pytest.raises(ValueError):
        cr.commit_return(str(bundle), manifest(author=""))


def test_protected_file_is_never_written(bundle):
    with pytest.raises(PermissionError):
        cr.commit_return(str(bundle), manifest(), protect=[str(bundle / "learning_rules.jsonl")])


def test_protected_paths_file_is_honored(bundle):
    (bundle.parent / "protected_paths.txt").write_text(str(bundle / "evolution_log.md") + "\n",
                                                      encoding="utf-8")
    with pytest.raises(PermissionError):
        cr.commit_return(str(bundle), manifest())


def test_promotions_are_queued_not_applied(bundle):
    cr.commit_return(str(bundle), manifest(promotion_candidates=[{"learning_id": "L4", "why": "x"}]))
    q = json.loads((bundle / "pending_promotions.jsonl").read_text(encoding="utf-8"))
    assert q["status"] == "pending human approval" and q["author"] == "toy-specialist"


def test_core_over_cap_is_flagged_not_trimmed(bundle):
    core = bundle / "core_memory.md"
    core.write_text("".join("- **Truth %d.**\n" % i for i in range(14)), encoding="utf-8")
    before = core.read_text(encoding="utf-8")
    res = cr.commit_return(str(bundle), manifest())
    assert res["core_over_cap"] is True and core.read_text(encoding="utf-8") == before


def test_cli_exit_codes(bundle, tmp_path):
    good = tmp_path / "m.json"
    good.write_text(json.dumps(manifest()), encoding="utf-8")
    assert cr.main(["--bundle", str(bundle), "--manifest", str(good)]) == 0
    assert cr.main(["--bundle", str(bundle), "--manifest", str(good), "--committer", "toy-specialist"]) == 1
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    assert cr.main(["--bundle", str(bundle), "--manifest", str(bad)]) == 2


# ---- retirement_gate -----------------------------------------------------------------

def test_synthetic_flags_only_the_unevidenced_learning():
    hist, promoted = rg.synthetic_history()
    res = rg.compute(hist, promoted, window=20)
    assert [c["learning_id"] for c in res["retirement_candidates"]] == ["L3"]
    assert res["metrics"]["recurrence_decay"] > 0
    assert res["metrics"]["utilization"] == round(2 / 3, 3)


def test_unevidenced_use_does_not_count():
    hist = [{"run": "r%d" % i, "learnings_fired": [{"learning_id": "L1"}]} for i in range(20)]
    assert rg.compute(hist, ["L1"], 20)["retirement_candidates"] == [{"learning_id": "L1", "evidenced_uses": 0}]


def test_no_verdict_until_the_window_is_full():
    hist = [{"run": "r%d" % i, "learnings_fired": []} for i in range(5)]
    res = rg.compute(hist, ["L1"], 20)
    assert res["window_full"] is False and res["retirement_candidates"] == []


def test_only_the_last_window_counts():
    old = [{"run": "o%d" % i, "learnings_fired": [{"learning_id": "L1", "output_span": "x"}]} for i in range(10)]
    recent = [{"run": "n%d" % i, "learnings_fired": []} for i in range(20)]
    assert rg.compute(old + recent, ["L1"], 20)["retirement_candidates"]


def test_cli_requires_both_inputs(tmp_path):
    h = tmp_path / "h.jsonl"
    h.write_text("", encoding="utf-8")
    assert rg.main(["--history", str(h)]) == 2


def test_cli_end_to_end(tmp_path):
    hist, promoted = rg.synthetic_history()
    h = tmp_path / "h.jsonl"
    h.write_text("".join(json.dumps(r) + "\n" for r in hist), encoding="utf-8")
    p = tmp_path / "p.json"
    p.write_text(json.dumps(promoted), encoding="utf-8")
    assert rg.main(["--history", str(h), "--promotions", str(p), "--out", str(tmp_path / "o")]) == 1
    out = json.loads((tmp_path / "o" / "retirement_candidates.json").read_text(encoding="utf-8"))
    assert out["retirement_candidates"][0]["learning_id"] == "L3"


# ---- agent_gate_resolve --------------------------------------------------------------

def test_agent_gates_resolve_and_typos_fail(tmp_path):
    agents = tmp_path / "agents"
    agents.mkdir()
    (agents / "toy-specialist.md").write_text("---\nname: toy-specialist\n---\n", encoding="utf-8")
    plan = tmp_path / "plan.md"
    plan.write_text("**Agent Gate:** toy-specialist\n", encoding="utf-8")
    assert agr.main([str(plan), "--agents-dir", str(agents), "--assert", "toy-specialist"]) == 0
    plan.write_text("**Agent Gate:** toy-specpialist\n", encoding="utf-8")
    assert agr.main([str(plan), "--agents-dir", str(agents)]) == 1


# ---- regression tests for the 2026-10-22 code review -----------------------------------

def test_refusal_writes_nothing_at_all(bundle):
    with pytest.raises(PermissionError):
        cr.commit_return(str(bundle), manifest(), protect=[str(bundle / "run_history.jsonl")])
    for name in ("evolution_log.md", "learning_rules.jsonl", "run_history.jsonl"):
        assert (bundle / name).read_text(encoding="utf-8") == ""


@pytest.mark.parametrize("bad", [
    {"learning_rules": "Read the audience line first"},
    {"promotion_candidates": ["L4"]},
    {"axis_missed": "tone"},
    {"evolution_entry": ["not", "a", "string"]},
])
def test_malformed_manifest_is_rejected_before_writing(bundle, bad):
    with pytest.raises(ValueError):
        cr.commit_return(str(bundle), manifest(**bad))
    assert (bundle / "learning_rules.jsonl").read_text(encoding="utf-8") == ""


def test_protected_match_ignores_case_where_the_os_does(bundle):
    p = str(bundle / "learning_rules.jsonl")
    variant = p.upper() if os.path.normcase("A") == "a" else p
    with pytest.raises(PermissionError):
        cr.commit_return(str(bundle), manifest(), protect=[variant])


def test_malformed_history_lines_are_reported(tmp_path, capsys):
    h = tmp_path / "h.jsonl"
    h.write_text('{"run": "r1"}\n{truncated\n', encoding="utf-8")
    assert len(rg.load_jsonl(str(h))) == 1
    assert "1 malformed" in capsys.readouterr().err


def test_commit_stamps_each_rule_with_its_run(bundle):
    cr.commit_return(str(bundle), manifest(run="r7"), today="2026-10-23")
    rule = json.loads((bundle / "learning_rules.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert rule["added_run"] == "r7"


def _quiet_history(n, prefix="r"):
    return [{"run": "%s%d" % (prefix, i), "learnings_fired": []} for i in range(n)]


def test_unpromoted_rules_are_watched_when_rules_are_given():
    hist = _quiet_history(25)
    rules = [{"id": "L9", "rule": "...", "added_run": "r0"}]
    res = rg.compute(hist, [], 20, rules=rules)
    assert [c["learning_id"] for c in res["retirement_candidates"]] == ["L9"]


def test_a_new_rule_waits_for_its_own_window_however_long_the_history():
    hist = _quiet_history(100)
    rules = [{"id": "L_old", "added_run": "r0"}, {"id": "L_new", "added_run": "r95"}]
    res = rg.compute(hist, [], 20, rules=rules)
    assert [c["learning_id"] for c in res["retirement_candidates"]] == ["L_old"]
    assert res["too_new_to_judge"] == ["L_new"]


def test_promotion_date_restarts_the_clock():
    hist = _quiet_history(100)
    res = rg.compute(hist, [{"learning_id": "L4", "since_run": "r90"}], 20)
    assert res["retirement_candidates"] == [] and res["too_new_to_judge"] == ["L4"]


def test_retired_ids_are_not_watched():
    hist = _quiet_history(25)
    rules = [{"id": "L1", "added_run": "r0"}, {"id": "L2", "added_run": "r0"}]
    res = rg.compute(hist, ["L1"], 20, rules=rules, retired=["L1"])
    assert [c["learning_id"] for c in res["retirement_candidates"]] == ["L2"]
    assert res["watched"] == 1


def test_cli_accepts_rules_without_promotions(tmp_path):
    h = tmp_path / "h.jsonl"
    h.write_text("".join(json.dumps(r) + "\n" for r in _quiet_history(25)), encoding="utf-8")
    r = tmp_path / "rules.jsonl"
    r.write_text(json.dumps({"id": "L9", "added_run": "r0"}) + "\n", encoding="utf-8")
    assert rg.main(["--history", str(h), "--rules", str(r)]) == 1


def test_duplicate_promotions_count_once():
    hist = [{"run": "r%d" % i, "learnings_fired": [{"learning_id": "L1", "output_span": "x"}]} for i in range(20)]
    res = rg.compute(hist, ["L1", "L3", "L3"], 20)
    assert res["metrics"]["utilization"] == 0.5 and len(res["retirement_candidates"]) == 1


def test_agents_dir_found_from_the_plan_location(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    (repo / ".claude" / "agents").mkdir(parents=True)
    (repo / ".claude" / "agents" / "toy-specialist.md").write_text("x", encoding="utf-8")
    (repo / "plans").mkdir()
    plan = repo / "plans" / "p.md"
    plan.write_text("**Agent Gate:** toy-specialist\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("HARNESS_AGENTS_DIR", raising=False)
    assert agr.main([str(plan)]) == 0
