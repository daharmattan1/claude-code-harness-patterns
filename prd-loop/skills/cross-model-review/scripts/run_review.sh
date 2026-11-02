#!/usr/bin/env bash
# run_review.sh -- run the four cross-model review lenses on a plan, in parallel.
#
#   bash run_review.sh <plan.md> <out-dir> [extra-file ...]
#
# Writes <out-dir>/{codex-code,gemini-code,codex-concept,gemini-concept}.json and a .stderr
# beside each. Run it from the root of the repository the plan is about.
set -u

# ---- config: the only place models and timeouts are named ----------------------------
CODEX_MODEL=${CODEX_MODEL:-gpt-6-astra}
CODEX_FALLBACK_MODEL=${CODEX_FALLBACK_MODEL:-gpt-6.1-sol}
GEMINI_MODEL=${GEMINI_MODEL:-gemini-3.1-pro-preview}
CODE_TIMEOUT=${CODE_TIMEOUT:-600}
CONCEPT_TIMEOUT=${CONCEPT_TIMEOUT:-300}
MAX_PATHS=${MAX_PATHS:-25}
# ---------------------------------------------------------------------------------------

[ $# -ge 2 ] || { echo "usage: run_review.sh <plan.md> <out-dir> [extra-file ...]" >&2; exit 2; }
PLAN=$1; OUT=$2; shift 2
[ -f "$PLAN" ] || { echo "plan not found: $PLAN" >&2; exit 2; }
HERE=$(cd "$(dirname "$0")/.." && pwd)
REF="$HERE/references"
ROOT=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
# Absolute paths before the script changes into $ROOT, so relative arguments keep working.
mkdir -p "$OUT" && OUT=$(cd "$OUT" && pwd)
PLAN=$(cd "$(dirname "$PLAN")" && pwd)/$(basename "$PLAN")

native(){ cygpath -m "$1" 2>/dev/null || echo "$1"; }   # Windows tools need C:/ paths

# Each Gemini lens gets its own throwaway settings home (two parallel CLIs never share state).
# The settings always turn off repo-wide search, which times out on large repos and burns the
# lens's whole budget; with GEMINI_API_KEY set they also select API-key auth, which a saved
# login type would otherwise override.
GEMINI_HOMES=()
cleanup(){ local d; for d in "${GEMINI_HOMES[@]+"${GEMINI_HOMES[@]}"}"; do rm -rf "$d"; done; }
trap cleanup EXIT
GEMINI_SETTINGS='{"security":{"auth":{"selectedType":"gemini-api-key"}},"tools":{"exclude":["grep_search","glob","google_web_search"]}}'
if [ -z "${GEMINI_API_KEY:-}" ]; then
  echo "NOTE: GEMINI_API_KEY is not set, so the Gemini lenses use your own Gemini CLI home and" >&2
  echo "      login. Repo-wide search stays on there and may time out the code lens. A short" >&2
  echo "      refusal that exits 0 is an auth failure, not a review." >&2
fi
gemini_home(){  # prints a fresh settings home, or nothing when there is no API key
  [ -n "${GEMINI_API_KEY:-}" ] || return 0
  local d; d=$(mktemp -d "${TMPDIR:-/tmp}/gemini-home.XXXXXX")
  mkdir -p "$d/.gemini" && printf '%s\n' "$GEMINI_SETTINGS" > "$d/.gemini/settings.json"
  echo "$d"
}

# Reading list for the code lenses: every existing repo path the plan names, plus extras.
grep -oE '[0-9A-Za-z_./-]+\.(py|ts|tsx|js|md|json|sql|sh|yaml|yml|toml)' "$PLAN" | sort -u \
  | while read -r p; do [ -e "$ROOT/$p" ] && echo "$p"; done | head -"$MAX_PATHS" > "$OUT/paths.txt"
for f in "$@"; do echo "$f" >> "$OUT/paths.txt"; done

brief(){  # brief <brief-file> <lens> <out> <code|concept> [codex|gemini]
  {
    cat "$1"
    printf '\n\n# YOUR ASSIGNED LENS: %s\n' "$2"
    if [ "$4" = code ]; then
      printf '\n# FILES THE PLAN TOUCHES. Read these directly; do not search the whole repo.\n'
      if [ "${5:-}" = gemini ]; then
        printf '# There is no shell tool in this mode: use your file-read tool only.\n'
      else
        printf '# Read them with read-only shell commands (cat, sed -n, grep -nE). Do not write anything.\n'
      fi
      cat "$OUT/paths.txt"
    fi
    printf '\n\n--- BEGIN PLAN UNDER REVIEW ---\n'
    cat "$PLAN"
    printf '\n--- END PLAN UNDER REVIEW ---\n'
  } > "$3"
}
brief "$REF/review-brief.md"            "THE FALSIFIER"          "$OUT/brief-codex-code.md"     code codex
brief "$REF/review-brief.md"            "THE 2AM OPERATOR"       "$OUT/brief-gemini-code.md"    code gemini
brief "$REF/review-brief-conceptual.md" "THE EPISTEMOLOGIST"     "$OUT/brief-codex-concept.md"  concept
brief "$REF/review-brief-conceptual.md" "THE SKEPTICAL INVESTOR" "$OUT/brief-gemini-concept.md" concept

SCHEMA=$(native "$REF/finding-schema.json")
codex_once(){  # brief out model timeout
  timeout "$4" codex exec -s read-only --ephemeral -C "$ROOT" -m "$3" \
    -c model_reasoning_effort="high" --output-schema "$SCHEMA" -o "$2" < "$1" 2>>"$2.stderr"
}
run_codex(){  # brief out timeout   (fallback model once if the first writes nothing)
  ( : > "$2.stderr"; : > "$2"
    codex_once "$1" "$2" "$CODEX_MODEL" "$3"
    if [ ! -s "$2" ]; then
      echo "fallback: $CODEX_FALLBACK_MODEL" >> "$2.stderr"
      codex_once "$1" "$2" "$CODEX_FALLBACK_MODEL" "$3"
    fi ) &
}
run_gemini(){  # brief out prompt timeout   (--skip-trust lets it read repo files)
  local home; home=$(gemini_home)
  if [ -n "$home" ]; then
    GEMINI_HOMES+=("$home")
    GEMINI_CLI_HOME=$(native "$home") timeout "$4" gemini -m "$GEMINI_MODEL" --approval-mode plan \
      --skip-trust -o text -p "$3" < "$1" > "$2" 2>"$2.stderr" &
  else
    timeout "$4" gemini -m "$GEMINI_MODEL" --approval-mode plan \
      --skip-trust -o text -p "$3" < "$1" > "$2" 2>"$2.stderr" &
  fi
}

CODE_P="Follow the review instructions on stdin. Read files in the repo to verify your claims. Output ONLY the JSON object described, no prose, no fences."
CONC_P="Follow the review instructions on stdin. This is a reasoning review: reason over the plan, do not hunt code. Output ONLY the JSON object described, no prose, no fences."

cd "$ROOT" || exit 1   # codex refuses to run outside a trusted directory
start=$(date +%s)
run_codex  "$OUT/brief-codex-code.md"     "$OUT/codex-code.json"     "$CODE_TIMEOUT";    p1=$!
run_gemini "$OUT/brief-gemini-code.md"    "$OUT/gemini-code.json"    "$CODE_P" "$CODE_TIMEOUT"; p2=$!
e3=skipped; e4=skipped
if [ "$CONCEPT_TIMEOUT" != "0" ]; then   # CONCEPT_TIMEOUT=0 runs the code lenses only
  run_codex  "$OUT/brief-codex-concept.md"  "$OUT/codex-concept.json"  "$CONCEPT_TIMEOUT"; p3=$!
  run_gemini "$OUT/brief-gemini-concept.md" "$OUT/gemini-concept.json" "$CONC_P" "$CONCEPT_TIMEOUT"; p4=$!
fi
wait $p1; e1=$?; wait $p2; e2=$?
if [ "$CONCEPT_TIMEOUT" != "0" ]; then wait $p3; e3=$?; wait $p4; e4=$?; fi

echo "elapsed $(( $(date +%s) - start ))s   exits: codex-code=$e1 gemini-code=$e2 codex-concept=$e3 gemini-concept=$e4"
for f in codex-code gemini-code codex-concept gemini-concept; do
  case "$f" in *concept) [ "$CONCEPT_TIMEOUT" = "0" ] && { echo "$f: skipped (CONCEPT_TIMEOUT=0)"; continue; } ;; esac
  b=$(wc -c < "$OUT/$f.json" 2>/dev/null || echo 0)
  flag=""; [ "$b" -lt 400 ] && flag="  <- under 400 bytes: treat as a failed lens, read $f.json.stderr"
  echo "$f: $b bytes$flag"
done
