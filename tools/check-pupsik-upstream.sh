#!/usr/bin/env bash
# check-pupsik-upstream.sh — per-file drift probe between the pupsik CLONE and
# the WORKSPACE copies smart-merge installs from it.
#
# This is a DIFFERENT question from tools/check-update.sh (which asks "is my
# clone behind origin/main on GitHub?"). This script asks "for each tracked
# tool file, do the clone and the workspace already agree, and if not, which
# side moved more recently?" - useful after you've hand-edited a tool in the
# workspace (a common way local fixes get made) and want to know whether that
# fix is still only local, or whether the clone has since diverged too.
#
#   bash tools/check-pupsik-upstream.sh              # human-readable table
#   bash tools/check-pupsik-upstream.sh --json        # machine-readable
#
# CLONE_PATH resolution mirrors check-update.sh: PUPSIK_CLONE env var → this
# script's own repo root (natural when run from inside the clone) →
# <workspace>/state/pupsik/clone-path.txt written by install.sh.
# WORKSPACE resolution: CLAUDE_WORKSPACE or WORKSPACE env var, else
# ~/Desktop/claude.
#
# Tracked files: the same list install.sh smart-merges (tools/*.py + the two
# compact hooks), read from THIS script's own TRACKED_TOOLS array below - not
# parsed out of install.sh, so keep the two lists in sync by hand if the
# tracked set changes.
#
# For each tracked file present in BOTH the clone and the workspace:
#   - identical bytes            -> "in sync"
#   - differ, clone mtime newer  -> "repo ahead"      (clone has an update
#                                     the workspace hasn't picked up yet -
#                                     run tools/update.sh)
#   - differ, workspace newer    -> "workspace ahead"  (a local edit that
#                                     hasn't been contributed back upstream)
#   - differ, same mtime (rare,
#     e.g. a fresh checkout)     -> "diverged"          (can't tell direction
#                                     from mtime alone - diff by hand)
# Files missing on one side are reported as "clone-only" / "workspace-only".
#
# FAIL-SOFT: this is a read-only report. Any error on an individual file
# (unreadable, etc) is recorded per-file and does not abort the run. The
# script always exits 0 - it's a diagnostic, not a gate. It also does NOT
# touch git, network, or write anywhere - it only reads local files - so
# there is nothing to opt out of and nothing to throttle.

set -uo pipefail

WORKSPACE="${CLAUDE_WORKSPACE:-${WORKSPACE:-$HOME/Desktop/claude}}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." 2>/dev/null && pwd)"

is_pupsik_clone() {
  local d="$1"
  [ -n "$d" ] && [ -d "$d" ] || return 1
  git -C "$d" rev-parse --git-dir >/dev/null 2>&1 || return 1
  git -C "$d" remote get-url origin 2>/dev/null | grep -qi "pupsik" || return 1
  return 0
}

CLONE_PATH=""
for cand in \
  "${PUPSIK_CLONE:-}" \
  "$SCRIPT_DIR" \
  "$(cat "$WORKSPACE/state/pupsik/clone-path.txt" 2>/dev/null || true)"
do
  if is_pupsik_clone "$cand"; then
    CLONE_PATH="$(cd "$cand" && pwd)"
    break
  fi
done

JSON_MODE=0
for a in "$@"; do
  [ "$a" = "--json" ] && JSON_MODE=1
done

if [ -z "$CLONE_PATH" ]; then
  if [ "$JSON_MODE" = "1" ]; then
    printf '{"error":"could not locate a pupsik clone (set PUPSIK_CLONE, or run from inside the clone, or ensure state/pupsik/clone-path.txt exists)","files":[]}\n'
  else
    echo "error: could not locate a pupsik clone."
    echo "  set PUPSIK_CLONE=/path/to/pupsik, or run this from inside the clone,"
    echo "  or make sure $WORKSPACE/state/pupsik/clone-path.txt points at one."
  fi
  exit 0
fi

# Same tracked-tool set update.sh's header comment documents (tools/*.py) plus
# the two compact hooks it smart-merges. Keep in sync with install.sh by hand.
TRACKED_TOOLS=(
  "tools/contacts_db.py"
  "tools/memory_search.py"
  "tools/note.py"
  "tools/doctor.py"
  "tools/enrichment_schema_migrate.py"
  "tools/now.py"
  "tools/note_graph.py"
  "tools/note_graph_schema.py"
  "tools/rules.py"
  "tools/brand_os.py"
  "tools/context_budget.py"
  "tools/mcp_profile.py"
  "tools/claude_md_trim.py"
  ".claude/hooks/pre-compact.sh"
  ".claude/hooks/post-compact.sh"
)

