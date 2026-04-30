# Modular Install — Pick Individual Components

## Who this is for

You're a user with your own Claude Code setup who wants individual components
from this toolkit. You don't want a full install that overlays your existing
conventions. You want to grab one or two specific pieces — just the rules, or
just the contact DB — without dragging in the rest.

This document lists each component, what it depends on, what it doesn't depend
on, and how to install just that piece.

## Components

Each component below is described with: **what it does**, **what files it consists of**, **what it depends on**, **what it doesn't depend on** (so you know it's safe to skip the rest), and a **3-line install snippet**.

### a) Critical rules

- **What it does:** A one-line index of MANDATORY behaviour rules, plus the full text of each rule. Claude Code auto-loads files from `~/.claude/rules/` at session start, so the rules are pinned to every session.
- **Files:** `templates/critical-rules.md.template` + `memory_templates/feedback_*.md` (the full text per rule).
- **Depends on:** Nothing. Pure markdown.
- **Doesn't depend on:** No Python, no MCP, no SQLite, no ChromaDB. It works on any Claude Code install.
- **Install:**

  ```bash
  mkdir -p ~/.claude/rules ~/.claude/projects/$(basename "$PWD")/memory
  cp pupsik/templates/critical-rules.md.template ~/.claude/rules/critical-rules.md
  cp pupsik/memory_templates/feedback_*.md ~/.claude/projects/$(basename "$PWD")/memory/
  ```

### b) Knowledge capture

- **What it does:** `note.py` captures a learning, decision, or research note the moment an insight surfaces. Upserts by title, so the same topic stays one note that gets refreshed instead of duplicating.
- **Files:** `tools/note.py` + `memory_templates/feedback_capture_knowledge.md` (the rule that reminds Claude to use it).
- **Depends on:** `tools/memory_search.py` for the surgical single-file reindex. Soft dependency — `note.py` writes the markdown file fine without it; you just don't get auto-reindex.
- **Doesn't depend on:** Contact DB, MCP servers, hooks. Standalone otherwise.
- **Install:**

  ```bash
  mkdir -p ~/Desktop/claude/tools ~/Desktop/claude/memory/{learnings,decisions,research}
  cp pupsik/tools/note.py ~/Desktop/claude/tools/ && chmod +x ~/Desktop/claude/tools/note.py
  cp pupsik/memory_templates/feedback_capture_knowledge.md ~/.claude/projects/$(basename "$PWD")/memory/
  ```

### c) Contact DB

- **What it does:** SQLite database of people, companies, interactions, and the relationships between them. CRUD via `contacts_db.py`. Graph traversal (`graph`, `chain`), staleness detection (`stale 7`).
- **Files:** `tools/contacts_db.py` + `data/contacts.db` (initialized via `contacts_db.py init`).
- **Depends on:** Python ≥ 3.10. Pure stdlib `sqlite3` — no extra packages.
- **Doesn't depend on:** ChromaDB, MCP servers, rules. Fully standalone.
- **Install:**

  ```bash
  mkdir -p ~/Desktop/claude/{tools,data}
  cp pupsik/tools/contacts_db.py ~/Desktop/claude/tools/ && chmod +x ~/Desktop/claude/tools/contacts_db.py
  python3 ~/Desktop/claude/tools/contacts_db.py init
  ```

### d) Semantic search

- **What it does:** Indexes any markdown directories you point it at, plus the contact DB if present, into a local ChromaDB. 9 collections: contacts, interactions, memory_files, chat_archives, briefings, outputs, journal, knowledge, research. The `knowledge` collection combines `memory/learnings/` and `memory/decisions/`. Search across them with `memory_search.py search "..."`.
- **Files:** `tools/memory_search.py` + the `chromadb` Python package.
- **Depends on:** `pip install chromadb`. Soft-coupled to `contacts_db.py` — 2 of the 9 collections (contacts, interactions) come from the SQLite DB; the other 7 work without it.
- **Doesn't depend on:** MCP servers, hooks, rules. Standalone except for `chromadb` and the optional contact-DB coupling.
- **Install:**

  ```bash
  pip install chromadb
  cp pupsik/tools/memory_search.py ~/Desktop/claude/tools/ && chmod +x ~/Desktop/claude/tools/memory_search.py
  python3 ~/Desktop/claude/tools/memory_search.py index
  ```

