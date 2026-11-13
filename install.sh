#!/usr/bin/env bash
# install.sh — base installer for the Claude Code personal setup package.
#
# What this does:
#   1. Checks dependencies (Python 3.10+, Node 18+, claude CLI)
#   2. Creates ~/Desktop/claude/{tools,data,outputs,memory,rules,.claude/hooks}
#   3. Copies tools/ → ~/Desktop/claude/tools/
#      (contacts_db.py, enrichment_schema_migrate.py, now.py)
#   4. Renders templates/CLAUDE.md.template → ~/Desktop/claude/CLAUDE.md (prompts for placeholders)
#   6. Copies memory_templates/feedback_*.md → ~/Desktop/claude/rules/
#      (never into Claude's own memory folder ~/.claude/projects/*/memory/)
#   6.5 Installs critical-rules.md to ~/.claude/rules/ (auto-loaded each session)
#   7. Installs the SessionStart hook to ~/Desktop/claude/.claude/hooks/
#   8. Prints JSON snippet to add to ~/.claude/settings.json to register the hook
#  10. Initializes the contacts DB
#
# Does NOT:
#   - Build the MCP servers (use install_mcps.sh)
#   - Register MCPs with Claude (use register_mcps.sh)
#   - Wire OAuth credentials (manual per docs/GOOGLE_CLOUD_SETUP.md)

set -euo pipefail

# ---------- Flags ----------
UPDATE_ONLY=0
POSITIONAL_ARGS=()
for arg in "$@"; do
  case "$arg" in
    --update-only)
      UPDATE_ONLY=1
      ;;
    --help|-h)
      cat <<USAGE
install.sh — Pupsik base installer.

Usage:
  bash install.sh [WORKSPACE] [--update-only]

Modes:
  (default)        Full install: dirs, deps, CLAUDE.md scaffold, contacts.db init,
                   tools, rules, hooks, templates.
  --update-only    Idempotent re-sync of tools, rules, hooks, and feedback templates.
                   Skips first-time-only steps:
                     - CLAUDE.md scaffold (kept if it already exists)
                     - contacts.db init (kept if it already exists)
                   Existing tool files are backed up before overwrite.
                   Existing feedback rules are LEFT ALONE (you may have edits).

Arguments:
  WORKSPACE        Defaults to \$HOME/Desktop/claude. Pass an absolute path to
                   install elsewhere.
USAGE
      exit 0
      ;;
    -*)
      printf "[install] unknown flag: %s (try --help)\n" "$arg" >&2
      exit 64
      ;;
    *)
      POSITIONAL_ARGS+=("$arg")
      ;;
  esac
done

# ---------- Paths ----------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE="${POSITIONAL_ARGS[0]:-$HOME/Desktop/claude}"
PROJECT_SLUG="$(echo "$WORKSPACE" | sed 's|/|-|g')"
# Claude's built-in memory folder for this workspace. Pupsik only READS it
# (to detect where an older install put the rules); it never writes there.
PROJECT_MEMORY_DIR="$HOME/.claude/projects/$PROJECT_SLUG/memory"
RULES_HOME="$WORKSPACE/rules"

# ---------- Helpers ----------
say()  { printf "\033[1;36m[setup]\033[0m %s\n" "$*"; }
warn() { printf "\033[1;33m[warn]\033[0m %s\n" "$*"; }
die()  { printf "\033[1;31m[error]\033[0m %s\n" "$*" >&2; exit 1; }

confirm() {
  local prompt="$1"
  local default="${2:-y}"
  local yn
  read -r -p "$prompt [$( [ "$default" = "y" ] && echo 'Y/n' || echo 'y/N')] " yn
  yn="${yn:-$default}"
  [[ "$yn" =~ ^[Yy]$ ]]
}

# ---------- Smart-merge counters + log ----------
# Track each managed-file action so update.sh can print a tally at the end.
SMART_NEW=0           # files installed for the first time
SMART_UPDATED=0       # files safely overwritten (user hadn't touched them)
SMART_UNCHANGED=0     # files identical to upstream
SMART_NEW_FILES=()    # paths where a .new sidecar was written
SMART_LOG="$HOME/Desktop/claude/.pupsik-update.log"
mkdir -p "$(dirname "$SMART_LOG")"
: > "$SMART_LOG"      # truncate at start of each run

