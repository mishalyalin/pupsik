# Architect Proposals Backlog - Protocol

Local-only memory of structural / workflow / tool proposals against your workspace. Both the morning briefing's Architect Lens and any reflective audit step (e.g. a nightly dream / reflection skill) write here. You review and approve in subsequent briefings.

This file is the contract between the writer (whichever skill is filing a proposal) and the reader (you, or any future audit step that scans open proposals).

## Lifecycle

1. **Proposed** - written here by morning brief Architect Lens, ad-hoc session Architect work, or a nightly reflection/research routine. Default `status: open`.
2. **Auto-applied** - if the proposal is a small same-turn fix under `feedback_architect_auto_apply.md`, it goes here with `status: applied` + `applied_at` already populated. Recorded for traceability, not for action.
3. **Open** - large enough to need your approval. Surfaces in the next-morning brief.
4. **Accepted** - you approved it. Goes into the implementation queue (handled in following sessions).
5. **Rejected** - you said no. Stays archived with `rationale_rejected` field. The reviewer will NOT re-propose for 90 days.
6. **Obsolete** - the reviewer determines the proposal no longer makes sense (workflow changed, problem already solved another way, etc).

## Schema

Each proposal is a YAML block in `latest.md` under one of the section headings (Open / Accepted-not-yet-implemented / Applied / Rejected / Obsolete).

```yaml
- id: arch-2026-05-11-001
  date_proposed: 2026-05-11
  source: morning-briefing | session-architect-lens | reflection-research
  source_url: <if external-research, URL or repo path>
  title: "Short noun phrase"
  description: |
    1-3 lines of what the proposal is.
  effort: small | medium | large
  status: open | accepted | applied | rejected | obsolete
  applied_at: <ISO 8601 with offset, if applied>
  accepted_at: <ISO 8601 with offset, if accepted but not yet applied>
  rejected_at: <ISO 8601 with offset, if rejected>
  rationale: |
    Why this proposal exists. What problem it addresses.
  why_relevant: |
    Which workstream this ties to. Be specific - "improves daily-briefing reliability", "reduces tax-prep manual work", "fixes the X integration", etc.
  attribution: |
    If derived from external OSS: source URL + author + license. Per THIRD_PARTY_ATTRIBUTIONS.md discipline.
  rationale_rejected: |
    (Only if rejected.) Why you said no. Used for 90-day re-propose suppression.
```

## ID convention

`arch-YYYY-MM-DD-NNN` where NNN is a 3-digit zero-padded counter for proposals filed on that date. Counter resets daily.

## Sections in latest.md

- `## Open` - awaiting your review
- `## Accepted (not yet implemented)` - approved, in implementation queue
- `## Applied` - already in production (small auto-applied + larger ones that were implemented)
- `## Rejected` - you said no, kept for 90-day re-propose suppression
- `## Obsolete` - no longer relevant

Each section sorted by `date_proposed` desc.

## Promotion rules

- Morning brief Architect Lens scans `Open` section for top 3 by (relevance x low-effort). Surfaces in the lens that matches the workstream affinity.
- Nightly reflection/research (if you wire one) reads ALL `Open` proposals plus runs new research. After review:
  - Stale proposals (>30 days open with no action) get one nudge in the next brief, then auto-archive as `Obsolete`.
  - External-research candidates flagged duplicate of an existing proposal get merged (one ID kept, the other marked obsolete).
  - 90-day suppression on rejected proposals: the reviewer will NOT surface the same source URL or substantially-identical title before 90 days from `rejected_at`.

## Archive

When `latest.md` exceeds 100 proposals OR end of calendar month, snapshot to `archive/YYYY-MM-DD.md` and clear all Applied/Rejected/Obsolete entries from `latest.md`. Keep all `open` and `accepted` proposals in `latest.md` indefinitely until they reach terminal state.

## Privacy

- Local only. NEVER include in any public export (e.g. a public version of your dotfiles).
- Briefings reformulate proposals into their own narrative voice - do NOT quote raw proposal text in the brief.
- If a proposal references private business data (specific balances, specific contacts, internal project codenames, etc) it stays in this backlog; the brief reformulates.

## Files this protocol touches

- READ/WRITE: `~/Desktop/claude/memory/architect_proposals/latest.md`
- WRITE (snapshot): `~/Desktop/claude/memory/architect_proposals/archive/YYYY-MM-DD.md`
- READ: workspace state for evaluating proposals (CLAUDE.md, MEMORY.md, scheduled tasks, etc)
- RUNS: any custom research routine you wire in (WebFetch + curl + gh CLI are all fair game)

## Wiring this up

Minimum viable wiring:

1. Add this directory (`memory/architect_proposals/`) with `_PROTOCOL.md` (this file) and `latest.md` (empty bootstrap with the 5 section headings).
2. Install `feedback_architect_proposals_backlog.md` so any audit step knows where to write.
3. Install `feedback_architect_auto_apply.md` if you also want small same-turn fixes to apply without prompting (the two rules co-exist - one captures everything for traceability, the other defines what may apply without sign-off).
4. Reference the backlog in your morning briefing skill: scan `Open` section top-3 and surface in the Architect lens. Write every Architect insight to the backlog before exiting.
5. Optional: if you run a nightly reflection / research skill, add a step that (a) reviews all open proposals for staleness or duplication, and (b) fetches new candidates from external sources (Reddit, HN, GitHub trending, the Claude Code blog, specific repos you watch). Filter against your own workstreams before adding to `Open`.

End of protocol.
