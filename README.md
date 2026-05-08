# Pupsik

> The Claude Code workspace that doesn't lose context between sessions.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Built for: Claude Code](https://img.shields.io/badge/Built_for-Claude_Code-blueviolet)](https://claude.com/claude-code)
[![Status: Stable](https://img.shields.io/badge/Status-Stable-green)](#)
[![Auto-update: enabled](https://img.shields.io/badge/Auto--update-enabled-blue)](#staying-up-to-date)
[![Privacy-checked: CI](https://img.shields.io/badge/Privacy--checked-CI-green)](.github/workflows/privacy-check.yml)

> "I run my entire business through Claude Code. Pupsik is the workspace I
> built so it doesn't lose context between sessions."

Pupsik is a drop-in toolkit that turns Claude Code into a stateful
collaborator: persistent contact graph, semantic memory search across 9
ChromaDB collections, multi-account Gmail / Calendar / WhatsApp via local
MCP servers, mandatory rule discipline pinned to every session, auto-compact
hooks that survive context compression, and a 2-agent worker-plus-checker
workflow.

Most people use Claude Code for code. If you're using it for everything else
too — sales, ops, finance, customer success, scheduling — this is the missing
layer. MIT licensed, macOS-friendly, runs entirely local.

## Quick Start

```bash
git clone https://github.com/mishalyalin/pupsik.git
cd pupsik
bash install.sh             # base setup: dirs, Python deps, CLAUDE.md, hooks, memory
bash install_mcps.sh        # builds multi-gmail, multi-gcal, whatsapp
bash register_mcps.sh       # registers the three MCPs with Claude Code
```

Then open a fresh Claude Code session in `$HOME/Desktop/claude/` (or wherever
you pointed the installer) and ask:

```
> What's your 2-agent rule?
```

If Claude paraphrases it back, the install worked. If it says "what rule?",
the `CLAUDE.md` isn't loading — see Troubleshooting below.

## Features

- **Persistent contact graph DB** (SQLite) — people, companies, interactions,
  links. Graph traversal, intro chains, staleness detection, all in pure
  Python stdlib.
- **Semantic memory search** (ChromaDB, 9 collections) — index your markdown
  notes, briefings, journal entries, decisions, learnings, research, plus the
  contact DB. One command searches across all of it.
- **Moment-of-emergence knowledge capture** (`note.py`) — capture a learning,
  decision, or research note the instant an insight surfaces. Upserts by
  title; one note per topic, kept current.
- **Multi-account Gmail + Calendar MCPs** — never get asked "which account"
  again. `gmail_search_all` and `gcal_list_all_events` cover all linked
  accounts in a single call.
- **WhatsApp chat reader MCP** (macOS only, read-only) — search, list, sync
  business contacts to the contact DB.
- **Optional contact-enrichment cron** (template) - 3-pass signature/web/bio
  enrichment via `gmail_search_all` + WebSearch, idempotent via `COALESCE`,
  privacy-guarded (skips personal/tenancy/events + distribution lists). Use
  `tools/enrichment_schema_migrate.py` to add the 10 enrichment columns to
  your `contacts.db`, then install the template at
  `templates/scheduled-tasks/contact-enrichment-weekly.md.template`.
- **Auto-compact hooks + 50% threshold** - `PreCompact` saves session state,
  `PostCompact` reminds Claude to restore it, and `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE=50`
  fires compaction at half-context instead of waiting until 95%. No more
  losing the plot mid-session.
- **`tools/doctor.py` health-check + safe auto-fix** - deterministic
  diagnostics across 13 checks (broken symlinks, stale locks, ChromaDB
  orphan rows, oversized CLAUDE.md / MEMORY.md, dangling memory pointers,
  dead scheduled-task dirs, unindexed recent notes). `check` is read-only,
  `fix-safe` applies safe repairs only (never LLM content rewrites - cron-safe),
  `orphans` lists unlinked entities for human review.
- **Friction protocol** - `note.py friction --severity {blocker|error|confused|nit} --phase X --message Y`
  captures repeat-correction patterns. Upsert by `(phase, severity)` increments
  a counter so the third recurrence of the same friction surfaces escalated.
  `friction summary --days 7 --top 3` aggregates for morning briefing.
- **2+ agent rule** — every real task runs a worker plus an independent
  checker. Catches the bugs a single-agent pass would miss.
- **Critical-rules file** — `~/.claude/rules/critical-rules.md` auto-loads
  every session. MANDATORY behaviour rules pinned to every project.
- **15 generic feedback rules** — contact-DB-first, save-outputs,
  verify-before-showing, never-ignore-own-rules, capture-knowledge,
  short-dashes-only, no-office-files, compute-weekday-don't-guess, and more.
- **Third-party attribution discipline** - `THIRD_PARTY_ATTRIBUTIONS.md` at
  the repo root tracks every pattern adapted from external OSS projects
  (currently: gbrain by Garry Tan, MIT). Source URL + author + license +
  adaptation type + honest delta of what was taken verbatim vs adapted vs
  added. License compatibility verified at import time.
- **5 pre-written agent prompts** — Architect / Discoverer / Packager /
  Migrator / Tester. Use them when the task warrants a team.
- **`auto` permission mode by default** — accepts safe ops automatically,
  prompts on writes / shell / risky calls.

## Documentation

- [`HOW_IT_WORKS.md`](HOW_IT_WORKS.md) — how the system works, conceptually:
  memory layers, tools, rules, the 2-agent discipline, compact hooks, an
  end-to-end example. **Start here** to understand what you're installing.
- [`UPGRADING.md`](UPGRADING.md) — for users on a previous version of this
  toolkit. What's preserved, what gets replaced, the one-time migration steps,
  rollback.
- [`MODULAR.md`](MODULAR.md) — for users with their own Claude Code setup who
  want individual components. Each piece, its dependencies, a 3-line install
  snippet, and mix-and-match recipes.
- [`CONTRIBUTING.md`](CONTRIBUTING.md) — how to file issues, how to PR,
  privacy guarantee.
- [`THIRD_PARTY_ATTRIBUTIONS.md`](THIRD_PARTY_ATTRIBUTIONS.md) — patterns,
  code, conventions adapted from external OSS projects. Source URL, author,
  license, adaptation type, and what was changed vs taken verbatim.
- [`CHANGELOG.md`](CHANGELOG.md) — release notes.

## Requirements

- **Node.js 18+** — for the MCP servers (`brew install node` on macOS).
- **Python 3.10+** — for the tools (`brew install python` on macOS).
- **Claude Code CLI** — `claude` command on PATH.
  See [claude.com/claude-code](https://claude.com/claude-code).
- **`pip install chromadb`** — the installer handles this.

Optional:

- **WhatsApp for Mac** — only if you want the WhatsApp MCP.

## How it works (one paragraph)

You install a workspace at `$HOME/Desktop/claude/` (configurable). Inside it
sit a `CLAUDE.md` Claude reads first every session, a `memory/` of long-form
markdown notes, a SQLite contact graph, a ChromaDB index, three MCP servers,
and a rules file pinned to every session. Claude reads the rules, reads
`CLAUDE.md`, runs a 200-token `wake-up` query, and is ready to go. When a
real task comes in, it spawns a Worker plus a Checker. When an insight
surfaces, it captures the note immediately. When the conversation gets long
enough to compact, the hooks save and restore session state. For the full
walk-through, see [`HOW_IT_WORKS.md`](HOW_IT_WORKS.md).

## Installation — guided path

If you'd rather have Claude do the install for you with review at each step:

1. Open a fresh Claude Code conversation in any directory.
2. Copy the contents of `SETUP_PROMPT.md` into the chat.
3. Claude spawns a team of 5 agents (architect, discoverer, packager,
   migrator, tester) and installs step-by-step, showing diffs and asking for
   approval.

## Staying up to date

Pupsik ships an in-repo updater. From inside your clone:

```bash
bash tools/update.sh
```

What it does:

1. `git fetch` from `origin/main`. If you're already up to date, exits silently.
2. Shows the new commits and the file-level diff before touching anything.
3. Refuses to update if you have uncommitted local edits (pass `--force` to
   stash + update + restore).
4. Fast-forward only — never rewrites your local commits.
5. Re-runs `bash install.sh --update-only` to apply new tools, hooks,
   templates, and rule files.

### What `update.sh` updates

- `tools/{contacts_db,memory_search,note}.py` (smart-merge — see below)
- `~/.claude/rules/critical-rules.md` (append-only smart merge — see below)
- `~/Desktop/claude/.claude/hooks/{pre,post}-compact.sh` (smart-merge)
- `memory_templates/feedback_*.md` (smart-merge in your project memory dir)

### What `update.sh` never touches

- Your `CLAUDE.md`
- Your `data/contacts.db`
- `memory/learnings/`, `memory/decisions/`, `memory/journal/`,
  `memory/people/`, `memory/projects/`
- `briefings/`, `outputs/`, `research/`
- Any feedback rule you've personalised in your project memory dir

In short: **all your data is safe**. Only the tooling layer is replaced.

### What happens if I customized files

`update.sh` is conservative — it never silently overwrites your edits.

For each managed file (tools, hooks, feedback rules):

- If the file is **identical to the upstream version** → nothing happens.
- If you **haven't modified it** since the previous install → it's safely
  updated to the new version (your old copy is backed up as
  `<file>.bak.<timestamp>`).
- If you **have modified it** → the new upstream version is installed
  side-by-side as `<file>.new`. Your version stays untouched. You diff
  and merge manually:

  ```bash
  diff ~/Desktop/claude/tools/memory_search.py{,.new}
  # ...resolve, then either rm the .new file or replace the original
  ```

After an update, `update.sh` prints a summary line listing every `.new`
file awaiting your attention.

Detection works by comparing the installed file against the latest
`<file>.bak.<timestamp>` from the previous install. If they match, you
haven't touched it; if they differ (or no `.bak` exists), the file is
treated as user-modified.

`~/.claude/rules/critical-rules.md` is special: it is **never replaced**.
New rule references in the upstream template are appended at the bottom
of your file under a `## Updates from upstream <date>` header. Existing
content is left alone, including any rules you've added yourself.

### Optional: weekly auto-update via cron

Add to `crontab -e`:

```
# Pull latest pupsik every Monday at 09:00 local time. Adjust path to wherever you cloned.
0 9 * * 1 cd ~/pupsik && bash tools/update.sh >> ~/pupsik/.update.log 2>&1
```

### Privacy-checked at the source

Every push to `mishalyalin/pupsik` runs the
[Privacy Check workflow](.github/workflows/privacy-check.yml) — a
multi-pattern grep that fails the build if any privacy-sensitive content
lands in the public diff (real names, emails, phone numbers, government
IDs, project codenames, API tokens, oversize blobs). The script lives at
[`.github/scripts/privacy-check.sh`](.github/scripts/privacy-check.sh) and
runs locally too.

If you fork and self-host, the same workflow runs on your fork.

## After installation

### 1. Personalize `CLAUDE.md`

The template at `$HOME/Desktop/claude/CLAUDE.md` has `{{PLACEHOLDERS}}` —
fill in your name, role, active projects. This is the file Claude reads
first every session.

### 2. Populate the contact DB

```bash
python3 ~/Desktop/claude/tools/contacts_db.py init
python3 ~/Desktop/claude/tools/contacts_db.py add "Alice Smith" \
  --email alice@example.com --company "Acme Corp" --category "work"
```

Or import from WhatsApp after the MCP is set up:

```
Ask Claude: "Run whatsapp_sync_to_contacts_db"
```

### 3. Add your Google accounts

Follow `docs/GOOGLE_CLOUD_SETUP.md` — about 15 minutes, done once.

### 4. Test the 2-agent rule

Give Claude a real task (not a one-shot lookup) and watch for it spawning
multiple agents. See `docs/AGENT_TEAM_RULE.md`.

## Troubleshooting

- **`claude` command not found** — install Claude Code CLI from
  [claude.com/claude-code](https://claude.com/claude-code).
- **MCP servers fail to build** — check `node --version` (need 18+). Run
  `npm install` in each `mcp-servers/*/` dir manually to see the error.
- **WhatsApp MCP returns "permission denied"** — grant Full Disk Access to
  your terminal. See `docs/WHATSAPP_SETUP.md` Step 2.
- **Gmail auth fails with "access blocked"** — you didn't add yourself as a
  test user in the Google Cloud consent screen. See `docs/GOOGLE_CLOUD_SETUP.md`
  Step 3.7.
- **Compact hooks don't trigger** — check `~/.claude/settings.json` is valid
  JSON and paths are absolute. See `docs/COMPACT_SETUP.md`.
- **Claude doesn't mention the 2-agent rule** — verify
  `~/Desktop/claude/CLAUDE.md` contains the rule section, and
  `memory/feedback_always_two_agents.md` is in the project memory directory.

## Uninstall

```bash
rm -rf ~/Desktop/claude/.claude/hooks ~/Desktop/claude/mcp-servers
rm ~/Desktop/claude/tools/contacts_db.py ~/Desktop/claude/tools/memory_search.py
claude mcp remove multi-gmail
claude mcp remove multi-gcal
claude mcp remove whatsapp
# Optionally:
rm ~/Desktop/claude/CLAUDE.md ~/Desktop/claude/data/contacts.db
```

The Google Cloud project, OAuth credentials, and installed npm packages
aren't touched — remove those manually if you want a clean slate.

## Contributing

PRs are welcome. The bar: changes should make sense to a fresh user who has
never met any of the contributors. Personal data — real names, real emails,
real account numbers — never lands in this repo. See
[`CONTRIBUTING.md`](CONTRIBUTING.md) for the full rules.

## Releases

For full release notes, see [`CHANGELOG.md`](CHANGELOG.md).

### What's new in this release (2026-05-07: gbrain pattern imports + privacy)

1. **`tools/doctor.py` - deterministic health-check + safe-auto-fix.**
   Three subcommands: `check` (read-only), `fix-safe` (safe auto-repairs),
   `orphans` (read-only orphan listing). Thirteen specific checks across
   broken symlinks, stale lock files, ChromaDB orphan rows, dangling memory
   pointers, dead scheduled-task directories, and oversized CLAUDE.md /
   MEMORY.md. Auto-fix is restricted to safe ops only - never LLM content
   rewrites - so the tool is cron-safe and won't clobber your prose.
2. **`note.py friction` subcommand.** Capture severity-tagged friction events
   (`blocker` / `error` / `confused` / `nit`) with phase + message + optional
   hint. Upsert by `(phase, severity)` increments a counter for repeat-pattern
   detection. `friction summary --days 7 --top 3` aggregates the loudest
   recurring friction for embedding in morning briefings.
3. **Output Rules adapted from gbrain.** Four cross-cutting quality rules
   (Deterministic Links, No Slop, Exact Phrasing Preservation, Title Quality)
   referenced in `THIRD_PARTY_ATTRIBUTIONS.md`. The consolidated public
   feedback file is on the follow-up backlog; for now they live in the
   attribution tracker as a reading guide.
4. **`THIRD_PARTY_ATTRIBUTIONS.md` at repo root.** New central tracker for
   patterns adapted from external OSS projects. Per-pattern source URL,
   author, license, adaptation type, and an honest delta of what was taken
   verbatim vs adapted vs added on top.
5. **Privacy hardening.** Five `memory_templates/feedback_*.md` files
   re-generalised after the privacy-pattern catalogue tightened over the
   previous weeks. The previously-missing `feedback_no_office.md` was
   added in pre-scrubbed form. `bash .github/scripts/privacy-check.sh
   --include-untracked` now passes 10/10 across the full repo.
6. **Em-dash style consistency.** The toolkit ships `feedback_short_dashes_only.md`
   as a MANDATORY rule. Mass sed-pass cleaned 90 em-dashes lurking in template
   prose and tooling docstrings, including in the rule files themselves.

For full detail and the upgrade pointer, see
[`CHANGELOG.md`](CHANGELOG.md#2026-05-07---gbrain-pattern-imports--privacy-fix).

### What's new in the previous release (2026-04-29)

1. **9-collection ChromaDB indexer** — `tools/memory_search.py` now indexes 9
   collections (briefings, outputs, journal, knowledge, research added on top
   of the existing contacts, interactions, memory_files, chat_archives). The
   `knowledge` collection combines `memory/learnings/` and `memory/decisions/`
   into one searchable index. Run `memory_search.py stats` to see them all.
2. **`tools/note.py` — moment-of-emergence knowledge capture.** One command
   captures a learning, decision, or research note. Upserts by title —
   re-capturing the same topic refreshes the existing note instead of
   creating a duplicate. One note per topic, kept current.
3. **New mandatory rule: `feedback_capture_knowledge.md`.** Tells Claude to
   call `note.py` the moment an insight surfaces, not when the topic closes.
   Loaded automatically alongside the other critical rules.
4. **Idempotent reindex.** `coll.upsert` everywhere. Re-running
   `memory_search.py index` is safe and cheap — no duplicates, no stale
   entries piling up.
5. **Surgical single-file reindex** — `memory_search.py index --file <path>`
   reindexes one file in roughly 50ms instead of doing a full rebuild on
   every capture. `note.py` uses this automatically after each save.
6. **Concurrency-safe lockfile with stale TTL.** Parallel reindex calls no
   longer deadlock; if a stale lock is detected, it self-recovers.
7. **Diff-based stale-chunk pruning.** When a file shrinks, old chunks get
   removed from the index instead of lingering and polluting search results.

For users on a previous version of this toolkit, see
[`UPGRADING.md`](UPGRADING.md) for the one-time migration path.

### What's new since the last release

1. **`auto` permission mode is the recommended default** (replaces
   `bypassPermissions`). `auto` auto-accepts safe ops and prompts on writes /
   shell / risky calls — safer than full bypass without losing flow.
   `bypassPermissions` is still a valid choice; this toolkit no longer
   recommends it as the default.
2. **`critical-rules.md` template added** —
   `templates/critical-rules.md.template` is installed to
   `~/.claude/rules/critical-rules.md`. Claude Code auto-loads files from
   `~/.claude/rules/` at session start, so the MANDATORY rules ride along on
   every session, project or otherwise.
3. **4 new generic feedback rules** bundled in `memory_templates/`:
   - `feedback_never_ignore_own_rules.md` — rules in `CLAUDE.md` and
     `feedback_*.md` are MANDATORY, not suggestions.
   - `feedback_verify_project_state.md` — verify status from fresh data
     before answering project / payment / partner questions.
   - `feedback_compute_weekday_dont_guess.md` — compute weekday from ISO
     date programmatically, don't reuse last brief's labels.
   - `feedback_short_dashes_only.md` — when drafting in the user's voice,
     use `-` not `—`.
4. **MCP servers re-shipped scrubbed** — the bundled `multi-gmail`,
   `multi-gcal`, `whatsapp` source no longer carries any owner-specific
   comments or labels.

Earlier additions still here:

- **Auto-compact hooks** — `PreCompact` saves session state to disk;
  `PostCompact` reminds Claude to restore it.
- **Always-2-agents rule** — `memory/feedback_always_two_agents.md` plus a
  `CLAUDE.md` section.
- **Bug fixes in `contacts_db.py`** — `db.commit()` on SQL,
  `sqlite3.Row.get()` replaced, no more hardcoded project name leaking
  into HTML.
- **Portable paths** — `memory_search.py` paths are derived from `$HOME`.
  Compact hooks honour `CLAUDE_WORKSPACE` env var for non-default install
  locations.

## About

Built and used in production by [Misha Lyalin](https://github.com/mishalyalin),
a solo founder running an early-stage company end-to-end through Claude Code.
This toolkit is what made that practical.

If you're a solo operator getting leverage from Claude Code, this is for you.
Fork it, take what you need, send PRs back.

If you find this useful, a star helps others discover it. ⭐

## License

MIT. See [`LICENSE`](LICENSE) for the full text.

The bundled MCP servers carry their own licenses (each `mcp-servers/*/LICENSE`
where present — `multi-gmail` is MIT). Everything else in this toolkit is
MIT.
