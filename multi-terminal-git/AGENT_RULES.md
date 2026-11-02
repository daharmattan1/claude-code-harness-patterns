# Agent rules: many terminals, one branch

Paste this into your `CLAUDE.md` or `AGENTS.md`. It assumes several agent sessions build on
one shared branch in one working tree, and that the tools in this folder are installed.

## Building

1. **Build in place on the current branch.** A dirty tree full of other sessions' uncommitted
   files is normal. It is not a blocker and not a reason to branch, stash, or switch.
2. **Never switch to an existing branch.** `git checkout <branch>` and `git switch <branch>`
   change files under every session sharing the tree. Creating a branch from HEAD
   (`git checkout -b`) is safe. Restoring one file (`git checkout <ref> -- <path>`) is safe.
3. **Never stash, reset, clean, or restore the whole tree.** Each of these discards work you
   cannot see.
4. **Do not create worktrees to dodge a dirty tree.** A worktree is a full checkout and nothing
   removes it. Create one only when asked, and plan its cleanup.

## Committing

5. **Commit by pathspec: `git commit -m "..." -- <path> <path>`.** Every session shares one
   index, so a plain `git commit` takes whatever anyone else staged. A pathspec commit builds a
   temporary index from only your paths, and the pre-commit checks see only your files.
6. **`git add` a new file by explicit path before the pathspec commit.** A pathspec only matches
   files git already tracks; a new file fails with "did not match any file(s) known to git".
   Never `git add -A` or `git add .`.
7. **Give a commit up to five minutes, and check `git rev-parse HEAD` before retrying.** On a
   large tree with many checks, a short tool timeout fires after the commit has already
   succeeded. Retrying then makes a duplicate.
8. **Never let pre-commit stash.** Install `hooks/pre-commit-nostash.sh` and do not run
   `pre-commit install` or a bare `pre-commit run`.
9. **After any commit that adds a new directory, read `git show --name-status HEAD`.** An
   ignore rule (a `lib/` or `build/` pattern) can drop a whole folder without a warning.

## Landing

10. **Land by cherry-picking specific commits, without a checkout:**
    `bin/land-to-main.sh <pr-branch> <commit>...`, then open a PR from `<pr-branch>`. A
    branch-vs-main PR cannot say "only these commits" when the shared branch also carries
    unfinished work.
11. **Land often.** Work that never lands turns the shared branch into a fork of main.
    `bin/newwork.sh` warns when the branch runs far ahead.
12. **Never push to main.** Push a branch and open a PR.

## Cleaning up

13. **Reap worktrees with `bin/reap-worktrees.sh`, dry run first.** Never `rm -rf` a worktree:
    it leaves a stale registration, and on Windows it can follow a junction into a shared
    `node_modules`. Lock (`git worktree lock`) anything that must survive.
