---
name: Verify project state before answering
description: 🔴 MANDATORY. Before any answer about project / payment / partner status, verify with fresh data (recent email, last 7 days, all configured accounts) — don't rely on `CLAUDE.md` alone.
type: feedback
---

# 🔴 Verify project state before answering

**Any claim about status (open/closed, paid/unpaid, shipped/not, waiting/received) requires checking fresh data before saying it out loud.**

## Why

`CLAUDE.md` is a snapshot at the last update. Between updates, the inbox accumulates new facts: opened accounts, shipments with tracking numbers, payments, signed documents, partner status changes. Answering only from `CLAUDE.md` ships an outdated picture as if it were current. That's worse than "I don't know" — it's misinformation delivered with confidence.

## How to apply

Before any answer / plan / recommendation that depends on the current state of a project:

1. **Email — all configured accounts, last 7 days** (e.g. `gmail_search_all` if multi-account MCP is installed):
   - By the partner / topic of the question
   - Search terms: `tracking`, `invoice`, `paid`, `shipped`, `signed`, `confirmed`, `verification`, `authorized`, `delivered`

2. **Any chat groups mentioned in the user's `CLAUDE.md`** (WhatsApp, Slack, Telegram, etc.) — supply-chain or partner conversations often happen there before email.

3. **`CLAUDE.md` Active Projects / Pending Decisions** — cross-check against the freshly-pulled facts.

4. **If a fresh fact contradicts `CLAUDE.md`** — update `CLAUDE.md` inline (status, date, tracking, amount) BEFORE replying. Update `## Last Updated`.

5. **Only then** answer the user with the current picture.

## Search templates (Gmail-style)

- `(payment OR invoice OR paid OR settled) after:YYYY/MM/DD`
- `(tracking OR shipped OR shipment OR delivery OR carrier) after:YYYY/MM/DD`
- `(signed OR contract OR agreement OR quotation OR quote) after:YYYY/MM/DD`
- By partner: `(from:@domain.com OR to:@domain.com) after:YYYY/MM/DD`

## Exceptions

If the question is clearly not about state (e.g. "explain what X is", "write code for Y") — verification is not needed. But any plan / next steps / "what's happening with" / "what's next" → REQUIRES verification.

## Antipattern

- ❌ Answering "X is still waiting" from `CLAUDE.md` when the inbox has the resolution from yesterday.
- ❌ Treating `CLAUDE.md` as live state instead of a snapshot.
- ❌ "I don't want to make extra tool calls" — that's exactly what makes the system valuable.
