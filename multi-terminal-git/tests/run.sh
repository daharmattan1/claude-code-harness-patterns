#!/usr/bin/env bash
# run.sh -- tests for the multi-terminal git scripts, each against a throwaway repo and a
# bare "origin". Every repo lives under a temp dir that is deleted on exit.
#
#   bash multi-terminal-git/tests/run.sh
#
# Set TMPDIR to choose where the throwaway repos go.
set -u

HERE=$(cd "$(dirname "$0")" && pwd)
BIN="$HERE/../bin"
HOOKS="$HERE/../hooks"
ROOT=$(mktemp -d "${TMPDIR:-/tmp}/mtg-tests.XXXXXX")
trap 'rm -rf "$ROOT"' EXIT
export GIT_AUTHOR_NAME=Test GIT_AUTHOR_EMAIL=test@example.com
export GIT_COMMITTER_NAME=Test GIT_COMMITTER_EMAIL=test@example.com
export GIT_CONFIG_GLOBAL="$ROOT/gitconfig"   # isolate from the user's git config
printf '[init]\n\tdefaultBranch = main\n[core]\n\tautocrlf = false\n\tlongpaths = true\n' > "$GIT_CONFIG_GLOBAL"
unset NEWWORK_BASE NEWWORK_REMOTE NEWWORK_WT_PREFIX NEWWORK_BRANCH_PREFIX REAP_CHURN REAP_AGE_DAYS 2>/dev/null

PASS=0; FAIL=0
ok()   { PASS=$((PASS+1)); echo "  ok    $1"; }
bad()  { FAIL=$((FAIL+1)); echo "  FAIL  $1"; }
check(){ if eval "$2"; then ok "$1"; else bad "$1"; fi; }

# A fresh bare origin plus a clone with one commit on main. Echoes the clone path.
new_repo(){
  local name=$1 d="$ROOT/$1"
  git init -q --bare "$d/origin.git"
  git clone -q "$d/origin.git" "$d/shared" 2>/dev/null
  ( cd "$d/shared" && echo base > base.txt && echo "line" > shared.txt &&
    git add . && git commit -qm base && git push -q origin main )
  echo "$d/shared"
}
set_mtime_days_ago(){ python3 -c "import os,sys,time;t=time.time()-int(sys.argv[2])*86400;os.utime(sys.argv[1],(t,t))" "$1" "$2" 2>/dev/null \
  || python -c "import os,sys,time;t=time.time()-int(sys.argv[2])*86400;os.utime(sys.argv[1],(t,t))" "$1" "$2"; }
tree_fingerprint(){ (cd "$1" && { git rev-parse HEAD; git ls-files -s; git status --porcelain; git diff; } | git hash-object --stdin); }

# --------------------------------------------------------------------------------------
echo "land-to-main.sh"
R=$(new_repo land)
(
  cd "$R"
  git checkout -qb shared-work
  echo a > a.txt && git add a.txt && git commit -qm "add a"
  echo b > b.txt && git add b.txt && git commit -qm "add b"
  echo "unfinished" > wip.txt && git add wip.txt && git commit -qm "wip: not ready"
  echo "someone else's unsaved edit" >> base.txt          # dirty tree, like a busy shared branch
  echo staged > staged.txt && git add staged.txt          # and a staged file
)
A=$(git -C "$R" rev-parse HEAD~2); B=$(git -C "$R" rev-parse HEAD~1)
before=$(tree_fingerprint "$R")
out=$(cd "$R" && bash "$BIN/land-to-main.sh" land-ab "$A" "$B" 2>&1); rc=$?
check "lands two chosen commits (exit 0)" '[ $rc -eq 0 ]'
git -C "$R" fetch -q origin
check "PR branch has exactly those two commits on main" \
  '[ "$(git -C "$R" log --format=%s origin/main..origin/land-ab)" = "$(printf "add b\nadd a")" ]'
