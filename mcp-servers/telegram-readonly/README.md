# telegram-readonly

A **local, read-only** Telegram MCP server. It can read messages from a small, explicit
**allowlist** of chats you choose — and nothing else. By construction it cannot send,
edit, delete, forward, join, leave, mark-as-read, change settings, or log in. There are
exactly three tools, all read-only:

| Tool | What it does |
|------|--------------|
| `telegram_list_allowed_chats()` | Lists the chats you allowlisted (no account-wide enumeration). |
| `telegram_read_chat(chat, limit=30)` | Reads recent messages from one allowlisted chat. |
| `telegram_search_chat(chat, query, limit=30)` | Searches inside one allowlisted chat. |

A chat that is not on the allowlist is **never** read — the tool refuses.

Your Telegram session is stored **encrypted** (`session.enc`, Fernet/AES) using a stable
key at `~/.telegram-readonly-mcp/key`. The assistant never sees your phone number, login
code, 2FA password, or the session string.

**How is this different from `docs/TELEGRAM_SETUP.md`?** That doc sets up a *bot* you
message to reach your Claude session (a messaging channel, bot API, no history access).
This server is the opposite direction: it lets Claude *read* a few chats you pick from
your own account (userbot, MTProto) — with the write path removed entirely.

---

## Security model (why this shape)

A Telegram user session is account-powerful, so a userbot MCP must make account theft /
any write action impossible rather than merely discouraged. Three layers, all structural:

1. **Read-only by construction.** The server exposes exactly three tools and only ever
   calls Telethon's read path (`get_messages`). No send/edit/delete/forward/join helper
   is defined or even imported — a prompt-injected "send a message" has no code path to
   reach.
2. **Per-chat allowlist, enforced on every read.** No `get_dialogs`, no account-wide
   enumeration is ever exposed. The blast radius of a compromised session is capped at
   the handful of chats you listed.
3. **User-does-login-himself.** `login.py` is interactive-only (it refuses argv/env
   credentials); the phone number, login code, and 2FA password go straight from your
   keyboard to Telethon. The resulting session string is Fernet-encrypted at rest and
   never printed, logged, or returned by any tool.

---

## Setup (do this once)

### 0. Create the venv

```bash
cd ~/code/mcp-servers/telegram-readonly   # or wherever you copied this folder
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp config.example.json config.json
```

### 1. Get your API credentials
1. Go to **https://my.telegram.org/apps** and log in with your phone number.
2. Create an app (any title/short-name is fine) → copy the **`api_id`** (a number) and
   **`api_hash`** (a long string).
3. Open `config.json` in this folder and paste them in:
   ```json
   {
     "api_id": 1234567,
     "api_hash": "your_real_api_hash_here",
     "allowlist": [ ... ]
   }
   ```

### 2. Choose the chats to read (the allowlist)
Edit the `allowlist` array in `config.json`. Each entry needs a human `label` and **either**
a `username` **or** a numeric `id`:
```json
"allowlist": [
  { "label": "Supplier group",  "id": null,        "username": "some_group_username" },
  { "label": "Family chat",     "id": 123456789,   "username": null }
]
```
- For a **public group/channel**, the `username` is the `t.me/<username>` handle (omit `https://t.me/`).
- For a **private group or a DM**, use the numeric `id` (you can leave `username` null).
- You can mix as many entries as you like. Only these chats are ever readable.

### 3. Log in (you type the phone/code/2FA — the assistant never does)
```bash
cd ~/code/mcp-servers/telegram-readonly
.venv/bin/python login.py
```
Telegram will prompt **in your terminal** for:
- your **phone number** (international format),
- the **login code** Telegram sends you,
- your **Two-Step-Verification password** (if you have one enabled).

These stay on your machine. On success you'll see:
```
✅ Login OK. Session encrypted to session.enc. You can now use the MCP.
```

### 4. Tell Claude the chats are set
Once `login.py` succeeds, tell Claude the Telegram chats are configured and it can use the
read tools. (MCP servers register on the next Claude Code restart — there is no hot-reload.)

---

## Registering the server with Claude Code (one-time)

`register_mcps.sh` at the repo root registers this server automatically **if** the venv
exists. To do it manually instead, add this to the `mcpServers` block of
`~/Desktop/claude/.claude/settings.json` (or `~/.claude.json`) — absolute paths, no `~`:
```json
"telegram-readonly": {
  "command": "/Users/<you>/code/mcp-servers/telegram-readonly/.venv/bin/python",
  "args": ["/Users/<you>/code/mcp-servers/telegram-readonly/server.py"]
}
```
Then restart Claude Code. The server starts fine even before you've logged in — until
then, the tools just say "Not logged in yet — run login.py".

---

## Security notes

- **Enable Telegram 2FA**: Telegram → **Settings → Privacy and Security → Two-Step
  Verification**. With 2FA on, no one can take over the account with just an SMS code.
- **Kill-switch**: you can revoke this session **anytime** from
  **Settings → Devices** (a.k.a. "Active Sessions") → terminate the session named for your
  Telethon app. After that, every tool here will refuse until you run `login.py` again.
- **Never commit your secrets.** `config.json` (your api_id/api_hash + allowlist),
  `session.enc`, and the venv are gitignored here as a backstop — but treat your working
  copy of this folder as private regardless.
- The encryption key (`~/.telegram-readonly-mcp/key`) and the session string are never
  printed, logged, or returned by any tool.
- Read-only by construction: the server only ever calls Telethon's read path
  (`get_messages`). No send/edit/delete/forward/join helper exists in the code.
