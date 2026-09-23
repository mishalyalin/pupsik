#!/usr/bin/env python3
"""One-time migration for the v2026-09 slim release. Safe to run any number of times.

Usage: python3 tools/slim_migrate.py <home> <workspace>

- Removes PreCompact/PostCompact hook entries that point at pre-compact.sh /
  post-compact.sh, the autoCompactWindow key and env.CLAUDE_AUTOCOMPACT_PCT_OVERRIDE
  from <home>/.claude/settings.json. Backs the file up first. If settings.json is a
  symlink, the target is edited in place (the link stays) and its mode is kept.
- Moves the retired workspace files into <home>/.claude/pupsik-removed-<date>/.
- Never overwrites an earlier backup: a second backup on the same day gets a .1, .2 ... suffix.
- Prints what it did, or "nothing to do".

Called by install.sh --update-only (so it runs on the first update, even when an
older update.sh is the one doing the pull). Clone-side only, not installed.
"""
import datetime
import json
import os
import shutil
import sys

RETIRED = [
    ".claude/hooks/pre-compact.sh",
    ".claude/hooks/post-compact.sh",
    "tools/context_budget.py",
    "tools/claude_md_trim.py",
    "tools/doctor.py",
    "tools/mcp_profile.py",
]
COMPACT_SCRIPTS = ("pre-compact.sh", "post-compact.sh")


def free_path(path):
    """Return path, or path.1, path.2 ... - the first one that does not exist yet."""
    if not os.path.lexists(path):
        return path
    n = 1
    while os.path.lexists(f"{path}.{n}"):
        n += 1
    return f"{path}.{n}"


def clean_settings(data, done):
    changed = False
    hooks = data.get("hooks")
    if isinstance(hooks, dict):
        for event in ("PreCompact", "PostCompact"):
            groups = hooks.get(event)
            if not isinstance(groups, list):
                continue
            kept_groups = []
            for g in groups:
                inner = g.get("hooks") if isinstance(g, dict) else None
                if not isinstance(inner, list):
                    kept_groups.append(g)
                    continue
                kept = [h for h in inner
                        if not (isinstance(h, dict) and any(n in str(h.get("command", "")) for n in COMPACT_SCRIPTS))]
                if len(kept) != len(inner):
                    changed = True
                    done.append(f"removed {len(inner) - len(kept)} {event} hook(s) from settings.json")
                if kept:
                    kept_groups.append(dict(g, hooks=kept))
            if kept_groups:
                hooks[event] = kept_groups
            else:
                del hooks[event]
        if not hooks:
            del data["hooks"]
    if "autoCompactWindow" in data:
        del data["autoCompactWindow"]
        changed = True
        done.append("removed autoCompactWindow from settings.json")
    env = data.get("env")
    if isinstance(env, dict) and "CLAUDE_AUTOCOMPACT_PCT_OVERRIDE" in env:
        del env["CLAUDE_AUTOCOMPACT_PCT_OVERRIDE"]
        if not env:
            del data["env"]
        changed = True
        done.append("removed env.CLAUDE_AUTOCOMPACT_PCT_OVERRIDE from settings.json")
    return changed


def main():
    if len(sys.argv) != 3:
        print(__doc__.strip().splitlines()[2])
        return 2
    home, ws = sys.argv[1], sys.argv[2]
    backup_dir = os.path.join(home, ".claude", "pupsik-removed-" + datetime.date.today().isoformat())
    done = []

    settings = os.path.join(home, ".claude", "settings.json")
    if os.path.isfile(settings):
        real = os.path.realpath(settings)  # write through a symlink, never replace it
        try:
            with open(real, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError) as e:
            data = None
            print(f"[pupsik] migration: could not parse {settings} ({e}) - left it alone")
        if isinstance(data, dict) and clean_settings(data, done):
            os.makedirs(backup_dir, exist_ok=True)
            bak = free_path(os.path.join(backup_dir, "settings.json.bak"))
            shutil.copy2(real, bak)
            tmp = real + ".pupsik-tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
                f.write("\n")
            shutil.copymode(real, tmp)
            os.replace(tmp, real)
            done.insert(0, f"backed up settings.json to {bak}")

    for rel in RETIRED:
        src = os.path.join(ws, rel)
        if not os.path.isfile(src):
            continue
        dst = free_path(os.path.join(backup_dir, rel))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
        os.remove(src)
        done.append(f"moved {rel} to {dst}")

    if done:
        print("[pupsik] slim migration (v2026-09):")
        for line in done:
            print("  - " + line)
    else:
        print("[pupsik] slim migration (v2026-09): nothing to do")
    return 0


if __name__ == "__main__":
    sys.exit(main())
