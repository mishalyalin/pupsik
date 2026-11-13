# Upgrading

You have a `~/Desktop/claude/` workspace from an earlier install: a `CLAUDE.md`, a `contacts.db`, probably rules and outputs of your own. This page covers what an update keeps, what it changes, and the one-time steps per release. Installing for the first time? Go to [`README.md`](README.md).

## TL;DR: run `tools/update.sh`

```bash
cd ~/code/pupsik      # or wherever you cloned it
bash tools/update.sh  # pulls, then smart-merges everything that should auto-update
```

`update.sh` smart-merges `contacts_db.py`, `enrichment_schema_migrate.py`, `now.py`, the session-start hook, the feedback rules in `~/Desktop/claude/rules/` and the critical-rules template (append-only). It never touches your `CLAUDE.md`, `contacts.db`, `memory/`, `outputs/`, Claude's built-in memory folder or your Claude settings.

Didn't clone with git? Download the repo again and run `bash install.sh --update-only`.

## What's kept

- **`data/contacts.db`** - contacts, interactions, links, custom columns.
- **`CLAUDE.md`** and everything under `memory/`, `outputs/`, `briefings/`, `research/`.
- **`~/.claude/rules/critical-rules.md`** - never replaced; new rule lines are appended under a dated header.
- **Claude's built-in memory** (`~/.claude/projects/<slug>/memory/`) and **`~/.claude/settings.json`** values such as `model`, `autoCompactWindow`, `env` and permissions. Pupsik doesn't change them.
- **Tools pupsik no longer ships** (see 2026-11-13 below) stay in your workspace and keep working. They just stop getting updates.

Every file an update replaces is backed up first as `<file>.bak.<timestamp>`; a file you changed gets the new version next to it as `<file>.new` instead.

## Per-release one-time steps

### 2026-11-13 release: slimmed to what Claude can't do itself

Claude now has built-in memory, scheduled tasks, connectors and artifacts, so pupsik stopped shipping:

- the ChromaDB search and note layer: `memory_search.py`, `note.py`, `note_graph.py`, `note_graph_schema.py`, `rules.py`, `templates/wakeup_l0.txt.template`, `memory_templates/{world_knowledge,user_context}/`
- the dashboard (`dashboard/`, `scripts/morning-dashboard.sh`, `tools/check-update.sh`) and the morning-briefing skill template
- the Brand OS bridge (`brand_os.py`, `scripts/brand-os-visual-gate.sh`)
- the rules that depended on those: `feedback_capture_knowledge`, `feedback_marketing_panel_default`, `feedback_briefing_pass3_direct_audit`, `feedback_session_retro`

**Your copies are not deleted.** If you use `memory_search.py` or the dashboard, they keep working from your workspace. Delete them yourself when you're done with them, along with `data/chroma/` and the `chromadb` pip package.

**Rules moved out of Claude's memory folder.** Older versions installed the `feedback_*.md` rules into `~/.claude/projects/<slug>/memory/`, which is Claude's own memory folder. New installs put them in `~/Desktop/claude/rules/`. On update:

