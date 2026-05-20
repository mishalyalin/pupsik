#!/usr/bin/env bash
# update.sh — pull the latest Pupsik from GitHub and re-apply installable bits.
#
# Run this from inside your local pupsik clone:
#   bash tools/update.sh           # safe update (refuses if you have local edits)
#   bash tools/update.sh --force   # stash uncommitted changes, then update
#
# What this DOES touch (smart-merge - never clobbers your edits):
#   - tools/{contacts_db,memory_search,note,doctor,
#            enrichment_schema_migrate,flag_russian_speakers,
#            now,note_graph,note_graph_schema,rules,brand_os}.py
#                                                 in ~/Desktop/claude/tools/
#   - hooks/{pre,post}-compact.sh                 in ~/Desktop/claude/.claude/hooks/
#   - templates/critical-rules.md.template        in ~/.claude/rules/critical-rules.md (append-only)
#   - memory_templates/feedback_*.md              in ~/.claude/projects/<slug>/memory/
#
# Scheduled-task templates (templates/scheduled-tasks/*.md.template) are NOT
# auto-installed — they are opt-in cron tasks. To enable one, copy the
# template to ~/.claude/scheduled-tasks/<task-name>/SKILL.md (drop the
# .template suffix), then register the cron via Claude Code's
# scheduled-tasks MCP. The matching memory_templates/feedback_*.md operating
# rule IS auto-installed (since it documents the task without enabling it).
#
# Smart-merge per file:
#   - Identical to upstream → nothing happens.
#   - You haven't modified it (matches the latest .bak) → safely overwritten,
#     a new .bak.<timestamp> backup is kept.
#   - You modified it → upstream version is dropped side-by-side as <file>.new.
#     Your edits stay untouched. Diff and merge manually.
#
# critical-rules.md is append-only: new rule references from the upstream
# template are appended under a "## Updates from upstream <date>" header.
# Your existing file is never replaced.
#
# What this does NOT touch:
#   - your CLAUDE.md, contacts.db, memory/learnings/, memory/decisions/,
#     memory/journal/, briefings/, outputs/, research/.
#
# Exit codes:
#   0  up to date or update succeeded
#   2  not a git repo
#   3  uncommitted local changes (without --force)
#   4  cannot fast-forward (you have local commits not in origin)

set -euo pipefail

# ---------- Flags ----------
QUIET=0
PASSTHROUGH_ARGS=()
for arg in "$@"; do
  case "$arg" in
    --quiet)
      QUIET=1
      ;;
    *)
      PASSTHROUGH_ARGS+=("$arg")
      ;;
  esac
done

# ---------- Move to repo root ----------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."
REPO_ROOT="$(pwd)"

# ---------- Version + state file paths ----------
STATE_DIR="$HOME/.pupsik-state"
STATE_FILE="$STATE_DIR/last-applied-version"
VERSION_FILE="$REPO_ROOT/VERSION"

# Capture PRE_VERSION before the pull. Fallback to state file, else "first-run".
PRE_VERSION="first-run"
if [ -f "$VERSION_FILE" ]; then
  PRE_VERSION="$(cat "$VERSION_FILE" 2>/dev/null || echo first-run)"
elif [ -f "$STATE_FILE" ]; then
  PRE_VERSION="$(cat "$STATE_FILE" 2>/dev/null || echo first-run)"
fi

# ---------- Sanity ----------
if ! git rev-parse --git-dir >/dev/null 2>&1; then
  echo "[pupsik] error: $REPO_ROOT is not a git repo."
  echo "         Did you 'git clone https://github.com/mishalyalin/pupsik.git', or download a zip?"
  echo "         Auto-update needs the git history. Re-clone with git."
  exit 2
fi

if ! git remote get-url origin >/dev/null 2>&1; then
  echo "[pupsik] error: this clone has no 'origin' remote configured."
  echo "         Run: git remote add origin https://github.com/mishalyalin/pupsik.git"
  exit 2
