---
name: Compute weekday from date, never guess
description: Briefings/scheduling MUST derive weekday from current date programmatically. Guessing or pattern-matching from prior brief = bug. Especially on weekends.
type: feedback
originSessionId: afe4e8b0-027c-486c-93b2-51ad76f5b3d8
---
When generating any morning briefing, calendar table, or "this week" view:
- The system gives an absolute date (e.g. "Today's date is 2026-04-26"). **Compute the day-of-week from that date** before writing any "Sat/Sun/Mon" labels.
- Never pattern-match from previous briefing or from the file name. Last brief's day ≠ today's day.

**Why:** 26 Apr 2026 = Sunday. I wrote "Saturday" everywhere in the brief because I assumed without checking. The whole week table shifted by one day - Mon 27 was labelled "Sun 27", "Mon 28" was actually Tue 28, etc. Caused real harm: missed a calendar conflict on Wed 29 because the day labels were wrong, and pushed the "Mon batch pings" reminder to the wrong day.

**How to apply:**
1. Before writing the briefing title, run `date` via Bash or compute weekday from the ISO date in CLAUDE.md's `currentDate`. One Bash call: `date -j -f "%Y-%m-%d" "2026-04-26" "+%A"` (macOS) or `date -d 2026-04-26 +%A` (Linux).
2. For the week table, generate ALL 7 days from today's date arithmetic, don't reuse last brief's table.
3. When matching calendar events to days: the API returns ISO dates — match against your computed weekday list, don't trust prior labels.
4. Saturday vs Sunday matters operationally: weekend rule batches B2B pings to Mon. If today=Sun, "Mon batch" = TOMORROW not "in 2 days". Wrong day → wrong urgency.
