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
bash install.sh             # creates ~/Desktop/claude/, installs tools + rules + hooks
bash install_mcps.sh        # builds the local Gmail / Calendar / WhatsApp MCPs
bash register_mcps.sh       # tells Claude Code about them
```

Then open a fresh Claude Code session in `~/Desktop/claude/` and ask:

```
> What's your 2-agent rule?
```

If Claude paraphrases it back, you're done. If it shrugs, the rules file didn't load - jump to Troubleshooting.

## What's in it

- **Contact graph DB** (SQLite). Every person I deal with, their company, every interaction, every link between them. I run `contacts_db.py find "Steve"` instead of digging through Gmail. There's a graph traversal too - "how do I get introduced to person X" returns a chain.
- **Semantic search across 9 ChromaDB collections.** My notes, briefings, journal, decisions, learnings, research, plus the contact DB. One query, all of it. `memory_search.py search "что было с Tupak в апреле"` and it pulls the relevant chunks.
- **Capture knowledge the second it happens.** `note.py learning "Title" "body"` writes a learning note and reindexes it in 50ms. Re-run the same title later and it upserts - one note per topic, kept current. The `decision`, `research`, `world_knowledge`, and `user_context` variants do the same. World knowledge (VAT rates, regulatory limits, industry conventions) and user context (working style, schedule, environmental constraints) live as their own ChromaDB sub-collections, separate from prescriptive `feedback_*.md` rules. Cherry-picked from obra/private-journal-mcp.
- **Multi-account Gmail / Calendar / WhatsApp MCPs.** I have 3 Gmail accounts. `gmail_search_all` searches all of them in one call. Same for Calendar. WhatsApp is read-only on macOS but it pulls into the contact DB.
- **`tools/doctor.py` health-check + safe auto-fix.** 13 deterministic checks across the workspace. Broken symlinks, stale lock files, ChromaDB orphan rows, oversized CLAUDE.md, dangling memory pointers. `check` is read-only; `fix-safe` only does safe repairs (never rewrites my prose); `orphans` lists unlinked entities for me to review. Cron-safe.
- **Friction protocol.** `note.py friction --severity blocker --phase X --message Y` captures the moments when something's wrong but I don't have time to fix it now. Re-run the same phase + severity and the counter increments. After 3 hits, my morning briefing surfaces it loud.
- **Optional contact-enrichment cron, 4 passes.** Gmail signature mining for LinkedIn / Twitter / GitHub / website / phone. Then web search for missing LinkedIn URLs. Then a short bio + Instagram. Then Pass 4: it reads my email and WhatsApp correspondence with the contact and writes a 2-4 sentence private summary into `relationship_context`. That field never leaves my local DB - not in any export, not in briefings (briefings reformulate, never quote), not in this repo. Telegram is never auto-read; a heuristic flags Russian-speaker contacts so I can paste TG history manually if I want their context refreshed. Runs Sunday 06:00 if I enable it.
- **Auto-compact hooks + 50% threshold.** `PreCompact` saves session state to disk before Claude compacts. `PostCompact` reminds it to restore. `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE=50` fires compaction at half-context instead of waiting until 95% and losing the plot.
- **2-agent rule.** Every real task spawns a Worker plus an independent Checker. Catches the bugs a single-agent pass misses. I learned this the hard way; it's now non-negotiable for anything I'd actually ship.
- **Architect proposals backlog.** Every time the morning briefing's Architect Lens spots a structural issue, the proposal gets written to `memory/architect_proposals/latest.md` with a status (`open` / `applied` / `rejected` / etc). Small same-turn fixes apply immediately and log as `applied`; bigger things wait for my sign-off as `open` and the brief surfaces the top-3 each morning. Rejected proposals get a 90-day re-propose suppression so I stop seeing the same noise. Local-only; never goes in any public export.
- **Date-aware session anchor.** `tools/now.py` is the single source of truth for current datetime + IANA timezone, and a SessionStart hook injects `⏰ NOW: YYYY-MM-DD (Weekday), HH:MM TZ` into the top of every session. Kills the failure mode where Claude pattern-matches a stale date from prior context and thinks today is six months ago.
- **Connection-aware memory graph.** `tools/note_graph.py` builds entity-mention edges across all my notes and surfaces 5-10 tight thematic clusters from the last 7 days. `memory_search.py wake-up` now includes an "Active clusters" block so I see what's currently hot without asking.
- **Rule retrieval on demand.** `tools/rules.py search "<topic>"` returns the FULL content of feedback rules that match - so when Claude is about to draft an outbound email or answer a status question, it pulls the actual verification protocols, not just the one-line pointer in `critical-rules.md`. Merges an optional alias manifest with semantic search; falls back gracefully if no manifest is present.
- **Brand OS opt-in for customer-comms rules (API-first, local-CLI fallback).** `tools/brand_os.py` is a thin bridge to an optional **Brand OS** - a versioned repo you maintain on your own GitHub that holds your brand voice, positioning canon, persuasion tactics (BE + Voss/NSTD + Cialdini-Sutherland), anti-patterns, evidence library, and a retrieval surface (Python CLI, HTTP API, or both). If you have one configured, the marketing-panel + outbound-email rules pull canon from it before drafting. If you don't, they fall back to the inline 21-tactic playbook + 3-lens panel spec shipped with the toolkit. Detection picks the best available mode:
  - **API mode** (preferred) - hit one server-side canon copy over HTTPS so every session (yours, your designer's, your social-media marketer's, every Claude session) shares the same canon. No `git clone` drift. Configured via `~/.brand-os-credentials` (mode 600, gitignored - see `.brand-os-credentials.example` for the format) or env vars `BRAND_OS_API_URL` + `BRAND_OS_API_USER` + `BRAND_OS_API_PASS`. Falls back to local CLI on network failure.
  - **Local CLI mode** (fallback) - `git clone` of the Brand OS repo on each user's machine; helper invokes the local Python CLI via subprocess. Detection chain: `BRAND_OS_PATH` env var > `~/.brand-os` symlink > auto-detect under `~/Desktop/claude/projects/*-brand-os`.
  - **Not configured** - silent + safe; the customer-comms rules fall back to inline canon.

  Reference implementation: [github.com/mishalyalin/pranasalt-brand-os](https://github.com/mishalyalin/pranasalt-brand-os) - a 4-layer canon (15 positioning anchors / 15 cocktails / 57 canon principles / 445 evidence rows) with a `marketing_brain.py` CLI + a Flask `web/app.py` that exposes `/api/icp`, `/api/search`, `/api/explain`, `/api/tactic/<name>`, `/api/for-vector/<key>`, `/api/for-stage/<name>`, `/api/canon`, `/api/list-tactics`, `/api/list-stages`, `/api/stats`. The value of a Brand OS: one URL to your designer, social-media marketer, copywriter, and any future Claude session - same brand tone, same banned words, same persuasion-cocktail recipes everywhere.
- **`~/.claude/rules/critical-rules.md` auto-loads every session.** This is where the MANDATORY rules live - the FIRST bullet is now "NEVER IMAGINE, ALWAYS VERIFY" (the parent of every verify-* rule), then contact DB before mentioning a person, never use em-dashes in my voice, never write Excel files (I don't use Office), all 3 Gmail accounts always, etc.
- **27 generic feedback rules** in `memory_templates/feedback_*.md`. Each one is a thing I corrected Claude on enough times to make it permanent. Not opinion-shaped advice - corrected behaviour pinned to disk.
- **5 agent role prompts** (Architect, Discoverer, Packager, Migrator, Tester). I use them when a task warrants a team, not a solo run.
- **Third-party attribution discipline.** `THIRD_PARTY_ATTRIBUTIONS.md` at the repo root tracks every pattern I borrowed from external OSS (currently: gbrain by Garry Tan, MIT). Source URL, author, license, what I took verbatim vs adapted vs added.
- **`auto` permission mode by default.** Accepts safe ops, prompts on writes / shell / risky calls. Replaces `bypassPermissions` as the recommendation. Less friction than full bypass, less risk of nuking things.

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
3. Claude spawns 5 agents (architect, discoverer, packager, migrator, tester) and walks through it step by step, asking for approval before writing anything.

Slower than `bash install.sh`. More transparent. Pick whichever you prefer.

## Staying up to date

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

### What `update.sh` updates

- `tools/{contacts_db,memory_search,note,doctor,enrichment_schema_migrate,flag_russian_speakers}.py` (smart-merge - see below)
- `~/.claude/rules/critical-rules.md` (append-only smart merge)
- `~/Desktop/claude/.claude/hooks/{pre,post}-compact.sh` (smart-merge)
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

### Optional: weekly auto-update via cron

```
# Every Monday at 09:00 local. Adjust the path to wherever you cloned.
0 9 * * 1 cd ~/pupsik && bash tools/update.sh >> ~/pupsik/.update.log 2>&1
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

### 4. Test the 2-agent rule

Give Claude a real task (not a one-shot lookup) and watch it spawn multiple agents. See `docs/AGENT_TEAM_RULE.md`.

## Troubleshooting

- **`claude` command not found** - install the Claude Code CLI from [claude.com/claude-code](https://claude.com/claude-code).
- **MCP servers fail to build** - check `node --version` (need 18+). Run `npm install` in each `mcp-servers/*/` dir manually to see the error.
- **WhatsApp MCP says "permission denied"** - your terminal needs Full Disk Access. See `docs/WHATSAPP_SETUP.md` Step 2.
- **Gmail auth fails with "access blocked"** - you didn't add yourself as a test user in the Google Cloud consent screen. See `docs/GOOGLE_CLOUD_SETUP.md` Step 3.7.
- **Compact hooks don't fire** - check `~/.claude/settings.json` is valid JSON and paths are absolute. See `docs/COMPACT_SETUP.md`.
- **Claude doesn't mention the 2-agent rule** - confirm `~/Desktop/claude/CLAUDE.md` has the rule section and `memory/feedback_always_two_agents.md` is in your project memory directory.

## Uninstall

```bash
rm -rf ~/Desktop/claude/.claude/hooks ~/Desktop/claude/mcp-servers
rm ~/Desktop/claude/tools/contacts_db.py ~/Desktop/claude/tools/memory_search.py
claude mcp remove multi-gmail
claude mcp remove multi-gcal
claude mcp remove whatsapp
# If you want to nuke everything:
rm ~/Desktop/claude/CLAUDE.md ~/Desktop/claude/data/contacts.db
```

The Google Cloud project, OAuth credentials, and installed npm packages aren't touched - kill those manually if you want a clean slate.

## Contributing

PRs are welcome. The bar: changes should make sense to a fresh user who has never met any of the contributors. No personal data, ever. See [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Releases

Full release notes in [`CHANGELOG.md`](CHANGELOG.md).

### What's new (2026-05-09)

1. **Pass 4 of the contact-enrichment cron** - reads my email and WhatsApp correspondence with each contact and synthesizes a 2-4 sentence private `relationship_context` summary. The field never leaves the local DB. Telegram is never auto-read - manual paste only, per the upstream rule.
2. **Russian-speaker heuristic.** `tools/flag_russian_speakers.py` flags contacts likely to be on Telegram (Cyrillic name / Latin transliteration of a Russian first name / Russian surname suffix / Russian-domain email / opt-in company match via `$RUSSIAN_CONTEXT_COMPANIES`). Idempotent. The cron's Step 0.5 calls it.
3. **Schema migration: 10 -> 12 columns.** `enrichment_schema_migrate.py` now adds `relationship_context` and `tg_manual_paste_recommended` on top of the original 10. Re-runs are safe.
4. **Upgrade discipline closed.** `tools/update.sh` and `install.sh` now smart-merge all 6 tools instead of just the original 3. Existing pupsik installs running `update.sh` will pick up `doctor.py`, `enrichment_schema_migrate.py`, and `flag_russian_speakers.py` automatically.
5. **UPGRADING.md rewritten.** Per-release format with one-time steps + verification checks for each release back to Phase 2. Backfill recipe included for users who ran the 2026-05-08 cron before this update.

### What's new (2026-05-07: gbrain pattern imports + privacy)

1. **`tools/doctor.py`** - 13 deterministic health checks across `check` / `fix-safe` / `orphans`. Cron-safe, never rewrites prose. Adapted from gbrain (Garry Tan, MIT).
2. **`note.py friction` subcommand** - severity-tagged friction events (`blocker` / `error` / `confused` / `nit`). Counter-incremented on repeat. `friction summary --days 7 --top 3` for morning briefings. Adapted from gbrain.
3. **Output Rules adapted from gbrain** - 4 cross-cutting quality rules (Deterministic Links, No Slop, Exact Phrasing Preservation, Title Quality) attributed in `THIRD_PARTY_ATTRIBUTIONS.md`.
4. **`THIRD_PARTY_ATTRIBUTIONS.md`** at repo root - central tracker for everything I borrowed.
5. **Privacy hardening.** 5 feedback templates re-generalised after the privacy-check pattern catalogue tightened. `bash .github/scripts/privacy-check.sh --include-untracked` now passes 10/10.
6. **Em-dash style consistency.** Mass sed-pass cleaned 90 em-dashes lurking in template prose and tooling docstrings. `feedback_short_dashes_only.md` is the rule.

### What's new (2026-04-29: Phase 2)

1. **9-collection ChromaDB indexer.** `memory_search.py` now indexes 9 collections (briefings, outputs, journal, knowledge, research added on top of contacts, interactions, memory_files, chat_archives). The `knowledge` collection holds both `learnings/` and `decisions/` in one searchable index.
2. **`tools/note.py`** - capture a learning, decision, or research note in one command. Upserts by title - one note per topic, kept current.
3. **`feedback_capture_knowledge.md`** - new MANDATORY rule. Tells Claude to call `note.py` the moment an insight surfaces, not at the end of the topic.
4. **Idempotent reindex.** `coll.upsert` everywhere. Re-running `memory_search.py index` is safe and cheap.
5. **Surgical single-file reindex.** `memory_search.py index --file <path>` reindexes one file in ~50ms instead of rebuilding the whole thing. `note.py` uses this automatically.
6. **Concurrency-safe lockfile with stale TTL.** Parallel reindex calls don't deadlock; stale locks self-recover.
7. **Diff-based stale-chunk pruning.** When a file shrinks, old chunks come out of the index instead of lingering and polluting search.

For users on a previous version, see [`UPGRADING.md`](UPGRADING.md) for the migration path.

## About

I'm a solo founder running an early-stage company end to end through Claude Code. This toolkit is what makes that practical. I built it for me. I use it every day. Putting it on GitHub because someone else with the same setup probably wants the same fixes.

If you find it useful, a star helps others discover it. ⭐

## License

MIT. See [`LICENSE`](LICENSE).

The bundled MCP servers carry their own licenses (each `mcp-servers/*/LICENSE` where present - `multi-gmail` is MIT). Everything else here is MIT.
