# Exemplar card: build a small CLI tool

A pattern card shows a plan author what a good plan in one category looks like. This one is
synthetic: the task and criteria are invented to illustrate the shape. Build your own cards
from your own completed plans; the format is the useful part.

## Category signals

The plan mentions: a script or command, flags, exit codes, tests, a README section.

## Recommended parameters

| Parameter | Value |
|---|---|
| Deliverable type | infrastructure |
| Quality bar | structural |
| Context mode | direct |
| Typical phases | 5 to 8 |
| Iterations per phase (expect) | about 0.5 |

## Success criteria that worked

1. `tools/todo-count.sh` exists and is executable.
2. `bash tools/todo-count.sh fixtures/sample-repo` prints `3` and exits 0.
3. `bash tools/todo-count.sh /nonexistent` exits 2 with a message on stderr.
4. `bats tests/todo-count.bats` reports 0 failures and at least 6 tests.
5. A fixture with zero markers prints `0` (negative control for an always-nonzero bug).
6. The README section "Counting TODOs" names every flag the script accepts.

## Phase skeleton

```
1. Fixtures: a sample repo with known counts, including an empty case
2. Script: the smallest version that passes criterion 2
3. Errors and flags: exit codes, --help, unreadable paths
4. Tests: one per criterion, plus the negative control
5. Docs: README section generated from --help, checked by a grep
6. Review and commit
```

## Failure modes

| Failure | Mitigation |
|---|---|
| Tests written after the code only exercise the happy path | Write the fixture first and assert on exact output |
| Works on one shell, breaks on another | Run tests under the oldest shell you support |
| README drifts from the flags | Generate the flag list from `--help` |
