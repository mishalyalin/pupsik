# How it works

A walkthrough of what this installs and why each piece is here.

If you're considering installing, read this first. If you already installed and want to upgrade, go to [`UPGRADING.md`](UPGRADING.md). If you only want some pieces, see [`MODULAR.md`](MODULAR.md).

## The problem

Out of the box, Claude Code is a stateless coding assistant. It reads files, writes files, runs commands, and forgets everything when the session ends. Fine for one-shot coding tasks. For ongoing work - which is what I do with it all day - the friction adds up:

- It doesn't remember the people I'm dealing with.
- It can't see my inbox, my calendar, or WhatsApp.
- It doesn't know my conventions, and it doesn't remember the mistakes it made last week.
- When the conversation gets long enough that Claude Code auto-compacts, the assistant loses the plot.
- It happily skips its own rules unless they're pinned to every session.

This toolkit fixes all of that.

## What gets installed

When you run `bash install.sh`, four things land on disk:

1. **A workspace directory** at `$HOME/Desktop/claude/` (configurable). This is
   where Claude reads from and writes to. Inside it:
   - `CLAUDE.md` - the project file Claude reads first every session.
   - `memory/` - markdown files: people profiles, project notes, learnings,
     decisions, research, behavioural rules.
   - `data/contacts.db` - SQLite contact graph (people, companies,
     interactions, links).
   - `data/chroma/` - ChromaDB index for semantic search.
   - `tools/` - Python scripts that read and write the above.
   - `outputs/` - anywhere you ask Claude to save a generated file.
   - `.claude/hooks/` - auto-compact hooks (pre-compact, post-compact).
2. **MCP servers** at `mcp-servers/multi-gmail/`, `mcp-servers/multi-gcal/`,
   `mcp-servers/whatsapp/`. Three local Node servers that give Claude
   cross-account inbox / calendar / chat access.
3. **A rules file** at `~/.claude/rules/critical-rules.md`. Claude Code
   auto-loads everything in `~/.claude/rules/` at session start, so the
   MANDATORY behaviour rules ride along on every session, in every project.
4. **A small set of feedback rules** at
   `~/.claude/projects/<slug>/memory/feedback_*.md`. Long-form versions of
   the rules in `critical-rules.md`, with the why and the how.

## Memory: where things live and why

Memory is split across four layers, each suited to a different access pattern.

### Layer 1 - `CLAUDE.md`

A single markdown file at the root of the workspace. Claude reads it first,
every session. It holds the things you'd want Claude to know within five
seconds of starting:

- Who you are (name, role, primary email).
- Active projects and their state.
- Pending decisions.
- Pointers to deeper memory files for everything else.

Keep it short. The template caps it at roughly 200 lines.

### Layer 2 - `memory/*.md`

Markdown files in subdirectories: `memory/people/`, `memory/projects/`,
`memory/learnings/`, `memory/decisions/`, `memory/research/`,
`memory/journal/`. Loaded on demand. When Claude needs context that isn't
in `CLAUDE.md`, it reads the appropriate file.

### Layer 3 - Contact graph DB

A SQLite database at `data/contacts.db`. Fast, structured, queryable.
Used for:

- "Who is `Alice Smith`? When did I last talk to them?"
- "Who's gone silent on me in the last 7 days?"
- "Show me a graph of everyone connected to `Vendor X`."
- "What's the shortest intro chain from `Alice` to `Bob`?"

CRUD via `tools/contacts_db.py`. Pure Python stdlib - no third-party deps.

### Layer 4 - Semantic search via ChromaDB

A ChromaDB at `data/chroma/`. Slow to populate, fast to query. Indexes
nine collections: `contacts`, `interactions`, `memory_files`, `chat_archives`,
`briefings`, `outputs`, `journal`, `knowledge` (= learnings + decisions),
`research`.

Used for:

- "Have I seen this topic before? What did I conclude?"
- "Pull up everything from my notes related to `Vendor Y`'s last quote."
- "What did I research about packaging suppliers?"

Search via `tools/memory_search.py search "..."`.

## Tools: how Claude reads and writes memory

Three Python scripts in `tools/`:

- **`contacts_db.py`** - CRUD, graph traversal, stale-contact detection,
  intro-chain finding. SQLite-backed. Standalone (no extra deps).
