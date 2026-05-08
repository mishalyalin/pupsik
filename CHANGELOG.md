# Changelog

All notable changes to this toolkit are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project loosely follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2026-05-08] - Contact enrichment cron + dedup fix

### Added
- **`templates/scheduled-tasks/contact-enrichment-weekly.md.template`** - cron template for a weekly 3-pass contact enrichment task. Pass 1 mines email signatures via `gmail_search_all`. Pass 2 runs targeted WebSearch for missing LinkedIn URLs. Pass 3 fetches a short bio + Instagram handle for PR-active contacts. Idempotent via `COALESCE(existing, new)` on every UPDATE; never clobbers a non-NULL field. Privacy-guarded: skips `category IN ('personal','tenancy','events')` and any distribution-list email pattern (info@/support@/team@/...). Capped at 50 candidates per run, 90-day refresh window, weekly cadence (Sunday 06:00). Optional Telegram notification on substantial change. `source: original`, NOT a gbrain import.
- **`memory_templates/feedback_contact_enrichment_weekly.md`** - operating rule that documents when the task runs, the SQL filter, the 3-pass flow, hard privacy guards, three manual-trigger paths, and how morning briefings should pick up `latest.md`. Pairs with the cron template.
- **`tools/enrichment_schema_migrate.py`** - idempotent helper that adds the 10 enrichment columns (`linkedin`, `twitter`, `github`, `website`, `instagram`, `bio`, `enrichment_source`, `enrichment_date`, `enrichment_confidence`, `last_enriched`) to an existing `contacts.db`. Default DB path resolves via `$CLAUDE_WORKSPACE/data/contacts.db` -> `$HOME/Desktop/claude/data/contacts.db`, override via argv. Catches `OperationalError: duplicate column name` so re-runs are safe; verifies all 10 columns are present before exiting 0.

### Fixed
- **`tools/memory_search.py`** - dedup bug in the indexer where chunks could be re-emitted across reindex passes. Patch from a parallel-session worker; merged unchanged.

## [2026-05-07] - gbrain pattern imports + privacy fix

### Added
- **`tools/doctor.py`** - deterministic health-check + safe-auto-fix tool. 13 checks across two subcommands: `check` (read-only diagnostics) and `fix-safe` (safe auto-repairs only - no LLM content rewrites). Plus `orphans` for read-only orphan listing. Catches stale lock files, broken symlinks, ChromaDB orphan rows, dangling memory-file pointers, dead scheduled-task directories, oversized CLAUDE.md / MEMORY.md. Adapted from gbrain (Garry Tan, MIT) `gbrain doctor` / `gbrain orphans` / `gbrain repair-jsonb` command suite.
- **`note.py friction` subcommand** - capture friction events (anything confusing, missing, surprising, or wrong) with severity tagging (`blocker` / `error` / `confused` / `nit`). Upsert by `(phase, severity)` increments a counter for repeat-pattern detection. `note.py friction summary --days 7 --top 3` aggregates for briefing surfaces. Adapted from gbrain `skills/_friction-protocol.md`.
- **Output Rules** - 4 cross-cutting quality rules added (Deterministic Links, No Slop, Exact Phrasing Preservation, Title Quality), referenced alongside the 7 existing per-rule feedback files. Adapted from gbrain `skills/_output-rules.md`.
- **`memory_search.py`** - friction-files routing in `_memory_md_chunks` so `memory/friction/*.md` is correctly indexed in the existing memory-files ChromaDB collection.
- **`THIRD_PARTY_ATTRIBUTIONS.md`** - new at repo root. Central tracker for every pattern adapted from external OSS projects. Lists source URL, author, license, adaptation type, and what was changed. License compatibility verified at import time.

### Fixed
- **Privacy: pre-existing leaks scrubbed in 4 `memory_templates/feedback_*.md` files.** The privacy-check patterns in `private-patterns.env` tightened over recent weeks (Vendor-A, Vendor-B-equivalents, registry-id-equivalents, etc. added to `BUSINESSES_PRIVATE`). Older generalised templates from initial public release contained example references that the new patterns now flag. All four templates re-generalised in this update: `feedback_capture_knowledge.md`, `feedback_verify_project_state.md`, `feedback_always_two_agents.md`, `feedback_compute_weekday_dont_guess.md`. Privacy-check now passes 10/10 across the full repo.

