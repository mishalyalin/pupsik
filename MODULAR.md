# Modular install - pick individual components

## When to use this doc

You already have your own Claude Code setup. You like it. You don't want a full pupsik install but you want to grab one or two pieces - say, just the contact DB, or just the rules, or just the multi-account Gmail MCP.

Each component below has: what it does, what files it is, what it depends on, what it doesn't, and a 3-line install snippet. Pick what you want, paste, done.

## Components

### a) Critical rules

- **What it does:** A one-line index of MANDATORY behaviour rules, plus the full text of each rule. Claude Code auto-loads files from `~/.claude/rules/` at session start, so the rules are pinned to every session.
- **Files:** `templates/critical-rules.md.template` + `memory_templates/feedback_*.md` (the full text per rule).
- **Depends on:** Nothing. Pure markdown.
- **Doesn't depend on:** No Python, no MCP, no SQLite, no ChromaDB. It works on any Claude Code install.
- **Install:**

  ```bash
  mkdir -p ~/.claude/rules ~/.claude/projects/$(basename "$PWD")/memory
  cp pupsik/templates/critical-rules.md.template ~/.claude/rules/critical-rules.md
  cp pupsik/memory_templates/feedback_*.md ~/.claude/projects/$(basename "$PWD")/memory/
  ```

### b) Knowledge capture

- **What it does:** `note.py` captures a learning, decision, or research note the moment an insight surfaces. Upserts by title, so the same topic stays one note that gets refreshed instead of duplicating.
- **Files:** `tools/note.py` + `memory_templates/feedback_capture_knowledge.md` (the rule that reminds Claude to use it).
- **Depends on:** `tools/memory_search.py` for the surgical single-file reindex. Soft dependency - `note.py` writes the markdown file fine without it; you just don't get auto-reindex.
- **Doesn't depend on:** Contact DB, MCP servers, hooks. Standalone otherwise.
- **Install:**

  ```bash
  mkdir -p ~/Desktop/claude/tools ~/Desktop/claude/memory/{learnings,decisions,research}
  cp pupsik/tools/note.py ~/Desktop/claude/tools/ && chmod +x ~/Desktop/claude/tools/note.py
  cp pupsik/memory_templates/feedback_capture_knowledge.md ~/.claude/projects/$(basename "$PWD")/memory/
  ```

### c) Contact DB

- **What it does:** SQLite database of people, companies, interactions, and the relationships between them. CRUD via `contacts_db.py`. Graph traversal (`graph`, `chain`), staleness detection (`stale 7`).
- **Files:** `tools/contacts_db.py` + `data/contacts.db` (initialized via `contacts_db.py init`).
- **Depends on:** Python ≥ 3.10. Pure stdlib `sqlite3` - no extra packages.
- **Doesn't depend on:** ChromaDB, MCP servers, rules. Fully standalone.
- **Install:**

  ```bash
  mkdir -p ~/Desktop/claude/{tools,data}
  cp pupsik/tools/contacts_db.py ~/Desktop/claude/tools/ && chmod +x ~/Desktop/claude/tools/contacts_db.py
  python3 ~/Desktop/claude/tools/contacts_db.py init
  ```

### d) Semantic search

- **What it does:** Indexes any markdown directories you point it at, plus the contact DB if present, into a local ChromaDB. 9 collections: contacts, interactions, memory_files, chat_archives, briefings, outputs, journal, knowledge, research. The `knowledge` collection combines `memory/learnings/` and `memory/decisions/`. Search across them with `memory_search.py search "..."`.
- **Files:** `tools/memory_search.py` + the `chromadb` Python package.
- **Depends on:** `pip install chromadb`. Soft-coupled to `contacts_db.py` - 2 of the 9 collections (contacts, interactions) come from the SQLite DB; the other 7 work without it.
- **Doesn't depend on:** MCP servers, hooks, rules. Standalone except for `chromadb` and the optional contact-DB coupling.
- **Install:**

  ```bash
  pip install chromadb
  cp pupsik/tools/memory_search.py ~/Desktop/claude/tools/ && chmod +x ~/Desktop/claude/tools/memory_search.py
  python3 ~/Desktop/claude/tools/memory_search.py index
  ```

### e) Compact hooks

- **What it does:** `pre-compact.sh` saves session state (active TODOs, last user message, key files modified, decisions) to disk before Claude's context gets compressed. `post-compact.sh` reminds Claude to restore that state on the next turn. Net effect: you don't lose the plot at compact boundaries.
- **Files:** `hooks/pre-compact.sh`, `hooks/post-compact.sh`. Plain shell scripts.
- **Depends on:** Nothing. Bash and standard Unix tools.
- **Doesn't depend on:** Python tools, MCP, SQLite, ChromaDB.
- **Install:**

  ```bash
  mkdir -p ~/Desktop/claude/.claude/hooks
  cp pupsik/hooks/{pre-compact,post-compact}.sh ~/Desktop/claude/.claude/hooks/
  chmod +x ~/Desktop/claude/.claude/hooks/*.sh
  # then register them in ~/.claude/settings.json (see hooks/README in the package for the JSON snippet)
  ```

