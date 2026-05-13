---
title: User Context Capture
adapted-from: obra/superpowers
source-url: https://github.com/obra/private-journal-mcp
source-author: Jesse Vincent
source-license: MIT
imported: 2026-05-13
adaptation-type: schema-only cherry-pick
adaptation-notes: |
  Verbatim from obra/private-journal-mcp:
    - The user_context category concept (preferences, working style, recurring
      patterns about the user that are NOT prescriptive feedback rules)

  Adapted in this toolkit:
    - Storage as per-file markdown in memory/user_context/ rather than a
      separate JSON store
    - Backing via note.py + ChromaDB knowledge collection rather than a
      separate MCP server
    - Upsert-by-slug semantics (same as learnings/decisions) - re-running with
      same title rewrites the body

  Additions in this toolkit (NOT in obra/private-journal-mcp):
    - Integration with ChromaDB knowledge collection (subtype=user_context)
    - Explicit separation from feedback_*.md (those are prescriptive rules
      Claude MUST follow; user_context is descriptive observations to inform
      planning)
    - Surfaces via `memory_search.py search` alongside learnings + decisions
related-files:
  - tools/note.py (user_context subcommand)
  - tools/memory_search.py (knowledge collection)
  - THIRD_PARTY_ATTRIBUTIONS.md (central tracker)
---

# User Context

The user's preferences, working style, recurring patterns, environmental constraints. Descriptive observations to inform planning - NOT prescriptive rules.

Examples:

- "User exercises Mon/Wed/Fri 10am at a fixed gym slot"
- "Back pain triggered by long flights - avoid scheduling deep work day-after"
- "Prefers afternoon for deep work; morning is for ops/briefings/email triage"
- "Energy dips Friday afternoons; batch low-stakes tasks then"
- "Russian-language calls warm up better than English for Slavic-origin counterparties"
- "Walks the dog 07:00-08:00 most weekdays - calls during this window get declined"

The split from `feedback_*.md` is intentional:

- `feedback_*.md` = prescriptive rules Claude MUST follow ("Always use short hyphens", "Never ask known identifiers"). Violation = bug.
- `user_context/` = descriptive observations about the user that inform how Claude PLANS and SCHEDULES work. Useful but not load-bearing the way feedback rules are.

NOT for:

- Identifiers (use a dedicated reference file - e.g. `memory/reference_<user>_identifiers.md`)
- Family/contact facts (use `memory/people/` or contacts.db)
- Prescriptive rules (use `memory/feedback_*.md`)
- Project-specific state (use CLAUDE.md or `memory/projects/`)

## How to log

```
python3 ~/Desktop/claude/tools/note.py user_context \
  "Short descriptive title" \
  "Body (2-5 sentences). Why does this matter for planning?" \
  [--tags "tag1,tag2"] \
  [--body-file PATH | --body-stdin]
```

Upsert semantics match learnings/decisions: same title slug = same file gets rewritten with new body + merged tags. Re-run when the pattern updates (e.g. schedule shift, new constraint, resolved constraint).

## Search

```
python3 ~/Desktop/claude/tools/memory_search.py search "user exercise schedule"
```

Files in this directory are indexed in the ChromaDB `knowledge` collection with `subtype: user_context`. They surface alongside learnings + decisions in any search.

## Privacy

`user_context/` may contain personal information about the operator (sleep schedule, health constraints, family rhythms). Treat the directory as local-only: never include in public exports of dotfiles or configuration. If you fork this toolkit, scrub any inherited examples and start your own from scratch.

## Provenance

Cherry-picked from obra/superpowers / obra/private-journal-mcp (Jesse Vincent, MIT) on 2026-05-13. See `THIRD_PARTY_ATTRIBUTIONS.md` at the repo root for the central tracker entry.
