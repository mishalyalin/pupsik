#!/bin/bash
# PostCompact hook — runs after Claude Code finishes compacting.
# Reminds Claude to re-load fresh wake-up context.
#
# Workspace resolution: CLAUDE_WORKSPACE env var takes precedence over default.
# Set CLAUDE_WORKSPACE in your shell profile if you installed to a non-default
# location (e.g. export CLAUDE_WORKSPACE="$HOME/Work/claude").

WORKSPACE="${CLAUDE_WORKSPACE:-$HOME/Desktop/claude}"
STATE_FILE="$WORKSPACE/.claude/compact-state/latest.json"

cat <<EOF
=== POST-COMPACT ===

Context was just compacted. Before continuing work:
1. Run: python3 $WORKSPACE/tools/memory_search.py wake-up
2. If the current task involves specific people/projects — semantic search those:
   python3 $WORKSPACE/tools/memory_search.py search "<topic>" --top 5
3. Last compact state: $STATE_FILE
4. If something was actively in-progress and unclear post-compact — ASK the user, don't guess.

=== END POST-COMPACT ===
EOF

exit 0
