# Changelog

All notable changes to this toolkit are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project loosely follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2026-05-13] - obra/superpowers cherry-picks (debugging rubric + plan test + knowledge sub-collections)

### Added
- **`memory_templates/feedback_systematic_debugging.md`** - operating rule. 4-phase debugging rubric (Reproduce / Isolate / Diagnose / Fix) with hard gates: no fix before isolation, no phase-3 skip, stop at 30 minutes without isolation. Adapted from obra/superpowers `skills/systematic-debugging` (Jesse Vincent, MIT).
- **`memory_templates/feedback_junior_engineer_plan_test.md`** - operating rule. "A plan is good only when an enthusiastic junior engineer could execute it cold, without coming back with questions." Applies to Worker briefs, implementation plans, decision notes, PR descriptions, and briefing action items. Adapted from obra/superpowers `skills/writing-plans` (Jesse Vincent, MIT).
- **`memory_templates/world_knowledge/_PROTOCOL.md`** - schema for a new ChromaDB knowledge sub-collection covering general facts not tied to a specific project (VAT rates, regulatory limits, industry conventions). Cherry-picked from obra/private-journal-mcp (related repo, MIT).
- **`memory_templates/user_context/_PROTOCOL.md`** - schema for a new ChromaDB knowledge sub-collection covering the user's preferences, working style, and recurring patterns. Distinct from `feedback_*.md` (those are prescriptive rules Claude MUST follow; user_context is descriptive observations to inform planning). Cherry-picked from obra/private-journal-mcp (related repo, MIT).
- **`install.sh` Step 6.2** - bootstraps `~/Desktop/claude/memory/world_knowledge/` and `~/Desktop/claude/memory/user_context/` on install. `_PROTOCOL.md` is smart-merged every run so the schema can evolve across upgrades. No seed notes are bootstrapped - the user creates entries as facts arise.

### Changed
- **`tools/note.py`** - two new subcommands: `note.py world_knowledge "Title" "Body"` and `note.py user_context "Title" "Body"`. Same upsert-by-slug semantics as learning/decision/research; same `--body-file` / `--body-stdin` / `--tags` / `--project` flags; same ChromaDB single-file reindex hook. New directories: `WORLD_KNOWLEDGE_DIR` and `USER_CONTEXT_DIR` constants added to `TYPE_DIRS`.
- **`tools/memory_search.py`** - knowledge collection extended. `_knowledge_meta_for` now derives `subtype: world_knowledge` and `subtype: user_context` from path. `index_knowledge` indexes both new directories alongside learnings + decisions. `_detect_collection_for` routes single-file upserts in the new directories to the knowledge collection. The `wake-up` summary surfaces the latest 2 notes from each of the 4 knowledge sub-collections (decision / learning / world / user). Module docstring updated to describe the 4-way knowledge collection contents.
- **`THIRD_PARTY_ATTRIBUTIONS.md`** - new section "obra/superpowers (Jesse Vincent)" with source URL, MIT license verification, and a 3-row import table covering all three cherry-picks in this release.
- **`README.md`** - feedback-rule count bumped from 19 to 21. New one-line mention of the world_knowledge + user_context knowledge sub-collections in the "What's in it" list, alongside the existing `note.py` bullet.

### Privacy invariants (new in this release)
- `memory/user_context/` may contain personal information about the operator (sleep schedule, health constraints, family rhythms). Treat the directory as local-only: never include in public exports of dotfiles or configuration. If you fork this toolkit, scrub any inherited examples and start your own from scratch.
- `memory/world_knowledge/` is intended to be portable across operators (regulations, industry facts, tool defaults) but may pick up project-specific context if the operator drifts. Keep an eye on what lands there during regular memory audits.

### Notes
- The new subcommands are additive: existing `note.py learning|decision|research|friction` flows are unchanged. Existing pupsik installs upgrade safely via `install.sh --update-only`.
- No new ChromaDB collection is created. world_knowledge and user_context share the existing `knowledge` collection (along with learnings + decisions); the `subtype` metadata field discriminates.

## [2026-05-11] - Architect proposals backlog

