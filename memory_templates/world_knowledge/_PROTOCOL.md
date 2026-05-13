---
title: World Knowledge Capture
adapted-from: obra/superpowers
source-url: https://github.com/obra/private-journal-mcp
source-author: Jesse Vincent
source-license: MIT
imported: 2026-05-13
adaptation-type: schema-only cherry-pick
adaptation-notes: |
  Verbatim from obra/private-journal-mcp:
    - The world_knowledge category concept (general facts not project-specific)

  Adapted in this toolkit:
    - Storage as per-file markdown in memory/world_knowledge/ rather than a
      separate JSON store
    - Backing via note.py + ChromaDB knowledge collection rather than a
      separate MCP server
    - Upsert-by-slug semantics (same as learnings/decisions) - re-running with
      same title rewrites the body

  Additions in this toolkit (NOT in obra/private-journal-mcp):
    - Integration with ChromaDB knowledge collection (subtype=world_knowledge)
    - Surfaces via `memory_search.py search` alongside learnings + decisions
related-files:
  - tools/note.py (world_knowledge subcommand)
  - tools/memory_search.py (knowledge collection)
  - THIRD_PARTY_ATTRIBUTIONS.md (central tracker)
---

# World Knowledge

General facts not tied to a specific project. The kind of thing where the answer is the same no matter which project triggered the question.

Examples:

- "VAT rate NL standard is 21% (reduced 9%, zero-rated exports)"
- "Companies House annual return due 12 months from incorporation date + 1 day late = penalty fee"
- "EU 1169/2011 Article 26(3): country of origin must be declared for primary ingredient if absent on front-of-pack"
- "Shopify Subscriptions native app is free; third-party subscription tooling starts in the high hundreds per month"
- "US wire transfer fee at a typical fintech: $0 domestic ACH, $15 international wire"
- "Postgres `EXPLAIN ANALYZE` shows actual runtime; `EXPLAIN` alone shows planner estimate"

NOT for:

- Project-specific state (use CLAUDE.md project sections or memory/projects/)
- Decisions (use `note.py decision` - those track WHY we picked option A over B)
- Learnings (use `note.py learning` - those track WHAT we learned about a specific situation)
- Feedback rules about user preferences (use memory/feedback_*.md)

The split is: world_knowledge = facts about the world; user_context = facts about the user; learnings/decisions = facts about specific events or choices.

## How to log

```
python3 ~/Desktop/claude/tools/note.py world_knowledge \
  "Short factual title" \
  "Body (2-5 sentences). Cite source if non-obvious." \
  [--tags "tag1,tag2"] \
  [--body-file PATH | --body-stdin]
```

Upsert semantics match learnings/decisions: same title slug = same file gets rewritten with new body + merged tags. Re-run when the fact changes (e.g. VAT rate update, regulatory threshold revision).

## Search

```
python3 ~/Desktop/claude/tools/memory_search.py search "VAT rate Netherlands"
```

Files in this directory are indexed in the ChromaDB `knowledge` collection with `subtype: world_knowledge`. They surface alongside learnings + decisions in any search.

## Provenance

Cherry-picked from obra/superpowers / obra/private-journal-mcp (Jesse Vincent, MIT) on 2026-05-13. See `THIRD_PARTY_ATTRIBUTIONS.md` at the repo root for the central tracker entry.