log_smart() {
  # $1=category (new/updated/unchanged/new_sidecar), $2=path
  printf "%s\t%s\n" "$1" "$2" >> "$SMART_LOG"
}

# smart_merge_file SRC DST [LABEL]
#
# 3-case logic for files we manage:
#   a) DST does not exist → copy src → dst, mark `new`.
#   b) src and dst are identical → do nothing, mark `unchanged`.
#   c) src and dst differ → check whether the user touched dst.
#       Find the latest .bak.<ts> sibling. If the installed dst still matches
#       that .bak (i.e. the user hasn't touched it since the last install),
#       it's safe to overwrite — back up current as a fresh .bak and copy.
#       Otherwise the user has modified it: drop the new version side-by-side
#       as DST.new, leave the user's version alone, and warn.
#
# Caller may set MAKE_EXECUTABLE=1 to chmod +x the destination after a copy.
#
# Caller may set PUPSIK_FORCE_RESYNC=1 (per-call env var) to opt into the
# "template-class" mode: when there is no .bak baseline to prove dst is
# pristine, ASSUME pristine, save current dst as .bak.<ts>.force-resync
# (so the user can recover if it was actually their edit), then overwrite.
# This is the right behaviour for files the user shouldn't be editing
# directly — tools/, hooks/ — where a
# missing .bak is almost always a pre-state-file-infra install, not a
# legitimate customization. update.sh sets this when calling install.sh
# in update-only mode. The default behaviour (no env var) stays
# conservative: drop a .new sidecar and let the user decide.
smart_merge_file() {
  local src="$1"
  local dst="$2"
  local label="${3:-$(basename "$dst")}"

  if [ ! -f "$dst" ]; then
    cp "$src" "$dst"
    [ "${MAKE_EXECUTABLE:-0}" = "1" ] && chmod +x "$dst"
    SMART_NEW=$((SMART_NEW + 1))
    log_smart new "$dst"
    say "  new: $label"
    return
  fi

  if cmp -s "$src" "$dst"; then
    SMART_UNCHANGED=$((SMART_UNCHANGED + 1))
    log_smart unchanged "$dst"
    return
  fi

  # src differs from dst. Find the latest .bak.<timestamp> sibling.
  local latest_bak
  latest_bak=$(ls -t "${dst}.bak."* 2>/dev/null | head -1 || true)

  if [ -n "$latest_bak" ] && cmp -s "$dst" "$latest_bak"; then
    # User hasn't touched dst since last install — safe to overwrite.
    cp "$dst" "${dst}.bak.$(date +%Y%m%d-%H%M%S)"
    cp "$src" "$dst"
    [ "${MAKE_EXECUTABLE:-0}" = "1" ] && chmod +x "$dst"
    SMART_UPDATED=$((SMART_UPDATED + 1))
    log_smart updated "$dst"
    say "  updated: $label"
    return
  fi

  # No .bak to compare → can't prove dst is pristine.
  #
  # Force-resync path (PUPSIK_FORCE_RESYNC=1): the caller has declared this
  # a template-class file the user shouldn't be editing. Save current dst as
  # a force-resync backup (recoverable), then overwrite. This closes the
  # "drift accumulates because old install never wrote .bak baselines" bug.
  if [ "${PUPSIK_FORCE_RESYNC:-0}" = "1" ]; then
    cp "$dst" "${dst}.bak.$(date +%Y%m%d-%H%M%S).force-resync"
    cp "$src" "$dst"
    [ "${MAKE_EXECUTABLE:-0}" = "1" ] && chmod +x "$dst"
    SMART_UPDATED=$((SMART_UPDATED + 1))
    log_smart updated "$dst"
    say "  resynced: $label (no baseline; saved current as .bak.force-resync)"
    return
  fi

  # Conservative default: user may have modified the file. Don't clobber.
  cp "$src" "${dst}.new"
  [ "${MAKE_EXECUTABLE:-0}" = "1" ] && chmod +x "${dst}.new"
  SMART_NEW_FILES+=("${dst}.new")
  log_smart new_sidecar "${dst}.new"
  warn "  $label was modified locally; new version saved to ${dst}.new"
  warn "    diff $dst ${dst}.new   # then merge manually"
}

