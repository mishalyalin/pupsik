#!/usr/bin/env bash
# register_mcps.sh — register the three MCP servers with Claude Code.
#
# Uses the `claude mcp add` CLI command, which updates ~/.claude.json
# for you (with a backup of the existing file).
#
# Prerequisites:
#   - install.sh + install_mcps.sh already run
#   - OAuth env vars set (or .env file present) for multi-gmail + multi-gcal
#   - `claude` CLI on PATH

set -euo pipefail

WORKSPACE="${1:-$HOME/Desktop/claude}"
MCP_DIR="$WORKSPACE/mcp-servers"

say()  { printf "\033[1;36m[reg]\033[0m %s\n" "$*"; }
warn() { printf "\033[1;33m[warn]\033[0m %s\n" "$*"; }
die()  { printf "\033[1;31m[error]\033[0m %s\n" "$*" >&2; exit 1; }

command -v claude >/dev/null 2>&1 || die "'claude' CLI not found. Install Claude Code first."

# Snapshot ~/.claude.json
if [ -f "$HOME/.claude.json" ]; then
  BACKUP="$HOME/.claude.json.bak.$(date +%Y%m%d-%H%M%S)"
  cp "$HOME/.claude.json" "$BACKUP"
  say "Backed up ~/.claude.json -> $BACKUP"
fi

# Ensure dist/ exists for each server
for srv in multi-gmail multi-gcal whatsapp; do
  entry="$MCP_DIR/$srv/dist/index.js"
  [ -f "$entry" ] || die "$entry missing — run install_mcps.sh first."
done

# Env vars for gmail/gcal — support loading from a shared .env in either server dir
ENV_FILE=""
for candidate in "$MCP_DIR/multi-gmail/.env" "$MCP_DIR/multi-gcal/.env"; do
  if [ -f "$candidate" ]; then
    ENV_FILE="$candidate"
    break
  fi
done

if [ -z "$ENV_FILE" ]; then
  warn "No .env file found for Google OAuth (tried $MCP_DIR/multi-gmail/.env, $MCP_DIR/multi-gcal/.env)."
  warn "multi-gmail and multi-gcal will register, but will error out at first call without GMAIL_CLIENT_ID/GMAIL_CLIENT_SECRET."
  warn "See docs/GOOGLE_CLOUD_SETUP.md."
  ENV_FILE=""
fi

# Build the wrapper command — load .env and export before node, if env file exists
wrap_with_env() {
  local entry="$1"
  if [ -n "$ENV_FILE" ]; then
    printf "bash -c 'source %s && export GMAIL_CLIENT_ID GMAIL_CLIENT_SECRET && node %s'" "$ENV_FILE" "$entry"
  else
    printf "node %s" "$entry"
  fi
}

# ---------- multi-gmail ----------
say "Registering multi-gmail..."
claude mcp remove multi-gmail 2>/dev/null || true
CMD=$(wrap_with_env "$MCP_DIR/multi-gmail/dist/index.js")
claude mcp add multi-gmail -- $CMD || warn "  multi-gmail register failed — run 'claude mcp add multi-gmail -- $CMD' manually"

# ---------- multi-gcal ----------
say "Registering multi-gcal..."
claude mcp remove multi-gcal 2>/dev/null || true
CMD=$(wrap_with_env "$MCP_DIR/multi-gcal/dist/index.js")
claude mcp add multi-gcal -- $CMD || warn "  multi-gcal register failed — run manually"

# ---------- whatsapp (no OAuth, just node) ----------
say "Registering whatsapp..."
claude mcp remove whatsapp 2>/dev/null || true
claude mcp add whatsapp -- node "$MCP_DIR/whatsapp/dist/index.js" || warn "  whatsapp register failed"

say "Current registrations:"
claude mcp list || warn "'claude mcp list' failed."

cat <<EOF

===============================================================================
 MCP registration complete (or attempted).
===============================================================================

Verify in Claude Code:
  - Restart your Claude Code session
  - Ask: "List my connected MCP servers."
  - You should see multi-gmail, multi-gcal, whatsapp.

If Gmail or Calendar calls fail with auth errors:
  1. Run:  cd $MCP_DIR/multi-gmail && source .env && \\
           export GMAIL_CLIENT_ID GMAIL_CLIENT_SECRET && \\
           npm run setup add <account-label>
  2. Same for multi-gcal. See docs/GOOGLE_CLOUD_SETUP.md.

For WhatsApp on macOS: grant Full Disk Access to your terminal
(System Settings → Privacy & Security → Full Disk Access). See
docs/WHATSAPP_SETUP.md.

===============================================================================

EOF
