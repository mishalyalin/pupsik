---
name: Use local MCP servers, not built-in connectors
description: 🔴 Always use the locally installed multi-gmail / multi-gcal / whatsapp MCP servers (from setup-package/mcp-servers/). Never fall back to built-in Gmail/Calendar connectors, even if a tool call fails.
type: feedback
---

# 🔴 Local MCP only

The user has locally installed MCP servers at `~/Desktop/claude/mcp-servers/` (or wherever `setup-package/install.sh` placed them). **Use those.**

## Tools to prefer

- `mcp__multi-gmail__*` — all Gmail operations
- `mcp__multi-gcal__*` — all Calendar operations
- `mcp__whatsapp__*` — all WhatsApp operations

## Antipattern

- ❌ "The local MCP returned an error, let me try the built-in Gmail connector"
- ❌ Using Claude Desktop's built-in Google connector when `mcp__multi-gmail__` is registered
- ❌ Silently switching providers without telling the user

## If the local MCP is broken

1. Debug the root cause. Common failures:
   - OAuth token expired → `npm run setup add <account>` to refresh
   - Process not running → check MCP registration in `~/.claude.json`
   - Build stale → `npm run build` in the server directory
2. Report the failure to the user with the specific error.
3. Fix it proactively (see `feedback_fix_mcp_proactively.md` if present).
4. Do NOT silently fall back to another tool — the user needs to know their local setup broke.

## Why

- Local MCP servers aggregate multiple accounts in one call (the built-ins don't).
- Local MCP keeps OAuth tokens encrypted on the user's disk, never touching third-party infra.
- Silent fallback defeats the whole point of the local setup.