# install.sh installs hooks/{pre,post}-compact.sh (clone-relative path
# "hooks/...") into $WORKSPACE/.claude/hooks/{pre,post}-compact.sh (workspace-
# relative path ".claude/hooks/..."). Every other tracked file keeps the same
# relative path on both sides. This map covers that one exception.
clone_rel_path() {
  case "$1" in
    .claude/hooks/pre-compact.sh)  echo "hooks/pre-compact.sh" ;;
    .claude/hooks/post-compact.sh) echo "hooks/post-compact.sh" ;;
    *)                              echo "$1" ;;
  esac
}

mtime_of() {
  # $1 = path. Portable mtime-as-epoch-seconds (BSD stat on macOS, GNU stat on
  # Linux). Prints "" on failure.
  stat -f "%m" "$1" 2>/dev/null || stat -c "%Y" "$1" 2>/dev/null || true
}

results_json="[]"
have_any=0
rows_text=()

for rel in "${TRACKED_TOOLS[@]}"; do
  clone_rel="$(clone_rel_path "$rel")"
  clone_file="$CLONE_PATH/$clone_rel"
  ws_file="$WORKSPACE/$rel"

  clone_exists=0; [ -f "$clone_file" ] && clone_exists=1
  ws_exists=0; [ -f "$ws_file" ] && ws_exists=1

  if [ "$clone_exists" = "0" ] && [ "$ws_exists" = "0" ]; then
    continue  # not installed on either side - not this repo's business to flag
  fi

  status=""
  diff_lines=0
  clone_mtime=""
  ws_mtime=""

  if [ "$clone_exists" = "1" ] && [ "$ws_exists" = "0" ]; then
    status="clone-only"
  elif [ "$clone_exists" = "0" ] && [ "$ws_exists" = "1" ]; then
    status="workspace-only"
  else
    if cmp -s "$clone_file" "$ws_file"; then
      status="in sync"
    else
      diff_lines="$(diff -U0 "$clone_file" "$ws_file" 2>/dev/null | grep -Ec '^[+-][^+-]' || true)"
      clone_mtime="$(mtime_of "$clone_file")"
      ws_mtime="$(mtime_of "$ws_file")"
      if [ -n "$clone_mtime" ] && [ -n "$ws_mtime" ]; then
        if [ "$clone_mtime" -gt "$ws_mtime" ]; then
          status="repo ahead"
        elif [ "$ws_mtime" -gt "$clone_mtime" ]; then
          status="workspace ahead"
        else
          status="diverged"
        fi
      else
        status="diverged"  # couldn't stat one side - can't tell direction
      fi
    fi
  fi

  have_any=1
  rows_text+=("$rel|$status|$diff_lines")

  results_json=$(python3 - "$results_json" "$rel" "$status" "$diff_lines" "$clone_mtime" "$ws_mtime" <<'PYEOF'
import json, sys
rows = json.loads(sys.argv[1])
rows.append({
    "file": sys.argv[2],
    "status": sys.argv[3],
    "diff_lines": int(sys.argv[4] or 0),
    "clone_mtime": int(sys.argv[5]) if sys.argv[5] else None,
    "ws_mtime": int(sys.argv[6]) if sys.argv[6] else None,
})
print(json.dumps(rows))
PYEOF
  )
done

if [ "$JSON_MODE" = "1" ]; then
  python3 - "$results_json" "$CLONE_PATH" "$WORKSPACE" <<'PYEOF'
import json, sys
rows = json.loads(sys.argv[1])
print(json.dumps({"clone_path": sys.argv[2], "workspace": sys.argv[3], "files": rows}, indent=2))
PYEOF
  exit 0
fi

echo "pupsik clone:  $CLONE_PATH"
echo "workspace:     $WORKSPACE"
echo ""

if [ "$have_any" = "0" ]; then
  echo "no tracked files found on either side."
  exit 0
fi

printf "%-45s %-16s %s\n" "FILE" "STATUS" "DIFF LINES"
for row in "${rows_text[@]}"; do
  IFS='|' read -r f s d <<< "$row"
  case "$s" in
    "repo ahead")      marker="repo ahead     (run tools/update.sh)" ;;
    "workspace ahead")  marker="workspace ahead (local edit not yet contributed upstream)" ;;
    "diverged")         marker="diverged        (diff by hand)" ;;
    "clone-only")       marker="clone-only      (not installed in workspace)" ;;
    "workspace-only")   marker="workspace-only  (not present in this clone)" ;;
    "in sync")          marker="in sync" ;;
    *)                  marker="$s" ;;
  esac
  if [ "$s" = "in sync" ]; then
    printf "%-45s %s\n" "$f" "$marker"
  else
    printf "%-45s %s (%s)\n" "$f" "$marker" "${d:-0} line(s) differ"
  fi
done

exit 0
