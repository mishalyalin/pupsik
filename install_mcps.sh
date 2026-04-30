#!/usr/bin/env bash
# install_mcps.sh — copy MCP server source into the workspace and build each one.
#
# Placement:
#   ~/Desktop/claude/mcp-servers/multi-gmail/
#   ~/Desktop/claude/mcp-servers/multi-gcal/
#   ~/Desktop/claude/mcp-servers/whatsapp/
#
# Prerequisites:
#   - Node.js >= 18
#   - npm on PATH
#   - install.sh already run (creates the workspace)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE="${1:-$HOME/Desktop/claude}"
MCP_DST="$WORKSPACE/mcp-servers"

say()  { printf "\033[1;36m[mcp]\033[0m %s\n" "$*"; }
warn() { printf "\033[1;33m[warn]\033[0m %s\n" "$*"; }
die()  { printf "\033[1;31m[error]\033[0m %s\n" "$*" >&2; exit 1; }

command -v node >/dev/null 2>&1 || die "node not found. Install Node.js 18+ (brew install node)."
command -v npm  >/dev/null 2>&1 || die "npm not found."
NODE_MAJOR=$(node --version | sed 's/v//' | cut -d. -f1)
[ "$NODE_MAJOR" -ge 18 ] || die "Node $(node --version) < 18. Upgrade first."

[ -d "$WORKSPACE" ] || die "Workspace $WORKSPACE missing — run install.sh first."

mkdir -p "$MCP_DST"

SERVERS=(multi-gmail multi-gcal whatsapp)

for srv in "${SERVERS[@]}"; do
  say "Processing $srv..."
  src="$SCRIPT_DIR/mcp-servers/$srv"
  dst="$MCP_DST/$srv"

  [ -d "$src" ] || { warn "  source $src missing, skipping"; continue; }

  # rsync (exclude node_modules / .env / .git / bun.lockb / .DS_Store)
  rsync -a \
    --exclude='node_modules' \
    --exclude='.env' \
    --exclude='.git' \
    --exclude='bun.lockb' \
    --exclude='.DS_Store' \
    "$src/" "$dst/"

  pushd "$dst" >/dev/null

  say "  npm install..."
  npm install --no-audit --no-fund --loglevel=warn

  if grep -q '"build"' package.json 2>/dev/null; then
    say "  npm run build..."
    npm run build
  fi

  [ -f "dist/index.js" ] || warn "  $srv: dist/index.js missing after build"
  popd >/dev/null
  say "  $srv done."
done

cat <<EOF

===============================================================================
 MCP servers built.
===============================================================================

Locations:
  $MCP_DST/multi-gmail
  $MCP_DST/multi-gcal
  $MCP_DST/whatsapp

Next:

  1. Register each MCP with Claude Code:
        bash $SCRIPT_DIR/register_mcps.sh

  2. Configure Google OAuth credentials for Gmail + Calendar
     (see docs/GOOGLE_CLOUD_SETUP.md).

  3. On macOS, grant Full Disk Access to your terminal for WhatsApp
     (see docs/WHATSAPP_SETUP.md).

===============================================================================

EOF
