---
name: Default workspace and permissions mode
description: All session work happens in `~/Desktop/claude/` with `auto` permission mode. Outputs, memory, data, tools all live here. Settings live in `~/.claude/settings.json`.
type: feedback
---

# Default workspace and permissions mode

**Working directory for every session: `~/Desktop/claude/`**

Recommended `~/.claude/settings.json` baseline:

```json
{
  "model": "claude-opus-4-6",
  "permissions": {
    "defaultMode": "auto"
  }
}
```

`auto` is the smart middle ground: auto-accepts safe ops (read, search, plan), prompts on writes / shell / risky tool calls. Use `bypassPermissions` only if you fully understand the trade-off — it skips ALL prompts and is appropriate only for sandboxed throwaway environments. `acceptEdits` and `default` are also valid choices; the package recommends `auto` because it gives the best ergonomics-vs-safety balance for daily work.

The workspace contains:

- `CLAUDE.md` — session-level context, loaded first
- `tools/` — helper scripts (contacts_db.py, memory_search.py, etc.)
- `data/` — contacts.db, chroma/, other persistent state
- `outputs/` — every generated artifact lands here (see `feedback_save_outputs.md`)
- `mcp-servers/` — local MCP server source (multi-gmail, multi-gcal, whatsapp)
- `.claude/` — hooks, settings, compact-state
- `memory/` — additional per-user memory files

## Why

- Single canonical location — no "is this file in Desktop or Downloads?" confusion
- Persistent across sessions (Claude's working dir resets per bash call, but absolute paths don't)
- Easy to back up / migrate / hand off
- `auto` mode keeps you fast without surrendering audit on destructive actions

## Pattern

- Always use absolute paths rooted at `~/Desktop/claude/...`
- Never `cd` out of this directory for user-level work
- If asked to operate on a file elsewhere — copy it into `~/Desktop/claude/` first, work on the copy
- If you need full bypass for a session, set it explicitly per-session — don't bake it into the global default
