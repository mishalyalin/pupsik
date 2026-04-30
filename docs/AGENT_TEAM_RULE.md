# The 2+ Agents Rule — User-Facing Explanation

Your Claude is configured to **always use at least 2 agents for real tasks.** One does the work, another independently verifies it. This page explains why, how to recognise it's happening, and when it's OK to override.

---

## Why this rule exists

Single-agent work misses bugs — every time. When Claude does a task AND checks its own work, it inherits its own blind spots. A second agent coming in cold, seeing only the acceptance criteria, catches things the first agent would have sworn were fine.

A real packaging task was built by a team of 3 agents (architect + packager + tester). The tester found:

1. A hardcoded name from the developer's own context that had leaked into a user-facing HTML export.
2. A SQL handler missing `db.commit()` — `INSERT` statements silently didn't persist. This bug had been in production for months.
3. `sqlite3.Row.get()` doesn't exist in Python — a `find` command crashed on non-empty results.

**Zero of those would have been caught by a single-agent run.** That's the reason for the rule.

---

## How to spot Claude using multiple agents

When you give Claude a real task, you should see it call something like:

> "Spawning 3 agents: architect to plan, worker to build, tester to verify."

Each agent runs independently. You'll see their outputs — plan files, logs, test reports — show up in the task directory. The orchestrator (the main Claude conversation) collects their results and decides what to do next.

**If you give a task and Claude just does it solo without spawning anyone — that's a miss.** Remind it of the rule.

---

## When 2+ agents are used (the common cases)

- Any code / script / tool change
- Building or migrating data (contacts DB, exports, ChromaDB reindex)
- Setting up a system (MCP, hooks, workflows)
- Any packaging / bundling / deploy
- Research deliverables, plans, architecture docs
- Emails / contracts / documents going to a third party

---

## When one agent is enough

- A single lookup ("what's the phone number for X?")
- A single tool call with no transformation (list my events today)
- Direct answer to a question from memory / DB ("when is my next flight?")

If you're asking for information, one agent is fine. If you're asking for **changes to the world** (files, configs, data, messages being sent), demand a second agent.

---

## Overriding the rule

Sometimes you want speed over rigour. That's fine — say so explicitly:

> "Just do this quickly, no checker needed."

Claude will skip the second agent for that one task. But the rule is the default; opting out is per-request.

---

## How to verify the rule is loaded

In a new session, ask:

> "What's your 2-agent rule?"

Claude should paraphrase: "For every meaningful task I spawn at least 2 agents — one does the work, another independently verifies it."

If Claude says "what rule?" — the `CLAUDE.md` or `memory/feedback_always_two_agents.md` isn't loading. Check:

1. `~/Desktop/claude/CLAUDE.md` exists and contains the "🔴 MANDATORY: Always 2+ agents per task" section.
2. `memory/feedback_always_two_agents.md` exists in the project memory directory (`~/.claude/projects/-Users-<you>-Desktop-claude/memory/`).

---

## The agents you may see

See `pupsik/agents/` for the role prompts.

- **Architect** — plans the work before anyone touches files
- **Discoverer** — inventories existing source material
- **Packager** — builds the artifact per plan (Worker role)
- **Migrator** — moves systems between states safely (Worker role)
- **Tester** — independently verifies output (Checker role — the crucial half of the 2-agent rule)

For complex work you may also see Reviewer, Security Auditor, or other specialist roles. More agents = more chances to catch errors.
