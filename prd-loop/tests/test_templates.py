"""Checks that the plan-file templates and exemplars carry what SPEC.md requires, and that the
review script parses. Run: pytest prd-loop/tests"""
import os
import re
import shutil
import subprocess

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# Every plan file needs these to be resumable: the state an agent reads first, and the log.
REQUIRED = [
    "## Metadata", "## Objective", "## Success Criteria", "## Phases", "## State",
    "### Current Phase", "### Iteration Count", "### Last Action", "### Next Action",
    "### Blockers", "### Failed Attempts on Current Action", "## Iteration Log",
    "## Escape Hatches", "## Completion",
]


def read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as f:
        return f.read()


def headings(text):
    return {line.strip() for line in text.splitlines() if re.match(r"#{2,3} ", line)}


@pytest.mark.parametrize("name", ["prd_full.md", "prd_lite.md"])
def test_template_has_every_required_section(name):
    missing = [h for h in REQUIRED if h not in headings(read("templates", name))]
    assert not missing, "%s is missing %s" % (name, missing)


# Exemplars are pattern cards (what a good plan in one category looks like), not plan files.
CARD = ["## Category signals", "## Recommended parameters", "## Success criteria that worked",
        "## Phase skeleton", "## Failure modes"]


@pytest.mark.parametrize("name", sorted(os.listdir(os.path.join(ROOT, "templates", "exemplars"))))
def test_exemplar_card_has_every_section(name):
    missing = [h for h in CARD if h not in headings(read("templates", "exemplars", name))]
    assert not missing, "%s is missing %s" % (name, missing)


def test_full_template_keeps_the_intent_rule():
    # The IN FLIGHT line is how an interrupted outside action is detected on resume.
    assert "IN FLIGHT" in read("templates", "prd_full.md")


def test_headings_the_check_requires_exist_in_the_spec():
    spec = read("SPEC.md")
    for h in ("Failed Attempts on Current Action", "Iteration Count", "Next Action"):
        assert h in spec, h


def find_bash():
    # On Windows a bare "bash" can resolve to the WSL launcher in System32, which fails
    # without a Linux distro installed. Prefer the bash that ships with Git for Windows.
    if os.name == "nt":
        git = shutil.which("git")
        if git:
            for rel in ("../bin/bash.exe", "../../bin/bash.exe"):
                cand = os.path.normpath(os.path.join(os.path.dirname(git), rel))
                if os.path.isfile(cand):
                    return cand
    return shutil.which("bash")


@pytest.mark.skipif(find_bash() is None, reason="bash not installed")
def test_review_script_parses():
    script = os.path.join(ROOT, "skills", "cross-model-review", "scripts", "run_review.sh")
    res = subprocess.run([find_bash(), "-n", script], capture_output=True, text=True)
    assert res.returncode == 0, res.stderr
