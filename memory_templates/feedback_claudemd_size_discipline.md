---
name: CLAUDE.md size discipline
description: Keep CLAUDE.md tight. Cap by TOKENS (soft 12k, hard 20k), not lines - a line cap misses the failure. Trim Last Updated past 7 days, prune resolved Upcoming items aggressively.
type: feedback
source: original
---

# CLAUDE.md size discipline: keep working memory tight, archive aggressively

## The rule

`CLAUDE.md` is working memory. Its purpose is to be re-read at session start with full attention by Claude. When it grows, `## Last Updated` changelog entries dilute the `## Upcoming` items that actually need action - and every token it costs is subtracted from your working room for the rest of the session.

**Cap by tokens, not by lines.** A line cap does not measure the thing that hurts. Measured failure, 2026-08-12: a real `CLAUDE.md` reached **244,364 characters (about 93,000 tokens) in 301 lines** - far past any sane budget while sitting at *half* the old 600-line "hard cap", so the rule never fired once. Markdown bullets are unbounded in width; line count is not a proxy for size.

**Hard targets:**

- `## Last Updated` section: keep only the last 7 days of entries inline. Older = `memory/journal/claude-md-changelog.md` (already done by `dream-v2` if you've installed that skill). One dense entry can be 7-11k characters by itself, so a stack of six is the likeliest single cause of a bloated file.
- `## Upcoming` section: aggressively prune resolved items every cycle. A resolved item that's been in `## Upcoming` for >3 days post-resolution = bug, fix inline.
- `## Active Projects`: each project gets ONE entity, ONE state — never two rows for the same project with conflicting status. Grep `❌` and `✅` markers before adding to `## Upcoming` (per `feedback_dont_conflate_closed_projects.md` if you have it).
- Total size: soft cap **~12k tokens**, hard cap **~20k tokens** (roughly 45k / 75k characters of mixed English - Cyrillic and CJK cost about 1.7x more tokens per character, so their character equivalent is lower). Measure, don't eyeball:

  ```bash
  python3 tools/context_budget.py files
  ```

  If the hard cap is breached, the nightly reflection should trim before the next briefing, OR the briefing should surface "CLAUDE.md-is-too-fat" as P0.
- **Trim by archiving, never by deleting.** Compress a heavy bullet to a one-line pointer and move the full text verbatim into `memory/journal/`. A trim that loses a live obligation - an unpaid invoice, a deadline, a reference number - costs far more than the tokens it saved. Diff against a backup afterwards and confirm every future-dated item survived somewhere.

## Why

Two compounding problems:

1. **It is spent before you start.** `CLAUDE.md` is part of the fixed session-start load, alongside the system prompt, tool schemas, MCP server instructions and the skills list. Auto-compaction fires against the model's real context window, so working room = that window minus the fixed load. When the fixed load creeps up on the window you get several "compacted - saved N tokens" in a row and then "context window is full", because each summary immediately re-fills. Measure both ends with `python3 tools/context_budget.py all`.
2. **Attention, not just arithmetic.** Long-context attention degrades as a window fills, and `CLAUDE.md` is the part re-read EVERY session - bloating it permanently subtracts attention from the actual task.
3. **Diluted action items.** When `## Upcoming` has 30 entries, the top 5 P0s get visually equal weight with the bottom 25 nice-to-haves. The user asks "what's important today" and Claude returns a flat list because everything looks equal in the file.

## Implementation

Already partially in place if you use the bundled skills:

- The nightly reflection (`dream-v2`) trims `## Last Updated` past 7 days to `memory/journal/claude-md-changelog.md`
- Architect proposals live in `memory/architect_proposals/latest.md`, NOT inline in `CLAUDE.md`

Additions per this rule:

- Nightly reflection also audits `## Upcoming` for resolved items each cycle (look for ✅ + DONE markers + state names already updated elsewhere). Trim resolved items into a quarterly `memory/journal/upcoming-archive-YYYY-Q.md`.
- The morning-briefing Architect Lens auto-flags when `CLAUDE.md` passes the soft cap (`context_budget.py files`).
- Past the hard cap, treat as INFRASTRUCTURE DEBT: same-day rewrite pass, archiving into `memory/journal/` rather than deleting.

## Triggers in current session work

If during a session Claude sees:

1. `## Upcoming` item is the same one that was in the brief 3 days ago AND state has changed → update item OR archive
2. A new `## Last Updated` entry is being written, oldest pre-7-day entry should be cut to changelog automatically
3. `CLAUDE.md` passes the soft token cap → flag to the user at end of session
4. A `## Last Updated` section holds more than one entry per 7-day window → the nightly trim is not running; check it before writing another entry

## Source

r/ClaudeAI viral "11 things I wish someone had told me about Claude Code" thread (Apr 2026) + marmelab mirror — "Tip 6: Keep CLAUDE.md under 200 lines" (most real-world stacks legitimately need more because of multi-project / multi-jurisdiction context, but the discipline of trimming applies).
