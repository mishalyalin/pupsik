# Upgrading

## If you're already on an older version

You have a `~/Desktop/claude/` workspace from a previous install. You have a `CLAUDE.md`, a `memory/` directory, a `contacts.db`, probably some rules and outputs you've added. You want the new stuff without losing what you've built.

This doc covers what gets preserved, what gets replaced, and the one-time steps for each release back to Phase 2. If you're installing for the first time, go to [`README.md`](README.md) instead.

## TL;DR: just run `tools/update.sh`

If you cloned with git:

```bash
cd ~/pupsik           # or wherever you cloned it
git pull              # fetch latest main
bash tools/update.sh  # smart-merges everything that should auto-update
```

`update.sh` smart-merges the toolkit's Python tools (`contacts_db.py`, `memory_search.py`, `note.py`, `doctor.py`, `enrichment_schema_migrate.py`, `flag_russian_speakers.py`, `now.py`, `note_graph.py`, `note_graph_schema.py`, `rules.py`), hooks, the critical-rules template (append-only), and feedback templates. It will NEVER touch your `CLAUDE.md`, your `contacts.db`, or anything you've written under `memory/`, `briefings/`, or `outputs/`.

Scheduled-task templates (the optional weekly enrichment cron) are NOT auto-installed - they're opt-in. The install command is in "Per-release one-time steps" below.

If you didn't clone with git, re-download the repo and run `bash install.sh --update-only` for the same smart-merge behaviour without the git pull.

## What's preserved

Nothing the upgrade touches deletes data. Specifically:

- **`data/contacts.db`** - your SQLite contact graph. Untouched. All contacts, companies, interactions, links, custom columns: kept.
- **`data/chroma/`** - your existing ChromaDB index. Will be re-indexed once with the new code; the re-index is idempotent (uses `coll.upsert`), so duplicates are not created.
- **`CLAUDE.md`** - your personalized version. Untouched.
- **`memory/*.md`** - your existing memory files (people profiles, project notes, learnings, custom feedback rules). Untouched.
- **`~/.claude/rules/critical-rules.md`** - your existing rules file. The installer will *append* a pointer to the new capture-knowledge rule if it isn't already referenced; it does not overwrite the file.
- **`~/.claude/projects/<slug>/memory/feedback_*.md`** - your existing feedback rules. Untouched.
- **`outputs/`, `briefings/`, `journal/`** - anything you've generated. Untouched.

## What gets replaced

The installer overwrites a small, known set of files. Each replaced file is backed up to `<file>.bak.<timestamp>` first, so rollback is one `mv` away.

- **`tools/memory_search.py`** - replaced. Gains:
  - 5 new ChromaDB collections (briefings, outputs, journal, knowledge, research) on top of the existing 4 (contacts, interactions, memory_files, chat_archives). Total: 9. Note: the `knowledge` collection holds both `memory/learnings/` and `memory/decisions/` files in one searchable index.
  - `coll.upsert` everywhere - re-indexing is idempotent and safe to re-run.
  - `index --file <path>` - surgical single-file reindex (~50ms) instead of rebuilding the whole index.
  - Concurrency-safe lockfile with stale TTL - parallel reindex calls no longer deadlock.
  - Diff-based stale-chunk pruning - when a file shrinks, old chunks get removed instead of lingering.
  - 2026-05-08: dedup fix - chat-archive reindex no longer crashes with `DuplicateIDError` on identical filenames in different directories.

