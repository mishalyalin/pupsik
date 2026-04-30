#!/usr/bin/env bash
# update.sh — pull the latest Pupsik from GitHub and re-apply installable bits.
#
# Run this from inside your local pupsik clone:
#   bash tools/update.sh           # safe update (refuses if you have local edits)
#   bash tools/update.sh --force   # stash uncommitted changes, then update
#
# What this DOES touch (smart-merge — never clobbers your edits):
#   - tools/{contacts_db,memory_search,note}.py   in ~/Desktop/claude/tools/
#   - hooks/{pre,post}-compact.sh                 in ~/Desktop/claude/.claude/hooks/
#   - templates/critical-rules.md.template        in ~/.claude/rules/critical-rules.md (append-only)
#   - memory_templates/feedback_*.md              in ~/.claude/projects/<slug>/memory/
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

# ---------- Move to repo root ----------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."
REPO_ROOT="$(pwd)"

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
  if [ "${1:-}" != "--force" ]; then
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
