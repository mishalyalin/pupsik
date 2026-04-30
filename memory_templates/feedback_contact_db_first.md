---
name: Check contact DB before mentioning any person
description: 🔴 MANDATORY — before mentioning any contact (name, email, company, last-seen, relationship), query `data/contacts.db` + ChromaDB. Never guess from general knowledge.
type: feedback
---

# 🔴 Contact DB first — never guess

Before mentioning any person by name, email, or company in a response:

1. Run `python3 ~/Desktop/claude/tools/memory_search.py search "<name or topic>" --top 5`
2. Or direct: `python3 ~/Desktop/claude/tools/contacts_db.py find "<name>"`
3. If nothing found → say so explicitly ("no record in contacts DB"), don't invent.

## Why

- The contacts DB is authoritative for the user's network.
- General knowledge is wrong in private contexts (different people share a name, the user knows them differently than the internet does).
- Guessing creates a false impression of memory continuity.

## When this applies

- Any answer that references a person by name
- Drafting emails / messages where a recipient is implied
- Timeline questions ("when did we last talk to X")
- Relationship questions ("who introduced us to Y")

## When it does NOT apply

- Pure lookup of public figures (company founders, authors of cited papers, public officials) — use web search.
- The user asks about themselves.

## Pattern

```
User: "What did I last say to <Name>?"
  ├─ Query contacts_db.py find "<Name>"
  ├─ If found: show last interaction + source (email / WA / calendar)
  └─ If not found: "No record in contacts DB for <Name> — should I search email?"
```
