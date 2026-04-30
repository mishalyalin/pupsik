# Upgrading from a Previous Version

## Who this is for

You're a user on a previous version of this toolkit. You already have a
Claude Code workspace at `$HOME/Desktop/claude/` from an earlier release.
You have a `CLAUDE.md`, a `memory/` directory, a `data/contacts.db`, and
probably some custom rules and outputs you've accumulated. You want the new
pieces — the 9-collection indexer, `note.py`, the capture-knowledge rule,
idempotent reindex, surgical single-file reindex — without losing your data.

This document covers what an upgrade preserves, what it replaces, and the
one-time steps to get current. If you're installing for the first time, see
[`README.md`](README.md) instead.

## What's preserved

Nothing the upgrade touches deletes data. Specifically:

- **`data/contacts.db`** — your SQLite contact graph. Untouched. All contacts, companies, interactions, links, custom columns: kept.
- **`data/chroma/`** — your existing ChromaDB index. Will be re-indexed once with the new code; the re-index is idempotent (uses `coll.upsert`), so duplicates are not created.
- **`CLAUDE.md`** — your personalized version. Untouched.
- **`memory/*.md`** — your existing memory files (people profiles, project notes, learnings, custom feedback rules). Untouched.
- **`~/.claude/rules/critical-rules.md`** — your existing rules file. The installer will *append* a pointer to the new capture-knowledge rule if it isn't already referenced; it does not overwrite the file.
- **`~/.claude/projects/<slug>/memory/feedback_*.md`** — your existing feedback rules. Untouched.
- **`outputs/`, `briefings/`, `journal/`** — anything you've generated. Untouched.

## What gets replaced

The installer overwrites a small, known set of files. Each replaced file is backed up to `<file>.bak.<timestamp>` first, so rollback is one `mv` away.

- **`tools/memory_search.py`** — replaced. Gains:
  - 5 new ChromaDB collections (briefings, outputs, journal, knowledge, research) on top of the existing 4 (contacts, interactions, memory_files, chat_archives). Total: 9. Note: the `knowledge` collection holds both `memory/learnings/` and `memory/decisions/` files in one searchable index.
  - `coll.upsert` everywhere — re-indexing is idempotent and safe to re-run.
  - `index --file <path>` — surgical single-file reindex (~50ms) instead of rebuilding the whole index.
  - Concurrency-safe lockfile with stale TTL — parallel reindex calls no longer deadlock.
  - Diff-based stale-chunk pruning — when a file shrinks, old chunks get removed instead of lingering.

- **`tools/note.py`** — new file (didn't exist before). Captures a learning, decision, or research note in-flight with one command. Upserts by title — re-capturing the same topic refreshes the existing note instead of creating a duplicate.

- **New mandatory rule: capture-knowledge-in-flight** — installed to `~/.claude/projects/<slug>/memory/feedback_capture_knowledge.md`. Tells Claude to call `note.py` the moment an insight surfaces, not when the topic closes.

- **`~/.claude/rules/critical-rules.md`** — receives a one-line pointer to the new rule, appended at the end of the rules section if not already present.

## One-time migration steps

1. **Run the installer.** From the unpacked package directory:

   ```bash
   bash setup-package/install.sh
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

   If it prints sensible context — recent interactions, active topics, contacts gone silent — you're good. If it errors or returns nothing, see Troubleshooting below.

4. **(Optional) Try the new capture rule** to confirm `note.py` is wired correctly:

   ```bash
   python3 ~/Desktop/claude/tools/note.py learning "Test capture" "verifying note.py installed correctly"
   ```

   This writes a learning note and surgically reindexes it (~50ms). You can verify it by searching:

   ```bash
   python3 ~/Desktop/claude/tools/memory_search.py search "test capture"
   ```

   Then delete the test note from `~/Desktop/claude/memory/learnings/` if you don't want it kept.

## What you should see post-upgrade

- `python3 ~/Desktop/claude/tools/memory_search.py stats` reports **9 collections** (was 4).
- `python3 ~/Desktop/claude/tools/note.py --help` returns a usage summary (the file exists and is executable).
- `cat ~/.claude/rules/critical-rules.md | grep capture` returns a one-line pointer to the new capture-knowledge rule.
- `python3 ~/Desktop/claude/tools/contacts_db.py find "<any name you had before>"` still returns that contact. Old data is intact.

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

The new ChromaDB collections (briefings, outputs, journal, knowledge, research) will simply sit unused — they don't break the old `memory_search.py`. To remove them too, delete `~/Desktop/claude/data/chroma/` and re-run the old indexer.

## Troubleshooting

- **`memory_search.py stats` still shows 4 collections** — the new file didn't get installed. Check `ls -la ~/Desktop/claude/tools/memory_search.py*` for a `.bak` file and a fresh `memory_search.py`. If only the `.bak` is there, re-run `install.sh`.
- **`note.py` not found** — same deal: re-run `install.sh` and confirm `~/Desktop/claude/tools/note.py` is present and executable (`chmod +x`).
- **Reindex hangs or errors with "lockfile stale"** — the new lockfile has a TTL and self-recovers. If it doesn't, delete `~/Desktop/claude/data/chroma/.lock` manually and re-run `index`.
- **`wake-up` returns empty** — your `CLAUDE.md` may have moved or your memory directory is empty. The wake-up command depends on having indexed content; run a full `index` first.
