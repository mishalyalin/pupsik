# Changelog

All notable changes to this toolkit are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project loosely follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2026-04-29] — Phase 2

### Added
- **9-collection ChromaDB indexer** — `tools/memory_search.py` indexes 9 collections
  (briefings, outputs, journal, knowledge, research, contacts, interactions,
  memory_files, chat_archives). The `knowledge` collection combines
  `memory/learnings/` and `memory/decisions/` into one searchable index.
- **`tools/note.py`** — moment-of-emergence knowledge capture. One command captures
  a learning, decision, or research note. Upserts by title — re-capturing the same
  topic refreshes the existing note instead of duplicating it.
- **`feedback_capture_knowledge.md`** — new mandatory rule that tells Claude to call
  `note.py` the moment an insight surfaces, not when the topic closes.
- **Surgical single-file reindex** — `memory_search.py index --file <path>` reindexes
  one file in roughly 50ms instead of rebuilding the whole index.
- **Concurrency-safe lockfile with stale TTL** — parallel reindex calls no longer
  deadlock; stale locks self-recover.
- **Diff-based stale-chunk pruning** — when a file shrinks, old chunks are removed
  from the index instead of lingering.

### Changed
- **Idempotent reindex** — `coll.upsert` everywhere. Re-running
  `memory_search.py index` is safe and cheap; no duplicates, no stale entries.

## [Unreleased — previous release]

### Added
- **`auto` permission mode** — recommended default. `auto` accepts safe ops and
  prompts on writes / shell / risky calls. Replaces `bypassPermissions` as the
  recommendation. `bypassPermissions` is still a valid choice; this toolkit no
  longer recommends it as the default.
- **`templates/critical-rules.md.template`** — installed to
  `~/.claude/rules/critical-rules.md`. Claude Code auto-loads this directory at
  session start, so the MANDATORY rules ride along on every session.
- **4 new generic feedback rules** in `memory_templates/`:
  - `feedback_never_ignore_own_rules.md` — rules in `CLAUDE.md` and `feedback_*.md`
    are MANDATORY, not suggestions.
  - `feedback_verify_project_state.md` — verify status from fresh data before
    answering project / payment / partner questions.
  - `feedback_compute_weekday_dont_guess.md` — compute weekday from ISO date
    programmatically, don't reuse last brief's labels.
  - `feedback_short_dashes_only.md` — when drafting in the user's voice, use "-"
    not "—".

### Changed
- **MCP servers re-shipped scrubbed** — `multi-gmail`, `multi-gcal`, and
  `whatsapp` source no longer carry any owner-specific comments or labels.

## [Unreleased — initial release]

### Added
- **Contact graph DB** — `tools/contacts_db.py`, SQLite-backed CRUD over
  contacts, companies, interactions, links. Graph traversal (`graph`, `chain`)
  and staleness detection (`stale 7`).
- **Semantic memory search** — `tools/memory_search.py` indexes markdown
  directories and the contact DB into a local ChromaDB.
- **Multi-account MCP servers** — `multi-gmail`, `multi-gcal` (read multiple
  Google accounts in one call), `whatsapp` (read-only macOS WhatsApp).
- **Auto-compact hooks** — `pre-compact.sh` saves session state before a
  context compact; `post-compact.sh` reminds Claude to restore it on the next turn.
- **2-agent rule** — `feedback_always_two_agents.md` and a `CLAUDE.md` section
  enforce a worker + independent checker for every real task.
- **5 agent role prompts** — Architect, Discoverer, Packager, Migrator, Tester
  in `agents/`.
- **Initial feedback rules** in `memory_templates/`:
  contact-DB-first, save-outputs, verify-before-showing, default-workspace,
  use-local-MCP, deploy-immediately, all-accounts-always.
