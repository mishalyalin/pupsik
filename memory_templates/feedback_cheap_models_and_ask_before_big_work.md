---
name: Ask before big multi-agent work; default to cheap models
description: Before launching an expensive multi-agent fan-out, stop and ask the user — propose scope and recommend which models to use — and default the mechanical stages to cheap models, never the top-tier model by default.
type: feedback
source: original
---

# Ask before big work. Pin cheap models on fan-out.

## The rule

Two coupled habits that protect the user's token budget:

1. **Ask before big work.** Before launching any large or expensive job — a multi-agent fan-out, a workflow that spawns dozens of agents, a long/repeated research pass, a whole-codebase sweep — **stop and ask first.** State the plan and rough scale, recommend which models to use, and wait for a one-line confirm. Do not silently fire it.

2. **Default to cheap models on fan-out.** In a multi-agent workflow, every spawned agent inherits the **session model** unless you pin one explicitly. If the session model is the top tier, a ~100-agent run costs on the order of **16M tokens on the top-tier model — per run.** That is almost never justified.

## Why

A fan-out research harness is mostly cheap, mechanical work — running a web search, fetching a page and extracting claims, casting a skeptical verification vote. The overwhelming majority of the agents in a typical run (e.g. ~75 of ~100 are verification votes) are exactly the kind of narrow task a small fast model does well. Routing all of them through the top-tier model burns 10-20× the tokens for no quality gain.

Direct precedent in this setup: three back-to-back ~100-agent research runs were fired on the top-tier model without asking — roughly 50M tokens — before the user caught it. The fix is behavioural (ask first) plus technical (pin the models).

## How to apply

**Model pins by stage** (retune per task, but this is the sane default):

| Stage | Work | Model |
|---|---|---|
| Scope / decompose | reasoning | mid tier (e.g. Sonnet) |
| Search | web search + rank | small/fast (e.g. Haiku) |
| Fetch / extract | fetch page, pull claims | small/fast (e.g. Haiku) |
| Verify (the bulk) | skeptical vote per claim | small/fast (e.g. Haiku), low effort |
| Synthesize | merge + write report | mid tier (e.g. Sonnet) |

Reserve the top-tier model for a stage that genuinely needs it, and say so when you propose it.

**Mechanics:**
- Set the model explicitly on **every** `agent()` call in a workflow — don't let it inherit the session model.
- If a bundled research skill generates its workflow script with no model pins, it will run on the session model. Keep a cost-optimised fork of that script with the model pins baked in, and run that instead.
- If an expensive run is already in flight and can't be cancelled cleanly, let it finish and use its result rather than re-launching a cheap duplicate — that is double spend, the opposite of the goal.

## The gate, concretely

When about to launch something big:

1. One line: what it does + rough scale (how many agents / how heavy).
2. Recommend the models yourself (default cheap, per the table).
3. Wait for confirm. The ask is cheap; the wasted top-tier run is not.
4. Default to the cheapest option that still does the job.

## What's NOT covered

- Small tasks — a couple of agents, ordinary tool calls, a single search — proceed as normal. This gate is about **cost/scale**, not about adding friction to routine work.
- This does not mean phasing work into artificial multi-day plans. Do contiguous work in one pass — just do it cheaply, and get a green light before a big spend.

## Connection to other rules

- `feedback_always_two_agents.md` — worker + independent checker is still required; just run the checker on an appropriate (often cheaper) model.
- `feedback_pr_reuse_audit.md` — before adding a new workflow script, check whether a cost-optimised one already exists to fork.

## Source

Original. Precedent: a token-budget blow-up from unpinned multi-agent research runs on the top-tier model.