ask() {
  local prompt="$1"
  local default="$2"
  local reply
  if [ -n "$default" ]; then
    read -r -p "$prompt [$default]: " reply
    reply="${reply:-$default}"
  else
    read -r -p "$prompt: " reply
  fi
  printf "%s" "$reply"
}

# ---------- Step 0: announce mode ----------
if [ "$UPDATE_ONLY" = "1" ]; then
  printf "\033[1;36m[setup]\033[0m Running in --update-only mode.\n"
  printf "\033[1;36m[setup]\033[0m First-time-only steps (CLAUDE.md scaffold, DB init) will be skipped.\n"
fi

# ---------- Step 1: dependency check ----------
say "Checking dependencies..."

command -v python3 >/dev/null 2>&1 || die "python3 not found. Install Python 3.10+ (brew install python)."
PY_VER=$(python3 -c 'import sys; print("{}.{}".format(sys.version_info.major, sys.version_info.minor))')
PY_MAJOR=$(echo "$PY_VER" | cut -d. -f1)
PY_MINOR=$(echo "$PY_VER" | cut -d. -f2)
if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 10 ]; }; then
  die "Python $PY_VER found, need >= 3.10."
fi
say "  python3 $PY_VER OK"

command -v node >/dev/null 2>&1 || warn "node not found — MCP server builds will fail later. Install Node.js 18+ (brew install node)."
if command -v node >/dev/null 2>&1; then
  NODE_VER=$(node --version | sed 's/v//')
  NODE_MAJOR=$(echo "$NODE_VER" | cut -d. -f1)
  if [ "$NODE_MAJOR" -lt 18 ]; then
    warn "Node $NODE_VER < 18 — MCP builds may fail."
  else
    say "  node $NODE_VER OK"
  fi
fi

if ! command -v claude >/dev/null 2>&1; then
  warn "'claude' CLI not found on PATH — register_mcps.sh will fail later. Install from claude.com/claude-code."
else
  say "  claude CLI OK"
fi

# ---------- Step 2: create workspace ----------
say "Creating workspace at $WORKSPACE..."
mkdir -p "$WORKSPACE"/{tools,data,outputs,memory,.claude/hooks}

# ---------- Step 3: copy tools (smart-merge, template-class) ----------
# tools/ files are templates - users shouldn't edit them directly. If there's
# no .bak baseline (pre-state-file-infra install) we still want to resync to
# pupsik HEAD; smart_merge_file saves current as .bak.<ts>.force-resync first
# so anything customized is recoverable.
say "Copying tools..."
PUPSIK_FORCE_RESYNC=1 MAKE_EXECUTABLE=1 smart_merge_file "$SCRIPT_DIR/tools/contacts_db.py"             "$WORKSPACE/tools/contacts_db.py"             "tools/contacts_db.py"
PUPSIK_FORCE_RESYNC=1 MAKE_EXECUTABLE=1 smart_merge_file "$SCRIPT_DIR/tools/enrichment_schema_migrate.py" "$WORKSPACE/tools/enrichment_schema_migrate.py" "tools/enrichment_schema_migrate.py"
PUPSIK_FORCE_RESYNC=1 MAKE_EXECUTABLE=1 smart_merge_file "$SCRIPT_DIR/tools/now.py"                     "$WORKSPACE/tools/now.py"                     "tools/now.py"

# Enforcement script for the opt-in privacy pre-commit hook (template-class).
mkdir -p "$WORKSPACE/scripts"
PUPSIK_FORCE_RESYNC=1 MAKE_EXECUTABLE=1 smart_merge_file "$SCRIPT_DIR/scripts/install-git-hooks.sh" "$WORKSPACE/scripts/install-git-hooks.sh" "scripts/install-git-hooks.sh"