fi

# ---------- Fetch ----------
echo "[pupsik] checking for updates..."
git fetch origin --quiet

LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse origin/main)

if [ "$LOCAL" = "$REMOTE" ]; then
  echo "[pupsik] already up to date ($(git rev-parse --short HEAD))"
  exit 0
fi

# ---------- Show what's coming ----------
echo "[pupsik] new commits:"
git log --oneline "$LOCAL..$REMOTE" | head -10
COUNT=$(git rev-list --count "$LOCAL..$REMOTE")
if [ "$COUNT" -gt 10 ]; then
  echo "  ...and $((COUNT - 10)) more"
fi

echo
echo "[pupsik] files changing:"
git diff --stat "$LOCAL" "$REMOTE"

# ---------- Refuse on dirty tree (unless --force) ----------
STASHED=0
if ! git diff-index --quiet HEAD --; then
  echo
  echo "[pupsik] WARNING: you have uncommitted local changes."
  FORCE=0
  for a in "${PASSTHROUGH_ARGS[@]:-}"; do
    [ "$a" = "--force" ] && FORCE=1
  done
  if [ "$FORCE" = "0" ]; then
    echo "         Stash or commit them, then re-run. Or pass --force to stash + update."
    exit 3
  fi
  echo "         --force: stashing your local changes before update..."
  git stash push --include-untracked --quiet --message "pupsik-update-auto-stash-$(date +%s)"
  STASHED=1
fi

# ---------- Fast-forward only ----------
if ! git pull --ff-only origin main --quiet 2>/dev/null; then
  echo "[pupsik] cannot fast-forward — you have local commits not in origin/main."
  echo "         Resolve manually:"
  echo "           git status"
  echo "           git log origin/main..HEAD"
  if [ "$STASHED" = "1" ]; then
    echo "         (Your --force stash is preserved at the top of 'git stash list'.)"
  fi
  exit 4
fi

NEW=$(git rev-parse --short HEAD)
echo "[pupsik] now at $NEW"

# ---------- Re-apply tools / rules / hooks / templates ----------
echo "[pupsik] applying updated tools/templates/rules to your workspace..."
if ! bash "$REPO_ROOT/install.sh" --update-only; then
  echo "[pupsik] WARNING: install.sh --update-only returned non-zero."
  echo "         You may need to re-run 'bash install.sh' manually."
fi

# ---------- Restore stash if we stashed ----------
if [ "$STASHED" = "1" ]; then
  echo "[pupsik] restoring your stashed local changes..."
  if git stash pop --quiet; then
    echo "[pupsik]   stash restored cleanly."
  else
    echo "[pupsik]   stash pop hit conflicts — resolve manually with 'git status'."
    echo "          Your changes are still in the stash list ('git stash list')."
  fi
fi

# ---------- Smart-merge tally ----------
# install.sh writes its per-file actions to $HOME/Desktop/claude/.pupsik-update.log
# Format: "<category>\t<path>" per line. Categories: new, updated, unchanged, new_sidecar.
SMART_LOG="$HOME/Desktop/claude/.pupsik-update.log"
echo
echo "[pupsik] update summary:"
if [ -f "$SMART_LOG" ]; then
  # grep -c returns exit 1 when there are zero matches. "|| true" lets the
  # script continue under set -e; the "0" stdout from grep -c is captured as-is.
  updated_count=$(grep   -c '^updated	'    "$SMART_LOG" || true)
  new_count=$(grep       -c '^new	'         "$SMART_LOG" || true)
  unchanged_count=$(grep -c '^unchanged	'   "$SMART_LOG" || true)
  sidecar_count=$(grep   -c '^new_sidecar	' "$SMART_LOG" || true)
  echo "  $updated_count files updated to new version"
  echo "  $new_count files installed for the first time"
  echo "  $unchanged_count files unchanged (already up to date)"
  if [ "${sidecar_count:-0}" -gt 0 ]; then
    echo "  $sidecar_count files have .new versions awaiting merge:"
    grep '^new_sidecar	' "$SMART_LOG" | cut -f2 | sed 's/^/    - /'
    echo
    echo "  Inspect with: diff <file> <file>.new"
    echo "  When done:    rm <file>.new   (or replace the original)"
  fi
