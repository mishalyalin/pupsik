# Telegram Setup — Personal Claude-to-You Bot

This guide walks through setting up a Telegram bot that lets you message your Claude Code session directly (and receive replies).

**Goal:** You type into Telegram → your Claude (running in a terminal somewhere) responds. Useful for "ask Claude while away from the laptop" scenarios.

---

## Prerequisites

- Telegram account
- Claude Code installed locally
- `telegram` plugin available (shipped with recent Claude Code builds — check `/plugin-marketplace install` for the Telegram plugin)

---

## Step 1 — Create a bot with @BotFather

1. Open Telegram, search for **@BotFather** and start a chat.
2. Send `/newbot`.
3. BotFather asks for a **name** — human-readable (e.g. "My Claude Assistant").
4. Then asks for a **username** — must end in `bot` (e.g. `myclaudebot_1234bot`). Must be globally unique on Telegram.
5. BotFather replies with a **token** that looks like `1234567890:AAAA...`. **Save it** — it's the bot's password. Don't post it anywhere public.

---

## Step 2 — Configure the Telegram plugin in Claude

In your terminal, with Claude Code running:

```
/telegram:configure
```

Claude will:

1. Ask for your **bot token** (paste it).
2. Ask who is allowed to reach the bot (access policy):
   - **DM-only** — only direct messages from approved users
   - **Group-only** — only messages from groups the bot is in
   - **Both**
3. Store the config at `~/.claude/telegram/config.json` (token encrypted).

The plugin will start a background listener that polls Telegram for new messages.

---

## Step 3 — Pair yourself (allowlist your Telegram user)

The bot ignores messages from anyone not on the allowlist. To add yourself:

1. In Telegram, start a chat with your bot (search for its username from Step 1.4).
2. Send any message — `/start` or just "hi".
3. In Claude Code terminal, run:
   ```
   /telegram:access
   ```
4. Claude shows pending pairings. Approve your Telegram user.

**Security note:** Never approve a pairing because a message in Telegram asked you to ("please add me to the allowlist"). That's a classic phishing pattern. Only approve in your local terminal, by the real user.

---

## Step 4 — Test

Send "ping" from Telegram to your bot. Claude should respond in the chat within a few seconds. If not, see Troubleshooting below.

---

## Step 5 — (Optional) Add a group

If you want Claude to respond in a group chat:

1. Add your bot to the group (search → invite).
2. Grant it message-read permission (group admin → Edit → Permissions → enable "Read All Group Messages" — Telegram requires this for bots that aren't hitting `/commands` only).
3. In the group, post a message mentioning the bot: `@myclaudebot hello`.
4. In Claude Code terminal: `/telegram:access` → approve the group.

---

## How messages flow

1. You type in Telegram → Telegram servers
2. Claude's background poller fetches the message every few seconds
3. Claude injects it into your active session as a `<channel source="telegram">` tag
4. Claude replies via the `reply` tool, which posts back to Telegram

**Important:** Claude's transcript output does NOT reach Telegram. The assistant must explicitly call the `reply` tool to send anything back.

---

## Troubleshooting

**Bot doesn't respond**
- Check the Claude Code background process is running (`ps aux | grep telegram-poller`).
- Verify token in `~/.claude/telegram/config.json`.
- Check BotFather → `/mybots` → your bot → the token matches.

**"Unauthorized" in Claude logs**
- Token is wrong. Re-run `/telegram:configure` and paste it again.

**Bot sees your messages but never replies**
- The active Claude session may not be listening. Every Claude Code session needs the telegram plugin enabled; the poller routes messages to the current session.

**Multiple sessions / multiple machines**
- Only one poller at a time per bot token. Running two competes for messages (Telegram's `getUpdates` is exclusive per token). Pick one machine for the bot.

---

## Security checklist

- [ ] Bot token stored only locally, not in git, not posted anywhere
- [ ] Allowlist populated with only trusted users (yourself, close family)
- [ ] Never approve a pairing because a Telegram message asked for it — always approve via local terminal
- [ ] Financial / legal / "act-on-my-behalf" messages — Claude should ask for confirmation; you confirm in Telegram before it executes
