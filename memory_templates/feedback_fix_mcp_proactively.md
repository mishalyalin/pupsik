---
name: Fix broken MCP servers, don't just report
description: When a local MCP server breaks (auth, crash, disconnect), debug and fix the root cause in the server code — don't just tell the user to re-run setup/reauth.
type: feedback
source: original
---

# Fix broken MCP servers, don't just report

When a locally-installed MCP server (e.g. a multi-account Gmail/Calendar bridge, a banking connector) disconnects or throws auth errors, DEBUG AND FIX the root cause in the server code. Do not punt the user to "re-run `npm run setup` / reauth" — that treats the symptom.

## Why

A local MCP server you built (or installed) should be reliable. Recurring re-auth prompts or "failed to connect" are almost always a code/dependency bug, not a user problem. For OAuth-backed servers, a constant re-auth loop nearly always means the underlying client library auto-refreshed a token in memory during an API call, but the server never persisted it.

## How to apply

1. **Reproduce in isolation.** Run the server's entry point standalone (`node path/to/dist/index.js`) and read the actual error / require-stack. "Failed to connect" in the host is a downstream symptom; the standalone error is the real signal.
2. **Triage the class of failure:**
   - **Auth/token expiry** → read the server's auth module. For OAuth, check for a `oauth2Client.on("tokens", ...)` (or equivalent) listener that PERSISTS auto-refreshed tokens. Without it, the token expires (~1h) and is lost on restart.
   - **Crash on any error** → check for `process.on("uncaughtException", ...)` + `process.on("unhandledRejection", ...)` guards. Without them, any thrown error kills the process and the host marks the MCP disconnected.
   - **Dependency corruption** → if the standalone error is `MODULE_NOT_FOUND` for a *submodule* of an installed package, or `node_modules` is suspiciously small, the dependency tree is broken (commonly from iCloud eviction on macOS — see `feedback_keep_working_files_off_icloud.md`). Here the fix IS `rm -rf node_modules && npm install`, not a source change.
3. **Rebuild + test all accounts/paths before handing back** (`npm run build` if TypeScript; re-spawn and verify tools surface).
4. **Note:** MCP servers do NOT hot-reload inside a running host session. After a fix, restart the agent/host so the server relaunches from the corrected tree.

## What NOT to do

- Don't send the user to reauth as a reflex — that hides a persistence bug that will recur every hour.
- Don't assume the source is broken when `node_modules` is the actual culprit (and vice-versa). The standalone error tells you which.
- Don't silently fall back to a built-in connector when a local MCP is the configured tool — fix the local one (see `feedback_use_local_mcp.md`).

## Source

Original (multi-account Gmail/Calendar bridge auth-persistence + crash-guard fixes; node_modules-corruption diagnosis). Pairs with `feedback_keep_working_files_off_icloud.md` (the dependency-corruption branch) and `feedback_use_local_mcp.md` (don't fall back to built-ins).