- pupsik's backup leftovers in Claude's memory folder (`feedback_*.md.bak.*`, `feedback_*.md.new` for pupsik's rule names only) are moved to `~/.claude/pupsik-removed-<date>/claude-memory/`;
- your rule files are left where they are, and rule updates are skipped with a note, until you move them:

  ```bash
  python3 ~/code/pupsik/tools/slim_migrate.py --move-rules "$HOME" "$HOME/Desktop/claude"
  ```

  This moves only the rule files pupsik ships (your own rules stay in Claude's memory folder) and adds one line to `critical-rules.md` saying where they live now. If a file already exists in `~/Desktop/claude/rules/`, it is left in place and reported, so you can compare the two by hand.

**Claude settings are no longer edited.** The 2026-09 cleanup used to remove `autoCompactWindow` and `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE` from `~/.claude/settings.json`. Those are Claude settings you may have set on purpose, so the cleanup now only removes pupsik's own retired compact hooks.

**Session hook.** It no longer starts a background update check (that fed the dashboard). It's replaced automatically if it's the pupsik one.

**`CLAUDE.md`.** Yours is never touched. If it still tells Claude to run `memory_search.py wake-up` at session start, remove that line, or keep it if you still use the tool. `templates/CLAUDE.md.template` shows the short version.

### 2026-09-23 release: slimmed for Claude 5-era models

`bash tools/update.sh` runs a one-time cleanup on the first run, even if your `update.sh` is older than this release. It:

- backs up `~/.claude/settings.json` to `~/.claude/pupsik-removed-<date>/settings.json.bak`, then removes the PreCompact / PostCompact hook entries that point at pupsik's `pre-compact.sh` / `post-compact.sh`. Your own hooks and settings stay. (Up to 2026-11-13 it also removed `autoCompactWindow` and `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE`; it no longer does.)
- moves the retired files into `~/.claude/pupsik-removed-<date>/` (the two compact hooks, `context_budget.py`, `claude_md_trim.py`, `doctor.py`, `mcp_profile.py`).
- replaces `.claude/hooks/session-start-reminder.sh` only if it is the pupsik one (keeps a `.bak`).
- prints what it did. Running it again prints "nothing to do".

`critical-rules.md` merges are append-only, so old pointer lines stay until you delete them. Compare with `templates/critical-rules.md.template` and prune by hand if you want the short version.

### Older releases

See [`CHANGELOG.md`](CHANGELOG.md). Most of what they added has since been removed; the one opt-in piece still shipped is the contact-enrichment cron below.

## Opt-in: weekly contact enrichment

Scheduled-task templates are never installed automatically.

1. Add the enrichment columns to your contact DB (idempotent, safe to re-run):

   ```bash
   python3 ~/Desktop/claude/tools/enrichment_schema_migrate.py
   ```

2. Install or refresh the task:

   ```bash
   mkdir -p ~/.claude/scheduled-tasks/contact-enrichment-weekly
   # back up your copy first if you edited it
   cp ~/code/pupsik/templates/scheduled-tasks/contact-enrichment-weekly.md.template \
      ~/.claude/scheduled-tasks/contact-enrichment-weekly/SKILL.md
   ```

3. Register it with Claude Code's scheduled tasks. The operating rule is `feedback_contact_enrichment_weekly.md`.

The `relationship_context` column never leaves your local DB - not in run summaries, briefings or any export. Telegram is never read automatically.

## Rollback

```bash
ls ~/Desktop/claude/tools/*.bak.* ~/Desktop/claude/rules/*.bak.*
# pick the timestamp you want, then for example:
mv ~/Desktop/claude/tools/contacts_db.py.bak.YYYYMMDD-HHMMSS ~/Desktop/claude/tools/contacts_db.py
mv ~/.claude/rules/critical-rules.md.bak.YYYYMMDD-HHMMSS ~/.claude/rules/critical-rules.md
```

Anything a migration moved is in `~/.claude/pupsik-removed-<date>/`; move it back to undo. Rules moved with `--move-rules` go back with:

```bash
mv ~/Desktop/claude/rules/feedback_*.md ~/.claude/projects/<slug>/memory/
```

## Troubleshooting

- **"Your pupsik rules are in Claude's memory folder"** on update - expected after the 2026-11-13 release. Run the `--move-rules` command above, or ignore it and keep your rules where they are (they just won't get updates).
- **Claude doesn't know your rules** - check `~/.claude/rules/critical-rules.md` exists and the files it points at are in `~/Desktop/claude/rules/` (or, if you didn't move them, Claude's memory folder).
- **`update.sh` refuses to run** - you have uncommitted edits in the clone. Commit or stash them, or run `bash tools/update.sh --force`.
