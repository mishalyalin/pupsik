#!/usr/bin/env python3
"""Rules retrieval - returns FULL content of matched feedback_*.md rules.

Merges alias manifest (data/rules-aliases.json, optional) + semantic
(memory_search.py). Alias >=2 token-overlap ranks above alias=1 above pure
semantic. Graceful fallback if manifest missing.

Usage: rules.py search "<topic>" [--top N]  |  list  |  read "<name>"

Layout assumptions (override below if your setup differs):
- Project memory: ~/.claude/projects/<project-slug>/memory/feedback_*.md
  The slug is the path-mangled form of your workspace (e.g. a workspace at
  ~/Desktop/claude becomes -Users-<user>-Desktop-claude). This script tries
  to auto-detect the slug from the workspace at ~/Desktop/claude. If your
  workspace lives elsewhere, edit RULES_DIRS below.
- Workspace memory: ~/Desktop/claude/memory/feedback_*.md (the pupsik default).
- Semantic search: ~/Desktop/claude/tools/memory_search.py (the pupsik default).

Optional alias manifest: ~/Desktop/claude/data/rules-aliases.json
Format: {"feedback_<name>": ["alias1", "alias2", ...]}
Create your own if you want keyword-boosted search; the script works without it.
"""
import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path


def _autodetect_project_slug():
    """Pick the .claude/projects/<slug>/memory dir matching ~/Desktop/claude.

    Convention: slugs are workspace paths with / replaced by - (leading -).
    If multiple candidates exist, pick the one whose slug contains 'Desktop-claude'.
    Returns None if nothing matches.
    """
    projects_dir = Path.home() / ".claude" / "projects"
    if not projects_dir.exists():
        return None
    workspace = Path.home() / "Desktop" / "claude"
    expected_slug = str(workspace).replace("/", "-")
    candidate = projects_dir / expected_slug / "memory"
    if candidate.exists():
        return candidate
    # Fallback: scan for any .claude/projects/<slug>/memory containing feedback_*.md.
    for child in projects_dir.iterdir():
        memory = child / "memory"
        if memory.exists() and any(memory.glob("feedback_*.md")):
            return memory
    return None


_project_memory = _autodetect_project_slug()
RULES_DIRS = []
if _project_memory is not None:
    RULES_DIRS.append(_project_memory)
RULES_DIRS.append(Path.home() / "Desktop/claude/memory")

MEMORY_SEARCH = Path.home() / "Desktop/claude/tools/memory_search.py"
ALIASES_PATH = Path.home() / "Desktop/claude/data/rules-aliases.json"


def find_rule_file(name: str):
    candidates = [name]
    if not name.startswith("feedback_"):
        candidates.append("feedback_" + name)
    candidates = [c if c.endswith(".md") else c + ".md" for c in candidates]
    for d in RULES_DIRS:
        for c in candidates:
            p = d / c
            if p.exists():
                return p
    return None


def cmd_list() -> int:
    seen, rows = set(), []
    for d in RULES_DIRS:
        if not d.exists():
            continue
        for p in sorted(d.glob("feedback_*.md")):
            if p.stem not in seen:
                seen.add(p.stem)
                rows.append((p.stem, p))
    for stem, p in sorted(rows):
        loc = f"{p.parent.parent.name}/{p.parent.name}"
        print(f"{stem:60}  ({loc})")
    print(f"\n# {len(rows)} unique rules across {len([d for d in RULES_DIRS if d.exists()])} locations")
    return 0


def cmd_read(name: str) -> int:
    p = find_rule_file(name)
    if p is None:
        print(f"ERROR: rule not found: {name}", file=sys.stderr)
        print("Try: rules.py list", file=sys.stderr)
        return 1
    print(f"# Source: {p}\n")
    print(p.read_text(encoding="utf-8"))
    return 0


def load_aliases():
    if not ALIASES_PATH.exists():
        # Optional manifest - script falls back to pure semantic search if absent.
        # Create one at ~/Desktop/claude/data/rules-aliases.json with format
        #   {"feedback_<name>": ["alias1", "alias2", ...]}
        # to boost retrieval on keywords your rule files don't explicitly mention.
        return {}
    try:
        with open(ALIASES_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"WARN: aliases manifest unreadable ({e}) - using pure semantic", file=sys.stderr)
        return {}


