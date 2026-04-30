# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
npm run build    # Compile TypeScript → dist/
npm run start    # Run the compiled MCP server (requires dist/)
npm run dev      # Run via ts-node without building
npm run setup    # Account management CLI (list/add/remove Gmail accounts)
```

Setup CLI usage:
```bash
npm run setup list
npm run setup add <label>          # e.g. add personal, add work
npm run setup remove <email>
```

Required env vars before running setup or starting the server:
```bash
export GMAIL_CLIENT_ID=...
export GMAIL_CLIENT_SECRET=...
```

## Architecture

This is a **Model Context Protocol (MCP) server** that aggregates multiple Gmail accounts and exposes them as tools to Claude.

### Module system
- TypeScript compiles to **CommonJS** (no `"type": "module"` in package.json)
- `tsconfig.json` uses `"module": "NodeNext"` + `"moduleResolution": "NodeNext"` — required to resolve the `@modelcontextprotocol/sdk` package's `exports` field (the SDK has `"type": "module"` with both ESM and CJS builds)
- All relative imports in source files use `.js` extensions (NodeNext requirement)

### Source structure

```
src/
  index.ts          — Entry point: creates McpServer, registers tools, connects via stdio
  setup.ts          — CLI for account management (add/list/remove)
  types.ts          — All shared TypeScript interfaces
  constants.ts      — Scopes, redirect URI, limits
  services/
    auth.ts         — OAuth2 flow: browser-based login, token exchange, auto-refresh
    token-store.ts  — AES-256-GCM encrypted file store at ~/.multi-gmail-mcp/tokens.enc
    gmail-client.ts — Gmail API wrappers: searchMessages, readMessage, readThread, getProfile
  tools/
    account-tools.ts — MCP tools: gmail_list_accounts, gmail_remove_account
    search-tools.ts  — MCP tools: gmail_search_all, gmail_search, gmail_read_message, gmail_read_thread
```

### Key design decisions

**Token storage**: Tokens are encrypted with AES-256-GCM using a key derived from `hostname + username` via SHA-256. Stored at `~/.multi-gmail-mcp/tokens.enc` (mode 600). This is NOT the OS keychain — it's a file-based encrypted store.

**`structuredContent` typing**: The MCP SDK requires `structuredContent` to be `{ [x: string]: unknown }`. Custom interfaces don't satisfy this, so return sites cast with `as unknown as { [key: string]: unknown }`.

**Message fetching**: `searchMessages` in `gmail-client.ts` fetches message list then full details in batches of 10 (parallel) to respect rate limits.

**Transport**: Runs via stdio only — designed for Claude Desktop and Claude Code MCP integration, not as an HTTP server.