### e) Compact hooks

- **What it does:** `pre-compact.sh` saves session state (active TODOs, last user message, key files modified, decisions) to disk before Claude's context gets compressed. `post-compact.sh` reminds Claude to restore that state on the next turn. Net effect: you don't lose the plot at compact boundaries.
- **Files:** `hooks/pre-compact.sh`, `hooks/post-compact.sh`. Plain shell scripts.
- **Depends on:** Nothing. Bash and standard Unix tools.
- **Doesn't depend on:** Python tools, MCP, SQLite, ChromaDB.
- **Install:**

  ```bash
  mkdir -p ~/Desktop/claude/.claude/hooks
  cp pupsik/hooks/{pre-compact,post-compact}.sh ~/Desktop/claude/.claude/hooks/
  chmod +x ~/Desktop/claude/.claude/hooks/*.sh
  # then register them in ~/.claude/settings.json (see hooks/README in the package for the JSON snippet)
  ```

### f) MCP servers

- **What it does:** Three local MCP servers — `multi-gmail` (Gmail across multiple accounts), `multi-gcal` (Calendar across multiple accounts), `whatsapp` (read-only Mac WhatsApp). Each is independent: pick one, two, or all three.
- **Files:** `mcp-servers/multi-gmail/`, `mcp-servers/multi-gcal/`, `mcp-servers/whatsapp/`. Each has its own source and prebuilt `dist/`.
- **Depends on:** Node ≥ 18 for build. Each server has its own OAuth setup (Gmail and Calendar share a Google Cloud project; WhatsApp needs Full Disk Access on Mac).
- **Doesn't depend on:** Each other. They're three independent npm packages. They also don't depend on Python tools, contact DB, ChromaDB, hooks, or rules.
- **Install (Gmail only as an example):**

  ```bash
  cd pupsik/mcp-servers/multi-gmail && npm install && npm run build
  claude mcp add multi-gmail node $(pwd)/dist/index.js
  # then follow docs/GOOGLE_CLOUD_SETUP.md once for OAuth
  ```

  Substitute `multi-gcal` or `whatsapp` for the same flow with the other two.

## Mix-and-match recipes

A few common combinations:

- **"Just the discipline"** — Critical rules (a) + Knowledge capture (b). Lightest possible install. No databases, no MCP. You get rule enforcement and `note.py`. Good for users who already have their own memory/search setup and just want the behavioural backbone.

- **"Just the brain"** — Contact DB (c) + Semantic search (d). No rules, no MCP, no hooks. Pure local data layer. Good for users who want to run searches and graph queries from their own scripts and let their existing Claude Code configuration handle rules.

- **"Just the inbox"** — MCP servers (f), one or all three. Zero local DB, zero rules. Good for users who want Gmail/Calendar/WhatsApp access in Claude Code and nothing else.

- **"Discipline + brain"** — (a) + (b) + (c) + (d). Everything except hooks and MCP servers. The minimal "Claude has memory and follows rules" setup, no third-party services.

## What to avoid mixing

- **Don't grab `note.py` without the capture-knowledge rule.** `note.py` is the tool; the rule is what reminds Claude to actually use it. Without the rule loaded into `~/.claude/projects/<slug>/memory/`, Claude won't reach for the tool when an insight surfaces, and the file just sits there. Always pair (b) — both pieces, not just the script.

- **Don't enable compact hooks (e) without configuring `~/.claude/settings.json`.** Copying the scripts to `.claude/hooks/` does nothing on its own — Claude Code only fires them if `settings.json` registers them. Either install both pieces or neither.

- **Don't install semantic search (d) without something for it to index.** It's not useless without (c), but it's noticeably less useful — half the value comes from the contact and interaction collections sourced from SQLite. If you skip (c), point `memory_search.py` at your own markdown directories instead, otherwise the index will be sparse.
