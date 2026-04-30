---
name: Always spawn minimum 2 agents per task — worker + checker
description: 🔴 MANDATORY — for every meaningful task, spawn at least 2 agents. One does the work, one verifies it was done correctly. More agents if the task needs specialization. "The result must be 100% correct."
type: feedback
---

# 🔴 MANDATORY: Always 2+ agents per task

## The rule

**Every meaningful task = minimum 2 agents:**

1. **Worker** — does the work.
2. **Checker / Tester** — independently verifies that the work was done correctly.

**If the task is complex — spawn more:**

- Architect (plan)
- Specialist roles (researcher, coder, reviewer, migrator, security auditor, etc.)
- Each agent gets appropriate tools, credentials, and a narrowly scoped focus.

**Pattern:**

- Worker and Checker are **separate agents**, launched independently.
- The Checker does NOT see the Worker's intermediate work — that way they don't inherit the Worker's assumptions.
- The Checker independently verifies the result and reports `PASS` or `FAIL` + list of issues.
- On `FAIL` → the Worker fixes the issues → the Checker re-verifies.
- Ship only after the Checker says `PASS`.

## Where it applies

**YES, spawn 2+ agents:**

- Any code / script / tool change
- Any data analysis (email scan, contact import, financial calc)
- Any system setup (MCP, hooks, workflows)
- Any export / packaging / migration
- Plans / architecture / research deliverables
- Emails / contracts / documents being sent to a third party

**NO, one agent is enough:**

- A single lookup (find an email, a contact, a fact)
- A single tool call with no transformation (list events, read file)
- Direct answer to a question from memory / DB

**If in doubt — spawn two.** Cost of an error >> cost of a second agent.

## Antipattern (what NOT to do)

- ❌ Do the work yourself → test it yourself → "done" (single point of failure)
- ❌ Spawn one agent → accept its result as truth
- ❌ "I'll just do this quickly myself" instead of building a team

## Pattern (what to do)

```
Task: Build X
  ├─ Agent 1 (Worker): builds X
  └─ Agent 2 (Tester): verifies X — reports PASS / FAIL + details

If FAIL:
  ├─ Worker fixes issues from Tester's report
  └─ Tester re-verifies

Ship only when Tester says PASS.
```

**For complex tasks:**

```
Task: Complex system
  ├─ Agent 1 (Architect): designs the plan
  ├─ Agent 2 (Worker): implements the plan
  ├─ Agent 3 (Reviewer): code-quality pass
  ├─ Agent 4 (Tester): end-to-end verification
  └─ Agent 5 (Security): audits for leaks / issues
```

## Example of why this matters

A real packaging task was built by a team of 3 agents (architect + packager + tester). The Tester caught **3 bugs** the single implementer would have missed:

1. A hardcoded name from the developer's own context leaking into a user-facing HTML export.
2. A SQL handler missing `db.commit()` — `INSERT` silently failed to persist.
3. `sqlite3.Row.get()` doesn't exist — a `find` command crashed on non-empty results.

One of those (#2) had been present in a production file for months, unnoticed. **Without the team check, it would not have been found.**

That is the reason for this rule: single-agent work misses bugs; a team catches them.

## How to apply

When receiving a task, the **first step** is to ask: "do I need a second agent?"

- If the task is more than one lookup / direct-answer → **YES, 2+ agents.**
- Define the roles: worker + checker (minimum), more for complex work.
- Give each agent a clear role, inputs, and acceptance criteria.
- Worker and Checker run **independently** (in parallel where possible).
- Wait for both reports. Fix-loop if needed.

## Full rule reference

- `~/.claude/rules/critical-rules.md` — one-line summary
- `memory/feedback_always_two_agents.md` — this file (full context)
- `pupsik/docs/AGENT_TEAM_RULE.md` — user-facing explanation
