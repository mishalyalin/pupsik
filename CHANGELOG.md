# Changelog

All notable changes to this toolkit are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project loosely follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2026-05-20.2] - Brand OS API-first: one canonical canon copy on a server, everyone hits the same URL

### Changed
- **`tools/brand_os.py`** - upgraded from local-CLI-only to **API-first / local-CLI fallback**. New detection chain:
  1. API mode - env vars `BRAND_OS_API_URL` + `BRAND_OS_API_USER` + `BRAND_OS_API_PASS`, OR a credentials file at `$BRAND_OS_CREDENTIALS_FILE` (default `~/.brand-os-credentials`, mode 600) with the same three keys as shell-style `key=value` lines.
  2. Local CLI mode - existing `BRAND_OS_PATH` env > `~/.brand-os` symlink > auto-detect convention.
  3. Otherwise: not configured (rules fall back to inline canon, helper is silent + safe).

  When the API is configured, `invoke <subcommand>` hits the matching `/api/*` JSON endpoint on the Brand OS server. The full subcommand surface maps to HTTP routes: `stats`, `icp`, `search`, `explain`, `tactic`, `for-vector`, `for-stage`, `canon`, `list-tactics`, `list-stages`. On network failure / 5xx the helper auto-falls-back to the local CLI if detected and emits a `[brand_os] api unreachable` stderr hint. On HTTP 4xx the server's JSON error is surfaced verbatim (no fallback - the request itself was bad).

  Stdlib only: `urllib.request` + `base64` for Basic Auth + `json` for parsing. SSL trust store is auto-fixed for macOS Python.org installs via opportunistic `certifi` import (graceful fallback to default context if `certifi` is not installed).

### Added
- **`.brand-os-credentials.example`** - documented template for the credentials file. Copy to `~/.brand-os-credentials` and `chmod 600` to enable API mode. Never commit your real credentials file - the pupsik `.gitignore` covers the common locations.
- **`.gitignore`** - new entries for `.brand-os-credentials*` and `brand-os-credentials*` so accidental drops in either the home dir or the repo dir stay out of git.
- **`memory_templates/feedback_marketing_panel_default.md`** + **`memory_templates/feedback_email_nstd.md`** - both templates updated to document the new API > local CLI > inline-fallback detection chain. Step 1 workflow + dispatch lines updated.
- **`README.md`** - Brand OS bullet rewritten to explain the three postures (API / local CLI / not configured) and link to the reference implementation's full `/api/*` route list.

### Why
A Brand OS that lives only as a local clone tends to drift: different team members have different `git pull` cadences, contractors never have it at all, and "did you pull the latest cocktails?" becomes a recurring question. The API-first mode hands every collaborator and every Claude session one URL. Server-side canon is the single source of truth; clients are stateless.

The local-CLI mode stays as the fallback for offline use, for forks who do not want to host a server, and for resilience when the API is briefly unreachable.

### Privacy invariants (new in this release)
- `~/.brand-os-credentials` is gitignored and the example file ships with placeholder values only. Privacy-check would catch a real password leak.
- The helper sends credentials only via the `Authorization: Basic` header to the host configured in the credentials file or env var. No third-party telemetry. No URL logging unless you call `status` or pass `-v`.
- The `stats` and `is-configured` commands DO NOT print the password or auth header. `status` shows only the URL.
- The `_ssl_context()` helper uses `certifi.where()` only when `certifi` is already importable (no pip install triggered by the helper itself).

### Notes
- Migrate without code change: drop a `~/.brand-os-credentials` file with your three keys and re-run `python3 tools/brand_os.py status` to confirm API mode. Existing local-CLI users who do not create the credentials file keep working unchanged.
- `rebuild-index` remains a server-side admin op. The helper falls back to local CLI for that subcommand if a local clone is present, otherwise prints a clear message pointing at SSH.

## [2026-05-20.1] - Brand OS opt-in: customer-comms rules pull canon from your own brand repo

