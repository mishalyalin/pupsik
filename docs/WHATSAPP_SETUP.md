# WhatsApp Setup — Local Chat Reader (macOS)

The WhatsApp MCP server reads your local WhatsApp for Mac database to give Claude searchable access to your chats, contacts, and messages. **Read-only** — it cannot send messages or modify anything.

**Platform:** macOS only (relies on `ChatStorage.sqlite` from the WhatsApp desktop app).

---

## Prerequisites

- **WhatsApp for Mac** installed and signed in (the native app, not the web/browser version)
- You've sent / received at least a few messages on this Mac so the local DB has content
- Terminal with **Full Disk Access** (we'll set this up below)

---

## Step 1 — Install the MCP server

This happens automatically when you run `install_mcps.sh` from the Pupsik repo. To do it manually:

```bash
cd ~/Desktop/claude/mcp-servers/whatsapp
npm install
npm run build
```

Verify the build succeeded:

```bash
ls dist/index.js   # should exist
```

---

## Step 2 — Grant Full Disk Access to your terminal

WhatsApp's database lives in a protected location (`~/Library/Group Containers/...`). macOS blocks apps from reading it unless you explicitly grant Full Disk Access.

1. Open **System Settings** (or System Preferences on older macOS).
2. **Privacy & Security** → **Full Disk Access**.
3. Click the **+** button.
4. Add:
   - **Terminal** (`/System/Applications/Utilities/Terminal.app`)
   - **iTerm** if you use it (`/Applications/iTerm.app`)
   - **Visual Studio Code** if Claude runs via the VS Code integration
5. Toggle each **ON**.
6. **Restart** the terminal / VS Code / IDE after enabling.

> Without this, the WhatsApp MCP server will start but every query returns "permission denied" reading the SQLite DB.

---

## Step 3 — Register the MCP server with Claude

The `register_mcps.sh` script does this automatically. Manually:

```bash
claude mcp add whatsapp -- node ~/Desktop/claude/mcp-servers/whatsapp/dist/index.js
```

Restart Claude Code so it picks up the new MCP registration.

---

## Step 4 — Test

In Claude Code:

```
Ask Claude: "List my WhatsApp chats from the last 7 days."
```

Claude should call `whatsapp_list_chats` and return results. If you see "permission denied" or "ChatStorage.sqlite not found" → back to Step 2, the Full Disk Access step.

---

## Step 5 — (Optional) Sync contacts to the graph DB

The WhatsApp MCP can populate your `contacts.db` with chat partners:

```
Ask Claude: "Run whatsapp_sync_to_contacts_db"
```

This:
- Extracts every 1:1 chat partner's phone + name from WhatsApp
- Matches against existing rows in `contacts.db` by phone
- Inserts new contacts where no match exists
- Never overwrites existing contact details

**Safe to re-run** — it's idempotent.

---

## What the MCP exposes

| Tool | What it does |
|------|--------------|
| `whatsapp_list_chats` | List recent chats (DMs + groups) |
| `whatsapp_messages_with` | Get message history with a specific contact or group |
| `whatsapp_search` | Full-text search across all messages |
| `whatsapp_sync_to_contacts_db` | Populate the graph DB from WA chat partners |

All read-only. No send / delete / modify.

---

## Troubleshooting

**"Cannot find ChatStorage.sqlite"**
→ WhatsApp for Mac isn't installed, OR you haven't signed in yet. Open WhatsApp and scan the QR code.

**"EACCES: permission denied, open '.../ChatStorage.sqlite'"**
→ Full Disk Access not granted. Back to Step 2, and **restart the terminal** after enabling.

**"database is locked"**
→ WhatsApp has an exclusive write lock when it's actively syncing. Close WhatsApp for a second, re-run the query. (The MCP opens the DB in read-only mode, but occasionally hits the lock.)

**Empty results**
→ Are you signed into the right WhatsApp account? `sqlite3 ~/Library/Group\ Containers/group.net.whatsapp.WhatsApp.shared/ChatStorage.sqlite 'SELECT COUNT(*) FROM ZWAMESSAGE;'` should return > 0.

**Claude says "tool not found: whatsapp_list_chats"**
→ MCP not registered. Run `claude mcp list` — if `whatsapp` is missing, re-run Step 3.

---

## Security notes

- **Read-only.** The MCP never writes to WhatsApp's DB and cannot send messages.
- **Local only.** Nothing is sent to Anthropic, Google, WhatsApp, or any third party. Queries hit your local SQLite file.
- **Full Disk Access is broad.** That permission grants the terminal access to many sensitive files (Messages, Mail, Calendar DBs, etc.), not just WhatsApp. Consider this when deciding whether to enable it.

---

## Platform limitations

- **macOS only.** The WhatsApp desktop apps on Windows / Linux use different storage formats and aren't supported by this MCP.
- **No live sync.** The MCP reads the DB as it exists on disk; WhatsApp updates it periodically when syncing, but there's a small lag vs. your phone.
- **No group metadata.** Group member lists and avatars aren't in the SQLite DB; only messages and chat IDs are.