else
  echo "  (no smart-merge log found; install.sh may have failed before writing one)"
fi

echo
echo "[pupsik] update complete."
echo "         Open a fresh Claude Code session to pick up new rules."

# ---------- Release notification (version-aware) ----------
# Read POST_VERSION from the freshly-pulled VERSION file.
POST_VERSION=""
if [ -f "$VERSION_FILE" ]; then
  POST_VERSION="$(cat "$VERSION_FILE" 2>/dev/null || echo)"
fi

mkdir -p "$STATE_DIR"

if [ -z "$POST_VERSION" ]; then
  # No VERSION file in the pulled tree (pre-version-system release). Skip
  # the notification flow entirely.
  :
elif [ "$PRE_VERSION" = "first-run" ]; then
  # No prior version recorded - treat as silent enrollment.
  echo "$POST_VERSION" > "$STATE_FILE"
elif [ "$PRE_VERSION" = "$POST_VERSION" ]; then
  # Already on this version. Silent.
  echo "$POST_VERSION" > "$STATE_FILE"
else
  # Cross-release upgrade. Extract CHANGELOG section(s) between
  # PRE (exclusive) and POST (inclusive) and print a banner.
  CHANGELOG_FILE="$REPO_ROOT/CHANGELOG.md"
  CHANGELOG_EXTRACT=""
  if [ -f "$CHANGELOG_FILE" ]; then
    # POST_VERSION is "YYYY-MM-DD.N"; PRE_VERSION same shape.
    # The CHANGELOG entries are headed by "## [YYYY-MM-DD] - title".
    # We extract every "## [date]" section where date > PRE_DATE and
    # date <= POST_DATE. Sections are delimited by the next "## [" header
    # or end of file.
    POST_DATE="${POST_VERSION%%.*}"
    PRE_DATE="${PRE_VERSION%%.*}"
    CHANGELOG_EXTRACT=$(python3 - "$CHANGELOG_FILE" "$PRE_DATE" "$POST_DATE" <<'PYEOF'
import sys, re
path, pre_date, post_date = sys.argv[1], sys.argv[2], sys.argv[3]
try:
    with open(path, encoding="utf-8") as f:
        text = f.read()
except OSError:
    sys.exit(0)
# Split on level-2 headings that match "## [YYYY-MM-DD] ..."
pattern = re.compile(r"^## \[(\d{4}-\d{2}-\d{2})\][^\n]*$", re.MULTILINE)
matches = list(pattern.finditer(text))
out_chunks = []
for i, m in enumerate(matches):
    date = m.group(1)
    if not (pre_date < date <= post_date):
        continue
    start = m.start()
    end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
    out_chunks.append(text[start:end].rstrip())
print("\n\n".join(out_chunks))
PYEOF
)
  fi

  echo
  echo "═══════════════════════════════════════════════════════"
  echo "🆕 Pupsik updated: $PRE_VERSION -> $POST_VERSION"
  echo "═══════════════════════════════════════════════════════"
  echo
  if [ -n "$CHANGELOG_EXTRACT" ]; then
    printf "%s\n" "$CHANGELOG_EXTRACT"
  else
    echo "  (No CHANGELOG entries found for this range. See CHANGELOG.md for full notes.)"
  fi
  echo
  echo "(Full notes: CHANGELOG.md - Breaking changes: see UPGRADING.md)"
  echo

  if [ "$QUIET" = "0" ] && [ -t 0 ]; then
    # Pause until user acknowledges. Tolerate read EOF (non-interactive shells).
    read -rp "Press ENTER to acknowledge..." _ack || true
  fi

  echo "$POST_VERSION" > "$STATE_FILE"
fi
