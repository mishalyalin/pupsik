---
name: Always search across ALL connected accounts
description: 🔴 MANDATORY — when the user asks about email or calendar, search every connected account. Never ask "which account?" — use `gmail_search_all` / `gcal_list_all_events`.
type: feedback
---

# 🔴 All accounts always

When the user asks an email or calendar question, search **all connected accounts** in one shot.

## Tools to use

- `mcp__multi-gmail__gmail_search_all` — searches every connected Gmail account
- `mcp__multi-gcal__gcal_list_all_events` — lists events from every connected calendar

## Antipattern

- ❌ "Which account should I check — personal, work, school?"
- ❌ Calling `gmail_search` (single-account) when `gmail_search_all` exists
- ❌ Skipping an account "because it's probably not there"

## Pattern

- ✅ Run `gmail_search_all` with the query — see results tagged by account
- ✅ For calendar: `gcal_list_all_events` with a time window — merged view across accounts
- ✅ If the user asks a follow-up scoped to one account ("just my work mail"), use the single-account tool then

## Why

- The user set up multiple accounts precisely so they don't have to re-specify which one.
- Cross-account misses (e.g., a flight booking sent to personal mail, a meeting on work calendar) are the most painful errors.
- One-shot search is also faster than round-tripping about scope.
