#!/bin/bash
# SessionStart hook: injects the NOW anchor (tools/now.py, falls back to `date`)
# plus lines from ~/.claude/RECENT-RULE-CHANGES.md dated in the last 14 days
# (format: "YYYY-MM-DD | what changed"). Install at <WORKSPACE>/.claude/hooks/.
WORKSPACE="${WORKSPACE:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
NOW=$(python3 "$WORKSPACE/tools/now.py" --anchor 2>/dev/null || echo "NOW: $(date '+%Y-%m-%d %H:%M %Z %A')")
CHANGES_FILE="$HOME/.claude/RECENT-RULE-CHANGES.md"
CUTOFF=$(date -v-14d +%Y-%m-%d 2>/dev/null || date -d '14 days ago' +%Y-%m-%d)
CHANGES=""
[ -f "$CHANGES_FILE" ] && CHANGES=$(awk -v c="$CUTOFF" '/^[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]/ && substr($0,1,10) >= c' "$CHANGES_FILE")
CTX="⏰ $NOW - trust this over any date you remember."
[ -n "$CHANGES" ] && CTX="$CTX"$'\n\n'"Rule changes in the last 14 days (these supersede anything read earlier):"$'\n'"$CHANGES"
# Refresh the dashboard "What's new in pupsik" data in the background (throttled, opt out with PUPSIK_NO_UPDATE_CHECK=1).
CLONE="$(cat "$WORKSPACE/state/pupsik/clone-path.txt" 2>/dev/null)"
[ "${PUPSIK_NO_UPDATE_CHECK:-0}" != "1" ] && [ -x "$CLONE/tools/check-update.sh" ] && ( CLAUDE_WORKSPACE="$WORKSPACE" bash "$CLONE/tools/check-update.sh" >/dev/null 2>&1 & )
printf '%s' "$CTX" | python3 -c 'import json,sys; print(json.dumps({"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":sys.stdin.read()}}))'