### f) MCP servers

- **What it does:** Three local MCP servers - `multi-gmail` (Gmail across multiple accounts), `multi-gcal` (Calendar across multiple accounts), `whatsapp` (read-only Mac WhatsApp). Each is independent: pick one, two, or all three.
- **Files:** `mcp-servers/multi-gmail/`, `mcp-servers/multi-gcal/`, `mcp-servers/whatsapp/`. Each has its own source and prebuilt `dist/`.
- **Depends on:** Node ≥ 18 for build. Each server has its own OAuth setup (Gmail and Calendar share a Google Cloud project; WhatsApp needs Full Disk Access on Mac).
- **Doesn't depend on:** Each other. They're three independent npm packages. They also don't depend on Python tools, contact DB, ChromaDB, hooks, or rules.
- **Install (Gmail only as an example):**

  ```bash
  cd pupsik/mcp-servers/multi-gmail && npm install && npm run build
  claude mcp add multi-gmail node $(pwd)/dist/index.js
  # then follow docs/GOOGLE_CLOUD_SETUP.md once for OAuth
  ```

  Substitute `multi-gcal` or `whatsapp` for the same flow with the other two.

### g) Health diagnostics + friction capture

- **What it does:** Two complementary modules for keeping the system healthy. `tools/doctor.py` runs 13 deterministic checks across the workspace (broken symlinks, stale locks, ChromaDB orphan rows, file-size limits, dead scheduled-task dirs, unindexed recent notes). `check` is read-only; `fix-safe` applies safe repairs only (never LLM content rewrites - cron-safe); `orphans` lists unlinked entities for human review. `note.py friction --severity {blocker|error|confused|nit} --phase X --message Y` captures repeat-correction patterns. Upsert by `(phase, severity)` increments a counter so a third recurrence of the same friction surfaces escalated in the morning briefing.
- **Files:** `tools/doctor.py` (13 checks), `tools/note.py` (the `friction` subcommand sits inside the existing capture tool from module b).
- **Depends on:** `tools/contacts_db.py` (module c) for the contacts checks; `tools/memory_search.py` (module d) for the ChromaDB orphan check; `note.py` (module b) for friction capture.
- **Doesn't depend on:** Hooks, MCP servers, contact-enrichment cron.
- **Install:**

  ```bash
  cp pupsik/tools/doctor.py ~/Desktop/claude/tools/
  chmod +x ~/Desktop/claude/tools/doctor.py
  python3 ~/Desktop/claude/tools/doctor.py check
  ```

  `note.py friction` is wired the moment module b is installed - no extra step.

- **Provenance:** `doctor.py` and the friction protocol are both adapted from gbrain by Garry Tan (MIT, 2026-05-07). See `THIRD_PARTY_ATTRIBUTIONS.md` for full attribution. Both adapted patterns are SAFE-ops only - no LLM content rewrites in the doctor (intentional), counter-only state in the friction tool (no automated escalation actions).

### h) Rule retrieval on demand

- **What it does:** `tools/rules.py search "<topic>"` returns the FULL content of feedback rules that match the query, so the agent can pull the actual verification protocol before non-trivial outbound work - not just the one-line pointer in `critical-rules.md`. Three subcommands: `search "<topic>" [--top N]` for semantic search, `read "<name>"` for a single rule by name (no `feedback_` prefix needed - e.g. `rules.py read short_dashes_only`), `list` for a directory dump. Merges an optional alias manifest (you create your own, the tool ships without one) with semantic search via `memory_search.py`. Falls back gracefully if no manifest is present. No network calls.
- **Files:** `tools/rules.py`.
- **Depends on:** `tools/memory_search.py` (module d) for the semantic search backend. If you don't have semantic search installed, `read` and `list` still work; only `search` needs it.
- **Doesn't depend on:** Contact DB, MCP servers, hooks, scheduled tasks. The rule files themselves come from module a (Critical rules); if you have your own `feedback_*.md` files in any project memory directory, `rules.py` indexes and retrieves them too.
- **Useful even standalone:** if you already have feedback-style rule files anywhere on disk and just want a "give me the relevant rule full text by topic" shortcut, this script is useful on its own. Point it at your rule directory in the file's top section if your layout isn't the default.
- **Install:**

  ```bash
  cp pupsik/tools/rules.py ~/Desktop/claude/tools/ && chmod +x ~/Desktop/claude/tools/rules.py
  # Sanity check:
  python3 ~/Desktop/claude/tools/rules.py list
  python3 ~/Desktop/claude/tools/rules.py search "outbound email"
  ```

  Optional: create an alias manifest at `~/Desktop/claude/data/rules-aliases.json` with the format `{"feedback_<name>": ["alias1", "alias2"]}` if you want explicit keyword routing on top of semantic search. The tool works fine without one.

- **Privacy invariants:** Reads only from local rule directories and (optionally) a local alias manifest. No network calls. The alias manifest is NOT shipped in this repo (manifests tend to bake in real names and project codes - keep yours local).