check "unfinished commit was not landed" '! git -C "$R" log --format=%s origin/land-ab | grep -q wip'
check "working tree, index and HEAD untouched" '[ "$(tree_fingerprint "$R")" = "$before" ]'

git -C "$R" push -q origin origin/land-ab:refs/heads/main                   # pretend the PR merged
out=$(cd "$R" && bash "$BIN/land-to-main.sh" land-again "$A" 2>&1); rc=$?
check "already-landed commit is skipped and nothing pushed" '[ $rc -ne 0 ] && echo "$out" | grep -q "skip"'
check "no branch was pushed for the no-op" '[ -z "$(git -C "$R" ls-remote --heads origin land-again)" ]'

R2=$(new_repo conflict)
( cd "$R2" && git checkout -qb feat && echo "feature version" > shared.txt && git commit -qam "edit shared" &&
  git checkout -q main && echo "main version" > shared.txt && git commit -qam "main edit" && git push -q origin main )
C=$(git -C "$R2" rev-parse feat)
out=$(cd "$R2" && bash "$BIN/land-to-main.sh" land-conflict "$C" 2>&1); rc=$?
check "conflict stops with exit 1" '[ $rc -ne 0 ] && echo "$out" | grep -q CONFLICT'
check "conflict pushes nothing" '[ -z "$(git -C "$R2" ls-remote --heads origin land-conflict)" ]'

( cd "$R2" && git checkout -q -b m1 main~1 && echo x > x.txt && git add x.txt && git commit -qm x &&
  git merge -q --no-ff -m merge feat 2>/dev/null || true )
M=$(git -C "$R2" rev-parse HEAD)
out=$(cd "$R2" && bash "$BIN/land-to-main.sh" land-merge "$M" 2>&1); rc=$?
check "merge commits are refused" '[ $rc -ne 0 ] && echo "$out" | grep -q "refusing merge commit"'

out=$(cd "$R2" && bash "$BIN/land-to-main.sh" --base 2>&1); rc=$?
check "option without a value fails with a clear message" '[ $rc -ne 0 ] && echo "$out" | grep -q "needs a value"'

# --------------------------------------------------------------------------------------
echo "pre-commit-nostash.sh"
R=$(new_repo hook)
cp "$HOOKS/pre-commit-nostash.sh" "$R/.git/hooks/pre-commit"; chmod +x "$R/.git/hooks/pre-commit"
SHIM="$ROOT/shim"; mkdir -p "$SHIM"
SHIM=$(cd "$SHIM" && pwd)   # POSIX form: a Windows "C:/..." entry would split PATH at its colon
printf '#!/usr/bin/env bash\necho "$@" >> "%s/precommit_args"\nexit 0\n' "$ROOT" > "$SHIM/pre-commit"; chmod +x "$SHIM/pre-commit"
NOSHIM_PATH=$(echo "$PATH" | tr ':' '\n' | while read -r p; do [ -x "$p/pre-commit" ] || echo "$p"; done | paste -sd: -)

( cd "$R" && echo one > one.txt && git add one.txt )
out=$(cd "$R" && PATH="$NOSHIM_PATH" git commit -qm one 2>&1); rc=$?
check "fails closed when pre-commit is missing" '[ $rc -ne 0 ] && echo "$out" | grep -q "not on PATH"'
out=$(cd "$R" && PATH="$NOSHIM_PATH" NOSTASH_ALLOW_NO_PRECOMMIT=1 git commit -qm one 2>&1); rc=$?
check "override commits unchecked" '[ $rc -eq 0 ]'

( cd "$R" && echo "other terminal's unsaved work" >> shared.txt && echo two > two.txt && git add two.txt )
out=$(cd "$R" && PATH="$SHIM:$PATH" git commit -qm two 2>&1); rc=$?
check "commits with the framework present" '[ $rc -eq 0 ]'
check "framework called with --files and only the staged file" 'grep -q -- "--files two.txt$" "$ROOT/precommit_args"'
check "unstaged edits in other files survive" 'grep -q "unsaved work" "$R/shared.txt"'

