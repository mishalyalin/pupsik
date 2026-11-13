#!/usr/bin/env python3
"""One-time migrations for the slim releases. Safe to run any number of times.

Usage: python3 tools/slim_migrate.py [--move-rules] <home> <workspace>

v2026-09:
- Removes PreCompact/PostCompact hook entries that point at pupsik's old
  pre-compact.sh / post-compact.sh from <home>/.claude/settings.json. Backs the
  file up first. If settings.json is a symlink, the target is edited in place
  (the link stays) and its mode is kept. Claude's own settings (autoCompactWindow,
  env, model and the rest) are never touched.
- Moves the retired workspace files into <home>/.claude/pupsik-removed-<date>/.

v2026-11:
- Moves pupsik's smart-merge leftovers (<rule>.bak.<ts>, <rule>.new) out of
  Claude's built-in memory folder (<home>/.claude/projects/<slug>/memory/) into
  the same backup folder. Only files named after a pupsik rule are touched.
- With --move-rules: moves pupsik's feedback_*.md rule files from Claude's
  memory folder to <workspace>/rules/, so pupsik can update them again without
  writing into Claude's folder. Your own rule files stay where they are. Adds
  one line to <home>/.claude/rules/critical-rules.md saying where they are now.

Never overwrites an earlier backup: a second backup on the same day gets a .1,
.2 ... suffix. Prints what it did, or "nothing to do".

Called by install.sh --update-only (so it runs on the first update, even when an
older update.sh is the one doing the pull). Clone-side only, not installed.
"""
import datetime
import glob
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
HERE = os.path.dirname(os.path.abspath(__file__))
# Rules pupsik shipped before and no longer ships, so their leftovers get cleaned too.
REMOVED_RULES = [
    "feedback_capture_knowledge.md",
    "feedback_marketing_panel_default.md",
    "feedback_briefing_pass3_direct_audit.md",
    "feedback_session_retro.md",
]
RULES_NOTE = "Pupsik rule files (feedback_*.md) live in"


def free_path(path):
    """Return path, or path.1, path.2 ... - the first one that does not exist yet."""
    if not os.path.lexists(path):
        return path
    n = 1
    while os.path.lexists(f"{path}.{n}"):
        n += 1
    return f"{path}.{n}"


def clean_settings(data, done):
    """Drop only hook entries that run pupsik's retired compact scripts."""
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
    return changed


def move(src, dst, done, label):
    dst = free_path(dst)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copy2(src, dst)
    os.remove(src)
    done.append(f"moved {label} to {dst}")


def main():
    args = sys.argv[1:]
    move_rules = "--move-rules" in args
    args = [a for a in args if a != "--move-rules"]
    if len(args) != 2:
        print(__doc__.strip().splitlines()[2])
        return 2
    home, ws = args[0], os.path.abspath(args[1])
    backup_dir = os.path.join(home, ".claude", "pupsik-removed-" + datetime.date.today().isoformat())
    memory_dir = os.path.join(home, ".claude", "projects", ws.replace("/", "-"), "memory")
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
        if os.path.isfile(src):
            move(src, os.path.join(backup_dir, rel), done, rel)

    current = {os.path.basename(f) for f in glob.glob(os.path.join(HERE, "..", "memory_templates", "feedback_*.md"))}
    if os.path.isdir(memory_dir):
        for name in sorted(current | set(REMOVED_RULES)):
            base = os.path.join(memory_dir, glob.escape(name))
            for src in sorted(glob.glob(base + ".bak.*") + glob.glob(base + ".new")):
                if os.path.isfile(src):
                    move(src, os.path.join(backup_dir, "claude-memory", os.path.basename(src)), done,
                         "memory/" + os.path.basename(src))

    if move_rules and os.path.isdir(memory_dir):
        rules_home = os.path.join(ws, "rules")
        for name in sorted(current):
            src = os.path.join(memory_dir, name)
            dst = os.path.join(rules_home, name)
            if not os.path.isfile(src):
                continue
            if os.path.exists(dst):
                done.append(f"kept memory/{name} - {dst} already exists, compare them by hand")
                continue
            os.makedirs(rules_home, exist_ok=True)
            shutil.move(src, dst)
            done.append(f"moved memory/{name} to {dst}")
        crit = os.path.join(home, ".claude", "rules", "critical-rules.md")
        if os.path.isfile(crit):
            with open(crit, encoding="utf-8") as f:
                text = f.read()
            if RULES_NOTE not in text:
                with open(crit, "a", encoding="utf-8") as f:
                    f.write(f"\n{RULES_NOTE} `{rules_home}/`.\n")
                done.append("added the rules location line to critical-rules.md")

    if done:
        print("[pupsik] slim migration:")
        for line in done:
            print("  - " + line)
    else:
        print("[pupsik] slim migration: nothing to do")
    return 0


if __name__ == "__main__":
    sys.exit(main())
