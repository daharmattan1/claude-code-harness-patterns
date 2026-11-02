# Installing the multi-terminal git tools

Requirements: Git 2.40 or later (`land-to-main.sh` uses `merge-tree --merge-base`), bash 4.4
or later for the pre-commit hook (macOS: `brew install bash`), Python 3.8 or later for the
git safety gate and its tests. The pre-commit hook also needs the
[pre-commit](https://pre-commit.com) framework (`pip install pre-commit`) and a
`.pre-commit-config.yaml` in your repo.

The commands below use two paths: `/path/to/this/repo` is where you downloaded this
collection, and `/path/to/your/repo` is the repo you are installing into.

## The scripts

Copy `bin/` anywhere on your PATH, or into your repo as `scripts/`:

```bash
mkdir -p /path/to/your/repo/scripts
cp /path/to/this/repo/multi-terminal-git/bin/*.sh /path/to/your/repo/scripts/
chmod +x /path/to/your/repo/scripts/*.sh
```

If your repo might be checked out on Linux or WSL, add `*.sh text eol=lf` to its
`.gitattributes`. A CRLF copy of these scripts runs in Git Bash but fails under Linux bash.

`land-to-main.sh` needs a remote (`origin` by default), and the PR branch name you give it
must be new. It pushes that branch; someone still merges the PR.

| Script | What it does | Touches the working tree? |
|---|---|---|
| `land-to-main.sh <pr-branch> <commit>...` | Rebuilds the named commits on the remote base and pushes them as a PR branch | No |
| `newwork.sh [<slug>] [--sparse]` | Drift report, fast-forwards local base, optionally a clean worktree beside the repo | Only the new worktree |
| `reap-worktrees.sh [--apply]` | Lists (or removes, with `--apply`) worktrees that are fully pushed, clean apart from churn, unlocked and idle | Only reaped worktrees |

## The pre-commit hook

This hook runs your `pre-commit` checks without stashing anyone's work. It needs the
framework and a `.pre-commit-config.yaml`. Without the framework it refuses every commit;
set `NOSTASH_ALLOW_NO_PRECOMMIT=1` to commit unchecked.

```bash
cp /path/to/this/repo/multi-terminal-git/hooks/pre-commit-nostash.sh /path/to/your/repo/.git/hooks/pre-commit
chmod +x /path/to/your/repo/.git/hooks/pre-commit
```

Do not run `pre-commit install` afterwards: it overwrites this hook with the stashing one.

## The git safety gate (Claude Code hook)

```bash
mkdir -p /path/to/your/repo/.claude/hooks
cp /path/to/this/repo/multi-terminal-git/hooks/git_safety_gate.py /path/to/your/repo/.claude/hooks/
```

Then register it in `.claude/settings.json`. If you also installed `../hooks/`, add this
entry to your existing `PreToolUse` array instead of pasting a second `hooks` block, which
would replace the first. The matcher needs both shell tools (git runs
from either) and the three tools that can create a worktree without a shell command:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash|PowerShell|EnterWorktree|Agent|Task",
        "hooks": [
          { "type": "command", "command": "python \"$CLAUDE_PROJECT_DIR/.claude/hooks/git_safety_gate.py\"", "timeout": 10 }
        ]
      }
    ]
  }
}
```

## Running the reaper on a schedule

The reaper is a dry run unless you pass `--apply`. Run it by hand first and read the report.

cron (Linux), every Monday at 08:30:

```cron
30 8 * * 1 cd /path/to/repo && bash scripts/reap-worktrees.sh --apply >> ~/reap-worktrees.log 2>&1
```

launchd (macOS): a `~/Library/LaunchAgents/local.reap-worktrees.plist` whose
`ProgramArguments` are `/bin/bash -c "cd /path/to/repo && scripts/reap-worktrees.sh --apply"`
and whose `StartCalendarInterval` is `Weekday 1, Hour 8, Minute 30`.

systemd (user timer): a `reap-worktrees.service` with
`ExecStart=/bin/bash -c 'cd /path/to/repo && scripts/reap-worktrees.sh --apply'` and a
matching `reap-worktrees.timer` with `OnCalendar=Mon 08:30`.

Windows Task Scheduler (a per-user task; no elevation needed):

```powershell
schtasks /Create /TN ReapWorktrees /SC WEEKLY /D MON /ST 08:30 /TR "\"C:\Program Files\Git\bin\bash.exe\" -lc 'cd /c/path/to/repo && scripts/reap-worktrees.sh --apply'"
```

## Running the tests

From the root of this repo (the tests are not copied into your repo):

```bash
bash multi-terminal-git/tests/run.sh          # the scripts, against throwaway repos
python -m pytest multi-terminal-git/tests     # the git safety gate
```

`run.sh` creates throwaway repos, bare origins and worktrees under `TMPDIR` (default
`/tmp`) and deletes them on exit. It never touches your own repos.