# ---------- Step 4 + 5: render templates ----------
render_template() {
  local src="$1"
  local dst="$2"
  local overwrite="$3"  # y / n / ask

  if [ -f "$dst" ]; then
    case "$overwrite" in
      n) warn "  $dst already exists, keeping existing (set overwrite=y to replace)"; return ;;
      ask)
        if ! confirm "  $dst already exists. Overwrite?" n; then
          warn "  Keeping existing $dst."
          return
        fi
        cp "$dst" "${dst}.bak.$(date +%Y%m%d-%H%M%S)"
        ;;
    esac
  fi

  cp "$src" "$dst"
}

# Gather placeholder values interactively (only if we're going to render CLAUDE.md)
NEED_VALUES=n
if [ "$UPDATE_ONLY" = "1" ]; then
  if [ -f "$WORKSPACE/CLAUDE.md" ]; then
    say "  --update-only: CLAUDE.md exists, leaving it alone."
    NEED_VALUES=n
  else
    say "  --update-only: CLAUDE.md missing — running first-time scaffold."
    NEED_VALUES=y
  fi
else
  [ ! -f "$WORKSPACE/CLAUDE.md" ] && NEED_VALUES=y
  [ "$NEED_VALUES" = "y" ] || confirm "  $WORKSPACE/CLAUDE.md already exists. Re-render from template?" n && NEED_VALUES=y || NEED_VALUES=n
fi

if [ "$NEED_VALUES" = "y" ]; then
  say "Rendering CLAUDE.md template — need some values..."
  OWNER_FIRST_NAME=$(ask "  Owner first name" "")
  OWNER_LAST_NAME=$(ask  "  Owner last name"  "")
  ROLE=$(ask           "  Role (e.g. 'Founder', 'Student', 'Product manager')" "User")
  PRIMARY_EMAIL=$(ask  "  Primary email" "")
  OTHER_EMAILS=$(ask   "  Other emails (comma-separated)" "")
  PHONE=$(ask          "  Phone" "")
  LOCATION=$(ask       "  Location (city or region)" "")
  LANGUAGES=$(ask      "  Languages" "English")
  SIGN_OFF=$(ask       "  Email sign-off (e.g. '-alice')" "-$(echo "$OWNER_FIRST_NAME" | tr '[:upper:]' '[:lower:]')")
  TODAY=$(date +%Y-%m-%d)

  # Write CLAUDE.md with substitutions using sed (avoids complex escaping)
  TMP=$(mktemp)
  cp "$SCRIPT_DIR/templates/CLAUDE.md.template" "$TMP"
  sed -i '' "s|{{OWNER_FIRST_NAME}}|${OWNER_FIRST_NAME}|g" "$TMP"
  sed -i '' "s|{{OWNER_LAST_NAME}}|${OWNER_LAST_NAME}|g" "$TMP"
  sed -i '' "s|{{OWNER_FULL_NAME}}|${OWNER_FIRST_NAME} ${OWNER_LAST_NAME}|g" "$TMP"
  sed -i '' "s|{{ROLE}}|${ROLE}|g" "$TMP"
  sed -i '' "s|{{PRIMARY_EMAIL}}|${PRIMARY_EMAIL}|g" "$TMP"
  sed -i '' "s|{{OTHER_EMAILS}}|${OTHER_EMAILS}|g" "$TMP"
  sed -i '' "s|{{PHONE}}|${PHONE}|g" "$TMP"
  sed -i '' "s|{{LOCATION}}|${LOCATION}|g" "$TMP"
  sed -i '' "s|{{LANGUAGES}}|${LANGUAGES}|g" "$TMP"
  sed -i '' "s|{{SIGN_OFF}}|${SIGN_OFF}|g" "$TMP"
  sed -i '' "s|{{TODAY}}|${TODAY}|g" "$TMP"
  sed -i '' "s|{{STYLE_LINE_1}}|Direct, concise|g" "$TMP"
  sed -i '' "s|{{STYLE_LINE_2}}|Short dashes (-) only, never em/en dashes|g" "$TMP"

  if [ -f "$WORKSPACE/CLAUDE.md" ]; then
    cp "$WORKSPACE/CLAUDE.md" "$WORKSPACE/CLAUDE.md.bak.$(date +%Y%m%d-%H%M%S)"
  fi
  mv "$TMP" "$WORKSPACE/CLAUDE.md"
  say "  Wrote $WORKSPACE/CLAUDE.md"