( cd "$R" && echo v1 > three.txt && git add three.txt && echo v2 >> three.txt )
out=$(cd "$R" && PATH="$SHIM:$PATH" git commit -qm three 2>&1); rc=$?
check "partially staged file is refused" '[ $rc -ne 0 ] && echo "$out" | grep -q "unstaged changes on top"'
check "refusal leaves the working copy intact" 'grep -q v2 "$R/three.txt"'

# --------------------------------------------------------------------------------------
echo "newwork.sh"
R=$(new_repo newwork)
out=$(cd "$R" && bash "$BIN/newwork.sh" 2>&1); rc=$?
check "drift report runs without a slug" '[ $rc -eq 0 ] && echo "$out" | grep -q "drift"'
check "no slug creates no worktree" '[ "$(git -C "$R" worktree list | wc -l | tr -d " ")" = "1" ]'
out=$(cd "$R" && bash "$BIN/newwork.sh" feat-x 2>&1); rc=$?
check "slug creates a worktree beside the repo" '[ $rc -eq 0 ] && [ -f "$ROOT/newwork/_wt-feat-x/base.txt" ]'
check "on a new branch off main" '[ "$(git -C "$ROOT/newwork/_wt-feat-x" rev-parse --abbrev-ref HEAD)" = "work/feat-x" ]'
check "shared tree did not switch branches" '[ "$(git -C "$R" rev-parse --abbrev-ref HEAD)" = "main" ]'
( cd "$ROOT/newwork/upstream-clone" 2>/dev/null || git clone -q "$ROOT/newwork/origin.git" "$ROOT/newwork/upstream-clone" 2>/dev/null
  cd "$ROOT/newwork/upstream-clone" && echo new > upstream.txt && git add upstream.txt && git commit -qm upstream && git push -q origin main )
echo "my unsaved edit" >> "$R/base.txt"
out=$(cd "$R" && bash "$BIN/newwork.sh" 2>&1)
check "base checked out in the shared tree is not fast-forwarded there"   '[ ! -f "$R/upstream.txt" ] && echo "$out" | grep -q "not touching a working tree"'
check "unsaved edits in the shared tree survive" 'grep -q "my unsaved edit" "$R/base.txt"'
out=$(cd "$R" && NEWWORK_WT_PREFIX=wt_ NEWWORK_BRANCH_PREFIX=topic/ bash "$BIN/newwork.sh" y 2>&1)
check "prefixes are configurable" '[ -d "$ROOT/newwork/wt_y" ] && git -C "$R" rev-parse -q --verify topic/y >/dev/null'

# --------------------------------------------------------------------------------------
echo "reap-worktrees.sh"
R=$(new_repo reap); P="$ROOT/reap"
( cd "$R"
  git worktree add -q "$P/clean" -b clean && git -C "$P/clean" push -q origin clean
  git worktree add -q "$P/churn" -b churn && git -C "$P/churn" push -q origin churn && echo x > "$P/churn/debug.log"
  git worktree add -q "$P/unpushed" -b unpushed && (cd "$P/unpushed" && echo u > u.txt && git add u.txt && git commit -qm u)
  git worktree add -q --detach "$P/detached" && (cd "$P/detached" && echo d > d.txt && git add d.txt && git commit -qm d)
  git worktree add -q "$P/dirty" -b dirty && git -C "$P/dirty" push -q origin dirty && echo notes > "$P/dirty/notes.md"
  git worktree add -q "$P/locked" -b locked && git -C "$P/locked" push -q origin locked && git worktree lock "$P/locked"
)
out=$(cd "$R" && bash "$BIN/reap-worktrees.sh" --age 0 2>&1)
section(){ echo "$out" | awk -v s="$1" '$0 ~ "^"s {f=1; next} /^[A-Z]+ \(/ {f=0} f'; }
check "clean pushed worktree is SAFE"       'section SAFE | grep -q "/clean "'
check "churn-only worktree is SAFE"         'section SAFE | grep -q "/churn "'
check "unpushed branch commit is REVIEW"    'section REVIEW | grep -q "/unpushed "'
check "unpushed DETACHED commit is REVIEW"  'section REVIEW | grep -q "/detached "'
check "real untracked work is REVIEW"       'section REVIEW | grep -q "/dirty "'
check "locked worktree is PROTECTED"        'section PROTECTED | grep -q "/locked "'
check "primary worktree is PROTECTED"       'section PROTECTED | grep -q "primary worktree"'
check "dry run deleted nothing"             '[ -d "$P/clean" ] && [ -d "$P/churn" ]'

