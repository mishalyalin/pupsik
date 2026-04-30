# Compact Hooks Setup

## What this does

Claude Code automatically compacts (compresses) the conversation when the context fills up. Without configuration, Claude loses the thread: it forgets active tasks, background processes, and recent decisions.

These two hooks solve the problem:

- **pre-compact.sh** - BEFORE compacting, saves a session snapshot to disk and injects an instruction into the compact summary about "what to do after"
- **post-compact.sh** - AFTER compacting, reminds Claude to run `memory_search.py wake-up`, read the saved snapshot, and do a semantic search on the current topic

**What you get:**
- Compaction happens normally (no threshold to configure - it's an internal Claude Code heuristic)
- But **after compaction Claude knows:** which TODOs are active, which agents are running in the background, which files were touched, which decisions were made
- State is saved to disk (`~/Desktop/claude/.claude/compact-state/`) with an archive of the last 20 compacts

## What does NOT work

Claude Code does NOT support a setting like "compact at 50%" or "compact at 70%" - the threshold is fixed internally and not exposed to settings. The only thing this configures is **proper recovery** after compaction.

If you want to compact earlier, do it manually: `/compact` or `/compact focus on X` to specify what to keep.

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

Add to the `"hooks"` section (create it if missing). The recommended `"permissions"` block is also shown - it sets `auto` as the default permission mode (auto-accepts safe operations, prompts on writes/shell):

```json
{
  "permissions": {
    "defaultMode": "auto"
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

On the next auto-compact, Claude should automatically run wake-up after recovery.

## Troubleshooting

- **Hooks not triggering:** check `~/.claude/settings.json` is valid JSON. The path in `"command"` must be **absolute** (no `~/`).
- **Permission denied:** `chmod +x ~/Desktop/claude/.claude/hooks/*.sh`
- **Hook runs but Claude doesn't react:** verify the hook's stdout reaches the context. The hook writes to stdout - Claude will see it on the next turn.
- **Don't know what Claude saved:** check `~/Desktop/claude/.claude/compact-state/latest.json` and the archive in the same folder.
