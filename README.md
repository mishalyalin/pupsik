# Pupsik

> What I use to make Claude Code remember things between sessions.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Built for: Claude Code](https://img.shields.io/badge/Built_for-Claude_Code-blueviolet)](https://claude.com/claude-code)
[![Status: I use it daily](https://img.shields.io/badge/Status-I_use_it_daily-green)](#)
[![Auto-update: enabled](https://img.shields.io/badge/Auto--update-enabled-blue)](#staying-up-to-date)
[![Privacy-checked: CI](https://img.shields.io/badge/Privacy--checked-CI-green)](.github/workflows/privacy-check.yml)

I'm Misha. Solo founder. I run my whole company on Claude Code - sales, ops, finance, taxes, kids' school stuff, all of it. Not just code.

The problem: Claude Code forgets everything between sessions. Every morning, fresh start, no memory.

So I built this. Pupsik is the workspace I drop into `~/Desktop/claude/`. It gives Claude a contact DB, semantic search across my notes, all my Gmail accounts in one call, WhatsApp read access, and a set of rules that stop it from doing dumb things.

It works for me every day. Putting it on GitHub because someone else probably has the same problem.

MIT. macOS-friendly. Local. No telemetry, no cloud sync, no SaaS dashboard.

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

If Claude paraphrases it back, you're done. If it shrugs, the rules file didn't load - jump to Troubleshooting.

## What's in it

- **Contact graph DB** (SQLite). Every person I deal with, their company, every interaction, every link between them. I run `contacts_db.py find "Steve"` instead of digging through Gmail. There's a graph traversal too - "how do I get introduced to person X" returns a chain.
- **Semantic search across 9 ChromaDB collections.** My notes, briefings, journal, decisions, learnings, research, plus the contact DB. One query, all of it. `memory_search.py search "что было с Vendor-A в апреле"` and it pulls the relevant chunks.
- **Capture knowledge the second it happens.** `note.py learning "Title" "body"` writes a learning note and reindexes it in 50ms. Re-run the same title later and it upserts - one note per topic, kept current. The `decision`, `research`, `world_knowledge`, and `user_context` variants do the same. World knowledge (VAT rates, regulatory limits, industry conventions) and user context (working style, schedule, environmental constraints) live as their own ChromaDB sub-collections, separate from prescriptive `feedback_*.md` rules. Cherry-picked from obra/private-journal-mcp.
- **Multi-account Gmail / Calendar / WhatsApp MCPs.** I have 3 Gmail accounts. `gmail_search_all` searches all of them in one call. Same for Calendar. WhatsApp is read-only on macOS but it pulls into the contact DB.
- **Telegram read-only MCP (opt-in).** A local userbot server that reads a small, explicit **allowlist** of chats — and nothing else. Read-only **by construction**: exactly 3 tools, no send/edit/delete/forward code path exists at all, no account-wide chat enumeration, session Fernet-encrypted at rest, and the login (phone / code / 2FA) is interactive-only — the assistant never sees credentials. This is the security shape I'd suggest for ANY account-powerful MCP: cap the blast radius structurally, not with a prompt. Python + Telethon, manual setup: `mcp-servers/telegram-readonly/README.md`. (Different thing from `docs/TELEGRAM_SETUP.md`, which is the message-Claude-from-your-phone bot.)
- **Optional contact-enrichment cron, 4 passes.** Gmail signature mining for LinkedIn / Twitter / GitHub / website / phone. Then web search for missing LinkedIn URLs. Then a short bio + Instagram. Then Pass 4: it reads my email and WhatsApp correspondence with the contact and writes a 2-4 sentence private summary into `relationship_context`. That field never leaves my local DB - not in any export, not in briefings (briefings reformulate, never quote), not in this repo. Telegram is never auto-read; if I want TG context for a specific contact, I paste the history into an ad-hoc prompt manually. Runs Sunday 06:00 if I enable it.
- **Date-aware session anchor.** `tools/now.py` is the single source of truth for current datetime + IANA timezone, and the SessionStart hook injects `⏰ NOW: YYYY-MM-DD (Weekday), HH:MM TZ` into the top of every session. Kills the failure mode where Claude pattern-matches a stale date from prior context and thinks today is six months ago.
- **Connection-aware memory graph.** `tools/note_graph.py` builds entity-mention edges across all my notes and surfaces 5-10 tight thematic clusters from the last 7 days. `memory_search.py wake-up` now includes an "Active clusters" block so I see what's currently hot without asking.
- **Rule retrieval on demand.** `tools/rules.py search "<topic>"` returns the FULL content of feedback rules that match - so when Claude is about to draft an outbound email or answer a status question, it pulls the actual verification protocols, not just the one-line pointer in `critical-rules.md`. Merges an optional alias manifest with semantic search; falls back gracefully if no manifest is present.
- **Brand OS opt-in for customer-comms rules (API-first, local-CLI fallback).** `tools/brand_os.py` is a thin bridge to an optional **Brand OS** - a versioned repo you maintain on your own GitHub that holds your brand voice, positioning canon, persuasion tactics (BE + Voss/NSTD + Cialdini-Sutherland), anti-patterns, evidence library, and a retrieval surface (Python CLI, HTTP API, or both). If you have one configured, the marketing-panel + outbound-email rules pull canon from it before drafting. If you don't, they fall back to the inline 21-tactic playbook + 3-lens panel spec shipped with the toolkit. Detection picks the best available mode:
  - **API mode** (preferred) - hit one server-side canon copy over HTTPS so every session (yours, your designer's, your social-media marketer's, every Claude session) shares the same canon. No `git clone` drift. Configured via `~/.brand-os-credentials` (mode 600, gitignored - see `.brand-os-credentials.example` for the format) or env vars `BRAND_OS_API_URL` + `BRAND_OS_API_USER` + `BRAND_OS_API_PASS`. Falls back to local CLI on network failure.
  - **Local CLI mode** (fallback) - `git clone` of the Brand OS repo on each user's machine; helper invokes the local Python CLI via subprocess. Detection chain: `BRAND_OS_PATH` env var > `~/.brand-os` symlink > auto-detect under `~/Desktop/claude/projects/*-brand-os`.
  - **Not configured** - silent + safe; the customer-comms rules fall back to inline canon.

  A typical Brand OS is structured as a multi-layer canon (positioning anchors / persuasion-cocktail recipes / canon principles drawn from Behavioral Economics + Voss/NSTD + Cialdini-Sutherland + LLM SEO / a Vault of evidence rows tying each principle to a primary source). Its retrieval surface is whatever you build - a Python CLI works, and a small Flask wrapper that exposes the same retrieval as `/api/*` JSON endpoints (e.g. `/api/icp`, `/api/search`, `/api/explain`, `/api/tactic/<name>`, `/api/for-vector/<key>`, `/api/for-stage/<name>`, `/api/canon`, `/api/list-tactics`, `/api/list-stages`, `/api/stats`) is the pattern `tools/brand_os.py` targets in API mode. The value of a Brand OS: one URL to your designer, social-media marketer, copywriter, and any future Claude session - same brand tone, same banned words, same persuasion-cocktail recipes everywhere. Keep your Brand OS repo PRIVATE - the canon is your competitive advantage; only the bridge helper here is public.
- **`~/.claude/rules/critical-rules.md` auto-loads every session.** A short list of facts and preferences, not process: verify before stating numbers or facts, check the contact DB before naming a person, capture knowledge with `note.py`, all Gmail accounts always, save outputs with descriptive names, one checker agent only for things that ship.
- **One checker for things that ship.** Code merged to main, public posts and outbound messages get one independent checker agent. Lookups, answers and small edits don't.
- **32 generic feedback rules** in `memory_templates/feedback_*.md`. Each one is a thing I corrected Claude on enough times to make it permanent. Not opinion-shaped advice - corrected behaviour pinned to disk.
- **Third-party attribution discipline.** `THIRD_PARTY_ATTRIBUTIONS.md` at the repo root tracks every pattern I borrowed from external OSS (currently: gbrain by Garry Tan, MIT). Source URL, author, license, what I took verbatim vs adapted vs added.
- **`auto` permission mode by default.** Accepts safe ops, prompts on writes / shell / risky calls. Replaces `bypassPermissions` as the recommendation. Less friction than full bypass, less risk of nuking things.
- **Structural enforcement against the leak / drift classes that bite repeatedly.** `.github/scripts/privacy-check.sh` Pass 11 catches `<author-handle>/<private-repo-suffix>` combinations even in byline-allowlisted files like README and CHANGELOG (the leak class that byline allowlist misses by design). `scripts/brand-os-visual-gate.sh` byte-diffs `dashboard/favicon.svg` and the `mask-icon` / `theme-color` hexes in `dashboard/build.py` against the locked Brand OS visual spec at build time, then aborts the VPS push when drift is detected. `.githooks/pre-commit` runs the privacy scan locally before the commit SHA is even minted (opt-in via `bash scripts/install-git-hooks.sh`, emergency bypass via `PUPSIK_SKIP_PRIVACY_CHECK=1 git commit`). All three are opt-in by configuration: forks without the relevant private-patterns / Brand OS clone / hook install see no change.

## Docs

- [`HOW_IT_WORKS.md`](HOW_IT_WORKS.md) - the concept walkthrough. **Start here** if you want to understand the architecture before installing.
- [`UPGRADING.md`](UPGRADING.md) - if you're already on an older version. What gets preserved, what gets replaced, how to roll back.
- [`MODULAR.md`](MODULAR.md) - if you have your own Claude Code setup and want individual pieces. Each component, its dependencies, install snippet.
- [`CONTRIBUTING.md`](CONTRIBUTING.md) - PR rules. Short version: no personal data, ever.
- [`THIRD_PARTY_ATTRIBUTIONS.md`](THIRD_PARTY_ATTRIBUTIONS.md) - what I borrowed from where.
- [`CHANGELOG.md`](CHANGELOG.md) - release notes.

## What you need

- **Node.js 18+** (`brew install node` on macOS) - for the MCP servers.
- **Python 3.10+** (`brew install python` on macOS) - for the tools.
- **Claude Code CLI** on PATH - get it from [claude.com/claude-code](https://claude.com/claude-code).
- **`pip install chromadb`** - the installer handles this.

Optional:

- **WhatsApp for Mac** - only if you want the WhatsApp MCP. Skip it otherwise.

## Or: have Claude install it for you

If you'd rather watch Claude do the install with diffs at every step:

1. Open a fresh Claude Code session in any directory.
2. Paste the contents of `SETUP_PROMPT.md` into the chat.
3. Claude walks through it step by step, asking for approval before writing anything, and has one checker agent verify the result.

Slower than `bash install.sh`. More transparent. Pick whichever you prefer.

## Staying up to date

The "Auto-update: enabled" badge means updates are **surfaced and one-command**,
not silently pulled behind your back. Your dashboard shows what's new since you
installed (see [the panel](#the-dashboard-whats-new-panel) below), and a single
command applies it. Nothing updates without you running it.

From inside your clone:

```bash
bash tools/update.sh
```

What it does:

1. `git fetch origin/main`. If you're up to date, exits silently.
2. Shows the new commits and the file diff before touching anything.
3. Refuses to run if you have uncommitted local edits (pass `--force` to stash, update, restore).
4. Fast-forward only - never rewrites your local commits.
5. Re-runs `bash install.sh --update-only` to apply new tools / hooks / rules / feedback templates.
6. Runs a one-time cleanup that removes retired pieces from your install (see the v2026-09 note under Releases). Safe to run again - it does nothing the second time.

### What `update.sh` updates

- `tools/{contacts_db,memory_search,note,now,rules,brand_os,note_graph,enrichment_schema_migrate}.py` (smart-merge - see below)
- `~/.claude/rules/critical-rules.md` (append-only smart merge)
- `~/Desktop/claude/.claude/hooks/session-start-reminder.sh` (smart-merge)
- `memory_templates/feedback_*.md` (smart-merge in your project memory directory)

### What `update.sh` will never touch

- Your `CLAUDE.md`
- Your `data/contacts.db`
- `memory/learnings/`, `memory/decisions/`, `memory/journal/`, `memory/people/`, `memory/projects/`
- `briefings/`, `outputs/`, `research/`
- Any feedback rule you've personalised in your project memory directory
- Scheduled-task templates (those are opt-in - see UPGRADING.md for the install command)

In short: **your data is safe.** Only the tooling layer gets replaced.

### What if I customised a file

`update.sh` is conservative. It never silently overwrites your edits.

For each managed file:

- **Identical to upstream** - nothing happens.
- **You haven't modified it since last install** - safely updated, your old copy backed up as `<file>.bak.<timestamp>`.
- **You modified it** - the new upstream version drops side-by-side as `<file>.new`. Your version stays untouched. Diff and merge:

  ```bash
  diff ~/Desktop/claude/tools/memory_search.py{,.new}
  # ...resolve, then either rm the .new file or replace the original
  ```

After the update, `update.sh` prints which `.new` files are waiting on you.

`~/.claude/rules/critical-rules.md` is special - it's **never replaced**. New rule references from the upstream template get appended at the bottom under a `## Updates from upstream <date>` header. Your existing content stays put, including any rules you wrote yourself.

### The dashboard "What's new" panel

Your morning dashboard (`dashboard/build.py`) renders a **"What's new in pupsik"**
panel at the top of the **Architect** tab. When your clone is behind upstream it
lists the new CHANGELOG entries (version · title · summary) and gives you an
**Update pupsik** button that copies `cd <clone> && git pull && bash tools/update.sh`
to your clipboard. When you're current it shows a quiet "✓ pupsik up to date".

The panel is fed by a lightweight probe, `tools/check-update.sh`:

- It's a **local `git fetch`** on the clone you already have — the same thing
  `git pull` does. It sends **no** data about you anywhere, keeping the
  "Local. No telemetry, no cloud sync" promise. (Outside a git clone it falls
  back to a read-only GET of the public `VERSION` + `CHANGELOG.md`.)
- The session-start hook runs it in the background (throttled to once per 6h,
  never blocking session start), so the panel stays fresh on its own.
- **Opt out** any time: `export PUPSIK_NO_UPDATE_CHECK=1`. Then it does nothing.

Full details, plus the optional **"update pupsik"** Claude skill (say "update
pupsik" and Claude runs the update for you), are in
[`docs/UPDATE_PUPSIK.md`](docs/UPDATE_PUPSIK.md).

### Optional: weekly auto-update via cron

```
# Every Monday at 09:00 local. Adjust the path to wherever you cloned.
# update.sh also refreshes the dashboard "What's new" panel's version marker.
0 9 * * 1 cd ~/pupsik && bash tools/update.sh >> ~/pupsik/.update.log 2>&1
```

Prefer to be *notified* but pull manually? Run the check only (no pull) — it
just refreshes the dashboard panel:

```
# Every day at 08:00 local — refresh the panel without updating.
0 8 * * * cd ~/pupsik && bash tools/check-update.sh >/dev/null 2>&1
```

### Privacy-checked at the source

Every push to `mishalyalin/pupsik` runs the [Privacy Check workflow](.github/workflows/privacy-check.yml) - a multi-pattern grep that fails the build if anything privacy-sensitive sneaks into the diff (real names, real emails, phone numbers, IDs, project codenames, API tokens, oversize blobs). The script lives at [`.github/scripts/privacy-check.sh`](.github/scripts/privacy-check.sh) and runs locally too.

If you fork it, the same workflow runs on your fork.

## After install

### 1. Edit your CLAUDE.md

The template at `~/Desktop/claude/CLAUDE.md` has `{{PLACEHOLDERS}}`. Fill in your name, role, what you're working on. This is the file Claude reads first every session - it's the "I am Misha and I'm working on these projects" doc, in your version.

### 2. Add some contacts

```bash
python3 ~/Desktop/claude/tools/contacts_db.py init
python3 ~/Desktop/claude/tools/contacts_db.py add "Alice Smith" \
  --email alice@example.com --company "Acme Corp" --category "work"
```

Or pull from WhatsApp once the MCP is up:

```
Ask Claude: "Run whatsapp_sync_to_contacts_db"
```

### 3. Wire up your Google accounts

Follow `docs/GOOGLE_CLOUD_SETUP.md`. About 15 minutes, one-time.

### 4. Register the session hook

`install.sh` prints a small `settings.json` snippet at the end. Add it to `~/.claude/settings.json` so every session starts with the current date and your recent rule changes.

## Troubleshooting

- **`claude` command not found** - install the Claude Code CLI from [claude.com/claude-code](https://claude.com/claude-code).
- **MCP servers fail to build** - check `node --version` (need 18+). Run `npm install` in each `mcp-servers/*/` dir manually to see the error.
- **WhatsApp MCP says "permission denied"** - your terminal needs Full Disk Access. See `docs/WHATSAPP_SETUP.md` Step 2.
- **Gmail auth fails with "access blocked"** - you didn't add yourself as a test user in the Google Cloud consent screen. See `docs/GOOGLE_CLOUD_SETUP.md` Step 3.7.
- **Session hook doesn't fire** - check `~/.claude/settings.json` is valid JSON and the hook path is absolute.
- **Claude doesn't know your rules** - confirm `~/.claude/rules/critical-rules.md` exists and the `feedback_*.md` files are in your project memory directory.

## Uninstall

```bash
rm -rf ~/Desktop/claude/.claude/hooks ~/Desktop/claude/mcp-servers ~/code/mcp-servers
rm ~/Desktop/claude/tools/contacts_db.py ~/Desktop/claude/tools/memory_search.py
claude mcp remove multi-gmail
claude mcp remove multi-gcal
claude mcp remove whatsapp
claude mcp remove telegram-readonly   # only if you enabled it
rm -rf ~/.telegram-readonly-mcp       # its encryption key, if you enabled it
# If you want to nuke everything:
rm ~/Desktop/claude/CLAUDE.md ~/Desktop/claude/data/contacts.db
```

The Google Cloud project, OAuth credentials, and installed npm packages aren't touched - kill those manually if you want a clean slate.

## Contributing

PRs are welcome. The bar: changes should make sense to a fresh user who has never met any of the contributors. No personal data, ever. See [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Releases

Full release notes in [`CHANGELOG.md`](CHANGELOG.md).

### v2026-09 (2026-09-23)

v2026-09 slimmed for Claude 5-era models: compaction hooks, context-budget tooling, doctor and heavy process rules removed - current models handle this natively. Updating removes them from your install automatically (backups kept).

Older release notes live in [`CHANGELOG.md`](CHANGELOG.md).

For users on a previous version, see [`UPGRADING.md`](UPGRADING.md) for the migration path.

## About

I'm a solo founder running an early-stage company end to end through Claude Code. This toolkit is what makes that practical. I built it for me. I use it every day. Putting it on GitHub because someone else with the same setup probably wants the same fixes.

If you find it useful, a star helps others discover it. ⭐

## License

MIT. See [`LICENSE`](LICENSE).

The bundled MCP servers carry their own licenses (each `mcp-servers/*/LICENSE` where present - `multi-gmail` is MIT). Everything else here is MIT.
