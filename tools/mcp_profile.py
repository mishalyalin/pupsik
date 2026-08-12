#!/usr/bin/env python3
"""mcp_profile.py - park MCP servers you are not using today, to buy back context.

The problem this solves. Tool *schemas* already load on demand: the agent defers
them and fetches one when it needs it. But every configured MCP server's
*instructions block* is injected into the session prompt unconditionally at
start, and there is no way to unload a server mid-session. So the only lever is
which servers are configured when the session begins. On a stack with a dozen
connectors that block is tens of thousands of tokens spent before you type - see
`tools/context_budget.py start` for what yours actually costs.

    light    keep only the servers in the daily set, move the rest to the park
    full     restore everything from the park
    status   show what is configured now and what is parked

The daily set defaults to the MCP servers pupsik installs (multi-gmail,
multi-gcal, whatsapp, telegram-readonly). Override per run:

    python3 tools/mcp_profile.py light --keep multi-gmail,whatsapp
    PUPSIK_MCP_DAILY=multi-gmail,multi-gcal python3 tools/mcp_profile.py light

Parked entries are stored verbatim in ~/.claude/mcp-parked.json - that park file
is what makes `full` lossless. Every rewritten file is ALSO copied to a
timestamped `.bak-mcpprofile-<n>` next to itself, as a plain human undo net; the
tool never reads those backups back.

A profile change takes effect on the NEXT Claude start (quit and reopen) - the
instructions are read once at session start.
"""

import argparse
import json
import os
import shutil
import sys

HOME = os.path.expanduser("~")
PARK_PATH = os.path.join(HOME, ".claude", "mcp-parked.json")
DEFAULT_DAILY = ["multi-gmail", "multi-gcal", "whatsapp", "telegram-readonly"]

# (label, path) pairs. A stack usually has a global config plus a per-workspace
# one; both are rewritten so a parked server cannot sneak back in via the other.
def config_targets(workspace):
    return [
        ("global", os.path.join(HOME, ".claude.json")),
        ("workspace", os.path.join(os.path.expanduser(workspace), ".claude", "settings.json")),
    ]


def load_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def backup_once(path, prefix=".bak-mcpprofile"):
    """Copy `path` aside without ever overwriting an older backup.

    A fixed backup name would be clobbered on the second profile change:
    `light` writes the original aside, then `full` writes the light state over
    the same name and the true original is gone. So each backup gets its own
    number.
    """
    if not os.path.exists(path):
        return None
    n = 1
    while os.path.exists("%s%s-%d" % (path, prefix, n)):
        n += 1
    dest = "%s%s-%d" % (path, prefix, n)
    shutil.copy(path, dest)
    return dest


def save_json(path, data):
    backup_once(path)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


def read_park():
    if os.path.exists(PARK_PATH):
        try:
            return load_json(PARK_PATH)
        except ValueError:
            print("warning: %s is not valid JSON, treating park as empty" % PARK_PATH)
    return {}


def write_park(data):
    os.makedirs(os.path.dirname(PARK_PATH), exist_ok=True)
    # The park file is the thing that makes `full` lossless, so never overwrite
    # an existing one blind - especially the unreadable case, where read_park()
    # has already fallen back to empty and the old content would just vanish.
    backup_once(PARK_PATH)
    with open(PARK_PATH, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


def resolve_daily(args):
    if args.keep:
        return [s.strip() for s in args.keep.split(",") if s.strip()]
    env = os.environ.get("PUPSIK_MCP_DAILY")
    if env:
        return [s.strip() for s in env.split(",") if s.strip()]
    return list(DEFAULT_DAILY)


def cmd_light(args):
    daily = set(resolve_daily(args))
    print("daily set: %s" % ", ".join(sorted(daily)))
    park = read_park()
    moved_any = False
    for label, path in config_targets(args.workspace):
        if not os.path.exists(path):
            print("  %-10s no config at %s - skipped" % (label, path))
            continue
        try:
            data = load_json(path)
        except ValueError as exc:
            print("  %-10s invalid JSON (%s) - skipped, nothing written" % (label, exc))
            continue
        servers = data.get("mcpServers") or {}
        keep = {k: v for k, v in servers.items() if k in daily}
        move = {k: v for k, v in servers.items() if k not in daily}
        if not move:
            print("  %-10s nothing to park" % label)
            continue
        park.setdefault(label, {}).update(move)
        data["mcpServers"] = keep
        save_json(path, data)
        moved_any = True
        print("  %-10s parked %s" % (label, ", ".join(sorted(move))))
    if moved_any:
        write_park(park)
        print("\npark: %s" % PARK_PATH)
        print("profile `light` staged. Quit and reopen Claude to apply.")
    else:
        print("\nnothing changed - already light.")
    return 0


def cmd_full(args):
    park = read_park()
    if not park:
        print("park is empty - nothing to restore")
        return 0
    restored_any = False
    for label, path in config_targets(args.workspace):
        add = park.get(label) or {}
        if not add:
            continue
        if not os.path.exists(path):
            print("  %-10s no config at %s - keeping entries parked" % (label, path))
            continue
        try:
            data = load_json(path)
        except ValueError as exc:
            print("  %-10s invalid JSON (%s) - keeping entries parked" % (label, exc))
            continue
        data.setdefault("mcpServers", {}).update(add)
        save_json(path, data)
        park.pop(label, None)
        restored_any = True
        print("  %-10s restored %s" % (label, ", ".join(sorted(add))))
    if park:
        write_park(park)
        print("\nsome entries stayed parked (see above): %s" % PARK_PATH)
    elif os.path.exists(PARK_PATH):
        os.remove(PARK_PATH)
    if restored_any:
        print("\nprofile `full` staged. Quit and reopen Claude to apply.")
    return 0


def cmd_status(args):
    for label, path in config_targets(args.workspace):
        if not os.path.exists(path):
            print("  %-10s (no config)" % label)
            continue
        try:
            servers = sorted((load_json(path).get("mcpServers") or {}).keys())
        except ValueError:
            print("  %-10s invalid JSON" % label)
            continue
        print("  %-10s %s" % (label, ", ".join(servers) if servers else "(none)"))
    park = read_park()
    if park:
        for label, servers in sorted(park.items()):
            print("  parked/%-3s %s" % (label, ", ".join(sorted(servers))))
    else:
        print("  parked     (nothing)")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Park unused MCP servers so their instructions stop loading at session start.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = ap.add_subparsers(dest="cmd")
    for name, fn in (("light", cmd_light), ("full", cmd_full), ("status", cmd_status)):
        p = sub.add_parser(name, help=(fn.__doc__ or name))
        p.add_argument(
            "--workspace",
            default="~/Desktop/claude",
            help="workspace whose .claude/settings.json also holds MCP config",
        )
        p.add_argument(
            "--keep",
            default=None,
            help="comma-separated servers to keep (default: PUPSIK_MCP_DAILY or the pupsik four)",
        )
        p.set_defaults(func=fn)
    args = ap.parse_args(argv)
    if not getattr(args, "func", None):
        return cmd_status(ap.parse_args(["status"]))
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
