---
name: junior-engineer-plan-test
description: A plan is good only when an enthusiastic junior engineer could execute it cold, without coming back with questions. Use this test before sending a Worker brief, writing an implementation plan, or recommending an action.
type: feedback
adapted-from: obra/superpowers
source-url: https://github.com/obra/superpowers/tree/main/skills/writing-plans
source-author: Jesse Vincent
source-license: MIT
imported: 2026-05-13
adaptation-type: adapted
---

# Junior-Engineer Plan Test

> A plan is good only when an enthusiastic junior engineer could execute it cold, without coming back with questions.

The test catches plans that depend on tacit knowledge. Apply it to:

- Worker-agent briefs (when spawning Agent tool)
- Implementation plans you write before coding
- Decision notes that recommend an action ("we should X")
- PR descriptions
- Briefing action items ("I need to do Y")

## Pass test

The plan specifies absolute file paths, exact commands, success criteria, and rollback steps. Names of people/products are spelled in full at first mention. Acronyms expanded once. External assumptions named explicitly ("assumes API key is provisioned; if not, blocker").

## Fail test (rewrite)

The plan says "update the briefing skill" without naming the file. Says "ping the supplier" without naming whom or via what channel. Says "fix the bug" without naming the bug or the verification step. Says "see the relevant doc" without the path.

## Bad example

`Worker brief: "Research [topic] and pick what to use."`

That's tacit-knowledge-loaded: which topic, which sources, what does "pick" mean, what's the success criterion, what's the deliverable shape.

## Good example

`Worker brief: "WebSearch for 'X' and 'Y'. Fetch the canonical repo README via WebFetch. Build a capability table with columns: name | description | NEW vs OVERLAPS vs DUPLICATE for the current stack at ~/Desktop/claude/. Flag any rule conflicts against the feedback_*.md files in ~/.claude/projects/.../memory/. Report under 1000 words with explicit sections."`

That gives the junior engineer the search queries, the data structure, the success criterion, and the report-shape. They can execute it cold.

## Cross-references

- The "don't delegate understanding" principle in `~/.claude/rules/critical-rules.md` (Worker-brief construction guidance) operationalises the same idea.
- The 2-agent rule (`feedback_always_two_agents.md`) depends on this rule: a Checker can only verify Worker output if the brief was specific enough to make verification possible.
- Systematic debugging (`feedback_systematic_debugging.md`) Phase 2 isolation statements are themselves a junior-engineer-plan-test for bugfix work - they make the success criterion explicit before a fix is proposed.

## When this rule fires

Any time you are about to:

- Spawn a Worker agent (the brief IS a plan)
- Tell the user "you should do X" (the recommendation IS a plan)
- Write an implementation outline before coding
- Open a PR (the description IS a plan for the reviewer)

Run the test: would a fresh-context engineer execute this without coming back with questions? If no, rewrite.

## Provenance

Adapted from obra/superpowers (Jesse Vincent, MIT) `skills/writing-plans`. The "junior engineer cold execution" framing and the pass/fail criteria shape are taken verbatim. Adaptation: phrased as a user-voice feedback rule in this toolkit's style, with generic examples reframed away from the original's specific use case.
