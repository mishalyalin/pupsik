#!/usr/bin/env bash
# install.sh — base installer for the Claude Code personal setup package.
#
# What this does:
#   1. Checks dependencies (Python 3.10+, Node 18+, claude CLI)
#   2. Creates ~/Desktop/claude/{tools,data,outputs,memory,.claude/hooks,.claude/compact-state}
#   3. Copies tools/ → ~/Desktop/claude/tools/
#      (contacts_db.py, memory_search.py, note.py, doctor.py,
#       enrichment_schema_migrate.py, flag_russian_speakers.py)
#   4. Renders templates/CLAUDE.md.template → ~/Desktop/claude/CLAUDE.md (prompts for placeholders)
#   5. Renders templates/wakeup_l0.txt.template → ~/Desktop/claude/memory/wakeup_l0.txt (prompts for placeholders)
#   6. Copies memory_templates/feedback_*.md → project memory dir
#   6.5 Installs critical-rules.md to ~/.claude/rules/ (auto-loaded each session)
#   7. Installs compact hooks (pre/post) to ~/Desktop/claude/.claude/hooks/
#   8. Prints JSON snippet to add to ~/.claude/settings.json to register the hooks
#   9. Installs Python deps (chromadb) via pip
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
                     - wakeup_l0.txt scaffold (kept if it already exists)
                     - chromadb pip install (only if missing)
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
PROJECT_MEMORY_DIR="$HOME/.claude/projects/$PROJECT_SLUG/memory"

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

# smart_merge_file SRC DST
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

  # User modified the file (or there's no .bak to compare). Don't clobber.
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
  printf "\033[1;36m[setup]\033[0m First-time-only steps (CLAUDE.md scaffold, DB init, wakeup_l0) will be skipped.\n"
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
mkdir -p "$WORKSPACE"/{tools,data,outputs,memory,.claude/hooks,.claude/compact-state}
# Phase 1/2 dirs for the 9-collection ChromaDB indexer + note.py captures
mkdir -p "$WORKSPACE"/memory/{learnings,decisions,journal,people,projects}
mkdir -p "$WORKSPACE"/{briefings,research}
mkdir -p "$PROJECT_MEMORY_DIR"

# ---------- Step 3: copy tools (smart-merge) ----------
say "Copying tools..."
MAKE_EXECUTABLE=1 smart_merge_file "$SCRIPT_DIR/tools/contacts_db.py"             "$WORKSPACE/tools/contacts_db.py"             "tools/contacts_db.py"
MAKE_EXECUTABLE=1 smart_merge_file "$SCRIPT_DIR/tools/memory_search.py"           "$WORKSPACE/tools/memory_search.py"           "tools/memory_search.py"
MAKE_EXECUTABLE=1 smart_merge_file "$SCRIPT_DIR/tools/note.py"                    "$WORKSPACE/tools/note.py"                    "tools/note.py"
MAKE_EXECUTABLE=1 smart_merge_file "$SCRIPT_DIR/tools/doctor.py"                  "$WORKSPACE/tools/doctor.py"                  "tools/doctor.py"
MAKE_EXECUTABLE=1 smart_merge_file "$SCRIPT_DIR/tools/enrichment_schema_migrate.py" "$WORKSPACE/tools/enrichment_schema_migrate.py" "tools/enrichment_schema_migrate.py"
MAKE_EXECUTABLE=1 smart_merge_file "$SCRIPT_DIR/tools/flag_russian_speakers.py"   "$WORKSPACE/tools/flag_russian_speakers.py"   "tools/flag_russian_speakers.py"
MAKE_EXECUTABLE=1 smart_merge_file "$SCRIPT_DIR/tools/now.py"                     "$WORKSPACE/tools/now.py"                     "tools/now.py"
MAKE_EXECUTABLE=1 smart_merge_file "$SCRIPT_DIR/tools/note_graph.py"              "$WORKSPACE/tools/note_graph.py"              "tools/note_graph.py"
MAKE_EXECUTABLE=1 smart_merge_file "$SCRIPT_DIR/tools/note_graph_schema.py"       "$WORKSPACE/tools/note_graph_schema.py"       "tools/note_graph_schema.py"
MAKE_EXECUTABLE=1 smart_merge_file "$SCRIPT_DIR/tools/rules.py"                   "$WORKSPACE/tools/rules.py"                   "tools/rules.py"
MAKE_EXECUTABLE=1 smart_merge_file "$SCRIPT_DIR/tools/brand_os.py"                "$WORKSPACE/tools/brand_os.py"                "tools/brand_os.py"