### Added
- **`memory_templates/architect_proposals/_PROTOCOL.md`** - schema + lifecycle for a local backlog of structural / workflow / tool proposals against your workspace. Proposals live in `~/Desktop/claude/memory/architect_proposals/latest.md` under five sections (Open / Accepted / Applied / Rejected / Obsolete). Each proposal is a YAML block with `id`, `source`, `effort`, `status`, `rationale`, `why_relevant`, optional `attribution`. ID convention `arch-YYYY-MM-DD-NNN`. 90-day re-propose suppression on rejected. `source: original`.
- **`memory_templates/architect_proposals/latest.md`** - empty bootstrap backlog with the five section headings. Installed once on first run; never overwritten (the user's accumulated backlog is preserved across `install.sh --update-only` runs).
- **`memory_templates/feedback_architect_auto_apply.md`** - operating rule. Architect Lens proposals that are SMALL same-turn fixes (file rename, typo, missing pointer, stale fact) apply immediately with a checker pass. Excludes destructive ops, external posts, large structural changes, and conflicts with MANDATORY rules. `source: original`.
- **`memory_templates/feedback_architect_proposals_backlog.md`** - operating rule. Every Architect-Lens output, ad-hoc architectural insight, and nightly reflection/research finding gets persisted to the backlog. Co-exists with the auto-apply rule: small things go in as `status: applied`, large structural things go in as `status: open` for explicit approval. Privacy invariant: backlog is local-only, never included in any public export. `source: original`.
- **`install.sh` Step 6.1** - bootstraps `~/Desktop/claude/memory/architect_proposals/` on install. `_PROTOCOL.md` is smart-merged every run (schema can evolve); `latest.md` is created once and never overwritten. Adds `archive/` subdirectory for monthly snapshots.

### Changed
- **`templates/critical-rules.md.template`** - new "System self-improvement" section adds one-line pointers to the auto-apply rule and the backlog rule.
- **`templates/morning_briefing_skill.md.template`** - new input #7 reads the backlog's `## Open` section for top-3 proposals to surface in the Architect lens. New "Architect proposals - write step" section requires persisting every Architect insight to the backlog before exiting (small auto-applied ones with `status: applied`, larger ones with `status: open`). New rule in the "what NOT to do" list: don't re-surface proposals already in `Rejected` unless 90 days have passed.

### Privacy invariants (new in this release)
- The architect proposals backlog (`memory/architect_proposals/latest.md` and its archive) is LOCAL ONLY. Never include in any public export of your dotfiles or workspace. Briefings reformulate proposals into their own voice; never quote raw backlog text in a brief.
- External-research findings that go into the backlog reference public URLs; those URLs are public so they can be shown. Your specific workstreams are private; do not echo workstream context to external surfaces.

### Notes
- The dream-v2 / nightly reflection skill is NOT shipped in this repo. The backlog pattern works standalone (morning briefing + ad-hoc session writes are enough to make it useful). If you wire a custom nightly reflection skill, the `_PROTOCOL.md` "Promotion rules" section documents how it should read the backlog and how to filter external-research candidates against your own workstreams. A reference implementation lives in the maintainer's private system but ships separately when generalised.

## [2026-05-08] - Contact enrichment Pass 4 (correspondence scan + TG manual-paste flag)

### Added
- **`tools/flag_russian_speakers.py`** - multi-signal heuristic to flag contacts likely to chat with the operator on Telegram. 5 signals: Cyrillic in name, Latin transliteration of a Russian first name (~120 names covered), Russian surname suffix (`-ov` / `-ova` / `-ev` / `-eva` / `-in` / `-ina` / `-sky` / `-skaya` / `-enko` / `-uk` and variants), Russian-domain email pattern, and an opt-in company match via `$RUSSIAN_CONTEXT_COMPANIES` env var (comma-separated substrings; leave unset to disable signal 5). Idempotent (only flips 0 -> 1, never clobbers a manual override). Sets the new `tg_manual_paste_recommended` column. `source: original`, NOT a gbrain import.
- **Pass 4 of the contact enrichment task** - email + WhatsApp correspondence scan synthesizing a 2-4 sentence private `relationship_context` summary per contact. Email read via `gmail_search_all` (re-uses Pass 1 thread set). WhatsApp read via `mcp__whatsapp__whatsapp_search` + `whatsapp_messages_with` for contacts with `phone` populated. Telegram is NEVER auto-read - blocked by the upstream `feedback_telegram_manual.md` rule. Flagged contacts (`tg_manual_paste_recommended = 1`) are surfaced in the run summary as "TG manual-paste candidates" so the operator can paste TG history into a one-off prompt for any specific row. COALESCE-guarded so the synthesis is preserved across runs (manual refresh path: `UPDATE contacts SET relationship_context = NULL WHERE id = ?` then re-run for that row).
- **Step 0.5 of the cron template** - runs `flag_russian_speakers.py --apply` before pulling enrichment candidates so newly-added contacts get auto-flagged.

### Changed
- **`tools/enrichment_schema_migrate.py`** - now adds 12 columns instead of 10. New columns: `relationship_context TEXT` (Pass 4's private summary, never exported) and `tg_manual_paste_recommended INTEGER DEFAULT 0` (Russian-speaker heuristic flag). Re-runs are safe and only add the missing 2 columns on existing pupsik installs.
- **`templates/scheduled-tasks/contact-enrichment-weekly.md.template`** - reframed from 3-pass to 4-pass. Adds Step 0.5 (heuristic refresh), Step 4.5 (Pass 4 correspondence scan + relationship_context synthesis), expanded what-NOT-to-do list (no auto-Telegram, no exporting `relationship_context`), updated SELECT/UPDATE SQL with new columns, expanded run-summary frontmatter with `new_relationship_context` and `tg_manual_paste_pending` counters.
- **`memory_templates/feedback_contact_enrichment_weekly.md`** - operating rule updated for 4-pass + Russian-speaker heuristic. Adds explicit privacy invariants for `relationship_context` (never leaves local DB).

### Privacy invariants (new in this release)
- `relationship_context` content NEVER appears outside the local `contacts.db`. Not in run summaries, not in archive files, not in briefings (briefings reformulate via `memory_search.py` but never quote), not in Telegram notifications, not in any pupsik public template.
- Telegram is NEVER auto-read by any tool in this repo. The `tg_manual_paste_recommended` flag is the only mechanism for surfacing TG-active contacts; the operator pastes manually if they want a Pass-4 refresh that includes TG context.

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