fi

# ---------- Step 6: feedback rules (smart-merge into the workspace) ----------
# Rules go to $RULES_HOME (<workspace>/rules/). Older pupsik versions put them
# in Claude's built-in memory folder; Claude manages that folder itself, so
# pupsik no longer writes there. If an older install's rules are still there
# and $RULES_HOME does not exist yet, we leave them where they are and say how
# to move them (python3 tools/slim_migrate.py --move-rules ...).
LEGACY_RULES=0
if [ ! -d "$RULES_HOME" ]; then
  for f in "$SCRIPT_DIR"/memory_templates/feedback_*.md; do
    if [ -f "$PROJECT_MEMORY_DIR/$(basename "$f")" ]; then LEGACY_RULES=1; break; fi
  done
fi
if [ "$LEGACY_RULES" = "1" ]; then
  warn "Your pupsik rules are in Claude's memory folder ($PROJECT_MEMORY_DIR)."
  warn "  Pupsik no longer writes there, so rule updates are skipped this run."
  warn "  To move them to $RULES_HOME (and get updates again):"
  warn "    python3 $SCRIPT_DIR/tools/slim_migrate.py --move-rules \"$HOME\" \"$WORKSPACE\""
else
  say "Installing feedback rules into $RULES_HOME..."
  mkdir -p "$RULES_HOME"
  for f in "$SCRIPT_DIR"/memory_templates/feedback_*.md; do
    name=$(basename "$f")
    smart_merge_file "$f" "$RULES_HOME/$name" "rules/$name"
  done
fi

# ---------- Step 6.5: critical-rules.md (smart append-only merge) ----------
say "Installing critical-rules.md..."
RULES_DIR="$HOME/.claude/rules"
mkdir -p "$RULES_DIR"
RULES_TARGET="$RULES_DIR/critical-rules.md"
RULES_SRC="$SCRIPT_DIR/templates/critical-rules.md.template"