# Dashboard module
say ""
say "Step 3.5: Copy dashboard module..."
mkdir -p "$WORKSPACE/dashboard" "$WORKSPACE/scripts" "$WORKSPACE/state/dashboard/archive"
smart_merge_file "$SCRIPT_DIR/dashboard/build.py"   "$WORKSPACE/dashboard/build.py"   "dashboard/build.py"
smart_merge_file "$SCRIPT_DIR/dashboard/styles.css" "$WORKSPACE/dashboard/styles.css" "dashboard/styles.css"
smart_merge_file "$SCRIPT_DIR/dashboard/favicon.svg" "$WORKSPACE/dashboard/favicon.svg" "dashboard/favicon.svg"
smart_merge_file "$SCRIPT_DIR/dashboard/NOTICE.md"  "$WORKSPACE/dashboard/NOTICE.md"  "dashboard/NOTICE.md"
smart_merge_file "$SCRIPT_DIR/dashboard/README.md"  "$WORKSPACE/dashboard/README.md"  "dashboard/README.md"
MAKE_EXECUTABLE=1 smart_merge_file "$SCRIPT_DIR/scripts/morning-dashboard.sh" "$WORKSPACE/scripts/morning-dashboard.sh" "scripts/morning-dashboard.sh"

# Optional dash shortcut on PATH (~/.local/bin/dash)
if [ -d "$HOME/.local/bin" ]; then
  DASH_BIN="$HOME/.local/bin/dash"
  if [ ! -e "$DASH_BIN" ]; then
    cat > "$DASH_BIN" <<DASH_EOF
#!/usr/bin/env bash
# dash - morning dashboard launcher (rebuild + open in browser)
exec bash "$WORKSPACE/scripts/morning-dashboard.sh" "\$@"
DASH_EOF
    chmod +x "$DASH_BIN"
    say "  created dash shortcut at $DASH_BIN"
  fi
fi

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

  # wakeup_l0.txt — use same values
  TMP=$(mktemp)
  cp "$SCRIPT_DIR/templates/wakeup_l0.txt.template" "$TMP"
  CONTEXT=$(ask "  One-line context for wake-up (e.g. 'grad student, NYC')" "$ROLE")
  EXTRA=$(ask "  One more identity line (optional)" "")
  sed -i '' "s|{{OWNER_FIRST_NAME}}|${OWNER_FIRST_NAME}|g" "$TMP"
  sed -i '' "s|{{OWNER_LAST_NAME}}|${OWNER_LAST_NAME}|g" "$TMP"
  sed -i '' "s|{{ROLE}}|${ROLE}|g" "$TMP"
  sed -i '' "s|{{CONTEXT_ONE_LINER}}|${CONTEXT}|g" "$TMP"
  sed -i '' "s|{{LOCATION}}|${LOCATION}|g" "$TMP"
  sed -i '' "s|{{PRIMARY_EMAIL}}|${PRIMARY_EMAIL}|g" "$TMP"
  sed -i '' "s|{{EXTRA_IDENTITY_LINE}}|${EXTRA}|g" "$TMP"
  mv "$TMP" "$WORKSPACE/memory/wakeup_l0.txt"
  say "  Wrote $WORKSPACE/memory/wakeup_l0.txt"
fi

# ---------- Step 6: memory feedback rules (smart-merge) ----------
say "Installing memory feedback rules..."
for f in "$SCRIPT_DIR"/memory_templates/feedback_*.md; do
  name=$(basename "$f")
  target="$PROJECT_MEMORY_DIR/$name"
  smart_merge_file "$f" "$target" "$name"
done