### i) Contact enrichment cron (4-pass)

- **What it does:** Optional weekly cron task (Sunday 06:00 local) that tops up your `contacts.db` with publicly available bio/social data (Passes 1-3) AND a private `relationship_context` summary distilled from your own email + WhatsApp correspondence with each contact (Pass 4). Pass 1 mines email signatures via `gmail_search_all`. Pass 2 runs targeted WebSearch for missing LinkedIn URLs. Pass 3 fetches a short bio + Instagram handle for PR-active contacts. Pass 4 reads the email threads from Pass 1 + the WhatsApp chat history (when phone is populated) and synthesizes a 2-4 sentence summary of the channel state, last topic, and outstanding asks. All updates use `COALESCE(existing, new)` so existing values are preserved. Privacy-guarded: skips `category IN ('personal','tenancy','events')` + distribution-list email patterns. Telegram is NEVER auto-read - if you want TG context for a contact, paste the history into an ad-hoc prompt manually.
- **Files:** `templates/scheduled-tasks/contact-enrichment-weekly.md.template` (the cron SKILL prompt), `memory_templates/feedback_contact_enrichment_weekly.md` (the operating rule), `tools/enrichment_schema_migrate.py` (idempotent migration adding the 11 enrichment columns).
- **Depends on:** `tools/contacts_db.py` (module c) for the DB. The `multi-gmail` MCP from module f for Pass 1+4 email scans. The `whatsapp` MCP from module f for Pass 4 WhatsApp scans (skipped per-row if no phone). `tools/memory_search.py` (module d) for the post-run reindex.
- **Doesn't depend on:** Hooks, capture tool (module b), Critical rules (module a) - the cron is opt-in and self-contained.
- **Install:**

  ```bash
  # 1. Copy + executable
  cp pupsik/tools/enrichment_schema_migrate.py ~/Desktop/claude/tools/
  chmod +x ~/Desktop/claude/tools/enrichment_schema_migrate.py

  # 2. Migrate schema (idempotent - adds 11 columns or reports already-present)
  python3 ~/Desktop/claude/tools/enrichment_schema_migrate.py

  # 3. Install the cron template
  mkdir -p ~/.claude/scheduled-tasks/contact-enrichment-weekly
  cp pupsik/templates/scheduled-tasks/contact-enrichment-weekly.md.template \
     ~/.claude/scheduled-tasks/contact-enrichment-weekly/SKILL.md

  # 4. Install the operating rule (in module b's flow if you have it; else manually)
  cp pupsik/memory_templates/feedback_contact_enrichment_weekly.md \
     ~/.claude/projects/<your-project-slug>/memory/

  # 5. Register the cron via Claude Code's scheduled-tasks MCP
  #    cron: "0 6 * * 0" (Sunday 06:00 local), enabled: true
  ```

- **Privacy invariants:** `relationship_context` content NEVER leaves your local `contacts.db`. Not in run summaries, not in archive files, not in briefings (briefings reformulate via `memory_search.py search`, never quote), not in Telegram notifications, not in any pupsik-public template. Telegram is NEVER auto-read; if needed, paste history into an ad-hoc prompt manually.

- **Provenance:** `source: original` (NOT a gbrain pattern). Cron architecture inherited from a sibling outbound-deadline poller (also original). See `templates/scheduled-tasks/contact-enrichment-weekly.md.template` Step 0 for the design history.

## Mix-and-match recipes

A few common combinations:

- **"Just the discipline"** - Critical rules (a) + Knowledge capture (b). Lightest possible install. No databases, no MCP. You get rule enforcement and `note.py`. Good for users who already have their own memory/search setup and just want the behavioural backbone.

- **"Just the brain"** - Contact DB (c) + Semantic search (d). No rules, no MCP, no hooks. Pure local data layer. Good for users who want to run searches and graph queries from their own scripts and let their existing Claude Code configuration handle rules.

- **"Just the inbox"** - MCP servers (f), one or all three. Zero local DB, zero rules. Good for users who want Gmail/Calendar/WhatsApp access in Claude Code and nothing else.

- **"Discipline + brain"** - (a) + (b) + (c) + (d). Everything except hooks and MCP servers. The minimal "Claude has memory and follows rules" setup, no third-party services.

## What to avoid mixing

- **Don't grab `note.py` without the capture-knowledge rule.** `note.py` is the tool; the rule is what reminds Claude to actually use it. Without the rule loaded into `~/.claude/projects/<slug>/memory/`, Claude won't reach for the tool when an insight surfaces, and the file just sits there. Always pair (b) - both pieces, not just the script.

- **Don't enable compact hooks (e) without configuring `~/.claude/settings.json`.** Copying the scripts to `.claude/hooks/` does nothing on its own - Claude Code only fires them if `settings.json` registers them. Either install both pieces or neither.

- **Don't install semantic search (d) without something for it to index.** It's not useless without (c), but it's noticeably less useful - half the value comes from the contact and interaction collections sourced from SQLite. If you skip (c), point `memory_search.py` at your own markdown directories instead, otherwise the index will be sparse.
