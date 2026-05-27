---
name: CI red = hard stop on PR merge
description: If any CI check fails on a Claude-authored PR, the PR does not merge. No exceptions, no pattern-matched justifications. Investigate-and-fix, never merge-anyway.
type: feedback
source: original
---

# CI red = hard stop. No exceptions.

## The rule

If any CI check on a Claude-authored PR fails or shows yellow-warning-treated-as-FAILURE, **that PR does not merge.** No exceptions, no pattern-matched justifications, no "let me just retry", no "the linter is being weird, ignore it".

The CI signal is binary: green → merge candidate, anything-else → blocked. Even if Claude can produce a plausible-sounding reason for why the failure isn't real, the answer is investigate-and-fix, not merge-anyway.

## Why

Direct precedent in this repo's history: a privacy-check job once flagged a common surname as a pattern match. The pattern-matched justification at the time was "the matcher is over-firing on a public surname, this is fine". The PR was merged via a branch-protection gap, and a hotfix PR was needed the same day. The CI was correct; the justification was wrong.

The structural fixes from that incident (branch protection + pre-commit hook + extra privacy passes) raised the cost of merging on FAILURE. But none of them encode the **behavioural rule** that future-Claude needs: "CI red ≠ optional opinion."

## What this rule blocks

When Claude is about to call `gh pr merge`, the must-check list:

1. `gh pr view <n> --json statusCheckRollup --jq '.statusCheckRollup[].conclusion'` returns ALL `SUCCESS`
2. No `FAILURE`, no `CANCELLED`, no `ACTION_REQUIRED`, no `STALE`, no `NEUTRAL` interpreted as anything other than green
3. No "I'm going to re-run this manually before merging" — re-run, then re-check status, then merge

If anyone (Claude OR the user OR a co-author) suggests merging on red because "I see why it's red and it's fine", the answer is: **then fix it green first**. The 60 seconds it takes to push a fix + wait for re-run is cheap. The hotfix PR is not.

## What's NOT covered

- Manual workflows triggered for testing (not on a PR) — those can be red without blocking work
- Optional informational checks marked `continue-on-error: true` — those by design don't block
- External CI services that aren't blocking checks on the branch — those are advisory

The rule applies to the **mergeable status** of the PR specifically.

## Connection to other rules

- `feedback_never_ignore_own_rules.md` — branch protection + pre-commit are structural enforcement; THIS is the behavioural rule.
- `feedback_systematic_debugging.md` — when CI is red, treat as a bug to reproduce-isolate-diagnose-fix. Not as an opinion to override.
- Branch protection: structural. Pre-commit hook: structural. Extra privacy passes: structural. This rule: behavioural, fills the gap when human/AI is tempted to bypass structure.

## Source

r/ClaudeAI viral thread on reviewing AI-generated PRs in 2026 + GitHub Blog Nov 2026 "More Code, Less Reuse" study. Direct precedent in this repo's hotfix-PR history.