- **`memory_search.py`** - semantic indexer + search. ChromaDB-backed.
  Idempotent (`coll.upsert` everywhere). Surgical single-file reindex
  (`index --file <path>`) takes ~50ms instead of rebuilding the world.
- **`note.py`** - moment-of-emergence capture. One command writes a
  learning, decision, or research note as markdown and reindexes the
  ChromaDB collection. Upserts by title, so the same topic stays one
  note that gets refreshed instead of creating duplicates.

The `note.py` design point is worth dwelling on: the rule is to capture
**the moment** an insight surfaces, not when the topic closes. If the
understanding evolves later, re-run `note.py` with the same title - it
upserts the existing note, preserves `created:`, updates `updated:`,
merges tags, and rewrites the body. One note per topic, kept current.

## MCP servers: cross-account inbox, calendar, chat

Three local Node servers, each independent:

- **`multi-gmail`** - reads multiple Gmail accounts in a single call.
  Tool name: `gmail_search_all`. The whole point is to avoid the prompt
  "which account?" - by default, all accounts every time.
- **`multi-gcal`** - same idea for Google Calendar. Tool name:
  `gcal_list_all_events`.
- **`whatsapp`** - read-only access to the macOS WhatsApp database.
  Reads chats, searches messages, syncs business contacts to the
  contact DB.

Each server has its own `dist/` build and its own auth setup. OAuth for
Gmail and Calendar is documented in `docs/GOOGLE_CLOUD_SETUP.md`. WhatsApp
needs Full Disk Access on macOS - see `docs/WHATSAPP_SETUP.md`.

Picking which to install: see `MODULAR.md`. They're independent - pick
one, two, or all three.

## Rules: how Claude stays disciplined

Two layers of rules, both pinned to every session.

### `~/.claude/rules/critical-rules.md`

Claude Code auto-loads files from `~/.claude/rules/` at session start.
Whatever lives there is read on every session, in every project. This
toolkit installs a one-line index of MANDATORY rules - short pointers to
the long-form versions.

### `~/.claude/projects/<slug>/memory/feedback_*.md`

The long-form versions, scoped to the workspace project. Each rule
explains the why, the how, and gives examples. When Claude needs to
verify the full text of a rule (because the one-liner is ambiguous),
it reads the long-form file.

### What rules ship in this toolkit

Generic rules only - no personal references:

- **`feedback_always_two_agents.md`** - every real task gets a Worker +
  an independent Checker. Single-agent work is banned for anything
  non-trivial.
- **`feedback_capture_knowledge.md`** - capture insights at the moment
  they surface via `note.py`, not at the end of the topic.
- **`feedback_contact_db_first.md`** - before mentioning any person,
  check the contact DB.
- **`feedback_never_ignore_own_rules.md`** - rules in `CLAUDE.md` and
  `feedback_*.md` are MANDATORY, not suggestions.
- **`feedback_verify_project_state.md`** - verify status from fresh
  data before answering project / payment / partner questions.
- **`feedback_compute_weekday_dont_guess.md`** - compute weekday from
  the ISO date programmatically; don't pattern-match from previous output.
- **`feedback_short_dashes_only.md`** - when drafting in the user's
  voice, use a short hyphen not an em-dash or en-dash.
- **`feedback_save_outputs.md`** - generated files go to a known
  outputs directory, not scattered around the filesystem.
- **`feedback_use_local_mcp.md`** - prefer the local multi-account MCPs
  over single-account connectors.
- **`feedback_all_accounts_always.md`** - `gmail_search_all` /
  `gcal_list_all_events`, never single-account; never ask which account.
- **`feedback_default_workspace.md`** - every session starts in the
  same workspace directory with the same default permission mode.
- **`feedback_deploy_immediately.md`** - when a change is verified, ship.
  Don't pause to ask permission for the obvious next step.
- **`feedback_verify_before_showing.md`** - verify links and outputs
  work before presenting them.

## The 2-agent rule, in detail

The single most useful piece of discipline this toolkit installs.

For any task that involves more than a one-shot lookup, Claude spawns at
least two agents:

- **Worker** - does the work.
- **Checker** - independently verifies the work and reports PASS or FAIL
  with details.

