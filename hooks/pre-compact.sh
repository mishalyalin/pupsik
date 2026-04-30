#!/bin/bash
# PreCompact hook — runs right before Claude Code compacts the conversation.
# Saves session state so Claude can recover context after compacting.
#
# Workspace resolution: CLAUDE_WORKSPACE env var takes precedence over default.
# Set CLAUDE_WORKSPACE in your shell profile if you installed to a non-default
# location (e.g. export CLAUDE_WORKSPACE="$HOME/Work/claude").

WORKSPACE="${CLAUDE_WORKSPACE:-$HOME/Desktop/claude}"
STATE_DIR="$WORKSPACE/.claude/compact-state"
mkdir -p "$STATE_DIR"

TIMESTAMP=$(date +%Y-%m-%d_%H-%M-%S)
STATE_FILE="$STATE_DIR/latest.json"
ARCHIVE_FILE="$STATE_DIR/$TIMESTAMP.json"

# Read stdin (Claude Code passes session JSON via stdin to hooks)
STDIN_JSON=$(cat)

# Save full snapshot + metadata
cat > "$STATE_FILE" <<EOF
{
  "compacted_at": "$TIMESTAMP",
  "workspace": "$(pwd)",
  "hook_input": $STDIN_JSON
}
EOF

# Keep archive for last 20 compacts
cp "$STATE_FILE" "$ARCHIVE_FILE"
ls -t "$STATE_DIR"/*.json 2>/dev/null | tail -n +21 | xargs rm -f 2>/dev/null

# Inject context reminder into the compact summary (Claude will see this)
cat <<EOF
=== PRE-COMPACT STATE SAVED ===

Session state snapshot written to $STATE_FILE.

After compaction, Claude MUST run the following to recover context:
1. python3 $WORKSPACE/tools/memory_search.py wake-up
2. cat $STATE_FILE | head -50
3. Re-read $WORKSPACE/CLAUDE.md if the current task needs it

This ensures no active work state is lost across compact boundaries.
=== END PRE-COMPACT ===
EOF

exit 0
