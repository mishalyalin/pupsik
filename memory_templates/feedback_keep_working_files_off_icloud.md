---
name: Keep working files off iCloud-synced paths (macOS)
description: On macOS with Desktop & Documents iCloud sync, iCloud Optimize Storage evicts file contents to dataless placeholders, which corrupts git clones, node_modules, and MCP server runtimes. Keep git clones in ~/code; reinstall a node_modules folder that is suspiciously small.
type: feedback
source: original
---

# Keep working files off iCloud-synced paths (macOS)

## The rule

On macOS, if "Desktop & Documents Folders" iCloud sync is ON, then `~/Desktop` and `~/Documents` are iCloud-synced. iCloud's **Optimize Mac Storage** silently evicts file contents to the cloud, leaving **dataless placeholders** on disk. That breaks anything that depends on a complete on-disk file tree:

- **git working clones** → `fatal: bad object HEAD` (the object files were evicted; git can't read them until iCloud re-downloads)
- **node_modules** → `Cannot find module './v1'` / `MODULE_NOT_FOUND` for a *submodule* of an installed dependency (the `.js` runtime files got evicted while `.d.ts` type stubs stayed)
- **MCP server runtimes** → "failed to connect" because the server crashes on startup `require()` of an evicted dependency file

Two practical rules:

1. **Keep GitHub-backed git clones under `~/code/`** (a dedicated directory OUTSIDE iCloud and OUTSIDE any cloud-sync folder like Google Drive / Dropbox). The clone is a disposable working copy — the repo already lives on the remote, so there is no reason to pay sync cost (and corruption risk) on it.
2. **Keep node_modules-heavy projects off iCloud-synced paths**, OR exclude their `node_modules/` from sync, OR accept that you will periodically reinstall.

> ⚠️ **This toolkit installs the workspace to `~/Desktop/claude/` by default.** If you have Desktop & Documents iCloud sync on, your workspace + its `tools/` and `data/` live on an iCloud-synced path and are subject to the eviction corruption above. Either turn off Optimize Storage, move the workspace off `~/Desktop`, or know the reinstall drill below. Since 2026-06-12, `install_mcps.sh` installs the MCP servers (the most eviction-sensitive piece, because of `node_modules/`) to `~/code/mcp-servers/` and only symlinks them from the workspace — if your servers still physically live under `~/Desktop/claude/mcp-servers/`, migrate them (see `UPGRADING.md`).

## Diagnostic: corrupted node_modules

The fastest tell is **size**. A healthy `node_modules/` is tens of MBs minimum. A corrupted (partially-evicted) one is a tiny fraction of that:

```bash
du -sh path/to/project/node_modules
# Healthy: 40-170MB.  Corrupted: 2-5MB (3-5% of normal) → evicted/partial install.
```

Confirm by running the entry point standalone and reading the require-stack error — it names the exact missing submodule + path:

```bash
node path/to/dist/index.js   # MODULE_NOT_FOUND names the evicted file
```

## Fix: reinstall, do NOT reauth

```bash
cd path/to/project
rm -rf node_modules package-lock.json
npm install
```

That is the whole fix. The compiled `dist/` output and any OAuth tokens are fine — only the dependency tree got truncated. **Do not** re-run auth/setup flows, **do not** rebuild TypeScript, **do not** assume the source is broken — the source is fine, the on-disk dependency files were evicted.

For an MCP server specifically: after reinstall, MCP servers do **not** hot-reload inside a running session — restart the agent (or the host app) so the server relaunches from the fixed tree.

## When moving an existing clone off iCloud

- Move the directory **intact** with `mv` — never delete-and-re-clone a clone that may hold uncommitted/un-pushed work.
- Before treating any clone as "redundant / safe to delete", verify it actually is: `git log @{u}..HEAD` (un-pushed commits), `git branch -vv` (no-upstream or ahead branches), `git stash list` (stashes). A clone that reports "clean" on the current branch can still hold unique work on *other* branches or in a stash. Don't trust a "clean / fully pushed" claim — check.
- Moving OUT of an iCloud folder can hang while iCloud materializes the dataless files first; let it finish rather than killing it mid-move.

## Not applicable if

- You are on Linux / Windows, or
- macOS with Desktop & Documents iCloud sync OFF, or
- Optimize Mac Storage is OFF (files stay fully materialized on disk).

In those cases the workspace's default `~/Desktop/claude/` location is fine as-is.

## Source

Original (macOS iCloud eviction incidents, 2026-05-30 git-clone corruption + 2026-06-01/02 MCP-server node_modules corruption). The git-clone and node_modules symptoms share one root cause: iCloud Optimize Storage evicting file contents to dataless placeholders.