The Worker and the Checker run as separate sub-agents - different
contexts, different instances. The Checker reads the result fresh and
either approves it or sends it back with specifics.

For complex tasks, more roles can be added: Architect (plans), Specialist
(domain expertise), Reviewer (style / consistency), Tester (final
verification). Always at least two; more when the cost of being wrong is
high.

This catches bugs the single-agent flow would miss. The classic case is
a Worker writing code, declaring done, and a Checker noticing a
production edge case the Worker rationalized away. The marginal cost
of a second agent is small; the marginal value of catching real defects
is large.

## Compact hooks: persisting state through context compression

Claude Code's auto-compact runs when the conversation context approaches
the model's limit. It summarizes the older parts of the conversation to
free up tokens. Without intervention, the assistant loses track of the
current task at this boundary.

The `PreCompact` hook (`hooks/pre-compact.sh`) runs *before* the compact
and writes a snapshot to disk: active TODOs, the last user message, key
files modified this session, decisions made. The `PostCompact` hook
(`hooks/post-compact.sh`) runs *after* the compact and emits a one-line
reminder telling Claude to read the snapshot file before continuing.

The recommended setup also sets `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE=50` in
the `env` block of `~/.claude/settings.json`. That lowers the auto-compact
threshold from the default (~95% of context) to 50%, so compaction fires
on a fresher window - the snapshot is cleaner and the post-compact summary
has more headroom to preserve. See `docs/COMPACT_SETUP.md` for tuning.

Net effect: the conversation gets compacted, but the assistant doesn't
lose the plot.

## Permission mode: `auto` is the default

Claude Code supports several permission modes. This toolkit recommends
`auto` as the default.

- `auto` - accepts safe, low-risk operations automatically (reads, simple
  queries) and prompts on writes, shell commands, or anything risky.
  Safer than full bypass without losing flow.
- `bypassPermissions` - accepts everything. Useful for sandboxed
  environments where you trust every tool call. Not recommended as the
  default for an interactive session.
- The default Claude Code mode - prompts on most non-read operations.
  Safest, but the prompt frequency interrupts flow.

The recommendation here is `auto`. If you prefer one of the others,
edit `~/.claude/settings.json` after install.

## End-to-end example

Here's a concrete walk-through. You sit down at a fresh session in
`$HOME/Desktop/claude/`.

1. **Session start.** Claude reads `CLAUDE.md`, then runs
   `python3 tools/memory_search.py wake-up` - about 200 tokens of fresh
   context: recent interactions, active projects, contacts gone silent.
2. **You ask:** "What did `Vendor X` say about the quote?"
3. **Claude checks the contact DB** for `Vendor X` (one query, ~5ms).
   Finds the contact and the most recent interaction.
4. **Claude searches semantically** - `memory_search.py search "Vendor X
   quote"` - across all 9 collections. Pulls up the briefing entry, the
   notes from the call, the email thread reference.
5. **Claude reads** the appropriate memory files and gives you the answer
   with citations to the files.
6. **Mid-conversation, you say:** "Decided to go with `Vendor X` over
   `Vendor Y`."
7. **Claude calls `note.py decision`** the moment the decision is made.
   The decision is captured before you move on, not at the end of the topic.
8. **You move on to a real task** - say, drafting a contract review.
9. **Claude spawns a Worker + a Checker.** Worker drafts, Checker
   independently reads the contract, lists deviations from your playbook.
   You review both outputs.
10. **The conversation gets long.** Claude Code auto-compacts. The
    `PreCompact` hook saves session state. After the compact, the
    `PostCompact` hook reminds Claude to restore it. The Worker / Checker
    cycle continues uninterrupted.

That flow is the toolkit's design point. Memory + tools + cross-account
inbox + rules + 2-agent discipline + compact-resilient state, all in one
workspace.

## Where to go next

- **Install it:** [`README.md`](README.md) - quick start commands.
- **Pick individual pieces:** [`MODULAR.md`](MODULAR.md) - install a subset.
- **Already installed an older version:** [`UPGRADING.md`](UPGRADING.md).
- **Contribute:** [`CONTRIBUTING.md`](CONTRIBUTING.md) - how to file
  issues and PRs.