def tokenize(s: str):
    s = re.sub(r"[^\w\s-]", " ", s.lower())
    return [t for t in s.split() if len(t) >= 2]


def score_aliases(query: str, aliases: dict):
    """Return [(rule_stem, match_count), ...] sorted desc by count, ties alphabetical."""
    q_tokens = tokenize(query)
    q_lower = query.lower()
    scores = {}
    for stem, alias_list in aliases.items():
        alias_lower = [a.lower() for a in alias_list]
        matched = set()
        for tok in q_tokens:
            for a in alias_lower:
                if tok in a or a in tok:
                    matched.add(tok)
                    break
            if tok in stem.lower():
                matched.add(tok)
        for a in alias_lower:
            if q_lower in a or a in q_lower:
                matched.add("__full__")
                break
        if matched:
            scores[stem] = len(matched)
    return sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))


def run_semantic(query: str, fetch: int):
    if not MEMORY_SEARCH.exists():
        return []
    try:
        result = subprocess.run(
            [sys.executable, str(MEMORY_SEARCH), "search", query,
             "--collection", "memory_files", "--top", str(fetch)],
            capture_output=True, text=True, timeout=60, check=False
        )
    except subprocess.TimeoutExpired:
        return []
    if result.returncode != 0:
        return []
    seen, stems = set(), []
    for line in result.stdout.splitlines():
        if "feedback_" in line:
            m = re.search(r"(feedback_[a-z0-9_]+)(?:\.md)?", line.strip())
            if m and m.group(1) not in seen:
                seen.add(m.group(1))
                stems.append(m.group(1))
    return stems


def cmd_search(query: str, top: int) -> int:
    aliases = load_aliases()
    alias_scored = score_aliases(query, aliases) if aliases else []
    score_map = dict(alias_scored)
    semantic_stems = run_semantic(query, top * 3)

    alias_high = [s for s, c in alias_scored if c >= 2]
    alias_low = [s for s, c in alias_scored if c == 1]
    alias_set = set(alias_high + alias_low)

    merged, sources = [], {}
    for stem in alias_high:
        if stem not in merged:
            merged.append(stem)
            sources[stem] = f"alias({score_map[stem]})"
            if len(merged) >= top:
                break
    if len(merged) < top:
        for stem in alias_low:
            if stem not in merged:
                merged.append(stem)
                sources[stem] = "alias(1)"
                if len(merged) >= top:
                    break
    if len(merged) < top:
        for stem in semantic_stems:
            if stem not in merged and stem not in alias_set:
                merged.append(stem)
                sources[stem] = "semantic"
                if len(merged) >= top:
                    break

    rule_files = [(s, find_rule_file(s)) for s in merged if find_rule_file(s) is not None]

    if not rule_files:
        print(f"No matching rules for: {query}", file=sys.stderr)
        print("Try: rules.py list", file=sys.stderr)
        return 1

    print(f"# Top {len(rule_files)} rules matching: {query!r}")
    print("# Match sources: " + ", ".join(f"{s}={sources[s]}" for s, _ in rule_files))
    print()
    for i, (stem, p) in enumerate(rule_files, 1):
        print("---")
        print(f"# [{i}/{len(rule_files)}] {stem}  [source: {sources[stem]}]")
        print(f"# Source: {p}\n")
        print(p.read_text(encoding="utf-8"))
        print()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_search = sub.add_parser("search", help="Alias + semantic search, print full content")
    p_search.add_argument("query")
    p_search.add_argument("--top", type=int, default=3)
    sub.add_parser("list", help="List all rule files")
    p_read = sub.add_parser("read", help="Print one rule by name")
    p_read.add_argument("name")
    args = parser.parse_args()
    if args.cmd == "search":
        return cmd_search(args.query, args.top)
    elif args.cmd == "list":
        return cmd_list()
    elif args.cmd == "read":
        return cmd_read(args.name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