### Notes
- The friction protocol and doctor patterns were independently checker-verified before this push (12/12 PASS for the live system shipping; this PR mirrors the public-safe portions).
- Outbound regulatory-deadline poller (a related pattern shipped to the maintainer's private system) was held back from this push pending generalisation - it currently references specific agency domains that need placeholder substitution before it can ship publicly.

## [2026-05-07] - Auto-compact threshold

### Added
- **`CLAUDE_AUTOCOMPACT_PCT_OVERRIDE` env var documented** - lowers Claude
  Code's auto-compact threshold from the default (~95% of context) to a
  user-tunable percentage. Recommended `50`. Recipe shipped in:
  - `install.sh` printed snippet now includes an `"env"` block
  - `docs/COMPACT_SETUP.md` rewritten - the previous "does not work" section
    was incorrect; the env var is supported by Claude Code and was
    independently verified against the installed binary
  - `HOW_IT_WORKS.md` and `README.md` mention the threshold

### Fixed
- **`docs/COMPACT_SETUP.md` misinformation** - the doc previously asserted
  Claude Code does NOT support a configurable compact threshold. It does.
  Section rewritten to teach the correct configuration.

## [2026-04-29] - Phase 2

### Added
- **9-collection ChromaDB indexer** - `tools/memory_search.py` indexes 9 collections
  (briefings, outputs, journal, knowledge, research, contacts, interactions,
  memory_files, chat_archives). The `knowledge` collection combines
  `memory/learnings/` and `memory/decisions/` into one searchable index.
- **`tools/note.py`** - moment-of-emergence knowledge capture. One command captures
  a learning, decision, or research note. Upserts by title - re-capturing the same
  topic refreshes the existing note instead of duplicating it.
- **`feedback_capture_knowledge.md`** - new mandatory rule that tells Claude to call
  `note.py` the moment an insight surfaces, not when the topic closes.
- **Surgical single-file reindex** - `memory_search.py index --file <path>` reindexes
  one file in roughly 50ms instead of rebuilding the whole index.
- **Concurrency-safe lockfile with stale TTL** - parallel reindex calls no longer
  deadlock; stale locks self-recover.
- **Diff-based stale-chunk pruning** - when a file shrinks, old chunks are removed
  from the index instead of lingering.

### Changed
- **Idempotent reindex** - `coll.upsert` everywhere. Re-running
  `memory_search.py index` is safe and cheap; no duplicates, no stale entries.

## [Unreleased - previous release]

### Added
- **`auto` permission mode** - recommended default. `auto` accepts safe ops and
  prompts on writes / shell / risky calls. Replaces `bypassPermissions` as the
  recommendation. `bypassPermissions` is still a valid choice; this toolkit no
  longer recommends it as the default.
- **`templates/critical-rules.md.template`** - installed to
  `~/.claude/rules/critical-rules.md`. Claude Code auto-loads this directory at
  session start, so the MANDATORY rules ride along on every session.
- **4 new generic feedback rules** in `memory_templates/`:
  - `feedback_never_ignore_own_rules.md` - rules in `CLAUDE.md` and `feedback_*.md`
    are MANDATORY, not suggestions.
  - `feedback_verify_project_state.md` - verify status from fresh data before
    answering project / payment / partner questions.
  - `feedback_compute_weekday_dont_guess.md` - compute weekday from ISO date
    programmatically, don't reuse last brief's labels.
  - `feedback_short_dashes_only.md` - when drafting in the user's voice, use "-"
    not "-".

### Changed
- **MCP servers re-shipped scrubbed** - `multi-gmail`, `multi-gcal`, and
  `whatsapp` source no longer carry any owner-specific comments or labels.

## [Unreleased - initial release]

### Added
- **Contact graph DB** - `tools/contacts_db.py`, SQLite-backed CRUD over
  contacts, companies, interactions, links. Graph traversal (`graph`, `chain`)
  and staleness detection (`stale 7`).
- **Semantic memory search** - `tools/memory_search.py` indexes markdown
  directories and the contact DB into a local ChromaDB.
- **Multi-account MCP servers** - `multi-gmail`, `multi-gcal` (read multiple
  Google accounts in one call), `whatsapp` (read-only macOS WhatsApp).
- **Auto-compact hooks** - `pre-compact.sh` saves session state before a
  context compact; `post-compact.sh` reminds Claude to restore it on the next turn.
- **2-agent rule** - `feedback_always_two_agents.md` and a `CLAUDE.md` section
  enforce a worker + independent checker for every real task.
- **5 agent role prompts** - Architect, Discoverer, Packager, Migrator, Tester
  in `agents/`.
- **Initial feedback rules** in `memory_templates/`:
  contact-DB-first, save-outputs, verify-before-showing, default-workspace,
  use-local-MCP, deploy-immediately, all-accounts-always.
