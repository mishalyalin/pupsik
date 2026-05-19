#!/usr/bin/env bash
# morning-dashboard.sh
#
# One-shot: rebuild the dashboard against today's artifacts, open in the
# default browser. Drop into a morning routine, alias as `dash`, or hook
# into a scheduled task.
#
# Run:  bash <workspace>/scripts/morning-dashboard.sh
#
# Optional: to also push the rebuilt HTML to a VPS for Telegram-web access,
# set DASHBOARD_VPS_HOST + DASHBOARD_VPS_PATH env vars (or override below).
# Example:
#   export DASHBOARD_VPS_HOST="root@your.vps.tld"
#   export DASHBOARD_VPS_PATH="/var/www/m-<secret-token>/"

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE="$(cd "$SCRIPT_DIR/.." && pwd)"
DASHBOARD_DIR="$WORKSPACE/dashboard"
INDEX_HTML="$DASHBOARD_DIR/index.html"

cd "$WORKSPACE"
python3 "$DASHBOARD_DIR/build.py"

if [[ ! -f "$INDEX_HTML" ]]; then
  echo "build failed: $INDEX_HTML not written" >&2
  exit 1
fi

# Optional VPS sync (Wave 2 - Telegram-bookmark URL). Skipped unless both
# env vars are set. Errors are non-fatal - local view still works.
if [[ -n "${DASHBOARD_VPS_HOST:-}" && -n "${DASHBOARD_VPS_PATH:-}" ]]; then
  (rsync -az --quiet \
    --include='index.html' --include='styles.css' --include='favicon.svg' \
    --exclude='*' \
    "$DASHBOARD_DIR/" "$DASHBOARD_VPS_HOST:$DASHBOARD_VPS_PATH" \
    && echo "[dash] vps synced" \
    || echo "[dash] vps sync failed (local still works)") &
fi

case "$(uname -s)" in
  Darwin) open "$INDEX_HTML" ;;
  Linux)  xdg-open "$INDEX_HTML" >/dev/null 2>&1 || echo "open it: $INDEX_HTML" ;;
  *)      echo "open it: $INDEX_HTML" ;;
esac

# Wait for the background rsync (if any) so we don't drop the connection.
wait || true
