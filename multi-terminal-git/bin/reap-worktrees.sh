#!/usr/bin/env bash
# reap-worktrees.sh -- remove worktrees that are provably safe to remove, report the rest.
#
# Worktrees are cheap to create and nothing deletes them, so on a busy repo they pile up:
# each one is a full checkout. This removes a worktree ONLY when all of these hold:
#   - every commit on its HEAD is in some remote ref (nothing unpushed)
#   - no untracked or modified files, except known churn (REAP_CHURN)
#   - it is not locked, not the primary worktree, not on the base branch
#   - nothing in it has changed for REAP_AGE_DAYS days (default 14)
# Everything else is reported as REVIEW or PROTECTED and left alone. Both checks run
# again immediately before removal, so work that appeared after classification is kept.
#
# Usage (run from inside the repo):
#   reap-worktrees.sh                     dry run: classify and report, delete nothing
#   reap-worktrees.sh --apply             remove the SAFE set
#   reap-worktrees.sh --age 30            only consider worktrees idle 30+ days
#   reap-worktrees.sh --include-orphans   also list non-git leftover dirs under REAP_ORPHAN_ROOTS
#                                         (removed only with --apply as well)
#
# Configuration (environment, or KEY=value lines in .reaprc at the repo root):
#   REAP_CHURN          extended regex of repo-relative paths that never count as work.
#                       Unset: lockfiles and *.log. Set but EMPTY: the script refuses to run,
#                       because an empty pattern would match every line and make every dirty
#                       worktree look clean.
#   REAP_AGE_DAYS       default idle threshold (14)
#   REAP_BASE           branch never reaped (main); master is always protected too
#   REAP_ORPHAN_ROOTS   space-separated glob patterns for the orphan sweep (default: none)
set -uo pipefail

REPO=$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null) || { echo "reap: not inside a git repo" >&2; exit 1; }
REPO=$(dirname "$REPO")
if [ -f "$REPO/.reaprc" ]; then
  while IFS='=' read -r k v; do
    case "$k" in REAP_*) [ -z "${!k+x}" ] && export "$k=$v" ;; esac
  done < "$REPO/.reaprc"
fi

APPLY=0; ORPHANS=0; AGE_DAYS=${REAP_AGE_DAYS:-14}
while [ $# -gt 0 ]; do
  case "$1" in
    --apply) APPLY=1 ;;
    --include-orphans) ORPHANS=1 ;;
    --age) shift; AGE_DAYS="${1:-14}" ;;
    -h|--help) sed -n '2,/^set -uo/s/^# \{0,1\}//p' "$0" | sed '$d'; exit 0 ;;
    *) echo "reap: unknown flag '$1'" >&2; exit 2 ;;
  esac
  shift
done

if [ "${REAP_CHURN+x}" = "x" ] && [ -z "$REAP_CHURN" ]; then
  echo "reap: REAP_CHURN is set but empty. An empty pattern matches every line, so every" >&2
  echo "dirty worktree would look clean. Unset it for the default, or give a real pattern." >&2
  exit 2
fi
CHURN=${REAP_CHURN:-'^(package-lock\.json|pnpm-lock\.yaml|yarn\.lock|.*\.log)$'}
BASE=${REAP_BASE:-main}
now=$(date +%s)

mtime(){ stat -c %Y "$1" 2>/dev/null || stat -f %m "$1" 2>/dev/null || echo 0; }

# Last activity: the later of the directory and the worktree's own index file.
last_active(){
  local wt="$1" gd a b
  gd=$(git -C "$wt" rev-parse --path-format=absolute --git-dir 2>/dev/null)
  a=$(mtime "$wt"); b=0
  [ -n "$gd" ] && [ -f "$gd/index" ] && b=$(mtime "$gd/index")
  [ "$a" -gt "$b" ] && echo "$a" || echo "$b"
}

# Commits reachable from HEAD and from no remote ref. HEAD goes BEFORE --not: --not
# negates every ref after it, so `--not --remotes HEAD` would always count 0.
# Prints "?" if git fails, and "?" is treated as unsafe.
unpushed(){ git -C "$1" rev-list --count HEAD --not --remotes 2>/dev/null || echo "?"; }

# Non-churn changes: every path that differs from HEAD (staged or not) plus untracked,
# non-ignored files. One path per line: -z avoids quoted names, and --no-renames reports a
# rename as its old and new paths, so renaming real work to a churn-looking name still
# counts the original path as work.
residue(){
  { git -C "$1" diff --name-only --no-renames -z HEAD 2>/dev/null
    git -C "$1" ls-files --others --exclude-standard -z 2>/dev/null; } \
    | tr '\0' '\n' | grep -Ev "$CHURN" | grep -c . | tr -d ' '
}

SAFE=(); REVIEW=(); PROTECTED=()

