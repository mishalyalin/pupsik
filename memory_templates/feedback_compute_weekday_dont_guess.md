---
name: Compute weekday from date, never guess
description: Briefings / scheduling / "this week" views MUST derive the weekday from the current ISO date programmatically. Guessing or pattern-matching from a prior brief = bug.
type: feedback
---

# Compute weekday from the date — never pattern-match

When generating any morning briefing, calendar table, "today" header, or "this week" view:

- The harness gives an absolute date (e.g. "Today's date is 2026-04-26"). **Compute the day-of-week from that date** before writing any "Sat/Sun/Mon" labels.
- Never reuse the day-label from a previous briefing or filename. Last brief's day ≠ today's day.

## Why this matters

If you write the wrong weekday, every downstream artefact shifts: calendar tables show Mon's events under "Sun", weekend rules misfire ("batch B2B pings to Mon" delivered the wrong day), and meeting conflicts get hidden. This is one of the easiest mistakes to make and the costliest to ship — because the rest of the briefing looks right.

## How to apply

1. Before writing the briefing title, compute the weekday from the ISO date:
   - macOS: `date -j -f "%Y-%m-%d" "2026-04-26" "+%A"`
   - Linux: `date -d 2026-04-26 +%A`
2. For a week table, generate ALL 7 days from today's date arithmetic. Do not reuse last week's table.
3. When matching calendar events to days: API returns ISO dates — match against your computed weekday list, not against prior labels.
4. Saturday vs Sunday matters operationally (e.g. weekend rules). If today=Sun, "Mon batch" = TOMORROW, not "in 2 days". Wrong day → wrong urgency.

## Antipattern

- ❌ Copying yesterday's brief and updating only the date number — the weekday label silently lies.
- ❌ Inferring the weekday from "looks like a Saturday" intuition.
- ❌ Trusting the previous file's name as the source of truth for today.
