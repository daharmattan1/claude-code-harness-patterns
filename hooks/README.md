# Claude Code hooks that stop an AI from grading its own work

This folder holds the hooks I use to stop an AI agent from grading its own writing. An agent will tell you its own draft is good, and if it can also publish that draft, nobody else reads it first. These hooks keep the writing, the grading and the publishing in separate hands. They're for anyone using Claude Code to make things other people will read.

In August a drafting agent wrote essays about AI slop for a public GitHub project and scored them itself, 84 to 89 out of 100. I read them and said out loud that I didn't think the review had happened. It hadn't, and a real review gave the same essays 71.

That's the trouble with letting an agent grade itself. It's convinced it's great, but it doesn't even know what great is half the time. I'd also helped them slip through by going around my own publish step and copying the files into place by hand.

Now the agent that writes a draft isn't allowed to publish it or grade it. It gets no command line, so it can't copy files around the way I did. A separate script does the publishing, which here means moving a finished draft into the folder people read from, and for anything long, a review by a different agent or a person has to have read the exact text first. If anyone changes the text after that review, the script won't publish it.

Some of these checks only log a warning until you switch them on, and in my own setup they still only log. Someone with full access to the computer can still go around them on purpose. [INSTALL.md](INSTALL.md) shows how to switch them on and lists everything that still gets past.


## Files

| File | What it does | Default |
|---|---|---|
| [`write_gate.py`](write_gate.py) | PreToolUse hook on Write, Edit and MultiEdit. Flags placeholders, long new deliverables written directly, edits to promoted files, and a drafter writing review or provenance files. | shadow (logs only) |
| [`promote.py`](promote.py) | The command that moves a draft out of `_workspace/` into a deliverable path and stamps the provenance sidecar. Not a hook. | review check logged; refuses with `PROMOTE_REQUIRE_REVIEW=1` |
| [`dispatch_guard.py`](dispatch_guard.py) | PreToolUse hook on Agent and Task. Denies a dispatch whose prompt names no verifier. | enforcing |
| [`postcompact_verify.py`](postcompact_verify.py) | SessionStart hook (source `compact`). Re-injects the active plan after a compaction. | advisory |
| [`pre_read_token_estimate.py`](pre_read_token_estimate.py), [`post_read_token_ledger.py`](post_read_token_ledger.py) | Estimate a read before it happens; keep a per-session ledger in the system temp folder. | advisory, silent |
| [`lib/`](lib/) | Shared hook I/O, the provenance and review-attestation predicates, path matching. | |
| [`examples/drafter.md`](examples/drafter.md) | A no-shell drafting agent to copy into `.claude/agents/`. | |
| [`docs/`](docs/) | [Provenance contract](docs/provenance-contract.md), [review attestation contract](docs/review-attestation-contract.md). | |

## Install

Python 3.8 or later, standard library only. Copy the hooks into `.claude/hooks/`, merge the `hooks` block from [`settings.example.json`](settings.example.json), declare your drafting subagent without a shell, and run a week in shadow before turning anything on. The steps and every setting are in [INSTALL.md](INSTALL.md).

From the root of this repo:

```bash
pytest hooks/tests
```
