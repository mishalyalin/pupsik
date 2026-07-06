#!/usr/bin/env bash
# install_mcps.sh — copy MCP server source OUTSIDE iCloud-synced paths and build each one.
#
# WHY outside iCloud: on macOS with "Desktop & Documents Folders" iCloud sync,
# iCloud's Optimize Storage silently evicts file contents to dataless
# placeholders. A partially-evicted node_modules/ makes node fail with
# MODULE_NOT_FOUND at spawn — the MCP servers randomly "disconnect" until
# reinstalled. Installing under $HOME/code/ (never synced) root-causes that.
# See memory_templates/feedback_keep_working_files_off_icloud.md.
#
# Placement:
#   ~/code/mcp-servers/multi-gmail/        (real install; override: MCP_INSTALL_DIR)
#   ~/code/mcp-servers/multi-gcal/
#   ~/code/mcp-servers/whatsapp/
#   $WORKSPACE/mcp-servers -> ~/code/mcp-servers   (compatibility symlink)
#
# Prerequisites:
#   - Node.js >= 18
#   - npm on PATH
#   - install.sh already run (creates the workspace)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE="${1:-$HOME/Desktop/claude}"
# Real install location — kept OUTSIDE iCloud-synced paths (~/Desktop, ~/Documents)
# and outside any cloud-sync folder. Override for non-default layouts:
#   MCP_INSTALL_DIR=/opt/mcp-servers bash install_mcps.sh
MCP_DST="${MCP_INSTALL_DIR:-$HOME/code/mcp-servers}"
LINK_PATH="$WORKSPACE/mcp-servers"

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

# ---------- telegram-readonly (Python, opt-in — copy only, no build) ----------
# Unlike the three Node servers above, telegram-readonly is a Python server and
# its setup is deliberately manual: it needs YOUR Telegram api_id/api_hash and an
# interactive login that only you should perform. We copy the source next to the
# other servers so everything lives in one place; the venv + login are yours.
say "Copying telegram-readonly (setup is manual — see its README)..."
tg_src="$SCRIPT_DIR/mcp-servers/telegram-readonly"
tg_dst="$MCP_DST/telegram-readonly"
if [ -d "$tg_src" ]; then
  rsync -a \
    --exclude='.venv' \
    --exclude='__pycache__' \
    --exclude='config.json' \
    --exclude='session.enc' \
    --exclude='*.enc' \
    --exclude='.DS_Store' \
    "$tg_src/" "$tg_dst/"
  say "  copied to $tg_dst. To enable (optional):"
  say "    cd $tg_dst && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"
  say "    cp config.example.json config.json   # fill api_id/api_hash + allowlist"
  say "    .venv/bin/python login.py            # interactive — you type phone/code/2FA"
  say "  then re-run register_mcps.sh (it registers this server only when .venv exists)."
else
  warn "  source $tg_src missing, skipping"
fi

# ---------- compatibility symlink: $WORKSPACE/mcp-servers -> $MCP_DST ----------
# Only when the install dir and the workspace path differ (a custom
# MCP_INSTALL_DIR could legitimately point INTO the workspace).
if [ "$LINK_PATH" != "$MCP_DST" ]; then
  if [ -L "$LINK_PATH" ]; then
    # Existing symlink — refresh it to the current install dir.
    ln -sfn "$MCP_DST" "$LINK_PATH"
    say "Refreshed symlink: $LINK_PATH -> $MCP_DST"
  elif [ -d "$LINK_PATH" ]; then
    # Real directory from an older install — do NOT touch it. Tell the user how
    # to migrate. NOTE: use rsync + swap, NOT a bare `mv` — Finder/fileproviderd
    # can cancel a rename out of an iCloud-synced dir ("Operation canceled").
    warn "$LINK_PATH already exists as a real directory (pre-2026-06-12 layout)."
    warn "Your servers were built fresh in $MCP_DST, but your old install (and"
    warn "any .env files in it) is still at $LINK_PATH. To migrate:"
    warn ""
    warn "    rsync -a \"$LINK_PATH/\" \"$MCP_DST/\"     # carries over .env files"
    warn "    rm -rf \"$LINK_PATH\""
    warn "    ln -s \"$MCP_DST\" \"$LINK_PATH\""
    warn "    bash $SCRIPT_DIR/install_mcps.sh $WORKSPACE   # rebuild on top, then"
    warn "    bash $SCRIPT_DIR/register_mcps.sh $WORKSPACE  # re-point Claude at the new path"
    warn ""
  else
    ln -s "$MCP_DST" "$LINK_PATH"
    say "Created symlink: $LINK_PATH -> $MCP_DST"
  fi
fi

cat <<EOF

===============================================================================
 MCP servers built.
===============================================================================

Locations (real path, outside iCloud-synced folders):
  $MCP_DST/multi-gmail
  $MCP_DST/multi-gcal
  $MCP_DST/whatsapp

Compatibility symlink:
  $LINK_PATH -> $MCP_DST

Next:

  1. Register each MCP with Claude Code:
        bash $SCRIPT_DIR/register_mcps.sh

  2. Configure Google OAuth credentials for Gmail + Calendar
     (see docs/GOOGLE_CLOUD_SETUP.md).

  3. On macOS, grant Full Disk Access to your terminal for WhatsApp
     (see docs/WHATSAPP_SETUP.md).

===============================================================================

EOF