# Append-only merge for critical-rules.md.
#
# Rule lines in the template look like:
#   - **NAME** — short summary. → `feedback_X.md`
#
# We use the right-hand `→ feedback_X.md` filename as the matching key.
# For each rule line in the template, if no line in the user's file
# references the same `feedback_*.md`, append it under a new
# "## Updates from upstream <date>" section.
critical_rules_smart_append() {
  local src="$1"
  local dst="$2"
  local missing
  missing=$(awk -v src="$src" -v dst="$dst" '
    BEGIN {
      # Build a set of feedback refs already present in the user file.
      while ((getline line < dst) > 0) {
        if (match(line, /feedback_[A-Za-z0-9_]+\.md/)) {
          ref = substr(line, RSTART, RLENGTH)
          have[ref] = 1
        }
      }
      close(dst)
    }
    {
      # For each line in src that contains a feedback_X.md ref AND
      # starts with a list marker, emit the line if the ref is missing.
      if ((match($0, /feedback_[A-Za-z0-9_]+\.md/)) && ($0 ~ /^[[:space:]]*-/)) {
        ref = substr($0, RSTART, RLENGTH)
        if (!(ref in have)) {
          print $0
          have[ref] = 1   # avoid duplicating the same ref if the template repeats it
        }
      }
    }
  ' "$src")

  if [ -z "$missing" ]; then
    return 0  # nothing to append
  fi

  # Backup the current file and append the new rules under a dated header.
  cp "$dst" "${dst}.bak.$(date +%Y%m%d-%H%M%S)"
  {
    printf "\n## Updates from upstream %s\n\n" "$(date +%Y-%m-%d)"
    printf "%s\n" "$missing"
  } >> "$dst"

  local count
  count=$(printf "%s\n" "$missing" | grep -c '^') || count=0
  say "  critical-rules.md: appended $count new rule(s) from upstream"
}

if [ -f "$RULES_SRC" ]; then
  if [ -f "$RULES_TARGET" ]; then
    if cmp -s "$RULES_SRC" "$RULES_TARGET"; then
      say "  critical-rules.md: unchanged (identical to upstream template)"
    else
      critical_rules_smart_append "$RULES_SRC" "$RULES_TARGET"
    fi
  else
    cp "$RULES_SRC" "$RULES_TARGET"
    say "  installed critical-rules.md"
  fi
else
  warn "  $RULES_SRC missing, skipping"
fi

# ---------- Step 6.9: one-time slim migrations (v2026-09 + v2026-11, idempotent) ----------
# Runs here, not only in update.sh, so an older update.sh that pulled this
# release still triggers it on the first run.
python3 "$SCRIPT_DIR/tools/slim_migrate.py" "$HOME" "$WORKSPACE" || warn "  slim migration hit an error - see message above"

# ---------- Step 7: SessionStart hook (template-class) ----------
# Pupsik-shipped hook → force-resync on drift (a .bak is kept). A hook you wrote
# yourself (no pupsik header line) is left alone.
say "Installing SessionStart hook..."
HOOK_TARGET="$WORKSPACE/.claude/hooks/session-start-reminder.sh"
if [ -f "$HOOK_TARGET" ] && ! grep -qE '^# (SessionStart hook|session-start-reminder\.sh)' "$HOOK_TARGET"; then
  warn "  $HOOK_TARGET looks custom (no pupsik header) - left it alone. The pupsik version is at $SCRIPT_DIR/hooks/session-start-reminder.sh"
else
  PUPSIK_FORCE_RESYNC=1 MAKE_EXECUTABLE=1 smart_merge_file "$SCRIPT_DIR/hooks/session-start-reminder.sh" "$HOOK_TARGET" "hooks/session-start-reminder.sh"
fi

# ---------- Step 8: print settings.json hook snippet ----------
if [ "$UPDATE_ONLY" = "1" ]; then
  say "  --update-only: hook refreshed (register it in settings.json once, if you haven't)."
else
cat <<EOF

===============================================================================
 Settings.json snippet (SessionStart hook + recommended default mode)
===============================================================================

Add the following to \$HOME/.claude/settings.json (inside the top-level object,
merging with any existing "permissions" / "hooks" sections):

{
  "permissions": {
    "defaultMode": "auto"
  },
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "$WORKSPACE/.claude/hooks/session-start-reminder.sh",
            "timeout": 10
          }
        ]
      }
    ]
  }
}

The hook injects the current date/time/timezone at the start of every session,
plus any rule changes you logged in ~/.claude/RECENT-RULE-CHANGES.md in the
last 14 days. Compaction is left to Claude Code's built-in behaviour.
===============================================================================

EOF
fi

# ---------- Step 10: init contacts DB ----------
if [ "$UPDATE_ONLY" = "1" ]; then
  if [ -f "$WORKSPACE/data/contacts.db" ]; then
    say "  --update-only: contacts.db exists, leaving it alone."
  else
    say "  --update-only: contacts.db missing — running first-time init."
    python3 "$WORKSPACE/tools/contacts_db.py" init || warn "contacts_db.py init returned non-zero — check Python deps"
  fi
else
  if [ ! -f "$WORKSPACE/data/contacts.db" ]; then
    say "Initializing contacts DB..."
    python3 "$WORKSPACE/tools/contacts_db.py" init || warn "contacts_db.py init returned non-zero — check Python deps"
  else
    say "contacts.db already exists — leaving it alone."
  fi
fi

