# Changelog

All notable changes to this toolkit are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project loosely follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2026-08-15] - CLAUDE.md rotation, a start-load budget guard for the generic hook, and a workspace/clone drift probe

`context_budget.py` (2026-08-12) measures the problem; this release adds the tools that act on the measurement, plus two smaller tool files reverse-synced from a workspace that had drifted ahead of this clone.

### Added

- **`tools/claude_md_trim.py`** - deterministic CLAUDE.md size check + rotation, no LLM calls.
  - `check` - token-counts the whole file AND every top-level `## `-heading section against soft/hard caps (default 12k/20k, override with `--soft`/`--hard`), flags any section that's individually over cap even when the file total looks fine. `--json` for scripting. Always exits 0 (read-only diagnostic, same convention as `doctor.py check`).
  - `rotate --changelog <path>` - moves the current `## Last Updated` section's body verbatim into a dated heading in a separate changelog file, and replaces it in CLAUDE.md with a one-line pointer. Idempotent: a no-op once the section is already <=2 lines. Dry-run by default, `--apply` to write, always prints exactly what moved.
  - Reuses `context_budget.py`'s token estimator instead of duplicating it; falls back to an inline copy of the same heuristic if `context_budget.py` isn't importable.
- **`hooks/session-start-reminder.sh`** - the generic template hook gained a start-load budget guard, adapted from the same logic `tools/context_budget.py`'s release notes describe. Shells out to `context_budget.py files --json` when that tool is installed at `$WORKSPACE/tools/context_budget.py`; falls back to an inline tiktoken-or-heuristic estimate of CLAUDE.md alone when it isn't, so the guard still works on a bare hook install. Two tiers: a hard-cap warning when CLAUDE.md alone is over 20k tokens, a softer combined-load warning when CLAUDE.md + rules + MEMORY.md together exceed 40k. All three caps are overridable via `CLAUDE_MD_SOFT_TOKENS` / `CLAUDE_MD_HARD_TOKENS` / `TOTAL_SOFT_TOKENS` env vars. This hook remains a manual, opt-in template (see its own header) - not force-resynced by `install.sh` or tracked by `update.sh`, since it requires per-install customization (workspace path, project slug) that an automatic overwrite would clobber.
- **`tools/check-pupsik-upstream.sh`** - per-tracked-file drift probe between a pupsik clone and the workspace it's installed into. Different question from `check-update.sh` (clone vs GitHub origin): this asks whether the clone and the workspace already agree file-by-file, and if not, which side has the newer edit - useful after hand-editing a tool locally. For each tracked file, reports "in sync" / "repo ahead" / "workspace ahead" / "diverged" (same mtime, direction unclear) / "clone-only" / "workspace-only", plus a diff-line count. `--json` for scripting. Read-only, no network, no git, always exits 0. Clone-side only, like `check-update.sh` - not installed into the workspace.

### Changed

- **`tools/doctor.py` / `tools/memory_search.py`** - reverse-synced from a workspace copy that had drifted ahead of this clone, with a couple of generic comment tweaks along the way. `doctor.py`'s `check_claude_md_size()` now measures **tokens** (soft ~12k WARN, hard ~20k FAIL) instead of lines, reusing `context_budget.py`'s estimator the same way `claude_md_trim.py` does, and the `orphan_unindexed_recent_notes()` check now reports when a ChromaDB collection itself is unreadable (previously silently skipped) instead of only reporting orphaned documents within a readable collection.
- **`install.sh` / `tools/update.sh`** - `claude_md_trim.py` added to the smart-merge list, so `update.sh` picks it up alongside the other tracked tools.

Sessions were dying with "Compacted conversation - saved 215k tokens" three times in a row followed by "your context window is full". The instinct is to raise the compaction threshold. That is the wrong lever, and this release ships the measurement that shows why.

**Root cause.** Auto-compaction fires against the model's **real context window**, not against any number in `settings.json`. So `autoCompactWindow` set above that window is inert - no error, no warning, no effect. Meanwhile the fixed session-start load (system prompt + tool schemas + every configured MCP server's instructions block + skills list + `CLAUDE.md` + rules + memory index) had grown until it was most of the window. Working room is `window - fixed load`; when that shrinks toward zero, every compact hands back a summary that immediately re-fills, which is exactly what the repeated-compact symptom looks like.

Measured on one mixed stack, over 1,100 compaction boundaries across ~270 transcripts: three current models clustered at a ~241k median pre-compact size, an older model sat at ~493k, a small model at ~99k - same machine, same settings file. Session-start load on the same stack had a median of ~181k against a ~241k trigger, i.e. ~60k of usable room before the first word was typed. Of that fixed load, ~93k tokens was one `CLAUDE.md` - trimming it to ~29k bought back a third of the working room.

### Added

