#!/bin/bash
# session-start-reminder.sh
#
# SessionStart hook for Claude Code. Wires into your settings.json under
# hooks.SessionStart. On every new session it injects:
#   1. NOW anchor (date / time / timezone / weekday / location) - hard anchor
#      against date-drift bugs when the agent pattern-matches stale dates.
#   2. CLAUDE.md staleness check (warns if the working-memory file is >2 days old).
#   3. Pointer to your critical-rules file (rules themselves load automatically
#      via Claude Code's ~/.claude/rules/ mechanism).
#
# Self-locating: this hook detects its own install path and resolves the
# workspace as two directories up. Expected install layout:
#   <WORKSPACE>/.claude/hooks/session-start-reminder.sh
#   <WORKSPACE>/tools/now.py
#   <WORKSPACE>/tools/memory_search.py
#   <WORKSPACE>/CLAUDE.md
# If you install elsewhere, override by setting WORKSPACE in the environment
# before the hook runs (e.g. via the "env" key in your settings.json hook entry).
#
# Setup:
#   - Copy this file to <WORKSPACE>/.claude/hooks/session-start-reminder.sh
#     (default WORKSPACE is ~/Desktop/claude/), then chmod +x it.
#   - In ~/.claude/settings.json add (or extend) a SessionStart hook entry that
#     runs this script. Example settings.json fragment (default workspace):
#       {
#         "hooks": {
#           "SessionStart": [
#             { "command": "~/Desktop/claude/.claude/hooks/session-start-reminder.sh" }
#           ]
#         }
#       }
#   - Replace <your-project-slug> below with your actual Claude Code project
#     slug (usually "-Users-<you>-Desktop-claude" or similar - check
#     ~/.claude/projects/ for the right directory name).

# ---------- Self-locate workspace ----------
HOOK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE="${WORKSPACE:-$(cd "$HOOK_DIR/../.." && pwd)}"

CLAUDE_MD="$WORKSPACE/CLAUDE.md"
NOW_PY="$WORKSPACE/tools/now.py"
MEMORY_SEARCH_PY="$WORKSPACE/tools/memory_search.py"

TODAY=$(date +%Y-%m-%d)

# Hard datetime anchor - prevents 'today/yesterday/tomorrow' pattern-match bugs
# from stale conversation context. See feedback_know_current_datetime.md.
NOW_ANCHOR=$(python3 "$NOW_PY" --anchor 2>/dev/null || echo "NOW: $(date '+%Y-%m-%d %H:%M:%S %Z %A')")

LAST_UPDATED=$(grep -A1 "^## Last Updated" "$CLAUDE_MD" 2>/dev/null | tail -1 | grep -oE "20[0-9]{2}-[0-9]{2}-[0-9]{2}" | head -1)

if [ -n "$LAST_UPDATED" ]; then
  DAYS_STALE=$(( ( $(date -j -f "%Y-%m-%d" "$TODAY" "+%s") - $(date -j -f "%Y-%m-%d" "$LAST_UPDATED" "+%s") ) / 86400 ))
  if [ "$DAYS_STALE" -gt 2 ]; then
    FRESHNESS_WARN="⚠️  CLAUDE.md stale ${DAYS_STALE}d (last updated ${LAST_UPDATED}). Before any answer about project status/partner/payment: verify fresh facts (emails, calendar, project state) per your verify_project_state rule. Update CLAUDE.md inline BEFORE replying."
  else
    FRESHNESS_WARN="CLAUDE.md fresh (updated ${LAST_UPDATED}, ${DAYS_STALE}d ago)."
  fi
else
  FRESHNESS_WARN="⚠️  Could not parse CLAUDE.md ## Last Updated."
fi

REMINDER=$(cat <<EOF
=== SESSION START (auto-injected by ~/.claude/settings.json hook) ===

⏰ ${NOW_ANCHOR}
   Trust this anchor over any date you remember from prior briefings/notes.
   Re-run "python3 ${NOW_PY}" any time you doubt the date.

${FRESHNESS_WARN}

Session Start Protocol:
1. Read ${CLAUDE_MD} (working memory)
2. Run: python3 ${MEMORY_SEARCH_PY} wake-up
3. Detect goal from user message, load relevant memory files

🔴 Critical rules live in ~/.claude/rules/critical-rules.md (loaded automatically every session).
Full feedback context in ~/.claude/projects/<your-project-slug>/memory/feedback_*.md.

If a rule conflicts with CLAUDE.md - follow the rule, flag CLAUDE.md as stale, fix inline.

=== END ===
EOF
)

python3 -c "
import json, sys
ctx = sys.stdin.read()
print(json.dumps({
  'hookSpecificOutput': {
    'hookEventName': 'SessionStart',
    'additionalContext': ctx
  }
}))
" <<< "$REMINDER"
