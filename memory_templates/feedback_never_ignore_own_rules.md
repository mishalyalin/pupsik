---
name: Never ignore own rules
description: 🔴 CRITICAL. Rules in `CLAUDE.md` and `memory/feedback_*.md` are MANDATORY protocols, not "suggestions". Ignoring an own rule = bug, not a stylistic choice.
type: feedback
---

# 🔴 Never ignore own rules

**Rules in `CLAUDE.md` (especially "🔴 MANDATORY" sections) and in `memory/feedback_*.md` are not advice — they are required protocols. Execute them every time, no exceptions.**

## Why this exists

The whole point of the persistent memory + critical-rules system is to remove repeat mistakes. If the rules are loaded but ignored, the user is paying for a feedback loop that produces zero learning. That is worse than not having the rules at all — it creates a false sense of safety.

A real failure: the user asked for a project plan. Two rules in `CLAUDE.md` said "verify state from fresh email before answering any project status question" and "check the contact DB before mentioning anyone by name." The agent skipped both, built the plan on a stale `CLAUDE.md` snapshot, and contradicted facts that were sitting in the inbox unread. Every wrong claim was traceable to a rule that was loaded but unused.

## How to apply

1. **Before any claim about a status / payment / partner** — verify against fresh data (last 7 days of email, all relevant accounts, any mentioned chat groups). Don't trust `CLAUDE.md` alone — it is a snapshot, not live state.

2. **If a fresh fact contradicts `CLAUDE.md`** — that's a bug in `CLAUDE.md`. Update inline NOW, before answering. Don't defer to "next briefing."

3. **If the user reveals a fact that was already in their inbox** — that's a double error: (a) you didn't check, (b) the fact is now in conversation context but not in memory. Persist it immediately to `CLAUDE.md` + the relevant `memory/project_*.md`. If the omission reveals a pattern, add a new `feedback_*.md` rule.

4. **No "🔴 MANDATORY" rule is overridable by intuition.** "I think I remember" is not a verification step — memory can be stale, the rule said "check anyway" for a reason.

5. **If you broke a rule** — name it in your reply ("I missed the verify-before-claim rule on this one"). Don't paper over with apologies. The user is paying for the system to work, not for graceful error handling.