- **`tools/note.py`** - new file (didn't exist before). Captures a learning, decision, or research note in-flight with one command. Upserts by title - re-capturing the same topic refreshes the existing note instead of creating a duplicate. 2026-05-07 added a `friction` subcommand for capturing repeat-correction patterns (severity-tagged, counter-incremented).

- **`tools/doctor.py`** (new 2026-05-07) - deterministic health-check + safe-auto-fix tool. 13 checks across 3 subcommands (`check`, `fix-safe`, `orphans`). Catches stale lock files, broken symlinks, ChromaDB orphan rows, oversized CLAUDE.md / MEMORY.md, dangling memory pointers. SAFE-ops only - never LLM content rewrites.

- **`tools/enrichment_schema_migrate.py`** (new 2026-05-08, updated 2026-05-09) - idempotent migration adding the 12 enrichment columns to your `contacts.db` (`linkedin`, `twitter`, `github`, `website`, `instagram`, `bio`, `enrichment_source`, `enrichment_date`, `enrichment_confidence`, `last_enriched`, `relationship_context`, `tg_manual_paste_recommended`). Re-runs are safe; only adds missing columns.

- **`tools/flag_russian_speakers.py`** (new 2026-05-09) - multi-signal heuristic that flags contacts likely to chat with you on Telegram. Used by Step 0.5 of the contact-enrichment-weekly cron (or runnable ad-hoc). Idempotent (only flips 0 to 1). Optional `$RUSSIAN_CONTEXT_COMPANIES` env var enables company-name-based flagging.

- **New mandatory rule: capture-knowledge-in-flight** - installed to `~/.claude/projects/<slug>/memory/feedback_capture_knowledge.md`. Tells Claude to call `note.py` the moment an insight surfaces, not when the topic closes.

- **2026-05-07 feedback rules** added under `memory_templates/`:
  - `feedback_friction_protocol.md` - operating rule for `note.py friction`
  - 4 cross-cutting Output Rules in `memory_templates/feedback_output_rules.md` (Deterministic Links, No Slop, Exact Phrasing Preservation, Title Quality)
  - All adapted from gbrain (Garry Tan, MIT). See `THIRD_PARTY_ATTRIBUTIONS.md`.

- **2026-05-08 feedback rule** added: `feedback_contact_enrichment_weekly.md` - operating rule for the optional weekly contact-enrichment cron. 2026-05-09 updated to 4-pass (Pass 4 = email + WhatsApp correspondence scan).

- **`~/.claude/rules/critical-rules.md`** - receives one-line pointers for each new rule, appended at the end of the rules section if not already present (existing pointers are never duplicated).

## One-time migration steps

### Phase-2 baseline (apply first if you haven't already)

1. **Run the installer.** From the unpacked package directory:

   ```bash
   bash pupsik/install.sh
   ```

   The installer detects an existing workspace, backs up files it intends to overwrite (`tools/memory_search.py.bak.YYYYMMDD-HHMMSS` and so on), and then writes the new versions.

2. **Run a one-off full reindex** to populate the 5 new ChromaDB collections from your existing markdown directories:

   ```bash
   python3 ~/Desktop/claude/tools/memory_search.py index
   ```

   This rebuilds all 9 collections from scratch. It's idempotent thanks to `coll.upsert`, so it's safe to interrupt and re-run. Expect roughly 90 seconds depending on how many files you have.

3. **(Optional) Verify the new memory layer is healthy:**

   ```bash
   python3 ~/Desktop/claude/tools/memory_search.py wake-up
   ```

   If it prints sensible context - recent interactions, active topics, contacts gone silent - you're good. If it errors or returns nothing, see Troubleshooting below.

4. **(Optional) Try the new capture rule** to confirm `note.py` is wired correctly:

   ```bash
   python3 ~/Desktop/claude/tools/note.py learning "Test capture" "verifying note.py installed correctly"
   ```

   This writes a learning note and surgically reindexes it (~50ms). You can verify it by searching:

   ```bash
   python3 ~/Desktop/claude/tools/memory_search.py search "test capture"
   ```

   Then delete the test note from `~/Desktop/claude/memory/learnings/` if you don't want it kept.

## Per-release one-time steps

If you're already on Phase-2 baseline, the steps below get you current with each subsequent release.

### 2026-05-19 release: PRIMARY rule (verify-don't-imagine) + rules.py retrieval tool + 4 new feedback rules

This release adds a NEW top-priority rule ("NEVER IMAGINE, ALWAYS VERIFY") that sits above every other MANDATORY protocol, plus a tool (`rules.py`) for pulling full rule content into a session on demand, plus 4 supporting rules (check-model-first, verify-don't-imagine-external-brand, marketing-panel-default, no-jargon).

No breaking changes. All existing flows continue to work. No new pip dependencies.

1. **Run the smart-merge update** (picks up `rules.py`, the 5 new feedback templates, and the updated `critical-rules.md` template):

   ```bash
   bash tools/update.sh
   ```

2. **Confirm the PRIMARY rule now appears at the top of `~/.claude/rules/critical-rules.md`.** Open the file and look for the first bullet under "MANDATORY protocols" - it should read "NEVER IMAGINE, ALWAYS VERIFY" with a horizontal-rule separator below it. If your existing `critical-rules.md` was already customised, the smart-merge appends new pointers without overwriting your edits; you may need to manually move the new bullet to the top if you want the visual priority.

3. **Try the new retrieval tool:**

   ```bash
   python3 ~/Desktop/claude/tools/rules.py list                          # list all available rules
   python3 ~/Desktop/claude/tools/rules.py search "outbound email"        # see what gets pulled
   python3 ~/Desktop/claude/tools/rules.py read never_imagine_always_verify
   ```

4. **(Optional) Create an alias manifest** to boost retrieval on keywords your rule files don't explicitly mention:

   ```bash
   mkdir -p ~/Desktop/claude/data
   cat > ~/Desktop/claude/data/rules-aliases.json <<'EOF'
   {
     "feedback_never_imagine_always_verify": ["imagine", "verify", "fabricate", "fact check"],
     "feedback_check_model_first": ["model", "numbers", "revenue", "cac", "burn"]
   }
   EOF
   ```

   Aliases are optional - `rules.py` works on pure semantic search without one.

### 2026-05-14 release: date-aware session anchor + connection-aware memory graph

This release adds two big things: a date/timezone anchor injected at session start (kills the "Claude thinks today is six months ago" failure mode) and a connection-aware memory graph that surfaces clusters of related notes in `wake-up`. It also introduces the `VERSION` file + `update.sh` notification flow, so future upgrades show you a summary of what changed instead of just rsync output.

No breaking changes. All existing flows continue to work.

1. **Install the `networkx` dependency** (new, for the graph layer):

   ```bash
   pip3 install --user networkx
   ```

2. **Run the smart-merge update** (picks up `now.py`, `note_graph.py`, `note_graph_schema.py`, the new feedback rule, the updated `note.py` / `memory_search.py` / `update.sh`, and the new `session-start-reminder.sh` hook):

   ```bash
   bash tools/update.sh
   ```

   The schema migration (`note_graph_schema.py`) is idempotent and auto-runs on first `note.py` invocation after the upgrade. No manual step needed.

3. **Wire the SessionStart hook into `~/.claude/settings.json`.** Open `~/.claude/settings.json` and merge this into the `hooks` block (replace `<HOME>` with your actual home path):

   ```json
   {
     "hooks": {
       "SessionStart": [
         {
           "matcher": "*",
           "hooks": [
             {
               "type": "command",
               "command": "<HOME>/Desktop/claude/.claude/hooks/session-start-reminder.sh",
               "timeout": 5
             }
           ]
         }
       ]
     }
   }
   ```

   The hook is OPT-IN: nothing breaks if you skip it, but the date anchor only fires if you wire it.

4. **(Optional) Backfill the graph from your existing notes.** One-time pass that indexes everything you've written so far (takes 30-60 seconds depending on note count):

   ```bash
   python3 ~/Desktop/claude/tools/note_graph.py backfill
   ```

   After backfill, `memory_search.py wake-up` will start including the "Active clusters (last 7d)" block.

### 2026-05-07 release: doctor + friction protocol + Output Rules

After running `bash tools/update.sh` (or `install.sh --update-only`):

1. **Verify `doctor.py` installed:**

   ```bash
   python3 ~/Desktop/claude/tools/doctor.py check
   ```

   Should print 13 checks with PASS / WARN counts. If any WARN, run `doctor.py fix-safe` to apply safe repairs (broken symlinks, stale locks, ChromaDB orphans).

2. **Verify the friction subcommand:**

   ```bash
   python3 ~/Desktop/claude/tools/note.py friction --help
   ```

   Should print usage with `--severity {blocker|error|confused|nit}` and `--phase X --message Y`.

3. **(Optional) Browse the new Output Rules** at `~/.claude/projects/<your-slug>/memory/feedback_output_rules.md`. The 4 new rules (Deterministic Links, No Slop, Exact Phrasing Preservation, Title Quality) are referenced in `critical-rules.md` after the smart-merge.

### 2026-05-08 release: contact enrichment cron (3-pass) + ChromaDB dedup fix

The dedup fix in `memory_search.py` is automatic via the smart-merge - no action needed.

The contact-enrichment cron is opt-in. To enable:

1. **Migrate your contacts.db schema** (idempotent):

   ```bash
   python3 ~/Desktop/claude/tools/enrichment_schema_migrate.py
   ```

   Adds the 10 enrichment columns (linkedin / twitter / github / website / instagram / bio / enrichment_source / enrichment_date / enrichment_confidence / last_enriched). Reports already-present if the columns exist.

2. **Install the cron template:**

   ```bash
   mkdir -p ~/.claude/scheduled-tasks/contact-enrichment-weekly
   cp ~/pupsik/templates/scheduled-tasks/contact-enrichment-weekly.md.template \
      ~/.claude/scheduled-tasks/contact-enrichment-weekly/SKILL.md
   ```

3. **Register the cron** via Claude Code's scheduled-tasks MCP (cron `0 6 * * 0` = Sunday 06:00 local).

4. **(Optional) Run once manually** to populate `relationship_context` (Pass 4) and bio/social fields (Passes 1-3) for existing contacts:

   Just paste the contents of `~/.claude/scheduled-tasks/contact-enrichment-weekly/SKILL.md` into a fresh Claude session. The session will run the 4-pass enrichment on rows where `last_enriched IS NULL`.

### 2026-05-09 release: Pass 4 correspondence scan + Russian-speaker heuristic

The 2026-05-09 release adds Pass 4 to the contact-enrichment cron and a multi-signal Russian-speaker heuristic. If you ran the 2026-05-08 schema migrate, the columns were 10. The 2026-05-09 migrate adds 2 more (`relationship_context`, `tg_manual_paste_recommended`).

If you're a fresh installer post-2026-05-09, you only run the migrate once (it adds all 12 in one go).

For existing 2026-05-08 installers, the same migrate command is idempotent:

```bash
python3 ~/Desktop/claude/tools/enrichment_schema_migrate.py
# Output: "+ relationship_context", "+ tg_manual_paste_recommended", "= linkedin" ... etc
```

The cron template at `~/.claude/scheduled-tasks/contact-enrichment-weekly/SKILL.md` is NOT smart-merged automatically (templates under `templates/scheduled-tasks/` are opt-in cron tasks). To pick up the Pass 4 + Step 0.5 changes:

```bash
# Backup your existing SKILL.md if you made local edits
cp ~/.claude/scheduled-tasks/contact-enrichment-weekly/SKILL.md \
   ~/.claude/scheduled-tasks/contact-enrichment-weekly/SKILL.md.bak.$(date +%Y%m%d)

# Copy the 2026-05-09 template
cp ~/pupsik/templates/scheduled-tasks/contact-enrichment-weekly.md.template \
   ~/.claude/scheduled-tasks/contact-enrichment-weekly/SKILL.md
```

If you set the optional `$RUSSIAN_CONTEXT_COMPANIES` env var (comma-separated company-name substrings), Pass 4's signal 5 (company-based Russian-speaker flagging) is enabled. Leave unset to disable signal 5; the other 4 signals (Cyrillic / Latin transliteration / surname suffix / email domain) work without it.

Run a one-off seed of the heuristic against your existing contacts:

```bash
python3 ~/Desktop/claude/tools/flag_russian_speakers.py            # dry-run
python3 ~/Desktop/claude/tools/flag_russian_speakers.py --apply    # commit
```

The next scheduled cron run will then re-evaluate any rows where `last_enriched IS NULL` OR `< date('now', '-90 days')` and synthesize a private `relationship_context` summary into the local DB. The `relationship_context` column NEVER leaves your local DB - not in run summaries, not in briefings, not in any export.

### Backfill an existing enrichment

If you already had Passes 1-3 done (you ran the 2026-05-08 cron before the 2026-05-09 update) and want to backfill `relationship_context` for those rows without waiting for the next 90-day refresh:

```bash
sqlite3 ~/Desktop/claude/data/contacts.db \
  "SELECT COUNT(*) FROM contacts WHERE relationship_context IS NULL AND last_enriched IS NOT NULL"
```

If the count is non-zero, paste the cron `SKILL.md` into a fresh Claude session and ask it to "run Pass 4 only on the rows where `relationship_context IS NULL` and `last_enriched IS NOT NULL`". The session will execute the email + WhatsApp scan + synthesis without re-running Passes 1-3.

## What you should see post-upgrade

After Phase-2 baseline:
- `python3 ~/Desktop/claude/tools/memory_search.py stats` reports **9 collections** (was 4).
- `python3 ~/Desktop/claude/tools/note.py --help` returns a usage summary (the file exists and is executable).
- `cat ~/.claude/rules/critical-rules.md | grep capture` returns a one-line pointer to the capture-knowledge rule.
- `python3 ~/Desktop/claude/tools/contacts_db.py find "<any name you had before>"` still returns that contact. Old data is intact.

After 2026-05-07 release:
- `python3 ~/Desktop/claude/tools/doctor.py check` runs 13 deterministic health checks.
- `python3 ~/Desktop/claude/tools/note.py friction --help` shows the friction subcommand.
- `cat ~/.claude/rules/critical-rules.md | grep friction` returns a pointer to the friction protocol rule.

After 2026-05-08 release:
- `sqlite3 ~/Desktop/claude/data/contacts.db ".schema contacts" | grep -E "linkedin|relationship_context"` shows the new columns present (10 in the 2026-05-08 release, 12 in 2026-05-09).
- `ls ~/.claude/scheduled-tasks/contact-enrichment-weekly/` shows the cron `SKILL.md` if you opted in.
- ChromaDB reindex no longer crashes with `DuplicateIDError` (the 2026-05-08 dedup fix).

After 2026-05-09 release:
- `sqlite3 ~/Desktop/claude/data/contacts.db "PRAGMA table_info(contacts)" | grep -E "tg_manual_paste|relationship_context"` shows both new columns.
- `python3 ~/Desktop/claude/tools/flag_russian_speakers.py --help` returns the multi-signal heuristic docstring.
- After running `flag_russian_speakers.py --apply`, `sqlite3 ~/Desktop/claude/data/contacts.db "SELECT COUNT(*) FROM contacts WHERE tg_manual_paste_recommended = 1"` reports a non-zero count (depending on your network composition).

## Rollback

Every file the installer replaces gets backed up first. To restore a previous version:

```bash
ls ~/Desktop/claude/tools/*.bak.*
# pick the timestamp you want, then:
mv ~/Desktop/claude/tools/memory_search.py.bak.YYYYMMDD-HHMMSS \
   ~/Desktop/claude/tools/memory_search.py
```

If you want a clean rollback of the rule file too:

```bash
mv ~/.claude/rules/critical-rules.md.bak.YYYYMMDD-HHMMSS \
   ~/.claude/rules/critical-rules.md
```

The new ChromaDB collections (briefings, outputs, journal, knowledge, research) will simply sit unused - they don't break the old `memory_search.py`. To remove them too, delete `~/Desktop/claude/data/chroma/` and re-run the old indexer.

## Troubleshooting

- **`memory_search.py stats` still shows 4 collections** - the new file didn't get installed. Check `ls -la ~/Desktop/claude/tools/memory_search.py*` for a `.bak` file and a fresh `memory_search.py`. If only the `.bak` is there, re-run `install.sh`.
- **`note.py` not found** - same deal: re-run `install.sh` and confirm `~/Desktop/claude/tools/note.py` is present and executable (`chmod +x`).
- **Reindex hangs or errors with "lockfile stale"** - the new lockfile has a TTL and self-recovers. If it doesn't, delete `~/Desktop/claude/data/chroma/.lock` manually and re-run `index`.
- **`wake-up` returns empty** - your `CLAUDE.md` may have moved or your memory directory is empty. The wake-up command depends on having indexed content; run a full `index` first.
