# feedback_know_current_datetime.md

🔴 **MANDATORY.** Always know today's date, time, day-of-week, and timezone. **Timezone is auto-detected** from `/etc/localtime` on the user's laptop - it moves with them across travel. Workspace = `~/Desktop/claude/`.

## The rule

1. **Trust the SessionStart `NOW:` anchor.** Hook `~/Desktop/claude/.claude/hooks/session-start-reminder.sh` injects a live timestamp into every session via `tools/now.py --anchor`. That line shows `Local zone: <IANA> - You are in <city>`. Authoritative.
2. **Trust the system `currentDate`.** Claude Code injects today's date into the system prompt - read it.
3. **Re-check before any date reference.** If you say "today", "yesterday", "tomorrow", "this week", "Tuesday", "next Friday" - run `python3 ~/Desktop/claude/tools/now.py --short` (it's < 50 ms) or grep for `currentDate` in your context. Two seconds of verification beats another precedent.
4. **NEVER pattern-match dates from conversation history.** Prior briefings reference past dates as "today". If you reuse that phrasing without re-anchoring, you describe yesterday as today and miss the actual today.
5. **NEVER treat the actual current date as future.** If a user mentions a reminder dated today, that reminder is firing NOW, not in the future.
6. **NEVER hard-code the user's location or timezone.** The user may travel. The system TZ on their laptop is the source of truth. If you think you know they are "in <city X>" without running `now.py`, you are guessing. Use `now.py --tz <IANA>` to override only when you have a specific reason (e.g. computing event times in a different zone for someone else).

## Why this rule exists

Pattern-match failures: in a session you can refer to a date as if it were still in the future when it has already arrived. The `currentDate` system field already holds the correct date - the bug is pattern-matching from stale briefing text that referenced an earlier date as "today" and never re-anchoring.

If a user reports date confusion (e.g. "today is X, why did you treat it as future"), treat it as a recurring failure mode and audit your anchor-trust discipline. The fix is not better memory; the fix is to never trust remembered dates over the anchor.

## What the supporting fix looks like

- `~/Desktop/claude/tools/now.py` - 4 modes (full / `--short` / `--json` / `--anchor`) + `--tz <IANA>` override. **Detects IANA timezone from `/etc/localtime` symlink** (macOS / Linux), extracts the city, computes weekday / ISO week / part-of-day / tomorrow / yesterday. Falls back to a default zone only if detection fails (and surfaces a WARN in that case).
- `~/Desktop/claude/.claude/hooks/session-start-reminder.sh` - injects a `⏰ NOW: YYYY-MM-DD (Weekday), HH:MM TZ. Local zone: <IANA> - You are in <city>.` line before the staleness warning. First thing the agent reads at every session start.
- This rule (`memory/feedback_know_current_datetime.md`).
- A compact pointer in `~/.claude/rules/critical-rules.md` MANDATORY section.

## Self-check examples

Wrong:
- "Friday is the X call" (stale - it's actually Thursday per anchor).
- "Tomorrow we ship Y" (stale - production was yesterday per anchor).
- "The appointment is Tuesday" (stale - the appointment happened on a prior Tuesday; today per anchor is later in the week).
- "You are in <some city>" - asserted without running `now.py`. Look at the anchor; the user could be anywhere.

Right:
- "Today (per anchor: Thu YYYY-MM-DD, HH:MM TZ, you in <city per system tz>) the X call is at 15:00 local."
- "Anchor says you are in Tokyo (Asia/Tokyo). Calendar event in another zone converts to JST+offset."

## Operational invariants

- Never ask the user what day it is.
- Never ask the user what timezone they are in - read the anchor / run `now.py`. Their laptop tz is the source of truth.
- Never ask the user where their workspace is (always `~/Desktop/claude/`).
- Never assume a fixed location for the user without checking the anchor.
- If `now.py` reports `timezone_source: fallback` (WARN), it means `/etc/localtime` was unreadable - flag this and ask the user to confirm location.
- If `now.py` is missing entirely, fall back to `date '+%Y-%m-%d %H:%M:%S %Z %A'` (which already uses system tz). If THAT fails, ask the user (rare emergency).

## Cross-references

- Related: `feedback_compute_weekday_dont_guess.md` (compute weekday from ISO, don't pattern-match).
- Related: `feedback_verify_project_state.md` (don't answer from stale CLAUDE.md - verify fresh).
- Critical rules pointer: `~/.claude/rules/critical-rules.md`.
