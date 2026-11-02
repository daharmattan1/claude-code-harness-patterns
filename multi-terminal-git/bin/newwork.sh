#!/usr/bin/env bash
# newwork.sh -- start a fresh chunk of work without disturbing the shared branch.
#
# Three things, all safe:
#   (a) a drift report: how far the branch you are on has run ahead of the base
#   (b) fast-forward the local base branch (never a real merge, never forced)
#   (c) with a slug: a clean worktree beside the repo, on a new branch off the base
#
# It never switches the shared tree, never force-pushes, never deletes anything.
#
# Usage:
#   newwork.sh                       drift report + fast-forward local base
#   newwork.sh <slug>                ...plus a new worktree <prefix><slug> on <branch-prefix><slug>
#   newwork.sh <slug> --sparse       ...a lean worktree that skips the dirs in NEWWORK_SPARSE_EXCLUDES
#
# Configuration (environment, or a .newworkrc file of KEY=value lines at the repo root):
#   NEWWORK_BASE             base branch                    (default: main)
#   NEWWORK_REMOTE           remote                         (default: origin)
#   NEWWORK_WT_PREFIX        worktree dir prefix, created beside the repo   (default: _wt-)
#   NEWWORK_BRANCH_PREFIX    branch prefix                  (default: work/)
#   NEWWORK_DRIFT_WARN       warn when this many commits ahead              (default: 300)
#   NEWWORK_SPARSE_EXCLUDES  space-separated dirs to omit with --sparse     (default: none)
set -uo pipefail

SLUG=""
SPARSE=0
for arg in "$@"; do
  case "$arg" in
    --sparse) SPARSE=1 ;;
    -h|--help) sed -n '2,/^set -uo/s/^# \{0,1\}//p' "$0" | sed '$d'; exit 0 ;;
    -*) echo "newwork: unknown flag '$arg'" >&2; exit 2 ;;
    *) SLUG="$arg" ;;
  esac
done

GITCOMMON=$(git rev-parse --git-common-dir 2>/dev/null) || { echo "newwork: not inside a git repo" >&2; exit 1; }
REPO=$(cd "$(dirname "$GITCOMMON")" && pwd)
PARENT=$(dirname "$REPO")

if [ -f "$REPO/.newworkrc" ]; then
  while IFS='=' read -r k v; do
    case "$k" in NEWWORK_*) [ -z "${!k:-}" ] && export "$k=$v" ;; esac
  done < "$REPO/.newworkrc"
fi
BASE=${NEWWORK_BASE:-main}
REMOTE=${NEWWORK_REMOTE:-origin}
WT_PREFIX=${NEWWORK_WT_PREFIX:-_wt-}
BR_PREFIX=${NEWWORK_BRANCH_PREFIX:-work/}
DRIFT_WARN=${NEWWORK_DRIFT_WARN:-300}
SPARSE_EXCLUDES=${NEWWORK_SPARSE_EXCLUDES:-}

git -C "$REPO" fetch "$REMOTE" "$BASE" --quiet 2>/dev/null || true

# (a) drift report
cur=$(git rev-parse --abbrev-ref HEAD 2>/dev/null)
counts=$(git rev-list --left-right --count "$REMOTE/$BASE...HEAD" 2>/dev/null)
behind=$(echo "$counts" | awk '{print $1}')
ahead=$(echo "$counts" | awk '{print $2}')
echo "== drift: '$cur' vs $REMOTE/$BASE =="
echo "   behind by ${behind:-?} commit(s); ahead by ${ahead:-?}"
if [ "${ahead:-0}" -gt "$DRIFT_WARN" ] 2>/dev/null; then
  echo "   !! more than $DRIFT_WARN commits ahead: land your work or re-baseline soon. This is how a shared branch turns into a two-way fork."
fi

# (b) fast-forward the local base, wherever it is checked out
echo "== fast-forward local $BASE =="
basewt=$(git -C "$REPO" worktree list --porcelain | awk -v b="refs/heads/$BASE" '/^worktree /{p=substr($0,10)} $0=="branch "b{print p}')
if [ -n "$basewt" ]; then
  # Fast-forwarding a checked-out branch rewrites files in that working tree, and this
  # script promises never to change a tree someone else may be working in. Say so instead.
  echo "   $BASE is checked out at $basewt; not touching a working tree from here."
  echo "   To update it yourself: git -C \"$basewt\" merge --ff-only $REMOTE/$BASE"
elif git -C "$REPO" fetch "$REMOTE" "$BASE:$BASE" >/dev/null 2>&1; then
  echo "   local $BASE ref fast-forwarded"
else
  echo "   local $BASE is not a clean fast-forward; left untouched"
fi

# (c) a new clean worktree off the base
[ -z "$SLUG" ] && exit 0
WT="$PARENT/$WT_PREFIX$SLUG"
BR="$BR_PREFIX$SLUG"
if [ -e "$WT" ]; then echo "== $WT already exists; not creating =="; exit 0; fi
echo "== new worktree: $WT  (branch $BR, off $BASE) =="
git -C "$REPO" worktree add --no-checkout "$WT" -b "$BR" "$BASE" || exit 1
if [ "$SPARSE" = "1" ] && [ -n "$SPARSE_EXCLUDES" ]; then
  # Non-cone sparse checkout: include everything, then re-exclude the heavy dirs. Patterns go
  # on stdin because Git Bash rewrites leading-slash arguments into Windows paths.
  { echo '/*'; for p in $SPARSE_EXCLUDES; do echo "!/$p/"; done; } \
    | git -C "$WT" sparse-checkout set --no-cone --stdin
  git -C "$WT" checkout
  echo "   lean worktree (omits: $SPARSE_EXCLUDES)"
else
  git -C "$WT" read-tree HEAD
  git -C "$WT" checkout-index -a -f
fi
git -C "$WT" submodule update --init --recursive 2>/dev/null || true
echo "   ready -> cd \"$WT\""
