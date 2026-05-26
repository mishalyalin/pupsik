---
name: briefing-pass3-direct-audit
description: 🔴 Morning briefing MANDATORY Pass 3 — direct compact-list audit by Claude in main context (no subagent delegation). Catches Pass 1 / Pass 2 misclassification and in-window misses.
metadata:
  type: feedback
---

# Morning briefing Pass 3 — direct compact-list audit (NO subagent)

After Pass 1 (filtered subagent) + Pass 2 (unfiltered fallback subagent, if used), Claude itself MUST run a third pass directly in main context, reading the compact list of all inbox messages last 48h.

**Why:** Sub-agent prompt tightening has failed repeatedly to fix two failure modes:

1. **Misattribution** — subagent reads an inbox message in a thread and reports it as the OWNER's outbound action (because owner's name appears in the thread byline). The briefing then includes a false "owner already replied to X" claim.
2. **In-window miss** — subagent runs `newer_than:1d` but reports "all silent" while a high-signal counter-party reply sits comfortably in the window. Subagent grep over from-fields drifts or summarises too aggressively.

Direct-read by Claude in main context eliminates both: no attribution drift, no summarisation loss.

**How to apply:**

1. After Pass 1 + Pass 2 subagents return, BEFORE composing the briefing.
2. `gmail_search_all` (or equivalent) with `newer_than:2d max_per_account=100`. Expect ~80-150 messages across accounts. Raw JSON usually too large for context — it auto-spills to `tool-results/` overflow file. **Do NOT read the full file.**
3. Inline-Python extract compact list from overflow file. Format:
   ```
   [unread] [acct8] [date25] | [from:50] | [subject:70]
   ```
   ~100 lines, fits comfortably in main context.
4. Claude reads compact list DIRECTLY (no Agent tool, no delegation). Scan for:
   - **Tracker counter-party activity** that Pass 1 said was "silent" — strongest single signal. Grep every counter-party currently in your escalation tracker.
   - **Gov/regulator** that Pass 2 might have dropped.
   - **Real-human cold inbound** from unknown senders.
5. If MISS found: `gmail_read_message` to read body → correct briefing state inline → update relevant memory file → bump/resolve tracker accordingly.
6. Mention the miss explicitly in the Architect lens: "Pass 1 missed X — caught by Pass 3 compact-list audit". Creates audit trail + makes failure mode visible to the owner.

**Trigger:** every morning-briefing run, no exceptions. Even on quiet weekends.

**Cost:** ~5-10 seconds of Claude main-context tokens (~100 lines compact list + scan). Trivial vs the cost of missing a high-signal counter-party reply.

**Why this is the structural fix vs more subagent rules:**
- Tightening subagent prompts hasn't worked across multiple incidents.
- Pass 3 = different layer of defense: direct verification by the entity that ships the briefing, not by a delegated subagent.
- Long-term answer is multi-agent observability hooks; Pass 3 is the bridge until that lands.

Related: [[feedback_never_imagine_always_verify]], [[feedback_always_two_agents]], [[feedback_scan_sent_regularly]]
