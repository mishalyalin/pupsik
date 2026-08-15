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

# ---------- Refresh the "What's new in pupsik" panel data (non-blocking) ----------
# Fire check-update.sh in the BACKGROUND so it never delays session start. It
# throttles itself (skips the network if checked <6h ago), is opt-out via
# PUPSIK_NO_UPDATE_CHECK=1, and is fully fail-soft. We locate the pupsik clone
# via the marker install.sh wrote to <workspace>/state/pupsik/clone-path.txt.
if [ "${PUPSIK_NO_UPDATE_CHECK:-0}" != "1" ]; then
  PUPSIK_CLONE_PATH="$(cat "$WORKSPACE/state/pupsik/clone-path.txt" 2>/dev/null || true)"
  if [ -n "$PUPSIK_CLONE_PATH" ] && [ -x "$PUPSIK_CLONE_PATH/tools/check-update.sh" ]; then
    ( CLAUDE_WORKSPACE="$WORKSPACE" bash "$PUPSIK_CLONE_PATH/tools/check-update.sh" >/dev/null 2>&1 & ) 2>/dev/null || true
  fi
fi

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

# ---------- Start-load budget guard ----------
# Every token of fixed session-start load (CLAUDE.md + ~/.claude/rules/*.md +
# the auto-memory MEMORY.md for this workspace) comes straight out of your
# working context window before the conversation even begins - so it's worth
# a cap. Prefers context_budget.py's `files` subcommand when it's been
# installed at $WORKSPACE/tools/context_budget.py (install.sh/update.sh put
# it there); falls back to an inline copy of the same token heuristic,
# CLAUDE.md-only, if that file isn't present - so the guard still works on a
# bare hook install with no other pupsik tooling. Caps default to 12k/20k
# tokens for CLAUDE.md alone and 40k for the combined start load - override
# by exporting CLAUDE_MD_SOFT_TOKENS / CLAUDE_MD_HARD_TOKENS / TOTAL_SOFT_TOKENS
# before the hook runs.
CONTEXT_BUDGET_PY="$WORKSPACE/tools/context_budget.py"
if [ -f "$CONTEXT_BUDGET_PY" ]; then
  BUDGET_JSON=$(python3 "$CONTEXT_BUDGET_PY" files --workspace "$WORKSPACE" --json 2>/dev/null || echo "")
else
  BUDGET_JSON=""
fi

BUDGET_WARN=$(CLAUDE_MD="$CLAUDE_MD" BUDGET_JSON="$BUDGET_JSON" \
  SOFT_TOKENS="${CLAUDE_MD_SOFT_TOKENS:-12000}" HARD_TOKENS="${CLAUDE_MD_HARD_TOKENS:-20000}" \
  TOTAL_SOFT_TOKENS="${TOTAL_SOFT_TOKENS:-40000}" python3 - <<'PYEOF' 2>/dev/null || echo ""
import json, os

soft = int(os.environ.get("SOFT_TOKENS", "12000"))
hard = int(os.environ.get("HARD_TOKENS", "20000"))
total_soft = int(os.environ.get("TOTAL_SOFT_TOKENS", "40000"))
claude_md = os.environ.get("CLAUDE_MD", "")
budget_json = os.environ.get("BUDGET_JSON", "")

c = r = m = total = 0
if budget_json:
    try:
        data = json.loads(budget_json)
        total = data.get("total_tokens", 0)
        for f in data.get("files", []):
            p = f.get("path", "")
            t = f.get("tokens", 0)
            if p == claude_md or p.endswith("/CLAUDE.md"):
                c = t
            elif p.endswith("critical-rules.md"):
                r += t
            elif p.endswith("MEMORY.md"):
                m += t
    except Exception:
        pass
else:
    # No context_budget.py installed - fall back to a CLAUDE.md-only inline
    # estimate so the guard still fires on a bare hook install.
    try:
        import tiktoken
        _enc = tiktoken.get_encoding("cl100k_base")
    except Exception:
        _enc = None

    def tok(p):
        try:
            t = open(os.path.expanduser(p), encoding="utf-8", errors="replace").read()
        except OSError:
            return 0
        if not t:
            return 0
        if _enc is not None:
            return len(_enc.encode(t))
        cyr = sum(1 for ch in t if "Ѐ" <= ch <= "ӿ") / len(t)
        return int(len(t) / (2.15 * cyr + 3.7 * (1 - cyr)))

    c = tok(claude_md)
    total = c

if c > hard:
    print(
        "🔴 CLAUDE.md ~%dk tokens - OVER the %dk hard cap (rules ~%dk, MEMORY ~%dk). "
        "Trim it by ARCHIVING to a memory/journal/ file, never by deleting, and lift "
        "any live item into an '## Upcoming'-style section first."
        % (c // 1000, hard // 1000, r // 1000, m // 1000)
    )
elif total > total_soft:
    print(
        "⚠️  Fixed start load ~%dk tokens (CLAUDE %dk + rules %dk + MEMORY %dk). "
        "Soft cap for CLAUDE.md alone is %dk."
        % (total // 1000, c // 1000, r // 1000, m // 1000, soft // 1000)
    )
PYEOF
)

if [ -n "$BUDGET_WARN" ]; then
  FRESHNESS_WARN="${FRESHNESS_WARN}"$'\n'"${BUDGET_WARN}"
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
