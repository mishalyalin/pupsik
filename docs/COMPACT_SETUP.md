# Compact Hooks Setup

## What this does

Claude Code automatically compacts (compresses) the conversation when the context fills up. Without configuration, Claude loses the thread: it forgets active tasks, background processes, and recent decisions.

Two hooks plus one env var solve it:

- **pre-compact.sh** - BEFORE compacting, saves a session snapshot to disk and injects an instruction into the compact summary about "what to do after"
- **post-compact.sh** - AFTER compacting, reminds Claude to run `memory_search.py wake-up`, read the saved snapshot, and do a semantic search on the current topic
- **`CLAUDE_AUTOCOMPACT_PCT_OVERRIDE=50` env var** - lowers the auto-compact threshold from the default (~95% of context) to 50%, so compaction fires on a fresher, smaller window. The post-compact summary has more headroom to preserve, and the snapshot is cleaner.

**What you get:**
- Compaction triggers at ~50% of context instead of waiting until you're nearly full (configurable via env var)
- **After compaction Claude knows:** which TODOs are active, which agents are running in the background, which files were touched, which decisions were made
- State is saved to disk (`~/Desktop/claude/.claude/compact-state/`) with an archive of the last 20 compacts

## Tuning the threshold

`CLAUDE_AUTOCOMPACT_PCT_OVERRIDE` accepts an integer percentage. Common settings:

- `40` - aggressive, snapshots state more often (good if you run long sessions and want maximum recoverability)
- `50` - **recommended default**, balances frequency vs interruption
- `60-70` - relaxed, fewer compacts (use if you mostly run short sessions)
- Remove the env var entirely to fall back to Claude Code's built-in heuristic (~95%)

The env var is read at session start, so changes require a Claude Code restart.

## Installation

### Automatic (part of install.sh)

If you run `bash install.sh`, the hooks are installed automatically (see step 8 in install.sh).

### Manual

**1. Copy hook scripts:**

```bash
mkdir -p ~/Desktop/claude/.claude/hooks
cp pupsik/hooks/pre-compact.sh ~/Desktop/claude/.claude/hooks/
cp pupsik/hooks/post-compact.sh ~/Desktop/claude/.claude/hooks/
chmod +x ~/Desktop/claude/.claude/hooks/*.sh
```

**2. Register in `~/.claude/settings.json`:**

Add to the `"hooks"` section (create it if missing). The recommended `"permissions"` and `"env"` blocks are also shown - `auto` is the default permission mode (auto-accepts safe operations, prompts on writes/shell), and `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE=50` lowers the auto-compact threshold to 50%:

```json
{
  "permissions": {
    "defaultMode": "auto"
  },
  "env": {
    "CLAUDE_AUTOCOMPACT_PCT_OVERRIDE": "50"
  },
  "hooks": {
    "PreCompact": [
      {
        "matcher": "auto",
        "hooks": [
          {
            "type": "command",
            "command": "<YOUR_HOME>/Desktop/claude/.claude/hooks/pre-compact.sh",
            "timeout": 10,
            "statusMessage": "Saving session state before auto-compact..."
          }
        ]
      },
      {
        "matcher": "manual",
        "hooks": [
          {
            "type": "command",
            "command": "<YOUR_HOME>/Desktop/claude/.claude/hooks/pre-compact.sh",
            "timeout": 10
          }
        ]
      }
    ],
    "PostCompact": [
      {
        "matcher": "auto",
        "hooks": [
          {
            "type": "command",
            "command": "<YOUR_HOME>/Desktop/claude/.claude/hooks/post-compact.sh",
            "timeout": 10
          }
        ]
      },
      {
        "matcher": "manual",
        "hooks": [
          {
            "type": "command",
            "command": "<YOUR_HOME>/Desktop/claude/.claude/hooks/post-compact.sh",
            "timeout": 10
          }
        ]
      }
    ]
  }
}
```

Replace `<YOUR_HOME>` with your path (`/Users/<username>`). Example: `/Users/alice`.

Get it automatically:
```bash
echo "Your home: $HOME"
```

**3. Add `Compact Instructions` to `CLAUDE.md`:**

Add a section to `~/Desktop/claude/CLAUDE.md` (near the top, after Session Start Protocol):

```markdown
## Compact Instructions

On auto-compact, preserve in the summary:
- **Active TODOs** from TodoWrite (names + status)
- **Latest user question/request** in the current thread
- **Open loops:** agents still running in the background (agentId + what they're doing)
- **Key files modified this session** (full paths)
- **Decisions made this session** - one line each
- **Pending async ops** - email scans, scheduled tasks, background commands

DO NOT save: full tool output dumps, file contents (just give path + lines), intermediate research steps.

After compaction: the PostCompact hook will remind about `memory_search.py wake-up` and `compact-state/latest.json`. Run those FIRST, then continue the task.
```

**4. Restart Claude Code** (exit and re-enter the session).

## Verification

After installation and restart:

```bash
# Check hooks are executable
ls -la ~/Desktop/claude/.claude/hooks/

# Validate JSON
python3 -c "import json; json.load(open('$HOME/.claude/settings.json'))"

# Test running a hook manually
echo '{"test": "payload"}' | ~/Desktop/claude/.claude/hooks/pre-compact.sh
```

Should print `=== PRE-COMPACT STATE SAVED ===` and create a file at `~/Desktop/claude/.claude/compact-state/latest.json`.

To verify the threshold env var loaded, watch for the status message `Saving session state before auto-compact...` when context hits ~50% (instead of ~95%). If it still fires only near the end, restart Claude Code - env vars are read at session start, not mid-session.

On the next auto-compact, Claude should automatically run wake-up after recovery.

## Troubleshooting

- **Hooks not triggering:** check `~/.claude/settings.json` is valid JSON. The path in `"command"` must be **absolute** (no `~/`).
- **Permission denied:** `chmod +x ~/Desktop/claude/.claude/hooks/*.sh`
- **Hook runs but Claude doesn't react:** verify the hook's stdout reaches the context. The hook writes to stdout - Claude will see it on the next turn.
- **Don't know what Claude saved:** check `~/Desktop/claude/.claude/compact-state/latest.json` and the archive in the same folder.
