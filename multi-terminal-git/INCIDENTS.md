# Incidents

Every rule and script in this folder exists because something broke. This is the record,
from one repo where dozens of agent sessions build on one shared branch. Dates are 2026.

| Date | What went wrong | Mechanism | What it produced |
|---|---|---|---|
| Mar 20 | Fourteen phases of a newsletter rebuild disappeared | A session switched branches, and every other session's uncommitted work was gone afterward. The record doesn't name the exact command; a plain `git switch` carries changes over, so it was likely a forced checkout or a stash that was never popped | Rule: never switch to an existing branch |
| Mar 21 | A skills-format conversion disappeared the same way | Same mechanism, one day later: a rule in a document did not stop it | The git safety gate (a hook, not a rule) |
| Mar 24 | Nine phases of work were committed straight to main with no PR | Two instruction files disagreed ("commit to main" against "branch, then PR"), and the agent followed the wrong one | Rule: never push to main; one source of truth for git rules |
| March | 36 stale "preserve dirty state" stashes piled up | Agents stashed to get a clean tree before doing their own work | Rule: a dirty tree is normal; never stash |
| Jun 12, and 4 to 5 sessions later | A commit swept in files another session had staged | One index is shared by every session; `git commit` takes all of it | Pathspec commits (rule 5) |
| Jun 12 | Landing work from the shared branch took cherry-picks in a separate checkout, every time, and the lesson kept not sticking | A branch-diff PR from a long-lived shared branch carries everything on it | `land-to-main.sh` |
| Jun 25 to 27 | Agents halted, or branched away, to "avoid" the dirty tree | Over-applied isolation advice | Rule: build in place |
| Jun 30 | Merging the whole shared branch would have shipped unfinished work | Same as Jun 12 | `land-to-main.sh` |
| Jul 19 | The shared branch and main became a two-way fork that took a multi-phase reconciliation | Work that never landed | `newwork.sh` and its drift warning |
| Aug 31 | Two commits "timed out" but had landed, one retry from duplicates | The tool's 2-minute timeout fired after a slow commit succeeded; wrapping the command in `timeout` does nothing | Rule 7: long tool timeout, check HEAD before retrying |
| to Sep 16 | Worktrees reached 119 directories and about 23 GB; the disk hit 96% | Worktrees were created about twice a day and nothing deleted them | `reap-worktrees.sh` |
| to Sep 30 | The agent harness never auto-cleaned its own isolation worktrees | Session hooks rewrote four tracked files in every worktree, so none was ever "unchanged" | Those files untracked; the reaper's churn list |
| Sep 24 | A stale worktree held the only copy of an agent's memory files | Worktrees were still being created faster than they were reaped | The gate blocks agent worktree creation |
| Oct 2, three times | Pre-commit stripped other sessions' unstaged work, 891 files on the third run | The framework stashes unstaged changes, checks out the tree, then re-applies; one file written mid-run makes the all-or-nothing apply fail, and the CRLF fallback can never apply | `pre-commit-nostash.sh` |
| Oct 2 | The no-stash hook failed on large commits | Git Bash caps `xargs -s` below the default | Batched `xargs -s 20000` |
| Oct 4 | The landing docs pointed at a main checkout that no longer existed | Landing assumed a standing checkout of main | Checkout-free landing with `merge-tree` and `commit-tree` |
| Oct 20 | The git gate blocked a note that only described a worktree command | The gate matched the whole command string, heredoc body included | Heredoc-aware, per-command parsing |
| Oct 21 | The reaper's "never remove unpushed work" check had never worked | `git log --not --remotes HEAD`: `--not` negates every ref after it, HEAD included, so the count was always 0 | `HEAD --not --remotes`, re-checked before removal, with a test that fails on the old order |
| Oct 22 | A whole `lib/` folder was missing from a commit, with no warning | A root `.gitignore` rule for Python build output matched it | Rule 9: read `git show --name-status` after adding a directory |

The last two were silent: nothing failed, and the output looked fine. A cross-model code
review found the reaper bug. The missing folder showed up only in a commit's file list.