out=$(cd "$R" && bash "$BIN/reap-worktrees.sh" --age 0 --apply 2>&1)
check "--apply removes the SAFE set"        '[ ! -d "$P/clean" ] && [ ! -d "$P/churn" ]'
check "--apply keeps every REVIEW worktree" '[ -d "$P/unpushed" ] && [ -d "$P/detached" ] && [ -d "$P/dirty" ]'
check "--apply keeps the locked worktree"   '[ -d "$P/locked" ]'
check "unpushed commits still reachable"    'git -C "$P/detached" log -1 --format=%s | grep -q "^d$"'

( cd "$R" && git worktree add -q "$P/fresh" -b fresh && git -C "$P/fresh" push -q origin fresh )
out=$(cd "$R" && bash "$BIN/reap-worktrees.sh" --age 14 2>&1)
check "fresh worktree is PROTECTED at --age 14" 'section PROTECTED | grep -q "/fresh "'
gd=$(git -C "$P/fresh" rev-parse --path-format=absolute --git-dir)
set_mtime_days_ago "$P/fresh" 30; set_mtime_days_ago "$gd/index" 30
out=$(cd "$R" && bash "$BIN/reap-worktrees.sh" --age 14 2>&1)
check "aged worktree becomes SAFE"          'section SAFE | grep -q "/fresh "'

( cd "$R" && git worktree add -q "$P/renamed" -b renamed && git -C "$P/renamed" push -q origin renamed &&
  cd "$P/renamed" && git mv base.txt moved.log )
out=$(cd "$R" && bash "$BIN/reap-worktrees.sh" --age 0 2>&1)
check "rename of real work to a churn-looking name is REVIEW" 'section REVIEW | grep -q "/renamed "'

mkdir -p "$ROOT/reap-orphans/old-tmp"; set_mtime_days_ago "$ROOT/reap-orphans/old-tmp" 30
out=$(cd "$R" && REAP_ORPHAN_ROOTS="$ROOT/reap/* $ROOT/reap-orphans/*" bash "$BIN/reap-worktrees.sh" --include-orphans --apply 2>&1)
check "orphan sweep refuses the repo itself"       'echo "$out" | grep -q "REFUSED.*shared" || [ -d "$R/.git" ]'
check "repo survives a broad orphan root"          '[ -d "$R/.git" ] && [ -f "$R/base.txt" ]'
check "a real idle orphan is removed"              '[ ! -d "$ROOT/reap-orphans/old-tmp" ]'
out=$(cd "$R" && REAP_ORPHAN_ROOTS="$ROOT" bash "$BIN/reap-worktrees.sh" --include-orphans --apply 2>&1)
check "an ancestor of the repo is refused"         'echo "$out" | grep -q REFUSED && [ -d "$R/.git" ]'

out=$(cd "$R" && REAP_CHURN= bash "$BIN/reap-worktrees.sh" 2>&1); rc=$?
check "empty REAP_CHURN is refused"         '[ $rc -eq 2 ]'

# --------------------------------------------------------------------------------------
echo
echo "passed: $PASS   failed: $FAIL"
[ "$FAIL" -eq 0 ]