# ---------- Step 6.1: architect proposals backlog (bootstrap) ----------
# The backlog directory lives under the WORKSPACE memory dir (it's data the
# user accumulates over time), not the per-project Claude Code memory dir.
# We bootstrap _PROTOCOL.md (schema) every run, and latest.md only on first
# install — never overwrite the user's accumulated backlog.
say "Bootstrapping architect proposals backlog..."
ARCH_DIR="$WORKSPACE/memory/architect_proposals"
mkdir -p "$ARCH_DIR/archive"
smart_merge_file "$SCRIPT_DIR/memory_templates/architect_proposals/_PROTOCOL.md" "$ARCH_DIR/_PROTOCOL.md" "architect_proposals/_PROTOCOL.md"
if [ ! -f "$ARCH_DIR/latest.md" ]; then
  cp "$SCRIPT_DIR/memory_templates/architect_proposals/latest.md" "$ARCH_DIR/latest.md"
  say "  new: architect_proposals/latest.md (empty bootstrap)"
else
  say "  architect_proposals/latest.md: kept (your accumulated backlog)"
fi

# ---------- Step 6.2: world_knowledge + user_context (bootstrap) ----------
# Two ChromaDB knowledge sub-collections cherry-picked from obra/superpowers
# private-journal-mcp (Jesse Vincent, MIT). Each directory lives under the
# WORKSPACE memory dir alongside learnings/ and decisions/.
#
# We smart-merge _PROTOCOL.md every run so the schema can evolve across
# upgrades. We do NOT bootstrap any seed notes - the user creates entries
# via `note.py world_knowledge` / `note.py user_context` as facts arise.
say "Bootstrapping world_knowledge + user_context directories..."
for kind in world_knowledge user_context; do
  KIND_DIR="$WORKSPACE/memory/$kind"
  mkdir -p "$KIND_DIR"
  smart_merge_file "$SCRIPT_DIR/memory_templates/$kind/_PROTOCOL.md" "$KIND_DIR/_PROTOCOL.md" "$kind/_PROTOCOL.md"
done

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

# ---------- Step 7: compact hooks (smart-merge) ----------
say "Installing compact hooks..."
MAKE_EXECUTABLE=1 smart_merge_file "$SCRIPT_DIR/hooks/pre-compact.sh"  "$WORKSPACE/.claude/hooks/pre-compact.sh"  "hooks/pre-compact.sh"
MAKE_EXECUTABLE=1 smart_merge_file "$SCRIPT_DIR/hooks/post-compact.sh" "$WORKSPACE/.claude/hooks/post-compact.sh" "hooks/post-compact.sh"

# ---------- Step 8: print settings.json hook snippet ----------
if [ "$UPDATE_ONLY" = "1" ]; then
  say "  --update-only: hooks refreshed (you've already registered them in settings.json)."
else
cat <<EOF

===============================================================================
 Settings.json snippet (compact hooks + recommended default mode)
===============================================================================

Add the following to \$HOME/.claude/settings.json (inside the top-level object,
merging with any existing "permissions" / "hooks" sections). Replace <HOME>
with: $HOME

{
  "model": "claude-opus-4-7",
  "permissions": {
    "defaultMode": "auto"
  },
  "env": {
    "CLAUDE_AUTOCOMPACT_PCT_OVERRIDE": "50"
  },
  "hooks": {
    "PreCompact": [
      {
        "matcher": "auto",
        "hooks": [
          {
            "type": "command",
            "command": "$WORKSPACE/.claude/hooks/pre-compact.sh",
            "timeout": 10,
            "statusMessage": "Saving session state before auto-compact..."
          }
        ]
      },
      {
        "matcher": "manual",
        "hooks": [
          {
            "type": "command",
            "command": "$WORKSPACE/.claude/hooks/pre-compact.sh",
            "timeout": 10
          }
        ]
      }
    ],
    "PostCompact": [
      {
        "matcher": "auto",
        "hooks": [
          {
            "type": "command",
            "command": "$WORKSPACE/.claude/hooks/post-compact.sh",
            "timeout": 10
          }
        ]
      },
      {
        "matcher": "manual",
        "hooks": [
          {
            "type": "command",
            "command": "$WORKSPACE/.claude/hooks/post-compact.sh",
            "timeout": 10
          }
        ]
      }
    ]
  }
}

The "defaultMode": "auto" line is the recommended default - it auto-accepts
safe operations (read, search, plan) and prompts on writes/shell/risky calls.
The "model" pin is set to the most capable Claude model at release time
(claude-opus-4-7); update it when a newer Opus ships, or replace with the
"opus" alias if your Claude Code build resolves it to the latest.