# ---------- Step 11: record current VERSION to state file ----------
# Records the current VERSION so future update.sh runs only show notifications
# for NEW changes, not the full release history.
#
# Behaviour:
#   - Fresh install: silently record current VERSION.
#   - --update-only on a pre-version-system install (no state file): print a
#     one-time "Pupsik now uses version tracking - you're on $VERSION" message
#     instead of letting update.sh spam the user with the entire history.
PUPSIK_STATE_DIR="$HOME/.pupsik-state"
PUPSIK_STATE_FILE="$PUPSIK_STATE_DIR/last-applied-version"
# Workspace-side markers:
#   installed-version.txt — the VERSION this workspace is running.
#   clone-path.txt        — where this pupsik clone lives (used by the
#                           update-pupsik skill).
# update.sh reaches this via `install.sh --update-only`, so both paths record it.
WS_PUPSIK_STATE_DIR="$WORKSPACE/state/pupsik"
if [ -f "$SCRIPT_DIR/VERSION" ]; then
  CURRENT_VERSION="$(cat "$SCRIPT_DIR/VERSION" 2>/dev/null || echo)"
  if [ -n "$CURRENT_VERSION" ]; then
    mkdir -p "$PUPSIK_STATE_DIR"
    if [ "$UPDATE_ONLY" = "1" ] && [ ! -f "$PUPSIK_STATE_FILE" ]; then
      say "Pupsik now uses version tracking - you're on $CURRENT_VERSION."
      say "Future update.sh runs will only show notifications for NEW releases."
    fi
    echo "$CURRENT_VERSION" > "$PUPSIK_STATE_FILE"
    mkdir -p "$WS_PUPSIK_STATE_DIR"
    echo "$CURRENT_VERSION" > "$WS_PUPSIK_STATE_DIR/installed-version.txt"
    echo "$SCRIPT_DIR"      > "$WS_PUPSIK_STATE_DIR/clone-path.txt"
  fi
fi

# ---------- Done ----------
if [ "$UPDATE_ONLY" = "1" ]; then
  # Print smart-merge tally; update.sh also reads $SMART_LOG.
  printf "\n[install] update summary:\n"
  printf "  %d file(s) updated to new version\n"   "$SMART_UPDATED"
  printf "  %d file(s) installed for the first time\n" "$SMART_NEW"
  printf "  %d file(s) unchanged (already up to date)\n" "$SMART_UNCHANGED"
  if [ "${#SMART_NEW_FILES[@]}" -gt 0 ]; then
    printf "  %d file(s) have .new versions awaiting your merge:\n" "${#SMART_NEW_FILES[@]}"
    for nf in "${SMART_NEW_FILES[@]}"; do
      printf "    - %s\n" "$nf"
    done
    printf "\n  Inspect with: diff <orig> <orig>.new\n"
    printf "  When done:    rm <orig>.new   (or replace the original)\n"
  fi
  printf "\n"
  say "Update complete. Open a fresh Claude Code session to pick up changes."
  exit 0
fi

DEFAULT_WORKSPACE="$HOME/Desktop/claude"
NON_DEFAULT_NOTE=""
if [ "$WORKSPACE" != "$DEFAULT_WORKSPACE" ]; then
  NON_DEFAULT_NOTE=$(cat <<NOTE

  0. You installed to a non-default workspace ($WORKSPACE). Some tools
     read the CLAUDE_WORKSPACE env var to find your workspace. Add this to
     your shell profile (~/.zshrc or ~/.bashrc) BEFORE starting Claude Code:

        export CLAUDE_WORKSPACE="$WORKSPACE"

     Then open a new shell (or \`source ~/.zshrc\`) so it takes effect.
     Alternatively, re-run install.sh and the install_mcps.sh/register_mcps.sh
     scripts with the same workspace argument in every new shell.
NOTE
)
fi

cat <<EOF

===============================================================================
 Base install complete.
===============================================================================

Next steps:
$NON_DEFAULT_NOTE
  1. Register the SessionStart hook in ~/.claude/settings.json - see the JSON
     snippet printed above.

  2. Build the MCP servers:
        bash $SCRIPT_DIR/install_mcps.sh $WORKSPACE

  3. Register the MCPs with Claude Code:
        bash $SCRIPT_DIR/register_mcps.sh $WORKSPACE

  4. Follow docs/GOOGLE_CLOUD_SETUP.md to wire Gmail + Calendar OAuth.

  5. If on macOS, follow docs/WHATSAPP_SETUP.md to grant Full Disk Access.

  6. Personalize $WORKSPACE/CLAUDE.md (any remaining placeholders, active
     projects section, etc.)

  7. Start a fresh Claude Code session in $WORKSPACE and verify the
     rules are loaded:
        > What are my critical rules?

===============================================================================

EOF
