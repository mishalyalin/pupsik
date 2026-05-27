---
name: End-of-session retro
description: Before context dies at session end, run a 2-minute retro to capture what was learned. Then act on it (note.py + propose feedback rules + architect entries).
type: feedback
source: original
---

# End-of-session retro: capture what was learned before context dies

## The rule

At the end of any non-trivial Claude Code session (>30 min of work OR shipped a PR OR made a meaningful decision), run a 2-minute retro before closing:

- **What did I learn this session?** (technical insights, gotchas, false starts)
- **What surprised me?** (assumptions that broke, tools that worked unexpectedly, contradictions)
- **What should be encoded for next time?** (new feedback rule, decision note, learning note, architect proposal)

Then ACT on the retro: capture via `note.py learning|decision|research` for each item that scored "yes, this matters 3 weeks from now". Don't ask the user "should I capture this?" — `feedback_capture_knowledge.md` already covers that (default = capture).

## Why this is separate from `feedback_capture_knowledge.md`

`feedback_capture_knowledge.md` is about capturing AT THE MOMENT an insight emerges. This rule is about a sweep AT SESSION END catching insights that:

- Were too fuzzy to capture mid-flight ("there's something here, can't articulate yet")
- Got buried under follow-up work and forgotten
- Only became visible by accumulating across the session
- Are meta-patterns (e.g. "I keep falling into X failure mode")

Both rules live together. The moment-of-emergence capture is the primary mechanism; the end-of-session sweep is the safety net.

## What "session end" means

Triggers:

1. The user signals close ("ok done" / "that's enough" / explicit "close session")
2. Claude is about to send the final summary message
3. The compact threshold is about to hit (~50% of context per `feedback_default_workspace.md`) — last chance to capture before summary loses fidelity
4. A natural boundary (PR merged, decision made, problem solved, runbook delivered)

## Format of the retro

Inline, 30-60 seconds. Three bullets max under each header:

```
## Session retro

**Learned:**
- X about how Y interacts with Z (e.g. "library X trains on uploaded data by default")
- The W tool actually does V (e.g. "smart_merge_file's no-bak branch drops sidecars, doesn't overwrite")

**Surprised:**
- I assumed A but found B (e.g. "assumed product Y supports outbound, actually inbound-only")

**Encode:**
- New feedback rule: <one-line description>
- Update existing: <file + what changes>
- Architect proposal: <one-line description>
```

Then fire the appropriate `note.py` calls + propose feedback rule + propose architect entry. Don't just write the retro — execute on it.

## Why this matters

The recurring pattern this rule closes: end-of-session summaries are great storytelling but the structural lessons get diluted into prose. When you re-read a 1500-word session summary 2 weeks later, you remember the narrative but lose the "I should never read full files for cross-variant diff again" structural rule. Capturing the structural lesson in a 30-line `note.py learning` makes it semantically searchable + showable in future briefings.

## Source

r/ClaudeAI viral "11 things I wish someone had told me about Claude Code" thread (Apr 2026) + marmelab mirror — "Tip 9: Ask Claude what it learned and write to CLAUDE.md".
