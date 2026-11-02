#!/usr/bin/env bash
# pre-commit-nostash.sh -- a git pre-commit hook that runs the pre-commit framework WITHOUT
# its stash-and-restore of unstaged changes.
#
# Why: the stock hook (what `pre-commit install` writes, or a bare `pre-commit run`) saves
# every unstaged change to a patch, runs `git checkout -- .` over the whole tree, runs the
# checks, then applies the patch back. On a working tree other terminals are writing to,
# that is unsafe:
#   1. `git apply` is all-or-nothing. One file written while the checks run rejects the
#      whole patch, and every other unstaged edit stays stripped from disk.
#   2. The framework's fallback retries with core.autocrlf=false, which cannot apply on a
#      CRLF checkout, and buries the real cause under hundreds of "patch does not apply".
#   3. Even a "successful" restore discards anything written to the tree during the run.
# `pre-commit run --files <paths>` never stashes, so this hook passes the commit's own files
# explicitly and touches nothing else.
#
# Install:  cp pre-commit-nostash.sh .git/hooks/pre-commit && chmod +x .git/hooks/pre-commit
#           (do NOT also run `pre-commit install`; it would overwrite this file)
#
# If the pre-commit framework is not installed, this hook FAILS CLOSED: the commit is
# refused rather than accepted unchecked. Set NOSTASH_ALLOW_NO_PRECOMMIT=1 to commit anyway.
#
# Needs bash 4.4 or later (macOS ships 3.2 as /bin/bash; `brew install bash`).
set -u

if [ -z "${BASH_VERSINFO:-}" ] || [ "${BASH_VERSINFO[0]}" -lt 4 ] ||
   { [ "${BASH_VERSINFO[0]}" -eq 4 ] && [ "${BASH_VERSINFO[1]}" -lt 4 ]; }; then
    echo "[pre-commit] this hook needs bash >= 4.4 (found ${BASH_VERSION:-unknown})." >&2
    exit 1
fi

REPO_ROOT=$(git rev-parse --show-toplevel) || exit 1
cd "$REPO_ROOT" || exit 1

# Files in the commit being built. Honors GIT_INDEX_FILE, so a pathspec commit
# (`git commit -- <paths>`) sees exactly its own paths.
mapfile -d '' STAGED < <(git diff --cached --name-only -z --diff-filter=ACMRTUXB)

if [ -n "$(git diff --cached --name-only --diff-filter=U)" ]; then
    echo "[pre-commit] Unmerged paths in the index. Resolve them before committing." >&2
    exit 1
fi

if [ "${#STAGED[@]}" -eq 0 ]; then
    # Never fall through to a bare `pre-commit run`: with no --files it stashes.
    echo "[pre-commit] No added or modified files in this commit; nothing to check."
    exit 0
fi

# A staged file with further unstaged edits would be checked as its working-tree bytes,
# not the bytes being committed. The stock hook hides that by stashing, which is exactly
# what is unsafe here, so refuse instead.
declare -A UNSTAGED=()
while IFS= read -r -d '' p; do UNSTAGED["$p"]=1; done < <(git diff --name-only -z)
PARTIAL=()
for p in "${STAGED[@]}"; do
    [ -n "${UNSTAGED["$p"]+x}" ] && PARTIAL+=("$p")
done
if [ "${#PARTIAL[@]}" -gt 0 ]; then
    echo "[pre-commit] Refusing to run checks: these files have unstaged changes on top of" >&2
    echo "their staged version, so the checks would not see what you are committing:" >&2
    printf '    %s\n' "${PARTIAL[@]}" >&2
    echo "If those edits are yours, \`git add\` the files and commit again. If another" >&2
    echo "terminal is editing them, wait for it, or commit with \`git commit -- <paths>\`." >&2
    exit 1
fi

if ! command -v pre-commit >/dev/null 2>&1; then
    if [ "${NOSTASH_ALLOW_NO_PRECOMMIT:-}" = "1" ]; then
        echo "[pre-commit] pre-commit not installed; NOSTASH_ALLOW_NO_PRECOMMIT=1, committing unchecked." >&2
        exit 0
    fi
    echo "[pre-commit] The pre-commit framework is not on PATH, so nothing can be checked." >&2
    echo "Install it (pip install pre-commit), or set NOSTASH_ALLOW_NO_PRECOMMIT=1 to commit unchecked." >&2
    exit 1
fi

# Run against a private copy of the index in which everything except this commit's files
# is marked skip-worktree. The framework decides "files were modified by this hook" by
# diffing the whole tree around each hook, so another terminal writing any tracked file
# mid-run would otherwise fail every check. Git's own index is never modified. If any
# step fails, run without the scoping (still no stash, just noisier).
SRC_INDEX=${GIT_INDEX_FILE:-$(git rev-parse --git-path index)}
SCOPED_INDEX="$(git rev-parse --absolute-git-dir)/pre-commit-nostash-index.$$"
if cp "$SRC_INDEX" "$SCOPED_INDEX" 2>/dev/null &&
   git ls-files -z | GIT_INDEX_FILE="$SCOPED_INDEX" git update-index -z --skip-worktree --stdin &&
   printf '%s\0' "${STAGED[@]}" | GIT_INDEX_FILE="$SCOPED_INDEX" git update-index -z --no-skip-worktree --stdin; then
    trap 'rm -f "$SCOPED_INDEX"' EXIT
    export GIT_INDEX_FILE="$SCOPED_INDEX"
else
    rm -f "$SCOPED_INDEX"
fi

# STAGED is non-empty here (checked above), so xargs never runs a bare, stashing
# `pre-commit run`. -s stays under the Windows 32K command-line limit; large commits batch.
if ! printf '%s\0' "${STAGED[@]}" | xargs -0 -s 20000 pre-commit run --hook-stage pre-commit --files; then
    echo "" >&2
    echo "[pre-commit] Checks failed. Fix the issues above, \`git add\` the files, and commit again." >&2
    echo "A \"files were modified by this hook\" failure on a file you did not touch usually means" >&2
    echo "another terminal wrote to the tree while the checks ran; retry." >&2
    exit 1
fi
exit 0
