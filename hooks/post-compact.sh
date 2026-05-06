#!/bin/bash
# PostCompact hook — runs after Claude Code finishes compacting.
# Reminds Claude to re-load fresh wake-up context.

cat <<EOF
=== POST-COMPACT ===

Context was just compacted. Before continuing work:
1. Run: python3 ~/Desktop/claude/tools/memory_search.py wake-up
2. If the current task involves specific people/projects — semantic search those:
   python3 ~/Desktop/claude/tools/memory_search.py search "<topic>" --top 5
3. Last compact state: ~/Desktop/claude/.claude/compact-state/latest.json
4. If something was actively in-progress and unclear post-compact — ASK the user, don't guess.

=== END POST-COMPACT ===
EOF

exit 0