The "env" block sets CLAUDE_AUTOCOMPACT_PCT_OVERRIDE=50, which lowers the
auto-compact threshold from the default (~95%) to 50% of context. Compacting
earlier means the PreCompact hook fires on a smaller, fresher window - state
snapshots are cleaner and the post-compact summary has more headroom to
preserve. Tune up (60-70) if you want fewer compacts, down (40) if you want
state captured more aggressively. Removing the env block reverts to the
built-in heuristic.

See feedback_default_workspace.md for the full rationale and alternatives.

See docs/COMPACT_SETUP.md for step-by-step merging guidance.
===============================================================================

EOF
fi

# ---------- Step 9: Python deps ----------
if [ "$UPDATE_ONLY" = "1" ]; then
  if python3 -c "import chromadb" 2>/dev/null; then
    say "  --update-only: chromadb already importable, skipping pip install."
  else
    say "Installing Python packages (chromadb)..."
    if command -v pip3 >/dev/null 2>&1; then
      pip3 install --user --quiet chromadb || warn "pip3 install chromadb failed — install manually with: pip3 install --user chromadb"
    else
      warn "pip3 not found. Install chromadb manually: python3 -m pip install --user chromadb"
    fi
  fi
else
  say "Installing Python packages (chromadb)..."
  if command -v pip3 >/dev/null 2>&1; then
    pip3 install --user --quiet chromadb || warn "pip3 install chromadb failed — install manually with: pip3 install --user chromadb"
  else
    warn "pip3 not found. Install chromadb manually: python3 -m pip install --user chromadb"
  fi
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
if [ -f "$SCRIPT_DIR/VERSION" ]; then
  CURRENT_VERSION="$(cat "$SCRIPT_DIR/VERSION" 2>/dev/null || echo)"
  if [ -n "$CURRENT_VERSION" ]; then
    mkdir -p "$PUPSIK_STATE_DIR"
    if [ "$UPDATE_ONLY" = "1" ] && [ ! -f "$PUPSIK_STATE_FILE" ]; then
      say "Pupsik now uses version tracking - you're on $CURRENT_VERSION."
      say "Future update.sh runs will only show notifications for NEW releases."
    fi
    echo "$CURRENT_VERSION" > "$PUPSIK_STATE_FILE"
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

  0. You installed to a non-default workspace ($WORKSPACE). The compact hooks
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
  1. Register the compact hooks in ~/.claude/settings.json — see the JSON
     snippet printed above, and docs/COMPACT_SETUP.md for merging guidance.

  2. Build the MCP servers:
        bash $SCRIPT_DIR/install_mcps.sh $WORKSPACE

  3. Register the MCPs with Claude Code:
        bash $SCRIPT_DIR/register_mcps.sh $WORKSPACE

  4. Follow docs/GOOGLE_CLOUD_SETUP.md to wire Gmail + Calendar OAuth.

  5. If on macOS, follow docs/WHATSAPP_SETUP.md to grant Full Disk Access.

  6. Personalize $WORKSPACE/CLAUDE.md (any remaining placeholders, active
     projects section, etc.)

  7. Start a fresh Claude Code session in $WORKSPACE and verify the
     2-agent rule is loaded:
        > What's your 2-agent rule?

  Knowledge capture (Phase 1 + Phase 2)
  -------------------------------------
  Your ChromaDB index now spans 9 collections — contacts, interactions,
  memory_files, chat_archives plus briefings, outputs, journal, knowledge
  (learnings + decisions), and research. New dirs were created under
  memory/ and at the workspace root.

  Capture atomic knowledge in-flight via tools/note.py — the MOMENT an
  insight, decision, or research finding emerges (don't wait for the
  topic to close):

    python3 $WORKSPACE/tools/note.py learning  "Title" "Body" --tags "..."
    python3 $WORKSPACE/tools/note.py decision  "Title" "Body" --rationale "..."
    python3 $WORKSPACE/tools/note.py research  "Title" "Body" --sources "url"

  Re-run with the same title to upsert the existing note. Each capture
  triggers a surgical single-file reindex (~50ms); a full reindex (~90s)
  runs only when you explicitly call \`memory_search.py index\`. See
  docs/HOW_IT_WORKS.md for the full capture protocol.

===============================================================================

EOF
