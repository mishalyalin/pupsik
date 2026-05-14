#!/usr/bin/env python3
"""Print your current datetime context - single source of truth.

Timezone is auto-detected from the system (`/etc/localtime` symlink on macOS/Linux).
The user's laptop TZ follows them across travel - NEVER hard-code a zone in caller code.

Workspace = ~/Desktop/claude/.

Designed to be invoked:
1. At SessionStart (via hook) so the agent gets a hard time anchor on every session.
2. Any time Claude is about to reference 'today/yesterday/tomorrow' and has any doubt.
3. Before composing briefings, calendar slots, or anything date-sensitive.

NEVER pattern-match dates from conversation history when this tool is one shell call away.

Usage:
  now.py                       # Full context (default)
  now.py --short               # Single line: YYYY-MM-DD HH:MM TZ Weekday
  now.py --json                # Machine-readable
  now.py --anchor              # Compact one-paragraph anchor for SessionStart hook
  now.py --tz Asia/Tokyo       # Force a specific IANA zone (override system detection)

Detection precedence:
  1. --tz CLI flag (explicit override)
  2. /etc/localtime symlink (macOS / most Linux)
  3. Fallback: Europe/London is a common default; change to your own preferred fallback if elsewhere
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys

try:
    import zoneinfo
except ImportError:
    print("ERROR: zoneinfo not available (need Python 3.9+).", file=sys.stderr)
    sys.exit(1)


def detect_iana_tz() -> tuple[str, str]:
    """Return (iana_name, source) describing how we resolved the timezone.

    source is one of: 'symlink', 'fallback'.
    Caller should treat 'fallback' as low-confidence and consider warning.
    """
    try:
        link = os.readlink("/etc/localtime")
        # Examples:
        #   macOS:  /var/db/timezone/zoneinfo/Europe/London
        #   Linux:  /usr/share/zoneinfo/Europe/London
        marker = "zoneinfo/"
        idx = link.find(marker)
        if idx >= 0:
            iana = link[idx + len(marker):]
            # Sanity check: must contain a slash (Continent/City) and be loadable.
            if "/" in iana:
                zoneinfo.ZoneInfo(iana)  # raises if invalid
                return iana, "symlink"
    except (OSError, zoneinfo.ZoneInfoNotFoundError, ValueError):
        pass
    return "Europe/London", "fallback"


def iana_to_city(iana: str) -> str:
    """Convert 'Europe/London' -> 'London', 'America/Los_Angeles' -> 'Los Angeles'."""
    if "/" not in iana:
        return iana
    last = iana.rsplit("/", 1)[-1]
    return last.replace("_", " ")


def part_of_day(hour: int) -> str:
    # 13:00+ reads as afternoon, not midday.
    if hour < 6:
        return "early morning"
    if hour < 12:
        return "morning"
    if hour < 13:
        return "midday"
    if hour < 18:
        return "afternoon"
    if hour < 22:
        return "evening"
    return "late evening"


def compute_now(forced_iana: str | None = None) -> dict:
    if forced_iana:
        iana = forced_iana
        source = "override"
        zoneinfo.ZoneInfo(iana)  # raises if invalid
    else:
        iana, source = detect_iana_tz()

    tz = zoneinfo.ZoneInfo(iana)
    now = dt.datetime.now(tz=tz)

    return {
        "iso_date": now.strftime("%Y-%m-%d"),
        "iso_time": now.strftime("%H:%M:%S"),
        "iso_datetime": now.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "timezone_abbr": now.strftime("%Z"),
        "timezone_iana": iana,
        "timezone_source": source,
        "weekday": now.strftime("%A"),
        "weekday_short": now.strftime("%a"),
        "week_iso": int(now.strftime("%V")),
        "day_of_year": int(now.strftime("%j")),
        "part_of_day": part_of_day(now.hour),
        "user_location": iana_to_city(iana),
        "workspace": str(os.path.expanduser("~/Desktop/claude/")),
        "tomorrow": (now + dt.timedelta(days=1)).strftime("%A %Y-%m-%d"),
        "yesterday": (now - dt.timedelta(days=1)).strftime("%A %Y-%m-%d"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--short", action="store_true", help="Single-line output")
    group.add_argument("--json", action="store_true", help="JSON output")
    group.add_argument("--anchor", action="store_true", help="Compact anchor for SessionStart hook")
    parser.add_argument("--tz", help="Force IANA timezone (e.g. Asia/Tokyo). Overrides system detection.")
    args = parser.parse_args()

    try:
        d = compute_now(forced_iana=args.tz)
    except zoneinfo.ZoneInfoNotFoundError:
        print(f"ERROR: unknown IANA timezone: {args.tz!r}", file=sys.stderr)
        return 2

    # Confidence hint - if we fell back, surface that so the user can sanity-check.
    tz_note = ""
    if d["timezone_source"] == "fallback":
        tz_note = "  [WARN: /etc/localtime unreadable, falling back to default]"
    elif d["timezone_source"] == "override":
        tz_note = "  [user-forced via --tz]"

    if args.json:
        print(json.dumps(d, indent=2))
        return 0

    if args.short:
        print(f"{d['iso_date']} {d['iso_time']} {d['timezone_abbr']} {d['weekday']}")
        return 0

    if args.anchor:
        suffix = f" ({d['timezone_source']})" if d["timezone_source"] != "symlink" else ""
        print(
            f"NOW: {d['iso_date']} ({d['weekday']}), "
            f"{d['iso_time']} {d['timezone_abbr']} ({d['part_of_day']}). "
            f"Week {d['week_iso']}. "
            f"Local zone: {d['timezone_iana']} - You are in {d['user_location']}{suffix}. "
            f"Tomorrow={d['tomorrow']}, yesterday={d['yesterday']}."
        )
        return 0

    # Full output (default)
    print(f"NOW (system-local time)")
    print(f"   Date:      {d['iso_date']} ({d['weekday']})")
    print(f"   Time:      {d['iso_time']} {d['timezone_abbr']} ({d['part_of_day']})")
    print(f"   ISO week:  {d['week_iso']}, day {d['day_of_year']}/365")
    print(f"   Timezone:  {d['timezone_iana']} ({d['timezone_abbr']}){tz_note}")
    print(f"   Location:  You are in {d['user_location']} (derived from system tz)")
    print(f"   Workspace: {d['workspace']}")
    print()
    print(f"Tomorrow:  {d['tomorrow']}")
    print(f"Yesterday: {d['yesterday']}")
    print()
    print(f"TZ source: {d['timezone_source']} (symlink=auto-detected from /etc/localtime, "
          f"override=--tz flag, fallback=detection failed).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
