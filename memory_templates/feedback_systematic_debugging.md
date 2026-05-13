---
name: systematic-debugging-rubric
description: When a bug needs to be fixed, follow a 4-phase rubric (Reproduce, Isolate, Diagnose, Fix) with hard gates between phases. No fix is proposed before isolation. No phase is skipped because "let me just try X and see if it works."
type: feedback
adapted-from: obra/superpowers
source-url: https://github.com/obra/superpowers/tree/main/skills/systematic-debugging
source-author: Jesse Vincent
source-license: MIT
imported: 2026-05-13
adaptation-type: adapted
---

# Systematic Debugging

Bugs get fixed by walking 4 phases in order. Hopping ahead breaks the rubric and produces fixes that mask the cause instead of removing it.

## Phase 1 - Reproduce

Get a deterministic repro on the current commit. Write down the exact command, input, environment, and observed-vs-expected delta. If the repro is flaky, that itself is the bug to chase first - intermittent failures hide their cause behind noise.

If the repro is not deterministic in under 30 minutes of trying, STOP and surface the problem to the user with what is known. Hope-driven fixes downstream of a flaky repro do not stick.

## Phase 2 - Isolate

Narrow the failure to the smallest surface that still reproduces. Strip away unrelated config, data, and code paths. Bisect git history if the bug used to work. State the result as an isolation claim, e.g. "fails on commit X but not X-1" or "fails when input Y is set but passes when omitted."

This phase produces an isolation statement. Without that statement, you cannot diagnose.

## Phase 3 - Diagnose

Now that the scope is known, find the actual cause. Read the relevant code/config/data. State the root cause as a falsifiable claim: "X happens because the dispatcher hits a 429 when run within 30s of another call." Not "maybe the API is rate-limited."

## Phase 4 - Fix

Apply the smallest change that addresses the root cause. Verify the original reproduction case now passes. Run any adjacent tests/flows that touch the same code path.

## Hard gates

- You may NOT propose a fix until phase 2 has produced an isolation statement.
- You may NOT skip phase 3 with "let me just try X and see if it works." That is hope, not diagnosis. Hope-driven fixes mask the real cause and fail again later.
- If a phase 1 reproduction takes >30 minutes and you have not isolated, STOP. Phase-jumping at that point is the failure mode. Surface the problem with what is known.

## Anti-pattern

The recurring failure mode is symptom-treatment: when something fails mid-task ("the API stream is hanging", "the test is flaky", "the deploy timed out"), the temptation is to recover by pivoting to other work or by trying a fix without diagnosis. That is a phase-2-and-3-skip. The symptom may pass on its own; the cause does not. The cause re-fires on the next session and on the user's next attempt. Walk the phases.

## When this rule fires

Any time the work is "fix this bug" / "this is broken" / "X stopped working" / a stack trace / a failing test. Applies whether the bug is in code, in a tool, in a config, or in a workflow.

Does NOT apply when the work is exploratory ("can we make this faster?", "what would it take to add X?") - those are design questions, not debugging.

## Cross-references

- The 2-agent rule (`feedback_always_two_agents.md`) depends on this rule: a Checker verifying a bugfix needs the Worker's phase-2 isolation statement to know what passing looks like.
- Knowledge capture (`feedback_capture_knowledge.md`): the phase-3 root-cause claim is exactly the kind of atomic finding `note.py learning` is for. Capture it the moment the diagnosis lands.

## Provenance

Adapted from obra/superpowers (Jesse Vincent, MIT) `skills/systematic-debugging`. The 4-phase rubric and the hard-gate framing are taken verbatim. Adaptation: phrased as a user-voice feedback rule in this toolkit's style + cross-referenced against the 2-agent and capture-knowledge rules.
