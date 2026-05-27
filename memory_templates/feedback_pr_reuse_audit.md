---
name: PR reuse audit - grep before adding new utility
description: Before any PR adds a new utility/function/script, grep for near-duplicates. CONSOLIDATE, JUSTIFY in PR description, or REJECT. Stops tools/ accumulation.
type: feedback
source: original
---

# PR reuse audit: before adding a new utility, grep for the duplicate

## The rule

Before any PR adds a NEW utility / function / script to a repo you own, run:

```bash
# Search for near-duplicate function names + signatures
rg -n "def <name>|function <name>|export.*<name>" --type-add 'sh:*.sh' .
# Search for similar purpose by keywords
rg -in "<core-keyword-of-utility>" --type py --type ts --type sh .
```

If any hit looks like the same purpose:

1. Either CONSOLIDATE (refactor existing + delete duplicate from this PR)
2. Or JUSTIFY (write in PR description WHY this is structurally different + must coexist)
3. Or REJECT (the existing utility already does this — close the PR)

## Why

Anti-pattern observed: agent-generated PRs add new utilities without checking what's already there. Over time, `tools/` accumulates near-duplicates that all do similar things but slightly differently — bug-fix surface multiplies, mental model fragments, and the next Claude session pattern-matches to the wrong one.

The typical `tools/` directory in a Claude-driven workspace already shows accumulation pressure: `memory_search.py` + `contacts_db.py find/sql` + `note_graph.py entity` + `rules.py search` are all overlapping retrieval entry points. Multiple time-anchoring patterns across `now.py` callsites. Hook scripts in `~/Desktop/claude/.claude/hooks/` + project-level hooks + repo `.githooks/` — different layers, easy to add a fourth without realising.

The next utility added without audit risks creating a 5th similar-but-different entry point.

## Audit checklist (5 minutes before PR open)

1. **Name match:** `rg "def <utility-name>" .` — exact + close variations (singular/plural, snake/camel)
2. **Purpose match:** pick the 2-3 core keywords describing what the utility does, grep for each
3. **Import-graph match:** search for files that would NEED this utility — do any already use a similar one?
4. **README / docs match:** does the project README mention this capability under a different name?
5. **Recent PR match:** `gh pr list --state merged --limit 30 --search "<keyword>"` — was this just added a few weeks ago and forgotten?

If any of these surface a hit, decide CONSOLIDATE vs JUSTIFY vs REJECT before opening the PR.

## What's NOT covered

- Truly novel utilities with no precedent (e.g. first time touching a new domain) — no audit needed beyond checking for accidental name collisions
- Test files duplicating production logic intentionally — different kind of file
- Configuration / data files that look like code (e.g. JSON manifests) — not utilities, no audit

## Connection to other rules

- `feedback_always_two_agents.md` — the Checker agent enforces this audit before the Worker's PR opens
- `feedback_ci_red_is_hard_stop.md` — if reuse-audit becomes a CI check (future), red = blocked
- `feedback_junior_engineer_plan_test.md` — a PR plan that doesn't include the reuse-audit step doesn't pass the junior-engineer test

## Source

r/ClaudeAI viral thread on reviewing AI-generated PRs in 2026 + GitHub Blog Nov 2026 "More Code, Less Reuse" study. The `tools/` directory in any long-running Claude workspace is at risk threshold.
