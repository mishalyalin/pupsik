---
name: Architect proposals backlog
description: Every Architect-Lens output, nightly research finding, and ad-hoc architectural insight gets persisted to the architect proposals backlog. Backlog is the canonical surface for "things to consider doing to your workspace / workflows / toolkit."
type: feedback
source: original
---

## What this rule says

Every Architect-Lens output, nightly reflection/research finding, and ad-hoc session architectural insight gets persisted to `~/Desktop/claude/memory/architect_proposals/latest.md` per the schema in `_PROTOCOL.md`. The backlog is the canonical surface for "things to consider doing to your workspace / workflows / toolkit."

The morning brief surfaces the top-3 open proposals each day. A nightly reflection skill (if you wire one) reviews ALL open proposals plus pulls new candidates from external sources of your choice - common picks are Reddit (e.g. r/ClaudeAI, r/LocalLLaMA, r/selfhosted), GitHub trending, HackerNews, the Claude Code release blog, and any specific repos you watch.

You confirm or reject proposals in subsequent briefs. Approved proposals go to the implementation queue. Rejected proposals get a 90-day re-propose suppression.

## When this rule fires

- During the morning brief's Architect Lens step: every proposal generated MUST be written to the backlog. Auto-applied ones (per `feedback_architect_auto_apply.md`) get `status: applied`. Larger ones get `status: open`.
- During any reflection / nightly research routine: external-research candidates get written to the backlog with `source: reflection-research` + URL + license check.
- During any ad-hoc session: if an Architect-Lens-style insight emerges, write to the backlog with `source: session-architect-lens`.

## Interaction with `feedback_architect_auto_apply.md`

Both rules co-exist. Auto-apply covers SMALL same-turn fixes (file rename, typo, missing pointer, stale fact in working memory, etc). The backlog captures EVERYTHING for traceability - both the small auto-applied ones AND the larger structural / workflow / new-tool proposals that need your sign-off.

If unsure whether a proposal is auto-apply or backlog-only: write to backlog FIRST (status: open), then if you proceed to auto-apply, update status to applied + applied_at. Never silently apply without recording.

## Privacy invariant

- Local only. NEVER include the backlog in a public export of your config / dotfiles.
- Briefings reformulate proposals into their own voice. Do NOT quote raw backlog text in the brief.
- Reflection-research findings reference public URLs; the URLs are public so they can be shown. Your specific workstreams are private; do not echo workstream context to external surfaces.

## What NOT to do

- Do NOT auto-apply large structural proposals (new scheduled task, new MCP, new feedback rule). Those go to backlog `status: open` for your sign-off. Recurring failure mode: building a sub-day cron from one isolated incident, then archiving it days later as over-fit to a single event. The corrective is: structural changes wait for explicit approval.
- Do NOT re-propose rejected items before 90 days from `rejected_at`. Suppress on source URL + substantially-identical title match.
- Do NOT bloat the backlog with low-confidence speculation. If `effort: large` AND `rationale` is "might be cool", don't write it. Backlog should be actionable, not aspirational.

## Files this rule references

- `~/Desktop/claude/memory/architect_proposals/_PROTOCOL.md` - full schema + lifecycle
- `~/Desktop/claude/memory/architect_proposals/latest.md` - current backlog
- Your morning briefing SKILL - writes to the backlog during the Architect Lens step
- Any nightly reflection / research SKILL you wire in - writes to the backlog during the research step
- `~/Desktop/claude/memory/THIRD_PARTY_ATTRIBUTIONS.md` - for reflection-research findings adapted to local code

## Provenance

`source: original`.

Trigger pattern that produces this rule: you find yourself wanting an audit step to autonomously scan external sources for ideas, propose them to you, and remember which ones you've already rejected so it stops surfacing the same noise.