- **`tools/context_budget.py`** - three deterministic measurements from your own transcripts, no conversation content read or printed.
  - `trigger` - the token count at which compaction actually fired, grouped by model, from `compactMetadata.preTokens` on each `{"type":"system","subtype":"compact_boundary"}` record. These are the agent's own counts, so they are exact. Read the median as your model's real usable window; a threshold above the max cannot bind.
  - `start` - what a session costs before you type, from the first assistant turn's `usage` (`input_tokens + cache_creation_input_tokens + cache_read_input_tokens`).
  - `files` - the slice of that load you can edit today: `CLAUDE.md`, `~/.claude/rules/*.md`, and the auto-memory `MEMORY.md` **belonging to this workspace only** (project dir name = the absolute workspace path with `/` replaced by `-`; summing every project's index would overstate the cost). Reports characters, lines, tokens and Cyrillic share per file. Exact via `tiktoken` when installed, otherwise a script-calibrated chars-per-token heuristic, and it says which method it used.
  - `all` runs the three in order. `--json` on any subcommand. `--dir` accepts a directory or a single `.jsonl`.
- **`tools/mcp_profile.py`** - `light` / `full` / `status`. Tool *schemas* already load on demand, but a configured MCP server's *instructions block* is injected unconditionally at session start and cannot be unloaded mid-session, so the only lever is what is configured when the session begins. `light` moves everything outside the daily set into `~/.claude/mcp-parked.json` and rewrites both the global (`~/.claude.json`) and workspace (`.claude/settings.json`) configs; `full` restores the parked entries verbatim. Daily set defaults to the four MCPs this toolkit installs, overridable with `--keep a,b` or `PUPSIK_MCP_DAILY`. Every write is backed up alongside the file first, non-MCP keys are preserved untouched, invalid JSON is skipped rather than rewritten, and a profile change applies on the next Claude start.

### Changed

- **`memory_templates/feedback_claudemd_size_discipline.md` now caps by tokens, not lines.** The old rule was soft 450 / hard 600 **lines** - and a real `CLAUDE.md` reached **244,364 characters (~93,000 tokens) in 301 lines**, so it sat at half the "hard cap" while being more than four times over any sane token budget, and the rule never fired once. Markdown bullets are unbounded in width; line count is not a proxy for size. New caps: soft ~12k tokens, hard ~20k, measured with `context_budget.py files`, with the note that Cyrillic/CJK cost ~1.7x more tokens per character. Added an explicit "trim by archiving, never by deleting" clause: compress to a pointer, move the full text verbatim into `memory/journal/`, then diff against a backup and confirm every future-dated item survived - a trim that drops a live invoice or deadline costs far more than the tokens it saved.
- **`docs/COMPACT_SETUP.md` leads with "First: measure, don't assume."** New section explaining trigger vs start vs files, that a threshold above the model's window is inert, and that the durable lever is the fixed load (memory files + MCP instruction blocks) rather than the threshold. The long-window (`[1m]`) caveat now says to verify the variant is actually offered in your own model picker before planning around it - a model string found in a binary or a changelog is not proof it can be selected.
- **`README.md`** - the auto-compact bullet no longer presents the threshold env var as a straightforward win; two new bullets cover the context budget and MCP profiles.
- **`install.sh` / `tools/update.sh`** - both new tools are smart-merged into `~/Desktop/claude/tools/` like the existing ten, so `update.sh` picks them up.

### Verification

- `trigger` / `start` / `files` each run clean against a real 1,846-transcript store; `trigger --dir /nonexistent` degrades to "0 across 0 transcripts" instead of raising. `files` against a workspace with no `CLAUDE.md` reports only the rules file rather than failing, and after the workspace-scoping fix it stopped pulling in four unrelated projects' `MEMORY.md` (49,045 tokens correctly, not 50,315).
- `mcp_profile.py` round-tripped in a sandboxed `HOME`: 3 global + 2 workspace servers → `light` parked 2 global + 1 workspace → `full` restored byte-identical server bodies, park file removed, and the non-MCP keys (`other`, `permissions`) survived both directions untouched.
- `bash -n install.sh tools/update.sh` and `python3 -m py_compile` on both new tools pass.

### Privacy

- No personal data added. Both tools read only counts, model names, timestamps and file sizes - never message content - and print no conversation text. `privacy-check.sh --include-untracked` clean.

## [2026-08-02.1] - follow-ups to the SIGSEGV fix: batch limit, vendored dirs, two lock/path bugs

Three things the drift fix left standing, all found by re-running the tooling against a real store rather than by reading the code.

### Fixed

- **`tools/memory_search.py` - upsert/delete are paged (`_safe_upsert` / `_safe_delete`, `CHROMA_BATCH = 4000`).** ChromaDB rejects a single call larger than its internal max batch (5,461 on the current rust bindings), so any collection that grew past that limit failed its rebuild outright - a plain `ValueError`, but at the end of a long index run. Applied at all seven call sites. `_safe_upsert` also asserts `documents`/`metadatas`/`ids` are the same length instead of letting a mismatch truncate silently.
- **`tools/memory_search.py` - vendored directories are no longer indexed.** `outputs/**/*.md` and `research/**/*.md` were `rglob`'d whole, so a single checked-in `node_modules` (or `.venv`, `site-packages`, `.next`, ...) poured generated markdown into the semantic index. It dilutes every search result and is one of the ways a collection reaches the batch limit above. `VENDOR_DIR_NAMES` matches on whole path components, so a real note called `my-node_modules-notes.md` is still indexed.
- **`tools/doctor.py` - `check_chroma_lock` no longer calls a live holder's lock stale.** It matched on `age > TTL` **or** dead pid, so a legitimate 20-minute reindex crossed the 10-minute TTL and got reported `FAIL` + `fixable: true` - inviting `fix-safe` to unlink the lockfile of a process that was still writing. Now a running pid is never stale, regardless of age; only a dead pid, or age when there is no pid to check. This is the same rule `check_stale_lockfiles` already used - the two had drifted apart.
- **`tools/doctor.py` - `PUPSIK_PRIVACY_CHECK` resolves the clone instead of hardcoding `~/pupsik`.** On a machine that also keeps the canonical clone under `~/code`, the check ran `privacy-check.sh` from whichever copy sat at the old path - here one six weeks behind main - and reported `PASS` on code nobody ships. Now: `PUPSIK_DIR` override, then `~/code/pupsik`, then the legacy path, falling back to the last candidate so the existing "not found" `SKIP` branch still fires. (Shipped in #37; recorded here.)

### Verification

- 14/14 on a positive+negative harness: 9,500 ids page into `[4000, 4000, 1500]` for both upsert and delete with the total preserved, and the same 9,500 through an unpaged call still raises - i.e. the bug being fixed is real, not hypothetical; mismatched list lengths raise `ValueError`; empty input is a no-op; `node_modules` / `.venv` paths are vendored while a real note and a substring-only filename are not; live pid + 5,000s-old lock -> `PASS`, dead pid + fresh lock -> `FAIL`, unparseable pid + old lock -> `FAIL` by age, no lock -> `PASS`.

### Privacy

- No personal data added. `privacy-check.sh --include-untracked` clean.

## [2026-08-02] - fix: ChromaDB HNSW drift crashed the memory index (SIGSEGV)

`memory_search.py index` and `memory_search.py search` could hard-crash the Python process with `EXC_BAD_ACCESS (SIGSEGV)` inside `chromadb_rust_bindings`. Not a hang, not a traceback - the interpreter dies, so `release_lock()` never runs and the next index is then blocked by the corpse's lockfile. It took ~3.5 months of daily reindexing for this to surface, so any long-running install is a candidate.

**Root cause.** A full reindex did `get_or_create_collection(...)` -> `coll.get()['ids']` -> `coll.delete(ids=...)` -> `upsert(...)`, i.e. it wiped the collection **in place** and rewrote it into the same HNSW segment. `delete()` removes rows from SQLite but never compacts the HNSW binaries (`data_level0.bin` / `length.bin`), so the index keeps referencing slots with no rows behind them. Each rebuild adds one whole generation of dead slots. The drift compounds silently until the rust loader reads past valid memory and the process dies.

Measured on a real store before the fix (`length.bin` size / 4 = slots, vs live rows in SQLite): `outputs` 8,523 rows / 39,098 slots (4.6x), `memory_files` 1,084 / 13,898 (12.8x), `knowledge` 2,319 / 10,607 (4.6x), `briefings` 1,424 / 4,272 (3.0x). The two that segfaulted were exactly the two worst; isolated per-collection in separate processes, 7 of 9 answered normally and those 2 exited 139, reproducibly - 20 crashes out of 20 attempts. Ratio alone is not the predictor (a 4.6x segment with 10.6k slots was still healthy), size matters too. Secondary damage on the same store: `briefings` reported `count() == 0` against 1,424 live rows, i.e. months of briefings were invisible to semantic search and nothing said so.

Upstream context: `chromadb >=1.5.4,<2` has an open macOS ARM64 segfault in the rust bindings ([chroma-core#6852](https://github.com/chroma-core/chroma/issues/6852)) and there is no known-good version to pin to. But the trigger here is **store state**, not the library version - which is why this is fixable from our side.

### Fixed

- **`tools/memory_search.py` - `_fresh_collection()`.** A full rebuild now does `delete_collection()` + `create_collection()`, which drops the segment directory and its binaries with it, instead of emptying the collection in place. Applied at all five full-rebuild sites (contacts, memory files, interactions, chat archives, and the generic `_index_md_dir` used by briefings / outputs / journal / knowledge / research). `index_single_file` - the surgical `index --file` path - deliberately keeps `get_or_create_collection`: it must upsert one file, never wipe the collection.
- **`tools/memory_search.py` - `acquire_lock()` checks whether the lock holder is still alive** (`os.kill(pid, 0)`). A SIGSEGV skips `release_lock()`, so the dead process's lockfile used to block the next index for the full `LOCK_STALE_AFTER_SEC` (10 min) window. A lock whose owner is gone is now overwritten immediately; a lock held by a live pid still refuses, exactly as before. Unknown/unreadable pid is treated as alive - the failure mode of freeing a lock on a guess is worse than waiting.

### Added

- **`tools/doctor.py` - `5b_chroma_drift` check.** Reports collections whose HNSW slot count far exceeds live rows (thresholds: `>=3x` **and** `>=5,000` slots - both, because ratio alone over-reports on small segments). It reads **only** `chroma.sqlite3` (read-only URI) and the segment files, with no `import chromadb` anywhere in it: a drifted store is precisely the store whose API calls segfault, so a check built on the API would die alongside the thing it is meant to diagnose. Note for anyone reading the query - embedding rows are keyed to the collection's **METADATA** segment, not the VECTOR one; joining on VECTOR returns zero rows and looks like a healthy store. Marked `fixable: false` on purpose: the cure is a full reindex (20+ min), never a silent auto-repair, and the summary line carries the exact command.
- Verified both directions before shipping: `FAIL` on the store that actually crashed (catches all 3 drifted segments), `PASS` on the rebuilt one.

### Changed

- **`README.md`, `MODULAR.md`, `UPGRADING.md`** - doctor check count 13 -> 14.

### If you are already running pupsik

The index is 100% derived from your markdown + `contacts.db`, so a rebuild costs time and nothing else. Check first, and only rebuild if it flags:

```bash
python3 ~/Desktop/claude/tools/doctor.py check          # look for 5b_chroma_drift
cd ~/Desktop/claude
mv data/chroma data/chroma.broken-$(date +%F)           # mv, never rm - keep the rollback
python3 tools/memory_search.py index
```

Keep the moved-aside store until the new one answers searches; delete it after. On the reference store the rebuild took under 20 min for 14,965 documents and shrank it from 460 MB to 192 MB.

### Verification

- Drift regression test, 1,500 documents through 5 consecutive full rebuilds, counting slots in `length.bin`: old pattern `[1500, 3000, 4500, 6000, 7500]` - exactly one dead generation per rebuild; `_fresh_collection` `[1500, 1500, 1500, 1500, 1500]` - flat. This also retro-explains the field numbers above (`outputs` carried ~4.6 generations, `memory_files` ~12.8).
- Lock semantics, in an isolated temp dir so no live lock was touched: dead holder + fresh timestamp -> acquires (the SIGSEGV case); live holder -> refuses; no pid recorded + fresh -> refuses (old age-based path intact); no pid + stale -> acquires. 4/4.
- Post-rebuild on the reference store: `search` 0 crashes in 20 runs (was 20/20), all 9 collections responding, `briefings` back from 0 to 1,424, `doctor.py check` 5b PASS.

### Privacy

- No personal data added. The check reads collection names and row counts only, and reports them in doctor output that stays local. `privacy-check.sh --include-untracked` clean.

## [2026-07-13.2] - pupsik baby logo — favicon + header logo mark

The dashboard now shows the pupsik baby (a friendly blue chip with a baby face) everywhere it shows identity: as the browser-tab **favicon** and as a small **logo mark** immediately left of the **pupsik** wordmark in the masthead. This supersedes the "favicon deliberately untouched" note from `2026-07-13.1` — the identity is now the baby, not the placeholder red "P".

### Changed

- **`dashboard/favicon.svg`** — replaced the placeholder red-"P" tile with the pupsik baby mark (rounded blue chip `#5BB8E8`, white face, dot eyes, pink cheeks, smile). This is the browser-tab / pinned-tab icon.
- **`dashboard/build.py` — masthead logo mark.** An inline ~20px `<svg class="pupsik-logo-icon">` of the same baby now sits immediately before the `pupsik` wordmark, so the header reads **[baby] pupsik**. The wordmark + repo byline/link from `2026-07-13.1` are unchanged. The `mask-icon` + `theme-color` hex are updated from `#DD3D1F` → **`#5BB8E8`** to match the new favicon's rect fill (the invariant `scripts/brand-os-visual-gate.sh` enforces: dashboard theme hex == favicon rect fill).
- **`dashboard/styles.css`** — added `.brand-lockup` (icon + wordmark travel together, optically centred) and `.pupsik-logo-icon` (20px, 5px radius, hairline ring, theme-aware in light + dark). Wordmark gradient untouched.
- **`dashboard/README.md`** — the "favicon intentionally left untouched" note is replaced: the favicon and header mark are now the pupsik baby, and the theme hex tracks the favicon rect fill.

### Gate

- `scripts/brand-os-visual-gate.sh` is **unchanged** — it hardcodes **no** favicon hash or hex; it detects a Brand OS spec dynamically and is opt-in (SKIP/exit 0 when none is present, the case for pupsik's own repo and generic forks). The favicon + theme-hex change keeps pupsik internally self-consistent (favicon rect fill `#5BB8E8` == `mask-icon`/`theme-color`), and forks with their own Brand OS are still reconciled to *their* spec via `--fix`.

### Privacy

- No personal data added. The masthead byline/link (`github.com/mishalyalin/pupsik`, "by Misha Lyalin") already shipped in `2026-07-13.1` and is covered by the byline allowlist. `privacy-check.sh --include-untracked` clean.

## [2026-07-13.1] - "What's new in pupsik" dashboard panel + local update-check + pupsik header branding

Every pupsik user now SEES, on their own dashboard, what changed since the version they installed — and gets a one-command way to pull the latest. Plus the dashboard header is branded as pupsik. No new updater was built: this is the vitrine + a lightweight check that feeds it, both wired around the existing `tools/update.sh`.

### Added

- **`tools/check-update.sh`** — a lightweight, fail-soft "am I behind upstream?" probe (git + stdlib only, no dependencies). It's a **local `git fetch`** on the clone you already have — the same thing `git pull` does, sending **no** data about you anywhere — with a read-only GitHub-raw fallback (`VERSION` + `CHANGELOG.md`) only if run outside a git clone. It writes `state/pupsik/update-status.json` (`{installed, latest, behind, new_entries, clone_path, checked_at, source, error?}`), computing which CHANGELOG entries are newer than the installed version (date-based `YYYY-MM-DD[.N]` compare). Self-throttling (skips the network if checked <6h ago, via the status file's mtime), opt-out via `PUPSIK_NO_UPDATE_CHECK=1`, and fail-soft on every path (any git/network/parse error writes a status with `error` set and `behind:false`, then exits 0). Keeps the "Local. No telemetry, no cloud sync" promise intact.
- **`dashboard/build.py` — "What's new in pupsik" panel** at the TOP of the Architect tab, above the backlog. When behind: a header ("⬆ What's new in pupsik — N updates since vX → vY"), the new CHANGELOG entries (version · title · summary, capped with "…and N more"), an **Update pupsik** button, and the exact update command. When current: a quiet "✓ pupsik up to date". `build.py` stays **stdlib-only and makes no network call** — it only READS the JSON (the git-fetch lives in `check-update.sh`); a missing/malformed file degrades to a subtle one-liner and never breaks the build. The button copies `cd <clone> && git pull && bash tools/update.sh` to the clipboard with a confirmation toast — honest one-click for a static, server-less dashboard (it does not fake running a shell).
- **`templates/update-pupsik-skill.md.template`** — an optional Claude skill so "update pupsik" in any session runs `git pull` + `tools/update.sh` and reports what changed. Reuses the existing updater; never runs on a schedule.
- **`docs/UPDATE_PUPSIK.md`** — how the panel, the check, the opt-out, throttling, and the skill fit together.

### Changed

- **`dashboard/build.py` + `dashboard/styles.css` — pupsik header branding.** The masthead now carries a **pupsik** wordmark (warm rounded system font + brand-gradient text-fill, **no external/CDN font**, theme-aware) with a quiet byline linking to `github.com/mishalyalin/pupsik` (opens in a new tab), "by Misha Lyalin", and the local home `~/Desktop/claude`. The prior header was a bare "Dashboard" with no personal branding leaked — nothing sensitive to replace. The `favicon.svg`, `mask-icon`, and `theme-color` hex are deliberately **untouched** (they're byte-checked by `scripts/brand-os-visual-gate.sh`).
- **`install.sh`** — Step 11 now also records `state/pupsik/installed-version.txt` (the VERSION this workspace runs) and `state/pupsik/clone-path.txt` (where the clone lives) in the workspace. `update.sh` reaches this via `install.sh --update-only`, so both fresh installs and updates keep the markers current. These feed `check-update.sh` (installed-version compare) and the session-start hook (locating the clone).
- **`hooks/session-start-reminder.sh`** — fires `check-update.sh` in the **background** on session start (fully non-blocking; never delays session start), locating the clone via `clone-path.txt`, respecting the 6h throttle and `PUPSIK_NO_UPDATE_CHECK=1`. So the panel stays fresh with zero user effort.
- **`README.md` / `dashboard/README.md`** — document the panel, the local git-fetch check, the opt-out flag, the "update pupsik" skill, and a check-only cron variant; reconcile the "Auto-update: enabled" badge as "surfaced + one-command, never a silent background pull".

### Why

pupsik's updater already existed and works well; what was missing was **discoverability** — users had no way to know a better version had shipped without remembering to run `update.sh`. The panel makes "there's something new" a passive, always-visible fact on the dashboard they already open every morning, and collapses acting on it to one copy-paste (or one sentence to Claude). The privacy shape is deliberate: a check that only ever does what `git pull` does, opt-out in one env var, so surfacing updates never becomes telemetry.

### Privacy

`check-update.sh` sends no user data on any path (local `git fetch`, or a read-only GET of two public files as fallback). `build.py` makes no network call at all. Byline "by Misha Lyalin" + the repo URL are privacy-allowlisted. No real third-party names, amounts, IDs, tokens, or personal workflow specifics were added. Privacy check **PASS** (`bash .github/scripts/privacy-check.sh --include-untracked`).

## [2026-07-06.1] - telegram-readonly MCP + dashboard reliability patterns + verify-ticks template

Four generic patterns from two weeks of live use, plus small repo-health fixes.

### Added

- **`mcp-servers/telegram-readonly/`** — a local, **read-only** Telegram MCP server (Python + Telethon + FastMCP, stdio). The security shape is the point, and it is structural rather than prompt-based: exactly **3 read tools** (`telegram_list_allowed_chats` / `telegram_read_chat` / `telegram_search_chat`); a **per-chat allowlist** enforced on every read (no `get_dialogs`, no account-wide enumeration is exposed at all — the blast radius of the account-powerful session is capped at the chats you listed); **no write code path** — no send/edit/delete/forward/join/mark-read helper is defined or even imported, so a prompt-injected "send a message" has nothing to call; the Telethon **StringSession is Fernet-encrypted at rest** under a stable per-install key (`~/.telegram-readonly-mcp/key`, mode 0600 — same stable-key pattern as the 2026-06-12 multi-gmail token store); and **login is interactive-only** (`login.py` refuses argv/env credentials — phone/code/2FA go from your keyboard straight to Telethon; the assistant never sees them). Ships like the other local servers: copied (not built) by `install_mcps.sh`, registered by `register_mcps.sh` **only when the user has created the venv** (a dead spawn every session helps no one). Distinct from `docs/TELEGRAM_SETUP.md` (the message-Claude-from-your-phone bot — opposite direction).
- **`templates/scheduled-tasks/verify-ticks.md.template`** — manual-only agent skill: verify the operator's checked-off dashboard items against their REAL communications before trusting them. Reads the dashboard's exported closed-state JSON, recovers each item's text from `index.html`, launches one verifier subagent per item in parallel (sent mail across all connected accounts + chat read-MCPs, 21-day window), and returns evidence-based verdicts — ✅ VERIFIED (with a quoted real message + date + channel), ⚠️ NO EVIDENCE (with what was searched), ℹ️ N/A (not verifiable from communications). Verdicts persist to `state/dashboard/tick-verifications.json` for the morning briefing to gently resurface ticked-but-unproven items. Hard rules: MANUAL ONLY (auto-run = bug), a verdict is never ✅ without a real quoted message, no web-searching private people, read-only against the dashboard state.

### Changed

- **`dashboard/build.py`** — two reliability patterns. (1) **Stale-briefing guard**: `todays_briefing()` now returns a stale flag when no briefing exists for today's date and the renderer fell back to an older file; the Today tab shows a visible `STALE` note naming the file actually rendered, and the page subtitle is marked too. A morning dashboard must never silently present yesterday's agenda as today's — that is the exact failure mode it exists to prevent. (2) **Asset cache-buster**: `styles.css` + favicon links carry `?v=<build-timestamp>` so every rebuild serves fresh assets instead of a browser-cached copy (bites as soon as the dashboard is served from a VPS). The `mask-icon` line is deliberately untouched — the brand-os visual gate greps it by shape.
- **`scripts/morning-dashboard.sh`** — two VPS-deploy failure classes closed. (1) `rsync --chmod=D755,F644`: `rsync -a` faithfully preserves a local `600` on `styles.css`/`favicon.svg`, nginx then serves 403, and the dashboard loads *unstyled* with zero error on the laptop side. (2) Optional **post-deploy smoke test** (new `DASHBOARD_VPS_URL` env var): curl each shipped asset and expect HTTP 200 — "uploaded" is not "served"; a 403/404 prints a loud per-asset FAIL at deploy time instead of at the next phone-bookmark open. Fully backwards compatible: skipped silently when the URL is unset.
- **`install_mcps.sh` / `register_mcps.sh`** — copy + conditionally register the new Python server alongside the three Node servers (see Added).

### Fixed

- **`README.md`** — the feedback-rule count had drifted: "27 generic feedback rules" vs 38 actually shipped in `memory_templates/`. Corrected; "What's new" section topped up (it had been sitting at 2026-05-09 while five releases landed in CHANGELOG).
- **`dashboard/README.md`** — documents the stale note, the cache-buster, the two deploy-reliability details, and the verify-ticks pairing.
- **`UPGRADING.md`** — per-release one-time steps for this release (all optional).
- **Three pre-existing privacy nits scrubbed** (caught by this release's manual sweep, all survived earlier passes because they sit in byline-allowlisted files or use bare first names): a real colleague's full name used as the fuzzy-match example in an older CHANGELOG entry (now a generic name pair); an owner-company mention in the 2026-06-02.1 entry (now "specific project repo clones"); a real supplier-contact first name + entity-type detail in `MARKETING.md` (now generic). Same class as the 2026-06-24.1 scrub, closing the remainder.

### Why

The Telegram server generalises the hardest lesson of account-powerful MCPs: read-only must be a property of the CODE (no write path exists), not of the prompt. The dashboard items are the "boring correctness" layer of a daily-driver dashboard: never lie about the date of what's on screen, never serve stale CSS, never trust that an upload was actually served. verify-ticks applies the toolkit's never-imagine-always-verify rule to the operator's own memory — the checkbox is a claim, not a fact.

### Privacy

Privacy check **PASS** (`bash .github/scripts/privacy-check.sh --include-untracked`) on the full tree including all new files. The Telegram server ships with placeholder credentials and generic chat labels only; its `.gitignore` excludes `config.json` / `session.enc` / the venv as a backstop. The verify-ticks template uses `Vendor-A`-style counterparties. No real names, chat labels, amounts, tokens, IDs, or personal workflow specifics were ported; the always-on vendor denylist needed no new terms (no new vendor/bank/advisor names appear in any added content).

## [2026-06-24.1] - scrub real vendor/bank names from public files + always-on privacy denylist

Privacy hardening. A few real vendor/bank names and one real incident had survived from early ports into public files; this scrubs them and makes the privacy scan catch the whole class going forward, with no dependency on a configured secret.

### Fixed

- **`README.md`** — the "Semantic search" example query named a real packaging supplier. Genericised to a `Vendor-A` placeholder (intent of the example unchanged: a semantic search over past notes).
- **`tools/note.py`** — the `--phase` help text example for `note.py friction` named the same real supplier (`... production confirm`). Genericised to a neutral `vendor-a production confirm` placeholder. This one had slipped past the privacy scan because it was lowercase and the old pattern was case-sensitive — now fixed by the case-insensitive denylist below.
- **`memory_templates/feedback_never_ignore_own_rules.md`** — the "Why" example narrated a real past incident with a specific date, a real bank, a real supplier, a real shipment courier, and a real tracking number. Rewritten as a generic illustrative incident: a plan was built on stale working-memory while fresh email clearly showed a bank account had opened (with transfers running) and a supplier payment + shipment with a tracking number had gone out — and the user was rightly annoyed. The lesson is identical; the real specifics are gone.

### Changed

- **`.github/scripts/privacy-check.sh`** — added an **always-on vendor/bank/advisor denylist** pass (new `VENDOR_DENYLIST_PATTERN`, runs regardless of whether the optional `private-patterns.env` / CI secrets are configured). A future PR that reintroduces any of the denied real vendor / bank / advisor names — including the known-leaked tracking number — now FAILS the "Paranoid privacy scan" even on a fork with no secrets set. The pass is **case-insensitive** (the real regression was a lowercase name that slipped a case-sensitive pattern), runs with `allow_byline=0` (vendor names are never excused, not even in README/CHANGELOG/LICENSE — the byline allowlist only ever covered the maintainer's own name), and the script's existing universal self-exclusion (it contains these patterns by definition) is preserved so it does not trip on itself. Common-word names are scoped to avoid false positives (the more generic ones are matched only as their full multi-word company phrase; the distinctive ones are matched bare, low false-positive risk in a dev-toolkit repo — see the in-script comment for the exact scoping rationale). Generic placeholders (`Vendor-A`, `Vendor-B`, `supplier production confirm`) are deliberately NOT denied. The `grep_text` / `run_pass` helpers gained an optional case-insensitive flag to support this; all existing callers are unaffected.

### Why

These names were low-signal but real — a vendor or bank name in a public dev toolkit identifies a real-world relationship and adds nothing to the documentation. The bigger fix is structural: the scan previously caught these only when the maintainer's gitignored `private-patterns.env` (or a CI secret) was configured, and even then a lowercase variant slipped through. Baking a small fixed denylist into the public script — always on, case-insensitive — closes both gaps so the class can't silently recur on a fork or after a fresh clone.

### Privacy

Privacy check **PASS** (`bash .github/scripts/privacy-check.sh`, 12 passes, 0 failures) on the scrubbed tree. Verified the new pass FAILS (exit 1) when a real vendor name is reintroduced — including lowercase, and including inside a byline-allowlisted file — and that genericised placeholders still pass. This CHANGELOG entry is itself written without naming the scrubbed vendors so it does not reintroduce them.

## [2026-06-23.1] - auto-compact threshold doc fix + deterministic-code rule

Two changes out of a live debugging session, both root-causing "I set the threshold and it did nothing."

### Fixed

- **`docs/COMPACT_SETUP.md`** — the doc told users to put `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE` in the `settings.json` `"env"` block and "watch for it firing at ~50%". That does NOT work for this variable. The var is read from the agent process's **launch environment** at startup; the `settings.json` env block is NOT applied to the app's own auto-compact logic (open bug [anthropics/claude-code#63186](https://github.com/anthropics/claude-code/issues/63186)) — the value set there is visible to subprocess tool calls (a `Bash` call can `echo` it) but never changes the threshold, so the wrong-way setup fails silently. The fix rewrites every part of the doc that describes HOW to set the threshold and splits it by surface: **CLI / terminal** (`export` in `~/.zshrc`/`~/.bashrc` works, because the CLI inherits the shell's launch env; `launchctl setenv` also works on macOS) vs **Claude Desktop** (neither shell `export` nor `settings.json` env reaches the Dock/Finder-spawned agent, per the [official desktop docs](https://code.claude.com/docs/en/desktop.md) — the ONLY channel is the in-app **Local environment editor**: prompt-box environment dropdown → hover **Local** → gear icon → add the var → restart). New `## Setting the threshold (per surface)` section, plus corrected `## Tuning the threshold`, the step-2 `settings.json` snippet note (env block kept for its other legitimate uses, with a clear "does NOT set the threshold" warning), `## Verification`, and `## Troubleshooting` (a Desktop user who set it the wrong way is now told the real reason it "still fires near the end"). Added the `[1m]`-model caveat (threshold may be computed against a hardcoded ~200K window rather than the advertised 1M — issues [#53801](https://github.com/anthropics/claude-code/issues/53801) / [#53358](https://github.com/anthropics/claude-code/issues/53358)) and the semantics note (value = percent of the auto-compaction window USED at which compaction fires; lower = earlier — [env-vars docs](https://code.claude.com/docs/en/env-vars)). The hooks content (`pre-compact.sh` / `post-compact.sh` / the `CLAUDE.md` "Compact Instructions" block / the hook verification commands) is unchanged — only the env-var setup guidance was wrong.

### Added

- **`memory_templates/feedback_code_for_deterministic_tasks.md`** — new generic feedback-rule template. If a task has one correct answer a function could compute the same way every run (date math, currency at a fixed rate, weekday-from-ISO, parsing a known format, dedup/sort/count, sums/totals/margins, regex over a fixed format) → WRITE CODE; don't hand-do or eyeball it (it drifts between runs and is where invented numbers enter). If the task genuinely needs judgment (language, tone, intent classification, "same entity?") → reason it; do NOT fake it with a brittle keyword/regex imitation that looks authoritative while silently mis-firing. Mixed → split (deterministic spine in code, judgment in prose). EITHER way the output is ALWAYS independently verified — run code against known I/O + a checker reads it, judgment re-derived by a checker; "the script ran without error" ≠ correct. Cross-references `feedback_always_two_agents.md`, `feedback_never_imagine_always_verify.md`, `feedback_compute_weekday_dont_guess.md`, `feedback_pr_reuse_audit.md`.

### Why

The doc fix comes straight from a live incident: the threshold env var was set in `settings.json` and silently did nothing because #63186 means that block isn't applied to compaction — and on Claude Desktop even a shell `export` doesn't reach the agent, so the only working channel (the in-app Local environment editor) wasn't documented at all. Any adopter following the old doc inherited the same dead-end. The deterministic-code rule generalises a recurring failure mode that prompt-tightening doesn't fix: hand-doing a deterministic task drifts and lets invented numbers in, while coding a judgment task ships a confident-looking imitation that mis-fires on the next input — matching the method to the task (and verifying either way) closes both.

### Privacy

Privacy check **PASS** (`bash .github/scripts/privacy-check.sh --include-untracked`). The new feedback template is fully generic — no verbatim quotes, person names, individual dates, or real `/Users/...` paths. The doc fix cites only public GitHub issue numbers and public `code.claude.com` doc URLs.

## [2026-06-12.1] - stable-key token store (travel fix) + MCP servers install off iCloud

Two hard-won reliability fixes, both root-causing "my MCPs randomly broke" failure modes.

### Fixed

- **`mcp-servers/multi-gmail/src/services/token-store.ts`** — stable-key token store. The encrypted token store (`~/.multi-gmail-mcp/tokens.enc`) used an AES-256-GCM key derived from `os.hostname()`. On macOS the hostname can be DHCP-assigned, so when the laptop moves between WiFi networks the hostname silently changes, the derived key changes with it, decryption fails — and a silent `catch` made the server report "no accounts" with zero diagnostics. The fix: (a) a **stable per-install key** (random 32 bytes, persisted once to `~/.multi-gmail-mcp/key`, mode 0600) replaces the hostname-derived key for all writes; (b) the legacy hostname-derived key is kept **read-only** as a fallback — if it still decrypts, the store is **auto-migrated** to the stable key in place (one stderr line logs the migration); (c) if **both** keys fail, the server now writes a LOUD stderr message ("Re-auth needed: `npm run setup reauth`") instead of silently returning an empty account list. Existing users: tokens migrate automatically on first read, no action needed — unless the hostname already drifted since the store was last written, in which case re-add accounts once (`npm run setup add <label>`).

### Changed

- **`install_mcps.sh`** — MCP servers now install to **`$HOME/code/mcp-servers`** by default (override with `MCP_INSTALL_DIR`), with a compatibility symlink at `$WORKSPACE/mcp-servers`. Why: the old default put the servers under `~/Desktop/claude/mcp-servers`, which on macOS with "Desktop & Documents Folders" iCloud sync is an iCloud-synced path — Optimize Storage evicts `node_modules` files to dataless placeholders, node fails at spawn with `MODULE_NOT_FOUND`, and the MCP servers randomly "disconnect" until reinstalled. Installing outside iCloud root-causes that whole failure class. If a real (pre-existing) `$WORKSPACE/mcp-servers` directory is found, the script does NOT touch it — it prints a migration recipe (`rsync -a` then swap, NOT a bare `mv`, which Finder/fileproviderd can cancel out of an iCloud-synced dir with "Operation canceled").
- **`register_mcps.sh`** — registers the servers' **real path** (symlinks resolved via `pwd -P`), honours `MCP_INSTALL_DIR`, prefers `~/code/mcp-servers`, falls back to the legacy `$WORKSPACE/mcp-servers` layout with a migration warning when the resolved path sits under `~/Desktop` / `~/Documents`.
- Docs updated consistently: `README.md` (uninstall), `SETUP_PROMPT.md` (Phase 4), `HOW_IT_WORKS.md`, `docs/WHATSAPP_SETUP.md`, `memory_templates/feedback_use_local_mcp.md`, `memory_templates/feedback_keep_working_files_off_icloud.md`. Migration steps for existing installs in `UPGRADING.md`.

### Why

Both fixes come from live incidents: the hostname-derived key broke Gmail access twice while the author was traveling (network change → DHCP hostname change → undecryptable tokens → "no accounts" with no error), and the iCloud eviction of `node_modules` under the workspace was the root cause of months of intermittent MCP disconnects. Any adopter on a Mac with default iCloud settings inherits both failure modes; both are now structural rather than documented-around.

### Privacy

Privacy check **11/11 PASS** (`--include-untracked`). Comments and docs use neutral phrasing (generic "laptop moves between networks / DHCP-assigned hostname changes") — no real hostnames, locations, accounts, or owner-specific incident details.

## [2026-06-05.1] - new rule: check if the user already sent it before proposing/drafting outbound

### Added

- **`memory_templates/feedback_check_already_communicated.md`** — before suggesting OR drafting any outbound message to a person (email / chat / DM / follow-up / confirmation), first scan the user's sent mail (all connected accounts) + chat history for an existing message from them on that topic in the last ~14 days. If it exists, do NOT propose the draft — surface what they already sent and track the pending reply instead. Only draft if nothing matching exists. This is the proactive-proposal corollary of "verify the message is needed before drafting": it fires earlier (before you even SUGGEST a draft) and catches the recurring failure where an agent helpfully offers to draft an email the user sent two days ago.
- **`templates/critical-rules.md.template`** — one-liner under `## 🔴 MANDATORY protocols`, next to "Verify project state before answering".

### Why

Direct trigger: an agent proposed drafting a logistics/insurance email to a counterparty when the owner had already sent that exact email days earlier. A 30-second sent-mail search would have changed the response from a redundant draft offer to "already handled, awaiting their reply." The check is cheap and belongs before the proposal, not after.

### Privacy

Privacy check 11/11 PASS (`--include-untracked`). Generic language only — no real names, recipients, or owner-specific facts in the rule text.


## [2026-06-02.3] - `feedback_fix_mcp_proactively.md`: two hard-won MCP-debug lessons

Amends the MCP-debug rule shipped in 2026-06-02.1 with two lessons from a live incident where three local MCP servers went down and the obvious fixes misled.

### Changed

- **`memory_templates/feedback_fix_mcp_proactively.md`** — two additions to the dependency-corruption guidance:
  - **Targeted-install footgun.** When a server's dependency tree is broken, run the FULL `rm -rf node_modules && npm install`, NOT a targeted `npm install <one-package>`. A single-package install on top of an already-partial tree fixes that one package but leaves the rest inconsistent (mismatched peers/transitives) — and the server can then *silently hang on connect* (no error, no crash, just no handshake response) even though the package you "fixed" is now present. Real example folded in: an `npm install zod@^3.25` to fix one crash left the server hanging because the rest of the tree was half-installed.
  - **Verify with the right signal.** Confirm a fix with the host's own health check (e.g. `claude mcp list`) **plus a live tool call** — NOT a hand-rolled JSON-RPC handshake probe. A minimal probe (`spawn` + `initialize` + wait for `"result"`) can false-negative (time out) on a server the host connects to fine, because the host's real handshake includes follow-ups (`notifications/initialized`) and stdin-keepalive that a quick probe omits. A probe timeout is not proof a server is down; use the probe only to extract the error from a server *already* confirmed down by the health check. Two matching "What NOT to do" bullets added.

### Why

Direct incident (2026-06-02): three servers showed ✗ at session start; one had an obviously corrupt tree (a core dependency entirely missing), but two others looked healthy by size yet still failed — a prior targeted single-package install had left their trees inconsistent. During the fix, a hand-rolled handshake probe reported one server as timed-out while the host's own `claude mcp list` reported it ✓ and a live call returned data — the probe was wrong, the host was right. Both lessons generalise to any adopter running local MCP servers.

### Privacy

- Privacy check **11/11 PASS** (`--include-untracked`). Generic language only; no real account names, tokens, or owner-specific server names in the rule text.

## [2026-06-02.2] - fix `note.py` crash on macOS system Python (3.9)

### Fixed

- **`tools/note.py`** — added `from __future__ import annotations` after the module docstring. The file uses PEP 604 `X | None` union type annotations (26 of them) which only parse natively on Python 3.10+. macOS ships **Python 3.9.6 as the system `python3`**, so on a stock macOS install `python3 tools/note.py ...` crashed at import time with `TypeError: unsupported operand type(s) for |: 'type' and 'NoneType'` — meaning the knowledge-capture CLI was unusable for any adopter running it under the default interpreter. The `__future__` import makes all annotations lazy strings (PEP 563), so the union syntax parses on 3.9 with zero runtime-behaviour change. No other toolkit tool has this issue (verified by parsing every `tools/*.py` under 3.9).

## [2026-06-02.1] - macOS iCloud-eviction rule + close the fix-MCP orphan pointer

This toolkit installs to `~/Desktop/claude/` by default. On macOS with "Desktop & Documents Folders" iCloud sync on, that path is iCloud-synced — and iCloud's Optimize Storage silently evicts file contents to dataless placeholders, which corrupts git working clones, `node_modules`, and MCP server runtimes living under the workspace. This release documents the gotcha + the reinstall drill, and closes a pre-existing orphan pointer in the critical-rules template.

### Added

- **`memory_templates/feedback_keep_working_files_off_icloud.md`** — new rule. On macOS with Desktop & Documents iCloud sync on, Optimize Storage evicts file contents to dataless placeholders and corrupts anything needing a complete on-disk tree: git clones (`fatal: bad object HEAD`), `node_modules` (`MODULE_NOT_FOUND` for a *submodule* — `.d.ts` stubs survive, `.js` runtime evicted), MCP runtimes (crash on startup `require()`). Rules: keep git clones in `~/code/` (a clone is a disposable working copy — the remote is canonical, no reason to pay sync cost on it); keep node_modules-heavy projects off iCloud-synced paths. Diagnostic: a `node_modules` folder under ~10% of normal size is evicted; fix is `rm -rf node_modules && npm install`, NOT reauth (the compiled output + OAuth tokens are fine, only the dependency tree got truncated). Includes the safe-move checklist for relocating an existing clone (`git log @{u}..HEAD` / `git branch -vv` / `git stash list` before trusting any "clean/pushed" claim; `mv` intact, never delete-and-re-clone). Scoped with an explicit "not applicable if Linux/Windows or iCloud sync off" footer.
- **`memory_templates/feedback_fix_mcp_proactively.md`** — NEW FILE that closes a pre-existing orphan: `templates/critical-rules.md.template` referenced this rule but the file was never shipped. Generic version: when a local MCP server breaks, reproduce standalone (`node dist/index.js`) and read the real require-stack error, then triage by class — auth/token-expiry (missing `oauth2Client.on("tokens", ...)` persistence), crash-on-error (missing `uncaughtException`/`unhandledRejection` guards), or dependency corruption (`MODULE_NOT_FOUND` for a submodule → reinstall per the iCloud rule). Don't reflex-punt to reauth; don't assume the source is broken when `node_modules` is the culprit.

### Changed

- **`templates/critical-rules.md.template`** — added the iCloud one-liner under `## Workspace / files` (keep clones in `~/code/`; small `node_modules` = evicted → reinstall). Refined the existing "Fix MCP proactively" line with the explicit exception that when `node_modules` is corrupted/evicted, reinstall IS the fix (the source is fine) — these two rules interact and the cross-reference prevents a future reader treating "debug the source, not reauth" as forbidding a legitimate dependency reinstall.

### Why these belong in the public template

The iCloud rule is not a power-user edge case for this toolkit specifically — the toolkit's documented install path *is* `~/Desktop/claude/`, which is exactly the iCloud-synced location when Desktop sync is on. Any adopter on that default with sync enabled will eventually hit the eviction corruption. The `feedback_fix_mcp_proactively.md` addition is pure orphan-closure: the pointer already shipped in `critical-rules.md.template`, only the target file was missing.

### Privacy invariants

- Privacy check passed (`bash .github/scripts/privacy-check.sh --include-untracked`).
- Both new files use generic language (no real repo names, no owner-specific paths beyond the toolkit's own documented `~/Desktop/claude/` + `~/code/` convention). The owner-specific source incidents (specific project repo clones, specific MCP server names + zod version pins) were deliberately left in the private workspace and NOT propagated — only the generalizable mechanism + diagnostic + fix made it into the template.

## [2026-05-27.2] - remove Russian-speaker heuristic + `tg_manual_paste_recommended` column

The Russian-speaker heuristic and its companion column were dropped because the cron never touches Telegram either way - the flag added no operational value, only confusion.

### Removed

- **`tools/flag_russian_speakers.py`** - the multi-signal Cyrillic / Latin-transliteration / surname-suffix / email-domain / `$RUSSIAN_CONTEXT_COMPANIES` heuristic. Deleted entirely. The feature it served (surfacing "TG manual-paste candidates" in the cron's run summary) was an indirection that did not change cron behaviour - Telegram remained NEVER auto-read regardless of the flag, and the manual-paste workflow works the same way without the column hint. If you want TG context for a specific contact, paste the history into an ad-hoc prompt manually for that one row.
- **`tg_manual_paste_recommended` column** on `contacts`. Removed from `tools/enrichment_schema_migrate.py`. Existing installs with this column in their `contacts.db` can drop it via `ALTER TABLE contacts DROP COLUMN tg_manual_paste_recommended` (SQLite 3.35+). The column was not load-bearing on any cron logic.
- **Step 0.5** of the contact-enrichment-weekly cron (which called `flag_russian_speakers.py --apply` before the candidate query). The cron template + operating rule + run-summary schema are simpler without it.
- **`$RUSSIAN_CONTEXT_COMPANIES` env var** support. No replacement.

### Changed

- **`tools/enrichment_schema_migrate.py`** - now migrates 11 columns instead of 12 (drops `tg_manual_paste_recommended` from `ENRICHMENT_COLUMNS`). Re-runs on existing 12-column tables remain safe; the script never deletes columns, it just stops adding the dropped one for fresh installs.
- **`memory_templates/feedback_contact_enrichment_weekly.md`** - the Russian-speaker heuristic section is gone. Schema requirement updated to 11 columns. Pass 4 description updated to say "paste TG history into an ad-hoc prompt manually" instead of "the heuristic flags candidates for manual paste".
- **`templates/scheduled-tasks/contact-enrichment-weekly.md.template`** - Step 0.5 removed. SELECT statement drops the `tg_manual_paste_recommended` column. The "TG manual-paste candidates" section of the run summary is removed. The `tg_manual_paste_pending: <int>` field is removed from the summary YAML schema.
- **`tools/update.sh`**, **`install.sh`** - smart-merge call for `flag_russian_speakers.py` removed. The toolkit count drops from 6 actively-merged tools to 5.
- **`README.md`**, **`MODULAR.md`**, **`UPGRADING.md`** - all narrative references to the heuristic dropped. The historical 2026-05-09 CHANGELOG entry stays as immutable release-note history.

### Migration for existing 2026-05-27.1 installers

If you adopted 2026-05-27.1 and your `contacts.db` has `tg_manual_paste_recommended INTEGER DEFAULT 0`:

```bash
# Backup first
cp ~/Desktop/claude/data/contacts.db \
   ~/Desktop/claude/data/contacts.db.bak.$(date +%Y%m%d)

# Drop the column (SQLite 3.35+ required - macOS shipped sqlite3 has had this since Big Sur)
sqlite3 ~/Desktop/claude/data/contacts.db \
  "ALTER TABLE contacts DROP COLUMN tg_manual_paste_recommended"

# Verify
sqlite3 ~/Desktop/claude/data/contacts.db ".schema contacts" | grep tg_manual || echo "(clean)"
```

`flag_russian_speakers.py` in your workspace will be sidecar-noted by the next `update.sh` (`.new` will not exist for a deleted file - you have to `rm` the workspace copy manually). Or run:

```bash
rm ~/Desktop/claude/tools/flag_russian_speakers.py
```

### Privacy invariants

- Privacy check passed (`bash .github/scripts/privacy-check.sh --include-untracked`).
- The removed feature itself was not a privacy concern (it never read TG, only flagged candidates), but the removal makes the codebase smaller and more honest about what the cron actually does.

## [2026-05-27.1] - five new self-improvement rules + note_graph fuzzy entity fallback

This release propagates five new self-improvement rules from a real workspace's session work (Apr-May 2026 r/ClaudeAI viral threads + AI-PR review checklist adoption) into the public template, plus a small but meaningful upgrade to `tools/note_graph.py` so `entity <name>` is friendlier when you don't remember the exact casing.

### Added

- **`memory_templates/feedback_session_retro.md`** — at session end, run a 2-min retro (learned / surprised / encode) and ACT on it via `note.py learning|decision|research` + propose new feedback rules + architect entries. The moment-of-emergence rule (`feedback_capture_knowledge.md`) is the primary mechanism; this is the safety net for fuzzy / buried / meta-pattern insights that didn't land mid-flight. Triggers: user signals close, final summary about to send, compact threshold near, natural boundary (PR merged / decision made / runbook delivered).
- **`memory_templates/feedback_claudemd_size_discipline.md`** — `CLAUDE.md` is working memory re-read EVERY session; bloating it permanently subtracts attention. Soft cap 450 lines, hard cap 600. The nightly reflection (`dream-v2`) already trims `## Last Updated` past 7 days to `memory/journal/claude-md-changelog.md` and audits `## Upcoming` for resolved items; this rule adds the discipline that the morning briefing's Architect Lens flags `>500` lines as INFRASTRUCTURE DEBT.
- **`memory_templates/feedback_context_hygiene.md`** — `/clear` + restart over patching when Claude hallucinates or misclassifies twice in a row, or autocompact fires ≥2x mid-task. Past ~400k tokens of long-context, attention degrades silently — more correction turns add MORE degraded context. Max 3 correction turns before mandatory clear. Restart prompt is a junior-engineer brief (goal + paths + tried+failed + ask), not a recap.
- **`memory_templates/feedback_ci_red_is_hard_stop.md`** — if any CI check on a Claude-authored PR fails (or yellow-warning-treated-as-FAILURE), the PR does not merge. No exceptions, no pattern-matched justifications. Before `gh pr merge`: `gh pr view <n> --json statusCheckRollup --jq '.statusCheckRollup[].conclusion'` must return all SUCCESS. Branch protection + pre-commit hook are structural enforcement; this rule fills the behavioural gap when human/AI is tempted to bypass structure.
- **`memory_templates/feedback_pr_reuse_audit.md`** — before any PR adds a new utility / function / script, grep `rg "def <name>"` + 2-3 core-purpose keywords across `tools/` and the repo. If a hit looks similar: CONSOLIDATE (refactor existing) OR JUSTIFY in the PR description OR REJECT (existing already does this). Targets the `tools/` accumulation problem before it becomes irreversible.
- **`templates/critical-rules.md.template`** — five new one-liners under `## System self-improvement` pointing at the five feedback rules above. These belong with the existing `Architect Lens auto-apply` and `Architect proposals backlog` rules because they share the same purpose: the system improves itself across sessions without each new session re-discovering the same lessons.

### Changed

- **`tools/note_graph.py`** — `fetch_entity_by_name(conn, name)` now returns `(rows, match_kind)` tuple with a four-tier match cascade: exact name → alias → fuzzy substring on name → fuzzy substring on alias. Minimum partial-length is 2 characters. `match_kind ∈ {exact, alias, fuzzy, none}`. The `entity <name>` CLI command surfaces a disambiguation hint when fuzzy matching returns multiple candidates. The old behaviour (exact + alias only) is preserved as the first two tiers, so existing scripts that called `fetch_entity_by_name` and unpacked a single list need a small unpack change — see the docstring. This is a small UX upgrade: when you don't remember "Aleksandr" vs "Alexander", `entity alex` now lists both with a hint, instead of returning empty.

### Why this is structural, not just five new rules

Each of the five rules closes a real failure mode that more prompt-tightening doesn't fix:

- Session retro closes the "story diluted, structural lesson lost" gap that end-of-session summaries leave.
- CLAUDE.md size discipline closes the "working memory bloats over months and the top-5 P0s drown" gap.
- Context hygiene closes the "keep arguing through a degraded session" anti-pattern that compound-frustrates without producing output.
- CI red = hard stop closes the "pattern-matched justification merges on red, hotfix follows" anti-pattern with a direct in-repo precedent.
- PR reuse audit closes the "agent-generated PR adds the fifth near-duplicate to `tools/`" pattern that fragments mental models.

Together they form the self-improvement layer that sits ABOVE the architect proposals backlog: backlog captures what to do; these rules govern HOW you work across sessions so the captures land.

### Cost

The five feedback files total ~280 lines. They're loaded only when their topic surfaces (`feedback_*.md` are pointer-described in `critical-rules.md.template` and full-text-read on demand). The note_graph change adds ~30 LOC; the four-tier match still runs in `< 50ms` on a typical 200-entity DB.

### Privacy invariants

- Privacy check passed (`bash .github/scripts/privacy-check.sh --include-untracked`).
- No private repo identifiers, names, addresses, supplier names, or owner-specific facts in any template or feedback rule. All rules use generic language ("user", "owner", "the repo") that adopters bind to their own context.

## [2026-05-26.1] - morning-briefing Pass 3 direct compact-list audit (no subagent delegation)

This release adds a structural fix to the morning-briefing skill, addressing a recurring subagent-misclassification failure mode that prompt-tightening hasn't solved.

### What broke (the user-visible incident)

On 2026-05-26 the briefing shipped with Pass 1 (filtered subagent) verdict "No counter-party activity from ESCALATED tracker. All silent in last 24h." A 06:24 BST reply from a high-signal supplier counter-party — 45 minutes before the subagent's data gather, comfortably inside its `newer_than:1d` window — was missed. The reply resolved a tracker item that had been escalating for days. Owner asked verbatim *"you do read all the email yourself, right, not just selectively, and you yourself read the latest?"* — and the honest answer was no: subagents had filtered, I had read their summaries, and a real counter-party reply had fallen through.

This is the second incident in 4 days. The first (2026-05-22) was misattribution — a subagent reported an inbox message as the OWNER's outbound action because the owner's name appeared in the thread byline, leading to a false "owner already replied" claim. Tightening the subagent's prompt did not prevent the second incident.

### Added
- **`templates/morning_briefing_skill.md.template`** — new "🔴 MANDATORY Pass 3" section between the two-agent pattern and the end of file. After Pass 1 (filtered Researcher subagent) + Pass 2 (unfiltered fallback subagent, if used), Claude itself queries `gmail_search_all newer_than:2d max_per_account=100`, extracts a compact list (account / date / from:50 / subject:70) inline via Python from the tool-results overflow file, and reads the ~100-line compact list directly in main context. Scan targets: tracker counter-party activity that Pass 1 said was "silent"; gov/regulator that Pass 2 might have dropped; real-human cold inbound from unknown senders. On MISS: `gmail_read_message` body → correct briefing state inline → bump/resolve tracker → mention the miss in the Architect lens for audit trail.
- **`memory_templates/feedback_briefing_pass3_direct_audit.md`** — full operating rule with the two failure modes (misattribution + in-window miss), procedure, trigger, cost, and the reasoning why this is the structural fix vs more subagent rules.

### Why this is structural, not just another subagent rule
- Tightening subagent prompts has failed across multiple incidents in different shapes (misattribution one week, in-window miss the next).
- Pass 3 lives in a different layer: it's direct verification by the entity that ships the briefing, not by a delegated subagent. No attribution drift. No summarisation loss.
- The long-term fix is multi-agent observability hooks (an open backlog item in this workspace's `architect_proposals/`). Pass 3 is the bridge until that lands.

### Cost
~5-10 seconds of main-context tokens per briefing run (compact list ~100 lines + scan). Trivial vs the cost of missing a high-signal counter-party reply.

### Privacy invariants
- Privacy check passed 11/11 (`bash .github/scripts/privacy-check.sh`).
- No private repo identifiers, addresses, supplier names, or owner-specific facts in the template or feedback rule. Both use generic language ("OWNER", "tracker counter-party", "high-signal supplier") that adopters bind to their own context.

## [2026-05-21.1] - update.sh always re-syncs workspace + install.sh template-class force-resync

After yesterday's three-fix release, smoke-testing `update.sh` revealed two complementary bugs in the workspace re-sync flow. (a) `update.sh` early-exited with "already up to date" when `git HEAD == origin/main`, never running the smart-merge phase — so any drift between workspace and pupsik tree that wasn't pulled fresh stayed put indefinitely. (b) `install.sh`'s `smart_merge_file` conservatively dropped `.new` sidecars when there was no `.bak.<ts>` baseline to prove the file pristine — but for files installed before the state-file infrastructure existed (pre-`2026-05-14.1`), no `.bak` ever existed, so legitimate drift (e.g. yesterday's em-dash normalisation on 7 tools) was never overwritten, just queued as sidecars the user had to manually merge. Together they meant the "after update.sh, workspace = pupsik HEAD" contract didn't hold in the common no-new-commits-but-drifted case.

This release closes both gaps and adds the file-class distinction (template / brand-overridable / user-config) that determines which posture each managed file gets.

### Changed
- **`tools/update.sh` always runs the smart-merge step**, regardless of whether `git pull` brought new commits. The `LOCAL == REMOTE` branch now just prints "no new commits to pull - re-syncing workspace files against current pupsik tree" and falls through to `install.sh --update-only` instead of `exit 0`-ing. The contract is now explicit at the top of the file: "after this returns 0, your workspace matches the pupsik clone."
- **`install.sh` `smart_merge_file()` accepts `PUPSIK_FORCE_RESYNC=1`** as a per-call env var. When set and there's no `.bak.<ts>` baseline to prove `dst` pristine, the function ASSUMES pristine, saves the current `dst` as `.bak.<ts>.force-resync` (recoverable), then overwrites with `src`. The default behaviour (no env var) stays conservative: drop `.new` sidecar and warn. This closes the "drift accumulates on installs older than 2026-05-14.1 because no `.bak` baseline was ever written" bug — without breaking the safety net for legitimate user customisations.
- **`install.sh` declares file-class posture per managed file:**
  - **template-class → `PUPSIK_FORCE_RESYNC=1`** (user shouldn't be editing these; pupsik HEAD is canonical): `tools/*.py`, hooks/`pre-compact.sh` + `post-compact.sh`, `memory_templates/*/_PROTOCOL.md` schemas, `scripts/brand-os-visual-gate.sh`, `scripts/install-git-hooks.sh`.
  - **brand-overridable → default sidecar** (workspace customisation is expected; pupsik upstream offered side-by-side for review): `dashboard/build.py`, `dashboard/styles.css`, `dashboard/favicon.svg` (favicon is governed by Brand OS visual spec per adopter, not pupsik), `dashboard/NOTICE.md`, `dashboard/README.md`, `scripts/morning-dashboard.sh` (adopters customise VPS config — token files, hardcoded hosts — vs the pupsik generic env-var template).
  - **user-config → default sidecar** (user-customisable; preserved on update): `memory_templates/feedback_*.md` → workspace `feedback_*.md` rules.

### Why
The `update.sh` contract — "your workspace matches the pupsik clone after this returns 0" — is the whole point of the script. Yesterday I shipped 7 tools with style-normalisation fixes (em-dashes converted to short hyphens) and discovered today that workspaces with no `.bak` baseline silently queued them as sidecars. That meant the fix that was the whole point of the release didn't actually apply to anyone who installed before the state-file infrastructure shipped. Sidecar-by-default is a great safety net for files users legitimately edit, but for template-class files (where editing is unintended) it just means drift accumulates.

The file-class distinction makes the right call for each file:
- A `note.py` with em-dashes should be overwritten — the user didn't put those there, they're upstream stale text we patched.
- A `dashboard/favicon.svg` painted in the adopter's brand colours should NOT be overwritten — the adopter painted it deliberately, and the Brand OS visual gate (a separate tool) handles the brand-vs-workspace sync at build time.
- A `feedback_short_dashes_only.md` that the user has annotated with their own examples should NOT be overwritten — that's exactly the customisation surface the rule files exist for.

### Privacy invariants
- `.bak.<ts>.force-resync` files stay on disk so any silent overwrite is recoverable. Nothing is deleted by the resync step.
- The privacy-check Pass 11 from `2026-05-20.3` runs on every commit (CI + local pre-commit hook), still ensures no private-repo identifier leaks. No regressions in the 11-pass scan.
- Privacy check 11/11 PASS (`--include-untracked`).

### Notes
- Bump VERSION `2026-05-20.3` → `2026-05-21.1`.
- Existing installs picking up this release will see their drift force-resynced on the next `tools/update.sh` run for any template-class file (typically `tools/*.py`, hooks, `_PROTOCOL.md`). The original workspace content is saved as `<file>.bak.<ts>.force-resync` next to the resynced file — diff against it if you want to confirm the resync was lossless. To opt back into sidecar behaviour for a specific file, edit `install.sh` and remove the `PUPSIK_FORCE_RESYNC=1` prefix on that smart_merge_file call.

## [2026-05-20.3] - Three structural fixes from today's leak + drift incidents

This week's repo had a privacy CI bypass (PR #12 with a flagged check that I merged anyway via a branch-protection gap) and two more incidents in one day: PR #17 + #18 leaked a private repo identifier into public docs, and the dashboard favicon shipped to the VPS drifted off-brand against the locked Brand OS visual spec. All three were caught manually. This release adds three structural enforcements so the same classes fail loudly next time instead of relying on human review.

### Added
- **`.github/scripts/privacy-check.sh` Pass 11 - private repo identifiers (fires in byline-allowlisted files too).** The leak class Pass 1 misses: byline allows the maintainer's GitHub handle in README / CHANGELOG / LICENSE / etc, but `<handle>/<private-repo-suffix>` together advertises the existence and location of a private repo to the public. Pass 11 scans for bare private-repo slugs across ALL files, regardless of byline allowlist. Pattern loaded from new `PRIVATE_REPOS_PRIVATE` env var in `private-patterns.env` (gitignored) or CI secret with the same name. SKIPPED if unset (forks without private repos see no change).
- **`.githooks/pre-commit` + `scripts/install-git-hooks.sh` - opt-in pre-commit hook running the privacy scan locally.** Catches the leak before the commit SHA is even minted, not after the push reaches CI. Opt-in: `bash scripts/install-git-hooks.sh` installs (symlink by default so hooks auto-update with pulls; `--copy` for frozen snapshot; `--remove` to uninstall). Emergency bypass: `PUPSIK_SKIP_PRIVACY_CHECK=1 git commit ...`.
- **`scripts/brand-os-visual-gate.sh` - structural enforcement of Brand OS visual spec.** Catches favicon / theme-color drift against a locked Brand OS spec at build time, before the wrong-brand asset reaches a public URL. Two checks: (a) bytes-identity between `dashboard/favicon.svg` and the canonical favicon in the configured Brand OS clone, and (b) `mask-icon` + `theme-color` hex codes in `dashboard/build.py` match the canonical rect fill. `--fix` mode rewrites drifted files in place against the spec.
- **`scripts/morning-dashboard.sh` now invokes the visual gate before the VPS push.** Gate failure = skip VPS push (a wrong-brand favicon must never reach a public URL); local view still opens so the user sees the dashboard plus the diff. Bypass: `PUPSIK_SKIP_BRAND_GATE=1 bash scripts/morning-dashboard.sh`.

### Changed
- **`.github/workflows/privacy-check.yml`** - new `PRIVATE_REPOS_PRIVATE` secret wired alongside the other 5 pattern secrets. Set with: `gh secret set PRIVATE_REPOS_PRIVATE` in your fork.
- **`.github/scripts/private-patterns.env.example`** - new `PRIVATE_REPOS_PRIVATE` documentation block with an example.
- **`install.sh`** - now copies `scripts/brand-os-visual-gate.sh` and `scripts/install-git-hooks.sh` into the workspace (smart-merge, never clobbers local edits).
- **`README.md`** - documents the visual gate, the pre-commit hook installer, and the new private-repo privacy pass.

### Why
Three real incidents in one week, all the same shape: I pattern-matched something from memory (a file's bytes, a private repo URL, a brand colour) and shipped it without verifying against the live source of truth. Each one cost a hotfix PR. This release shifts those checks from "human discipline" to "build + commit + CI". Same mistake on the next attempt fails loudly and locally.

### Privacy invariants (new in this release)
- The private-patterns.env.example template ships with the new `PRIVATE_REPOS_PRIVATE` slot empty so forks without private repos see no change.
- `scripts/brand-os-visual-gate.sh` reads ONLY local files: a Brand OS clone (detected via `BRAND_OS_PATH` env or convention) and the local `dashboard/`. No network calls.
- The pre-commit hook re-uses the existing privacy-check.sh script unchanged - it does not introduce new patterns, just runs the existing scan earlier in the workflow.
- Privacy check 11/11 PASS (`--include-untracked`).

### Notes
- The pre-commit hook is opt-in to avoid surprising new clones. Existing users running `bash tools/update.sh` pick up the hook files but must run `bash scripts/install-git-hooks.sh` once to enable.
- The Brand OS visual gate is also opt-in by configuration: with no Brand OS clone detected, it prints a yellow "SKIPPED" line and exits 0. Forks with their own Brand OS clone (via env var, symlink, or convention) automatically get drift enforcement.
- Bump VERSION 2026-05-20.2 -> 2026-05-20.3.

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
- **`tools/brand_os.py`** - integration helper for an opt-in **Brand OS** - a versioned repo (keep it private; the canon is your competitive advantage) holding your brand voice, positioning canon, persuasion tactics, anti-patterns, evidence library, and templates - PLUS a Python CLI for structured retrieval over the canon. The helper detects a Brand OS via three discovery paths (env var `BRAND_OS_PATH` > `~/.brand-os` symlink > auto-detect under `~/Desktop/claude/projects/*-brand-os`) and exposes a thin pass-through CLI: `status` / `is-configured` / `invoke <subcommand> ...`. If no Brand OS is configured, the helper exits cleanly and the customer-comms rules fall back to their inline canon - so the toolkit works the same as before.

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
