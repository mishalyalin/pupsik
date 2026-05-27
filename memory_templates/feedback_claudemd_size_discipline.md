---
name: CLAUDE.md size discipline
description: Keep CLAUDE.md tight. Soft cap 450 lines, hard cap 600. Trim Last Updated past 7 days, prune resolved Upcoming items aggressively.
type: feedback
source: original
---

# CLAUDE.md size discipline: keep working memory tight, archive aggressively

## The rule

`CLAUDE.md` is working memory. Its purpose is to be re-read at session start with full attention by Claude. When it grows past ~440 lines, the rate of attention degrades and important `## Upcoming` items get diluted by `## Last Updated` changelog entries.

**Hard targets:**

- `## Last Updated` section: keep only the last 7 days of entries inline. Older = `memory/journal/claude-md-changelog.md` (already done by `dream-v2` if you've installed that skill).
- `## Upcoming` section: aggressively prune resolved items every cycle. A resolved item that's been in `## Upcoming` for >3 days post-resolution = bug, fix inline.
- `## Active Projects`: each project gets ONE entity, ONE state — never two rows for the same project with conflicting status. Grep `❌` and `✅` markers before adding to `## Upcoming` (per `feedback_dont_conflate_closed_projects.md` if you have it).
- Total file length: soft cap **450 lines**, hard cap **600 lines**. If hard cap is breached, the nightly reflection should trim before next briefing, OR the briefing should surface "CLAUDE.md-is-too-fat" as P0.

## Why

Two compounding problems:

1. **Context degradation cliff** (long-context model behaviour). On a 1M-context model, past ~400k tokens, attention degrades measurably. `CLAUDE.md` is one part of context but it's the part that gets re-read EVERY session — bloating it permanently subtracts attention from the actual task.
2. **Diluted action items.** When `## Upcoming` has 30 entries, the top 5 P0s get visually equal weight with the bottom 25 nice-to-haves. The user asks "what's important today" and Claude returns a flat list because everything looks equal in the file.

## Implementation

Already partially in place if you use the bundled skills:

- The nightly reflection (`dream-v2`) trims `## Last Updated` past 7 days to `memory/journal/claude-md-changelog.md`
- Architect proposals live in `memory/architect_proposals/latest.md`, NOT inline in `CLAUDE.md`

Additions per this rule:

- Nightly reflection also audits `## Upcoming` for resolved items each cycle (look for ✅ + DONE markers + state names already updated elsewhere). Trim resolved items into a quarterly `memory/journal/upcoming-archive-YYYY-Q.md`.
- The morning-briefing Architect Lens auto-flags when `CLAUDE.md` > 500 lines.
- When `CLAUDE.md` > 600 lines, treat as INFRASTRUCTURE DEBT: same-day rewrite Pass.

## Triggers in current session work

If during a session Claude sees:

1. `## Upcoming` item is the same one that was in the brief 3 days ago AND state has changed → update item OR archive
2. A new `## Last Updated` entry is being written, oldest pre-7-day entry should be cut to changelog automatically
3. `CLAUDE.md` size hits 500 lines → flag to the user at end of session

## Source

r/ClaudeAI viral "11 things I wish someone had told me about Claude Code" thread (Apr 2026) + marmelab mirror — "Tip 6: Keep CLAUDE.md under 200 lines" (most real-world stacks legitimately need more because of multi-project / multi-jurisdiction context, but the discipline of trimming applies).
