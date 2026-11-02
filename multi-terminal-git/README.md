# Running dozens of Claude Code sessions on one git branch without losing work

This folder is how I run dozens of Claude Code sessions at once on one copy of a project and one git branch. When that many AI sessions share one copy, a single git command from one of them can wipe out everyone else's unsaved work. A check here blocks those commands, and the scripts keep the sessions out of each other's files. It's for anyone running more than a couple of AI coding sessions on the same project.

Constant headaches and wondering what worktrees are, why they clog up my machine, why need them, why it can't be simple to coordinate. Why I have to repeat instructions constantly. Feels like a tax on being on edge, something that should be abstracted away.

On March 20, 2026, one session switched branches and every other session's unsaved work was gone, fourteen phases of a newsletter rebuild included. I wrote down a rule telling every session not to do that, and the next day it happened again anyway. So I turned the rule into code that blocks the command before it runs.

That's one of four pieces here.

- A check that stops risky git commands before they run, like that branch switch.
- A commit check that only looks at the files being committed and never hides anyone else's work.
- A script that puts finished work onto main without touching anyone's files.
- A cleanup script for the extra project copies (git calls them worktrees) that were filling my disk, 119 of them at about 23 GB. It only deletes a copy whose work is already saved online.

The command check can't see git commands hidden inside other scripts. Every incident behind all this is in [INCIDENTS.md](INCIDENTS.md), with its date.


## Files

| File | What it does |
|---|---|
| [`hooks/git_safety_gate.py`](hooks/git_safety_gate.py) | Claude Code PreToolUse hook. Denies switching to an existing branch, pushing to main, and creating a worktree without an explicit opt-in. |
| [`hooks/pre-commit-nostash.sh`](hooks/pre-commit-nostash.sh) | Git pre-commit hook that never stashes. Checks only the commit's own files against a private copy of the index. |
| [`bin/land-to-main.sh`](bin/land-to-main.sh) | Rebuilds chosen commits on main and pushes them as a PR branch, without a checkout, so the shared working tree is never touched. |
| [`bin/newwork.sh`](bin/newwork.sh) | Starts a fresh chunk of work in a clean worktree and warns when your branch has drifted far from main. |
| [`bin/reap-worktrees.sh`](bin/reap-worktrees.sh) | Removes idle worktrees whose work already exists on a remote. Dry run unless `--apply`. |
| [AGENT_RULES.md](AGENT_RULES.md) | The rules to put in your agents' instructions. |
| [INCIDENTS.md](INCIDENTS.md) | Every break behind these scripts, dated. |

## Install

Bash 4.4 or later and git 2.40 or later (`land-to-main.sh` uses `git merge-tree --merge-base`). The pre-commit hook also needs the `pre-commit` framework. Put `bin/` on your PATH, install the pre-commit hook, and register the safety gate in `.claude/settings.json`. [INSTALL.md](INSTALL.md) has each step, the gate's matcher, and cron and launchd entries for the weekly reap.

From the root of this repo:

```bash
bash multi-terminal-git/tests/run.sh
python -m pytest multi-terminal-git/tests
```
