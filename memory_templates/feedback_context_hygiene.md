---
name: Context hygiene - /clear over patching
description: When Claude hallucinates or goes off-track twice in a row, /clear and restart with a fresh self-contained prompt. Don't keep patching through degraded context.
type: feedback
source: original
---

# Context hygiene: `/clear` + restart over patching

## The rule

When Claude hallucinates, misclassifies, or goes off-track **twice in a row** in a session, the right move is `/clear` + restart with a fresh prompt, NOT continue patching with more turns of correction.

**Hard triggers for mandatory `/clear`:**

1. Two consecutive hallucinated facts (e.g. invented dates, wrong numbers, fabricated names) in the same session
2. Two consecutive subagent misclassifications (e.g. subagent attributed an inbox message to the wrong actor) within a single pass
3. Same misunderstanding of intent repeated after correction (the user says "no, X" and Claude does Y, then says "OK X" but does Z that's still not X)
4. Autocompact has fired ≥2 times in the session AND Claude is still working on the original task — context has been re-summarised too many times, fidelity is degraded

## Why this is non-negotiable

Claude has no introspection on its own degradation. Past ~400k tokens of long-context, the model's attention to instructions degrades silently — without an error message, without a warning. The behaviour LOOKS like normal Claude but with worse facts and more drift.

When this kicks in, more turns of "no, I meant X" don't unstick it — they add MORE context that the degraded model then has to attend to alongside the actual task. The error compounds.

`/clear` resets the cycle: re-enter with a tight self-contained prompt + the necessary context + a request that doesn't depend on remembered turns. Often closes the original problem in 2-3 fresh turns vs another 10-15 increasingly-frustrated patch turns.

## What to encode in the fresh prompt

Before `/clear`, write a self-contained restart prompt that:

- Names the goal (1 sentence)
- Lists facts/files needed (paths + 1-line each)
- States what was tried and failed (1 sentence)
- Asks the specific question/action

Don't include "let me explain what we discussed". Don't include the full conversation history. Don't include emotional context ("I'm frustrated"). Treat it as a brief to a junior engineer who's never seen this conversation — per `feedback_junior_engineer_plan_test.md`.

## Anti-pattern: keep arguing through degraded context

If Claude is hallucinating + you correct it + it hallucinates differently + you correct it again + ...: STOP. This is the degradation cliff. Continuing burns time and frustration without producing output. Three correction turns is the absolute max before mandatory `/clear`.

## Connection to other rules

- `feedback_never_imagine_always_verify.md` — context degradation manifests as MORE imagination. When you catch one hallucination, that's a yellow flag. Two = mandatory clear.
- `feedback_capture_knowledge.md` — capture WHAT degraded + which session length triggered it BEFORE `/clear` so the pattern can be encoded.
- `feedback_session_retro.md` — at session end, if you `/clear`ed mid-session, that's a session-end retro item.

## Source

r/ClaudeAI viral "11 things I wish someone had told me about Claude Code" thread (Apr 2026), tip on `/rewind` + `/clear` discipline.