classify(){
  local wt="$1" locked="$2" primary="$3" branch age n r
  [ -d "$wt" ] || return 0
  [ "$primary" = "1" ] && { PROTECTED+=("$wt|primary worktree"); return 0; }
  [ "$locked" = "1" ] && { PROTECTED+=("$wt|locked"); return 0; }
  branch=$(git -C "$wt" rev-parse --abbrev-ref HEAD 2>/dev/null)
  case "$branch" in "$BASE"|master) PROTECTED+=("$wt|on $branch"); return 0 ;; esac
  age=$(( (now - $(last_active "$wt")) / 86400 ))
  [ "$age" -lt "$AGE_DAYS" ] && { PROTECTED+=("$wt|active ${age}d ago"); return 0; }
  n=$(unpushed "$wt")
  [ "$n" != "0" ] && { REVIEW+=("$wt|$n unpushed commit(s) [$branch]"); return 0; }
  r=$(residue "$wt")
  [ "$r" != "0" ] && { REVIEW+=("$wt|$r non-churn change(s), idle ${age}d [$branch]"); return 0; }
  SAFE+=("$wt|clean, idle ${age}d [$branch]")
}

git -C "$REPO" worktree prune 2>/dev/null
cur=""; lock=0; first=1; primary=1
while IFS= read -r line; do
  case "$line" in
    worktree\ *)
      [ -n "$cur" ] && classify "$cur" "$lock" "$primary"
      cur="${line#worktree }"; lock=0
      if [ "$first" = "1" ]; then primary=1; first=0; else primary=0; fi ;;
    locked*) lock=1 ;;
  esac
done < <(git -C "$REPO" worktree list --porcelain 2>/dev/null)
[ -n "$cur" ] && classify "$cur" "$lock" "$primary"

report(){
  local title="$1"; shift
  echo; echo "$title ($#)"
  local e
  for e in "$@"; do echo "    ${e%%|*}  --  ${e#*|}"; done
}
report "SAFE (reapable)" "${SAFE[@]+"${SAFE[@]}"}"
report "REVIEW (holds work that is not on a remote; left alone)" "${REVIEW[@]+"${REVIEW[@]}"}"
report "PROTECTED (skipped by rule)" "${PROTECTED[@]+"${PROTECTED[@]}"}"

if [ "$APPLY" = "1" ] && [ ${#SAFE[@]} -gt 0 ]; then
  echo; echo "removing ${#SAFE[@]} worktree(s)..."
  for e in "${SAFE[@]}"; do
    wt="${e%%|*}"
    # Re-prove both conditions at the moment of action; --force is only passed because
    # churn would otherwise make git refuse.
    r=$(residue "$wt"); n=$(unpushed "$wt")
    if [ "$r" != "0" ]; then echo "    SKIPPED ($r non-churn change(s) appeared): $wt"; continue; fi
    if [ "$n" != "0" ]; then echo "    SKIPPED ($n unpushed commit(s) appeared): $wt"; continue; fi
    if git -C "$REPO" worktree remove --force "$wt" 2>/dev/null; then echo "    removed  $wt"
    else echo "    SKIPPED (git refused; check by hand): $wt"; fi
  done
  git -C "$REPO" worktree prune 2>/dev/null
fi

REPO_P=$(cd "$REPO" && pwd -P)
# Never delete the repo, anything that contains it, its parent, the home dir or /.
too_broad(){
  local p; p=$(cd "$1" 2>/dev/null && pwd -P) || return 0
  case "$p" in /|"$HOME"|"$(cd "$HOME" 2>/dev/null && pwd -P)"|"$(dirname "$REPO_P")") return 0 ;; esac
  case "$REPO_P/" in "$p"/*) return 0 ;; esac
  return 1
}

if [ "$ORPHANS" = "1" ] && [ -n "${REAP_ORPHAN_ROOTS:-}" ]; then
  echo; echo "orphan sweep (non-git dirs idle ${AGE_DAYS}d+ under REAP_ORPHAN_ROOTS)"
  for pat in $REAP_ORPHAN_ROOTS; do
    for d in $pat; do
      [ -d "$d" ] || continue
      too_broad "$d" && { echo "    REFUSED (repo, its parent, an ancestor, home or /): $d"; continue; }
      [ -e "$d/.git" ] && { echo "    has .git, left alone: $d"; continue; }
      if [ -L "$d" ]; then
        # A symlink or junction: remove the link only, never recurse into its target.
        if [ "$APPLY" = "1" ]; then rm -f "$d" && echo "    unlinked  $d"; else echo "    would unlink  $d"; fi
        continue
      fi
      age=$(( (now - $(mtime "$d")) / 86400 ))
      [ "$age" -lt "$AGE_DAYS" ] && continue
      if [ "$APPLY" = "1" ]; then rm -rf "$d" && echo "    removed  $d"; else echo "    would remove  idle ${age}d  $d"; fi
    done
  done
fi

echo
[ "$APPLY" = "1" ] || echo "DRY RUN: nothing was deleted. Re-run with --apply to act."
