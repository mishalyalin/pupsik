---
name: AI Architect Lens - auto-apply
description: When the morning briefing's AI Architect Lens proposes system improvements, apply them immediately without asking. Just report what was done.
type: feedback
source: original
---

When the AI Architect Lens (or any reflective audit step) of a briefing/skill proposes concrete improvements to the system - SKILL.md edits, hook tweaks, memory file additions, MCP config fixes, briefing format updates - apply them in the same turn. Don't ask "should I?". Run a checker agent to validate, then report what shipped.

## Why

Architect Lens output is an observation made from inside the run. The data is fresh, the failure mode is concrete, and waiting until the next session to ask for permission loses the context window that made the proposal worth making.

Repeated "should I apply this?" prompts also train you to defer obviously-correct changes, which is the opposite of the goal.

## How to apply

- Architect Lens output -> immediate edit to whatever file/system the proposal targets (skills, hooks, memory, settings.json, scheduled tasks, etc.)
- Spawn a checker agent per the 2-agent rule (`feedback_always_two_agents.md`) to validate the edit doesn't break adjacent rules.
- Report 1-3 sentences: what was changed, where, why. No "do you want me to..."
- Treat this as a standing authorization for **system-level self-improvements proposed by Architect Lens specifically**.

## What this does NOT cover

This rule is narrow on purpose. It does NOT extend to:

- **Destructive ops** (rm, git reset, force push, drop table, etc.) - still need explicit ask.
- **External posts** (Slack, Telegram, email send, posting to forums) - still need explicit ask.
- **Large structural changes** (a new scheduled task, a new MCP server, a new feedback rule that didn't exist before) - those go into the architect proposals backlog (`feedback_architect_proposals_backlog.md`) as `status: open` for your sign-off. See "Interaction with the backlog" below.
- **Architect proposals that conflict with an existing MANDATORY rule** - flag the conflict instead of auto-applying.

## Interaction with the architect proposals backlog

The auto-apply rule and the backlog rule co-exist:

- **Auto-apply** applies to SMALL same-turn fixes: file rename, typo, missing pointer, stale `CLAUDE.md` fact, hook arg fix, etc.
- **Backlog** captures EVERYTHING for traceability - both the small auto-applied ones (status: applied) AND the larger structural / workflow / new-tool proposals that need your sign-off (status: open).

If unsure whether a proposal is auto-apply or backlog-only: write to backlog FIRST (status: open), then if you proceed to auto-apply, update status to applied + applied_at. Never silently apply without recording.

## Capture follow-up

If the improvement reflects a generalizable pattern, capture as `note.py learning` so future sessions can find it.

## Precedent shape

This rule comes from observing the recurring pattern: an audit step proposes two improvements, the user says "just apply it, only tell me what you did." After that conversation happens twice, the right move is to make it a standing rule and stop asking.
