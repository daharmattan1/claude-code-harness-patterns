#!/usr/bin/env bash
# land-to-main.sh -- cherry-pick specific commits onto the base branch and push them as a
# new PR branch, WITHOUT a checkout.
#
# Why: when several terminals build on one shared branch, that branch carries everyone's
# work, finished and unfinished. A normal branch-vs-main PR cannot say "only these
# commits". This script can, and it never touches the working tree, the index, or HEAD,
# so the other terminals keep working while you land.
#
# How: each commit is rebuilt with `git merge-tree --write-tree --merge-base` and
# `git commit-tree` on top of the remote base. Authorship is kept; signatures are not.
#
# Usage:  land-to-main.sh [--base main] [--remote origin] <pr-branch> <commit>...
#         (commits oldest first), then open a PR from <pr-branch> into the base.
#
# Stops on the first conflict and pushes nothing. A commit already on the base is
# skipped. Merge commits are refused. Requires Git 2.40 or later.
set -u

BASE=main
REMOTE=origin
while [ $# -gt 0 ]; do
    case "$1" in
        --base|--remote)
            [ $# -ge 2 ] || { echo "land-to-main: $1 needs a value" >&2; exit 1; }
            if [ "$1" = "--base" ]; then BASE=$2; else REMOTE=$2; fi
            shift 2 ;;
        -h|--help) sed -n '2,/^set -u/s/^# \{0,1\}//p' "$0" | sed '$d'; exit 0 ;;
        *) break ;;
    esac
done
if [ $# -lt 2 ]; then
    echo "usage: land-to-main.sh [--base main] [--remote origin] <pr-branch> <commit>..." >&2
    exit 1
fi
BRANCH=$1; shift
export MSYS_NO_PATHCONV=1   # Git Bash on Windows would otherwise rewrite rev:path arguments

git fetch -q "$REMOTE" "$BASE" || { echo "fetch failed" >&2; exit 1; }
if [ -n "$(git ls-remote --heads "$REMOTE" "$BRANCH")" ]; then
    echo "$REMOTE already has a branch named $BRANCH; pick another name." >&2
    exit 1
fi

base=$(git rev-parse "$REMOTE/$BASE")
tip=$base
for arg in "$@"; do
    c=$(git rev-parse --verify --quiet "$arg^{commit}") || { echo "not a commit: $arg" >&2; exit 1; }
    if [ "$(git rev-list --parents -n 1 "$c" | wc -w)" -ne 2 ]; then
        echo "refusing merge commit $arg; pick its individual commits instead." >&2
        exit 1
    fi
    if ! out=$(git merge-tree --write-tree --merge-base="$c^" "$tip" "$c"); then
        echo "CONFLICT picking ${c:0:10} onto $BASE; nothing pushed:" >&2
        echo "$out" | tail -n +2 >&2
        exit 1
    fi
    tree=$(echo "$out" | head -1)
    if [ "$tree" = "$(git rev-parse "$tip^{tree}")" ]; then
        echo "skip  ${c:0:10}  (already on $BASE)"
        continue
    fi
    tip=$(git log -1 --format=%B "$c" |
        GIT_AUTHOR_NAME=$(git log -1 --format=%an "$c") \
        GIT_AUTHOR_EMAIL=$(git log -1 --format=%ae "$c") \
        GIT_AUTHOR_DATE=$(git log -1 --format=%aD "$c") \
        git commit-tree "$tree" -p "$tip" -F -) || exit 1
    echo "pick  ${c:0:10} -> ${tip:0:10}  $(git log -1 --format=%s "$c")"
done

if [ "$tip" = "$base" ]; then
    echo "Nothing to land: every commit is already on $BASE." >&2
    exit 1
fi
git push -q "$REMOTE" "$tip:refs/heads/$BRANCH" || { echo "push failed" >&2; exit 1; }
echo "Pushed $BRANCH ($(git rev-list --count "$base..$tip") commit(s) on $REMOTE/$BASE)."
echo "Next: open a PR from $BRANCH into $BASE (for example: gh pr create --base $BASE --head $BRANCH)"
