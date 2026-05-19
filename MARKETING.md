# Marketing copy

Drop-in copy for sharing the repo. Pick the channel, copy the block, tweak.

I'm not a marketer. These are the words I'd use if someone asked me what this is.

---

## Twitter / X - thread

```
I run my whole company on Claude Code.

Sales, ops, finance, taxes, kids' school stuff. Not just code.

The problem: it forgets everything between sessions.

So I built a workspace toolkit. Open-sourced today.

→ contact graph DB
→ semantic search across 9 ChromaDB collections
→ all 3 of my Gmail accounts in one call (multi-account MCPs)
→ rule discipline pinned to every session (top rule: NEVER IMAGINE, ALWAYS VERIFY)
→ `rules.py search "<topic>"` pulls the full verification protocol on demand
→ 2-agent worker + checker for anything I'd actually ship
→ moment-of-emergence knowledge capture

MIT. macOS. Local-first. No cloud sync, no telemetry.

github.com/mishalyalin/pupsik
```

## Twitter / X - single tweet (under 280)

```
Open-sourced the workspace I run my whole company on. Claude Code with persistent memory, multi-account inbox, rule discipline, auto-capture knowledge base. MIT.

github.com/mishalyalin/pupsik
```

## LinkedIn

```
For a few months now I've been running my entire company through Claude Code. Sales, ops, finance, taxes, customer success, kids' school logistics. Not just code.

The bottleneck was never Claude's intelligence. It was state. Every session started from zero. Every morning I was re-explaining who Marco at the box supplier was, what was happening with the BV setup, which deals were live.

So I built the missing layer. Persistent contact graph. Semantic memory across 9 ChromaDB collections. Multi-account Gmail / Calendar / WhatsApp through local MCP servers. A 2-agent worker + checker rule that catches the bugs a single-agent pass misses. Auto-capture knowledge base that surfaces decisions I made three weeks ago.

Open-sourcing it today. MIT. Generic, no personal data anywhere.

If you're a solo operator getting leverage from Claude Code and feel the same friction - fork it, take what you need.

→ github.com/mishalyalin/pupsik
```

## Hacker News - title

```
Show HN: I run my whole company on Claude Code - here's the workspace I built
```

Or:

```
Show HN: Pupsik - Claude Code workspace with persistent memory, MCPs, rule discipline
```

Body (~500 chars):

```
I'm a solo founder. I run my whole company through Claude Code, not just code. Over a few months I built a workspace toolkit so it doesn't lose context between sessions: SQLite contact graph, ChromaDB semantic search across 9 collections, multi-account Gmail / Cal / WhatsApp MCPs, a 2-agent worker + checker rule, a `note.py` capture-on-emergence tool, a `rules.py` retrieval tool that loads the full text of verification rules before non-trivial outbound, auto-compact hooks, and a doctor for keeping the workspace healthy. The top rule, pinned to every session: never imagine, always verify - any number / date / fact / name in any output must trace back to a real source before stating.

Open-sourcing today. MIT.

Repo: https://github.com/mishalyalin/pupsik
```

## Reddit - r/ClaudeAI, r/LocalLLaMA, r/selfhosted

Title:

```
[OSS] The workspace I run my whole company on. Claude Code with persistent
memory, multi-account inbox MCPs, rule discipline.
```

Body:

```
Hey. Solo founder. Spent the last few months running my whole company through Claude Code (sales, ops, finance, kids' stuff) and built a workspace toolkit so it stays useful between sessions.

What's in it:

- SQLite contact graph DB. People, companies, interactions, links. Graph traversal, intro chains, staleness detection.
- ChromaDB semantic search across 9 collections (memory files, briefings, outputs, journal, learnings, decisions, research, plus the contact DB).
- Multi-account Gmail + Calendar + WhatsApp via local MCP servers. I have 3 Gmail accounts; one call hits all of them.
- 2-agent worker + checker rule. Catches the single-agent bugs.
- `note.py` for moment-of-emergence knowledge capture. Upsert by title.
- `rules.py` for on-demand rule retrieval. `rules.py search "<topic>"` pulls the full text of any matched verification rule into the session before the agent drafts outbound work. The top rule: never imagine, always verify.
- `doctor.py` for workspace health. 13 deterministic checks, safe auto-fix.
- Auto-compact hooks so the conversation survives context compression.
- A `~/.claude/rules/critical-rules.md` template that pins MANDATORY rules to every session.

Local-first. MIT. macOS for the WhatsApp piece, the rest is portable.

Repo: https://github.com/mishalyalin/pupsik
```

## Dev.to - title

```
How I made Claude Code remember things between sessions (and the toolkit
I'm open-sourcing)
```

## Indie Hackers - title

```
Open-sourcing the Claude Code workspace I run my whole company on
```

---

## Notes for posting

- Hacker News slot is one shot. Pick the day. Tuesday-Thursday morning Pacific does best.
- LinkedIn version is a story, not a pitch. Deliberate.
- Twitter: the thread converts better than the single tweet for tooling repos. Threads invite scrolling.
- Reddit: each community has its own self-promo norms. Read the rules first; some require `[OSS]` or `[Show]` prefixes.
- Star count to aim for in week 1: 100. After that GitHub trending starts surfacing it organically.

## Hashtags to consider

`#ClaudeCode` `#OpenSource` `#AI` `#Productivity` `#SoloFounder` `#MCP` `#SemanticSearch` `#LocalFirst`
