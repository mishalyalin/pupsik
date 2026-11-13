# Pupsik

> The parts I still add to Claude Code: every Gmail account at once, WhatsApp and Telegram read access, a contact graph, and rules I've had to teach it.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Built for: Claude Code](https://img.shields.io/badge/Built_for-Claude_Code-blueviolet)](https://claude.com/claude-code)
[![Status: I use it daily](https://img.shields.io/badge/Status-I_use_it_daily-green)](#)
[![Privacy-checked: CI](https://img.shields.io/badge/Privacy--checked-CI-green)](.github/workflows/privacy-check.yml)

I'm Misha. Solo founder. I run my whole company on Claude Code - sales, ops, finance, all of it. Not just code.

When I started, Claude Code forgot everything between sessions, so pupsik had its own memory layer, a dashboard and a lot of process rules. Claude now has built-in memory, scheduled tasks, connectors and artifacts, so I took those parts out. What's left is the stuff Claude still can't do on its own.

MIT. macOS-friendly. Local. No telemetry, no cloud sync, no SaaS dashboard.

## What's in it

- **Multi-account Gmail and Calendar MCPs.** I have 3 Gmail accounts. `gmail_search_all` searches all of them in one call; the calendar server does the same. The built-in connectors work with one account at a time.
- **WhatsApp read-only MCP (macOS).** Reads the local WhatsApp for Mac database: search, read a chat, sync people into the contact DB.
- **Telegram read-only MCP (opt-in).** A local userbot server that reads a small, explicit **allowlist** of chats and nothing else. Read-only **by construction**: exactly 3 tools, no send/edit/delete/forward code path at all, no account-wide chat listing, session encrypted at rest, and the login (phone / code / 2FA) is interactive-only, so the assistant never sees credentials. That's the shape I'd suggest for any MCP with access to a whole account: limit what it can do in code, not in a prompt. Setup: [`mcp-servers/telegram-readonly/README.md`](mcp-servers/telegram-readonly/README.md).
- **Contact graph DB (SQLite).** Every person, their company, every interaction, the links between them. `contacts_db.py find "Steve"` instead of digging through mail; `chain "A" "B"` returns an intro path.
- **Optional weekly contact enrichment.** A scheduled-task template: email signatures, then web search for missing profiles, then a short private summary of your correspondence with each contact. The summary never leaves your local DB. Opt-in.
- **Rules from real corrections.** `~/.claude/rules/critical-rules.md` loads every session: verify before stating facts, check the contact DB before naming a person, check what was already sent before drafting, all Gmail accounts always, one checker for things that ship. Each line points at a `feedback_*.md` file in `~/Desktop/claude/rules/` with the reasons and examples.
- **Date anchor.** A small SessionStart hook adds the current date, time and timezone, plus any rule changes you logged in the last 14 days.
- **Privacy check in CI** (and an opt-in pre-commit hook), so forks don't leak personal data either.

### What pupsik leaves to Claude

Pupsik doesn't write into Claude's own folders. It puts nothing in Claude's built-in memory (`~/.claude/projects/*/memory/`) and doesn't change your Claude settings (model, compaction, permissions). The one exception is cleanup of its own old files: an update moves pupsik's leftover backups out of Claude's memory folder and removes hooks that ran pupsik's retired compact scripts, with a backup of each. Rules go to `~/.claude/rules/` and `~/Desktop/claude/rules/`, tools to `~/Desktop/claude/tools/`. Memory, briefings, dashboards and scheduled jobs are Claude's built-in features now, so use those.

## Quick start

```bash
git clone https://github.com/mishalyalin/pupsik.git
cd pupsik
bash install.sh             # creates ~/Desktop/claude/, installs tools + rules + session hook
bash install_mcps.sh        # builds the local Gmail / Calendar / WhatsApp MCPs
bash register_mcps.sh       # tells Claude Code about them
```

Then open a fresh Claude Code session in `~/Desktop/claude/` and ask:

```
> What are my critical rules?
```

If Claude paraphrases them back, you're done. If it shrugs, the rules file didn't load - see Troubleshooting.

Want only one piece (say, just the multi-account Gmail server)? Each `mcp-servers/*/` folder builds on its own: `npm install && npm run build` inside it, then the matching `claude mcp add` line from `register_mcps.sh`.

## What you need

- **Node.js 18+** (`brew install node` on macOS) - for the MCP servers.
- **Python 3.10+** (`brew install python` on macOS) - for the tools and the Telegram server.
- **Claude Code** - get it from [claude.com/claude-code](https://claude.com/claude-code).

Optional:

- **WhatsApp for Mac** - only if you want the WhatsApp MCP.

## Or: have Claude install it for you

1. Open a fresh Claude Code session in any directory.
2. Paste the contents of `SETUP_PROMPT.md` into the chat.
3. Claude walks through it step by step, asking before writing anything.

## Staying up to date

From inside your clone:

```bash
bash tools/update.sh
```

It fetches `origin/main`, shows what changed, refuses to run over uncommitted local edits (`--force` stashes and restores them), fast-forwards, then re-runs `install.sh --update-only`. Or install the optional "update pupsik" skill and just say it: [`docs/UPDATE_PUPSIK.md`](docs/UPDATE_PUPSIK.md).

### What `update.sh` updates

- `~/Desktop/claude/tools/{contacts_db,enrichment_schema_migrate,now}.py`
- `~/Desktop/claude/.claude/hooks/session-start-reminder.sh`
- `~/Desktop/claude/rules/feedback_*.md`
- `~/.claude/rules/critical-rules.md` - append-only: new rule lines go under a dated `## Updates from upstream` header, nothing you wrote is replaced.

### What it never touches

- Your `CLAUDE.md`, `data/contacts.db`, `memory/`, `outputs/`
- Claude's built-in memory and your Claude settings (apart from cleaning up pupsik's own old leftovers and hooks, with backups - see `UPGRADING.md`)
- Scheduled-task templates (opt-in - see `UPGRADING.md`)

### If you customised a file

- **Rules (`rules/feedback_*.md`)** - if you edited one, the new version lands next to it as `<file>.new` and yours stays. Unchanged ones are updated, with the old copy kept as `<file>.bak.<timestamp>`.
- **Tools and the session hook** - these are replaced with the new version. Your old copy is kept as `<file>.bak.<timestamp>` (or `.bak.<timestamp>.force-resync`), so a local edit can be recovered, but it is not merged for you.

### Privacy-checked at the source

Every push runs the [Privacy Check workflow](.github/workflows/privacy-check.yml) - a multi-pattern grep that fails the build if anything personal sneaks in (real names, emails, phone numbers, IDs, tokens, oversize blobs). The script is [`.github/scripts/privacy-check.sh`](.github/scripts/privacy-check.sh) and runs locally too. Forks get the same check.

## After install

1. **Edit your `CLAUDE.md`.** Fill in the `{{PLACEHOLDERS}}` and keep it short - Claude reads it every session.
2. **Add some contacts:**

   ```bash
   python3 ~/Desktop/claude/tools/contacts_db.py sql \
     "INSERT INTO contacts (name, email, company, category) VALUES ('Alice Smith', 'alice@example.com', 'Acme Corp', 'work')"
   ```

   Or, once the WhatsApp MCP is up, ask Claude to "run whatsapp_sync_to_contacts_db".
3. **Wire up Google.** Follow `docs/GOOGLE_CLOUD_SETUP.md` - about 15 minutes, once.
4. **Register the session hook.** `install.sh` prints a small `settings.json` snippet at the end. Add it to `~/.claude/settings.json`.

## Troubleshooting

- **`claude` command not found** - install Claude Code from [claude.com/claude-code](https://claude.com/claude-code).
- **MCP servers fail to build** - check `node --version` (need 18+). Run `npm install` in each `mcp-servers/*/` folder to see the error.
- **WhatsApp MCP says "permission denied"** - your terminal needs Full Disk Access. See `docs/WHATSAPP_SETUP.md` Step 2.
- **Gmail auth fails with "access blocked"** - add yourself as a test user on the Google Cloud consent screen. See `docs/GOOGLE_CLOUD_SETUP.md` Step 3.7.
- **Session hook doesn't fire** - check `~/.claude/settings.json` is valid JSON and the hook path is absolute.
- **Claude doesn't know your rules** - confirm `~/.claude/rules/critical-rules.md` exists and the `feedback_*.md` files are in `~/Desktop/claude/rules/`. Upgrading from an older version? Your rules may still be in Claude's memory folder - see `UPGRADING.md`.

## Uninstall

```bash
rm -rf ~/Desktop/claude/.claude/hooks ~/Desktop/claude/rules ~/code/mcp-servers
rm ~/Desktop/claude/tools/contacts_db.py ~/Desktop/claude/tools/now.py ~/Desktop/claude/tools/enrichment_schema_migrate.py
claude mcp remove multi-gmail
claude mcp remove multi-gcal
claude mcp remove whatsapp
claude mcp remove telegram-readonly   # only if you enabled it
rm -rf ~/.telegram-readonly-mcp       # its encryption key, if you enabled it
# To remove everything:
rm ~/Desktop/claude/CLAUDE.md ~/Desktop/claude/data/contacts.db
```

The Google Cloud project, OAuth credentials and npm packages aren't touched - remove those by hand for a clean slate.

## Docs

- [`UPGRADING.md`](UPGRADING.md) - coming from an older version: what's kept, what's removed, how to roll back.
- [`CONTRIBUTING.md`](CONTRIBUTING.md) - PR rules. Short version: no personal data, ever.
- [`THIRD_PARTY_ATTRIBUTIONS.md`](THIRD_PARTY_ATTRIBUTIONS.md) - what I borrowed from where.
- [`CHANGELOG.md`](CHANGELOG.md) - release notes.

## Releases

### v2026-11 (2026-11-13)

Slimmed to what Claude can't do itself. Removed: the ChromaDB search and note-capture layer, the dashboard, the Brand OS bridge, the morning-briefing template and the rules that depended on them. Pupsik no longer writes into Claude's built-in memory folder or changes Claude settings. Updating doesn't delete files you already have. Details in [`CHANGELOG.md`](CHANGELOG.md) and [`UPGRADING.md`](UPGRADING.md).

### v2026-09 (2026-09-23)

Compaction hooks, context-budget tooling, doctor and heavy process rules removed - current models handle these natively.

## About

I'm a solo founder running an early-stage company end to end through Claude Code. I built this for me and use it every day. It's on GitHub because someone with the same setup probably wants the same fixes.

If you find it useful, a star helps others discover it. ⭐

## License

MIT. See [`LICENSE`](LICENSE).

The bundled MCP servers carry their own licenses (each `mcp-servers/*/LICENSE` where present - `multi-gmail` is MIT). Everything else here is MIT.
