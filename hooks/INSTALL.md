# Installing the hooks

Requirements: Python 3.8 or later, standard library only. `pytest` only to run the tests.

## 1. Copy the folder

From the root of the project you want to guard:

```bash
mkdir -p .claude/hooks
cp -r /path/to/this/repo/hooks/*.py /path/to/this/repo/hooks/lib .claude/hooks/
```

The hooks import from `lib/` next to them, so keep that layout.

## 2. Register them

Merge the `hooks` block from `settings.example.json` into `.claude/settings.json`. If you
already have a `PreToolUse` array (for example from `../multi-terminal-git/`), add these
entries to it rather than pasting a second block, which would replace the first. If your
machine has `python3` and no `python`, change the command prefix.

| Hook | Event | Matcher | Default |
|---|---|---|---|
| `write_gate.py` | PreToolUse | `Write\|Edit\|MultiEdit` | shadow (logs only) |
| `dispatch_guard.py` | PreToolUse | `Agent\|Task` | enforcing (denies a dispatch with no verifier) |
| `pre_read_token_estimate.py` | PreToolUse | `Read` | advisory |
| `post_read_token_ledger.py` | PostToolUse | `Read\|Edit\|Write` | silent ledger |
| `postcompact_verify.py` | SessionStart | `compact` | advisory |

`promote.py` is not a hook. It is the command your workflow runs to move a draft out of
`_workspace/` into a deliverable path:

```bash
python .claude/hooks/promote.py --draft _workspace/memo/draft.md --target deliverables/memo.md
```

## 3. Declare the drafting agent without a shell

The write gate and the promoter assume the agent that drafts cannot run shell commands. That
is the one wall here: a subagent gets only the tools its definition lists. In the drafter's
`.claude/agents/<name>.md`, list `Read, Glob, Grep, Write` and nothing that runs commands (no
Bash, no PowerShell). [`examples/drafter.md`](examples/drafter.md) is a starting point; copy it
to `.claude/agents/drafter.md`. Then put its name in `HARNESS_DRAFTER_AGENTS` so the write gate
denies it writing review and provenance files. Without this, everything below is a tripwire only.

## 4. Configure

| Variable | Effect | Default |
|---|---|---|
| `HARNESS_DELIVERABLES` | Comma-separated globs for final deliverables (`**` crosses directories) | `deliverables/**/*.md` |
| `HARNESS_DRAFTER_AGENTS` | Subagent types that may not write review or provenance files | `drafter` |
| `WRITE_GATE_ENFORCING=1` | The write gate denies instead of logging | off |
| `PROMOTE_REQUIRE_REVIEW=1` | Promoting a draft of 9,000+ characters requires a hash-bound PASS attestation (shorter drafts never need one) | off (logged) |
| `DISPATCH_GUARD_SHADOW=1` | The dispatch guard logs instead of denying | off |
| `DISPATCH_REQUIRE_MODEL=1` | Generic subagent types must pass an explicit model | off |
| `HARNESS_PLAN_GLOB` | Which files count as active plans after a compaction | `plans/*_active.md` |

Set them in the `env` block of `.claude/settings.json` so they travel with the project.

## 5. Turn enforcement on deliberately

Run a week in shadow. Read `.claude/logs/write_gate_shadow.jsonl` and
`.claude/logs/promote_review_shadow.jsonl`. When every row is something you would have
wanted blocked, set the enforcing variables. A gate that blocks the wrong thing teaches
everyone to route around it.

Add `.claude/logs/` to your `.gitignore`. The logs hold absolute local paths. The token
ledger is written outside the project, to your system temp folder
(`claude_token_ledger_<session>.json`).

## 6. Run the tests

From the root of this repo (the tests are not copied into your project):

```bash
pytest hooks/tests
```

## 7. What still gets past

These are the known holes, with the hooks installed and both enforcing switches on.

- **Files outside the deliverable globs.** They default to markdown, so an .html page, a .docx or a post published through an API never meets the write gate.
- **Short files.** A draft under 9,000 characters never needs a review attestation, and a short clean file written straight to a deliverable path gets no sidecar and no log entry.
- **Edits after promotion.** The write gate flags the first Edit to a promoted file. After that the sidecar no longer matches, so later edits pass unflagged. A change made in a text editor or from a shell never reaches the hook at all.
- **A missing `agent_type`.** The drafter deny keys on that field. If Claude Code stops sending it, the deny doesn't fire, and a top-level session's writes arrive with it blank.
- **A top-level agent with a shell.** It can `cp` a file onto a deliverable path and hand-write a sidecar or an attestation with a matching hash. That is a deliberate act now, not an accident, but nothing here stops it.
- **A careless review.** An attestation proves a named reviewer's record says PASS for these exact bytes. A rubber-stamp PASS satisfies every check.

[docs/provenance-contract.md](docs/provenance-contract.md) and [docs/review-attestation-contract.md](docs/review-attestation-contract.md) spell out each contract and its limits.