### Added
- **`tools/brand_os.py`** - integration helper for an opt-in **Brand OS** - a versioned repo holding your brand voice, positioning canon, persuasion tactics, anti-patterns, evidence library, and templates - PLUS a Python CLI for structured retrieval over the canon. Reference implementation: [github.com/mishalyalin/pranasalt-brand-os](https://github.com/mishalyalin/pranasalt-brand-os). The helper detects a Brand OS via three discovery paths (env var `BRAND_OS_PATH` > `~/.brand-os` symlink > auto-detect under `~/Desktop/claude/projects/*-brand-os`) and exposes a thin pass-through CLI: `status` / `is-configured` / `invoke <subcommand> ...`. If no Brand OS is configured, the helper exits cleanly and the customer-comms rules fall back to their inline canon - so the toolkit works the same as before.

### Changed
- **`memory_templates/feedback_marketing_panel_default.md`** - rewritten with a 5-step workflow. **Step 1**: probe for a Brand OS via `tools/brand_os.py is-configured`. **Step 2**: if configured, dispatch the multi-lens panel ON TOP of the brain's output (each lens reads brain canon, then adds specialist contribution); if not configured, dispatch the panel directly using the inline frameworks (Ariely BE / Voss NSTD / Cialdini-Sutherland) as before. **Steps 3-5**: verify, recommend, await approval, implement. The Brand OS output is the canonical source for any conflict; the inline canon is the fallback for capabilities the Brand OS does not yet cover, never the override.
- **`memory_templates/feedback_email_nstd.md`** (new file in pupsik) - the outbound-email NSTD rule with the same opt-in pattern. **Step 0**: verify the email is actually needed (highest-priority gate - silent waits and standing-process-running checks block needless drafts). **Step 1**: pull tactic stack from the Brand OS if configured. **Step 2**: two-version output (clean + annotated). **Step 3**: inline 21-tactic canon fallback if no Brand OS. **Steps 4-5**: channel escalation rules + reply analysis. Mirrors the Brand-OS-first pattern from the marketing panel.

### Why
A Brand OS is shareable. You can give your designer, your social-media marketer, your community manager, your copywriter, and any future Claude session a single GitHub URL and they immediately have the same brand tone, the same banned words, the same positioning anchors, the same persuasion-cocktail recipes. No more "wait, are we allowed to say 'wellness' on Instagram?" living in six different freelancers' heads. One place. One commit history. One traceable answer per question. Pull Requests for proposed changes. Append-only evidence log.

The pupsik toolkit supports two postures:
- **No Brand OS**: hard-wired inline canon (Ariely BE + Voss NSTD + Cialdini-Sutherland cross-brand) as the default. Customer comms still work, the rules still fire, you just lose the shared-canon benefit.
- **Brand OS configured**: opt-in retrieval via env var + `tools/brand_os.py`. The brain's output supersedes the inline canon for any conflict. The inline canon stays as the fallback for capabilities the Brand OS does not yet cover.

### Privacy invariants (new in this release)
- `tools/brand_os.py` reads only the local filesystem (env var, symlink, conventional path under `~/Desktop/claude/projects/`). No network calls.
- The helper invokes only the Brand OS's own CLI (whichever of `tools/marketing_brain.py`, `tools/brand_brain.py`, `tools/brand_cli.py`, or `brain.py` it finds first). It does not exec arbitrary paths.
- Detection failure mode is silent + safe: returns "not configured" and the rules fall back to inline canon. No leaking of probed paths to stderr unless you call `status`.

### Notes
- The Brand OS repo itself is **your own** (your GitHub, your domain canon). The pupsik helper is just the bridge. You can wire any retrieval CLI you like as long as it lives at one of the four candidate paths inside the Brand OS root.
- Existing users on 2026-05-19.2 keep working unchanged - the new rules default to inline canon when no Brand OS is detected.
- Pick the new behaviour up via `bash tools/update.sh` (smart-merge) or copy `tools/brand_os.py` manually.

## [2026-05-19.2] - Morning dashboard module (markdown-in, HTML-out, six tabs)

### Added
- **`dashboard/build.py`** - renderer for a single-page HTML dashboard pulling from existing workspace artifacts. Six numbered sections - Today (briefing) / Projects (CLAUDE.md ## Active Projects, as a 3-column grid of cards with checkboxes) / Upcoming (## Upcoming, same layout) / Pulse (curated industry narrative from `dashboard/pulse-deep.md` or briefing `## Pulse` section) / Architect (`memory/architect_proposals/latest.md`) / Knowledge (last 7 days of decisions + learnings). Python stdlib only - no pip install, no server.
- **`dashboard/styles.css`** - visual layer. Cream `#faf8f3` background, charcoal text, numbered chips, 1080px max-width, monospace for commands, no emojis. Aesthetic adapted from [impeccable.style](https://impeccable.style/) (vocabulary only - no assets copied).
- **`dashboard/favicon.svg`** - red rounded square with cream "P" mark. 215 bytes. Customise colour by editing the `fill` attribute.
- **`dashboard/NOTICE.md`** + **`dashboard/README.md`** - attribution + user-facing docs covering env-var configuration (PULSE_HEADERS / STATUS_KEYWORDS), checkbox persistence, optional VPS deploy for Telegram-bookmark access.
- **`scripts/morning-dashboard.sh`** - one-shot launcher: rebuilds against current artifacts, optionally rsyncs to a VPS (if `DASHBOARD_VPS_HOST` + `DASHBOARD_VPS_PATH` env vars set), then opens in default browser.
- **`install.sh`** Step 3.5 - copies dashboard files into the workspace and optionally creates a `dash` shortcut at `~/.local/bin/dash` if that directory is on PATH.

### Highlights
- **Six-tab pattern** adapted from [ilyyyyyyya/suma-starter](https://github.com/ilyyyyyyya/suma-starter) (clean-room reimplementation - source repo carries no LICENSE at time of adaptation).
- **Cards with persistent checkboxes**. State stored in `localStorage`, keyed by stable SHA256 of section + title. Checking a card moves it to a collapsed "closed" zone at the bottom of the section; state survives across reloads AND across days. Cards only resurface if the title changes in `CLAUDE.md` (which yields a new hash). Export button downloads `dashboard-closed.json` for your morning-briefing skill to ingest.
- **Pulse layered fallback**. `dashboard/pulse-deep.md` takes priority if present (point a research agent at it). Falls back to the briefing's `## Pulse` section, then to the most recent briefing with a Pulse section, then to an empty-state message.
- **Hardened markdown rendering**. Inline links restricted to `http(s)://`, `mailto:`, `#`, or absolute paths via `safe_href()` allowlist - blocks `javascript:` and `data:` URL schemes that could land in user-generated decisions/learnings.
- **Emoji stripping**. Honours the impeccable.style "no emojis" aesthetic across cards, headings, and Pulse content. Coverage tested against 5 Unicode blocks (symbols, transport, regional flags, enclosed alphanumerics, variation selectors).
- **Status keywords** highlighted inline as monospace pills (DELIVERED / OVERDUE / PAID / ACTIVE / BLOCKED / PENDING / MISSED / ESCALATED / SHIPPED / LOCKED / CONFIRMED / RESOLVED / REJECTED). Override the list via `DASHBOARD_STATUS_KEYWORDS` env var.

### Privacy invariants (new in this release)
- Dashboard reads only local workspace files (CLAUDE.md, briefings/, memory/). No network calls in `build.py`.
- VPS sync is opt-in via env vars only. No VPS hostname is baked into shipped code.
- Checkbox state is local-first (`localStorage`). The export-to-JSON path is manual - nothing leaves the browser unless you click the button.

### Notes
- The dashboard is a sibling of `tools/` - put it in your workspace and run `bash scripts/morning-dashboard.sh` (or `dash` if the shortcut landed). Re-running `install.sh` smart-merges the new files into existing workspaces.

## [2026-05-19] - PRIMARY rule (verify-don't-imagine) + rules.py retrieval tool + 4 new feedback rules

### Added
- **`tools/rules.py`** - retrieval tool that returns the FULL content of feedback rules matching a topic. Merges an optional alias manifest with semantic search via `memory_search.py`. Subcommands: `search "<topic>" [--top N]`, `list`, `read "<name>"`. The point: when the agent is about to do something the rules cover (outbound email, status answer, brand documentation), it can pull the relevant rules in full instead of relying on the one-line pointers in `critical-rules.md`. The alias manifest is optional - the tool gracefully falls back to pure semantic search if no manifest is present. Auto-detects your project memory directory under `~/.claude/projects/<slug>/memory/` (override in the file if your layout differs).
- **`memory_templates/feedback_never_imagine_always_verify.md`** - THE PRIMARY rule. Every number, date, price, fact, name, or claim in any output must be verified against a real source (file / email / chat / DB / WebFetch) BEFORE stating. 8 operational sub-cases: numbers, project state, public facts, brand patterns, links, people, private intel, dates. Cross-references every other verify-* rule. Promoted to the FIRST bullet in `templates/critical-rules.md.template` with a visual separator.
- **`memory_templates/feedback_check_model_first.md`** - HARD GATE for any outbound containing numerical claims. Pre-send checklist (read latest model output / cite source for every number / state assumptions explicitly / never silently estimate). Generalises from financial-model context to any quantitative claim about your business.
- **`memory_templates/feedback_verify_dont_imagine_external_brand.md`** - When documenting external brand patterns (competitor pricing, copy, funnel) for use in your own work, claims must be backed by direct WebFetch evidence, screenshots, or explicit `[INFERRED]` marker. Both what the brand SHOWS and what it deliberately HIDES are data.
- **`memory_templates/feedback_marketing_panel_default.md`** - For any customer-facing copy work, dispatch a 3-lens panel (Behavioral Economics + Voss negotiations + cross-brand DTC mechanics) BEFORE proposing. Verify, recommend, await user approval, implement. Departure from `feedback_architect_auto_apply.md` because customer-facing copy is reputation-irreversible.
- **`memory_templates/feedback_no_jargon.md`** - Banned consultancy vocab list (tie-breaker, parity, peak priority, swing factor, north star, low-hanging fruit, deep-dive, alignment, stakeholder, deliverable, action item, bandwidth, sunset, deprecate, etc). Plain language only. Format conditionals as flat "if X - A, if Y - B" instead of "tie-breaker / decision tree / swing factor".

### Changed
- **`templates/critical-rules.md.template`** - new FIRST bullet under MANDATORY protocols: "NEVER IMAGINE, ALWAYS VERIFY" + a horizontal-rule separator. Visual signal that this rule sits above the rest. Includes a pointer to `rules.py search` as the canonical way to load full verify-* rule content into the session before non-trivial outbound.

### Privacy invariants (new in this release)
- `rules.py` reads only from local rule directories and (optionally) a local alias manifest. No network calls.
- The optional alias manifest is NOT shipped (a manifest tends to bake in real names and project codes). Create your own at `~/Desktop/claude/data/rules-aliases.json` with format `{"feedback_<name>": ["alias1", "alias2"]}`. The tool works fine without it.

### Notes
- The new rules are additive. Existing flows continue to work.
- `rules.py` depends only on `memory_search.py` (already in the toolkit). No new pip packages.
- The 5 new feedback templates can be picked up via `bash tools/update.sh` (smart-merge) or copied manually into `~/.claude/projects/<your-slug>/memory/`.

## [2026-05-14] - Date-aware session anchor + connection-aware memory graph

### Added
- **`tools/now.py`** - single source of truth for current datetime. Auto-detects IANA timezone from `/etc/localtime` symlink on macOS/Linux. 4 output modes (default / `--short` / `--json` / `--anchor`) + `--tz <IANA>` override. Latency ~35ms. Used by SessionStart hook to inject a hard time anchor that prevents Claude from pattern-matching dates from stale conversation context.
- **`tools/note_graph.py`** - connection-aware memory graph layer. Builds entity-mention edges across all your `memory/`, `outputs/`, `briefings/`, `research/` notes. 7 subcommands: `backfill` / `extract` / `related` / `entity` / `graph` / `clusters` / `export-wikilinks`. Uses Louvain modularity + TF-ICF labels to surface 5-10 tight thematic clusters from your last 7 days of notes.
- **`tools/note_graph_schema.py`** - idempotent migration script that adds 4 SQL tables to your existing `contacts.db`: `entities`, `notes`, `note_entity_edges`, `note_note_edges`. Existing contacts/companies/interactions are untouched.
- **`hooks/session-start-reminder.sh`** - NEW SessionStart hook. Injects `⏰ NOW: YYYY-MM-DD (Weekday), HH:MM TZ. Local zone: <IANA> - You are in <city>` anchor at the top of every session's context. Also includes the existing CLAUDE.md staleness check + critical-rules pointer.
- **`memory_templates/feedback_know_current_datetime.md`** - operating rule. NEVER hard-code timezone or location. NEVER treat the actual current date as future. Trust the SessionStart anchor over any date pattern-matched from prior context. Re-run `now.py --short` before any date reference if there's doubt.
- **`VERSION`** - new file at repo root. Single-line semver-ish identifier (`YYYY-MM-DD.N`). Used by `update.sh` to detect upgrades and surface CHANGELOG deltas.

### Changed
- **`tools/update.sh`** - now detects when you upgrade across releases and prints a formatted summary of CHANGELOG entries between your old version and the new one. Adds a `--quiet` flag for headless/CI use.
- **`tools/note.py`** - new fire-and-forget hook: every `note.py learning|decision|research|world_knowledge|user_context|friction` invocation now auto-indexes the new note into the graph via `note_graph.py extract` in the background. Sub-1-second latency, never blocks the foreground write.
- **`tools/memory_search.py`** - `wake_up` summary now includes an "Active clusters (last 7d)" block. Pulls top 5-10 thematic clusters from `note_graph.py clusters` with timeout-protected subprocess call.
- **`install.sh`** - records current VERSION to `~/.pupsik-state/last-applied-version` on first install, so subsequent `update.sh` runs only surface CHANGELOG entries for NEW releases.
- **`templates/critical-rules.md.template`** - new first MANDATORY-protocols bullet: "Know current datetime + location" pointing at the new feedback rule.

### Privacy invariants (new in this release)
- `~/.pupsik-state/last-applied-version` is a local-only file. Never commit to any repo.
- The graph layer (`note_graph_schema.py`) adds tables to your existing `contacts.db` but does NOT introduce any new data outside what your notes already contain. Entity extraction is regex-based on note bodies, no external API calls.

### Notes
- The new tools are additive. Existing `note.py learning|...` flows are unchanged.
- The graph layer needs `networkx` (pip install networkx). The schema migration is idempotent (re-running is safe).
- The SessionStart hook is OPT-IN: you wire it into your `~/.claude/settings.json` hooks list yourself. See `install.sh` output for the JSON snippet to add.

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
