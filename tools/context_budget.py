#!/usr/bin/env python3
"""context_budget.py - measure why your sessions run out of context, on YOUR machine.

Three questions, three subcommands. All three read only local transcript metadata
(token counts, model names, timestamps) - never message content.

  trigger   At how many tokens does auto-compaction ACTUALLY fire, per model?
            This is the number that matters, and it is NOT your settings.json
            value: compaction fires against the model's real context window.
            Any `autoCompactWindow` set above that window is inert.

  start     How many tokens are already spent before you type a word? Read from
            the first assistant message's usage of each session (input +
            cache_creation + cache_read). This is your fixed per-session load:
            system prompt, tool schemas, MCP server instructions, skills list,
            CLAUDE.md, rules, memory index.

  files     Of that fixed load, how much is the part YOU control - CLAUDE.md,
            ~/.claude/rules/*.md, MEMORY.md - in characters and tokens.

Why it matters: `trigger` minus `start` is the working room you actually have.
When that difference gets small you see "Compacted conversation - saved 215k
tokens" several times in a row and then "context window is full", because each
compact hands back a summary that immediately re-fills.

Usage:
    python3 tools/context_budget.py trigger [--dir PATH] [--json]
    python3 tools/context_budget.py start   [--dir PATH] [--json]
    python3 tools/context_budget.py files   [--workspace PATH] [--json]
    python3 tools/context_budget.py all

Default transcript dir: ~/.claude/projects (scanned recursively for *.jsonl).

Token counts in `trigger` and `start` are reported by the agent itself, so they
are exact. Counts in `files` are an estimate: exact if `tiktoken` is installed
(cl100k_base, a close proxy), otherwise a characters-per-token heuristic that is
calibrated separately for Latin and Cyrillic text and labelled as such.
"""

import argparse
import glob
import json
import os
import statistics
import sys

DEFAULT_TRANSCRIPT_DIR = os.path.expanduser("~/.claude/projects")

# Files that make up the part of the session-start load you can edit yourself.
# Paths are relative to the workspace, except the rules dir which is global.
WORKSPACE_FILES = ["CLAUDE.md"]
GLOBAL_GLOBS = ["~/.claude/rules/*.md"]


def project_memory_index(workspace):
    """Path to the auto-memory MEMORY.md belonging to `workspace`, if it exists.

    Claude Code names each project directory after the absolute workspace path
    with every `/` replaced by `-`, so the index for /Users/x/Desktop/claude
    lives at ~/.claude/projects/-Users-x-Desktop-claude/memory/MEMORY.md. Only
    the matching one counts - other projects' indexes are not in this session's
    load, and summing them all would overstate the cost.
    """
    slug = os.path.abspath(os.path.expanduser(workspace)).replace(os.sep, "-")
    candidate = os.path.expanduser(
        os.path.join("~/.claude/projects", slug, "memory", "MEMORY.md")
    )
    return [candidate] if os.path.exists(candidate) else []


# ---------------------------------------------------------------- token sizing

def _tiktoken_encoder():
    try:
        import tiktoken
    except ImportError:
        return None
    try:
        return tiktoken.get_encoding("cl100k_base")
    except Exception:
        return None


def estimate_tokens(text, encoder=None):
    """Return (tokens, method). Exact-ish via tiktoken, else a calibrated heuristic."""
    if encoder is not None:
        return len(encoder.encode(text)), "tiktoken/cl100k_base"
    if not text:
        return 0, "heuristic"
    # BPE tokenizers pack Latin script far denser than Cyrillic. Measured on
    # cl100k_base: ~3.7 chars/token for English prose, ~2.15 for Russian.
    cyr = sum(1 for c in text if "Ѐ" <= c <= "ӿ")
    share = cyr / len(text)
    chars_per_token = 2.15 * share + 3.7 * (1 - share)
    return int(len(text) / chars_per_token), "heuristic"


# ------------------------------------------------------------------ transcripts

def iter_transcripts(root):
    root = os.path.expanduser(root)
    if os.path.isfile(root):
        yield root
        return
    for path in sorted(glob.glob(os.path.join(root, "**", "*.jsonl"), recursive=True)):
        yield path


def read_compactions(root):
    """Every auto/manual compaction boundary, with the token count it fired at.

    The agent writes a `{"type": "system", "subtype": "compact_boundary"}` record
    carrying `compactMetadata.preTokens` - the context size immediately before
    the compact. The model is taken from the nearest preceding assistant message.
    """
    events = []
    files = 0
    files_with = 0
    for path in iter_transcripts(root):
        files += 1
        seen_here = 0
        last_model = None
        with open(path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                # Cheap prefilter: parsing every line of every transcript is
                # slow. Boundary check comes FIRST - a line could in principle
                # satisfy both prefilters, and losing a boundary would silently
                # under-report, while losing a model attribution only falls back
                # to the previous one.
                is_boundary = '"compact_boundary"' in line
                is_assistant = '"model"' in line and '"assistant"' in line
                if not (is_boundary or is_assistant):
                    continue
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                if rec.get("type") == "assistant":
                    model = (rec.get("message") or {}).get("model")
                    if model:
                        last_model = model
                    continue
                if not is_boundary:
                    continue
                meta = rec.get("compactMetadata") or {}
                pre = meta.get("preTokens")
                if not isinstance(pre, int):
                    continue
                events.append(
                    {
                        "file": os.path.basename(path),
                        "model": last_model or "unknown",
                        "pre_tokens": pre,
                        "trigger": meta.get("trigger", "unknown"),
                        "timestamp": rec.get("timestamp"),
                    }
                )
                seen_here += 1
        if seen_here:
            files_with += 1
    return events, files, files_with


def read_session_starts(root):
    """First assistant usage per transcript = tokens spent before you typed."""
    starts = []
    for path in iter_transcripts(root):
        with open(path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if '"usage"' not in line or '"assistant"' not in line:
                    continue
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                if rec.get("type") != "assistant":
                    continue
                msg = rec.get("message") or {}
                usage = msg.get("usage") or {}
                total = (
                    (usage.get("input_tokens") or 0)
                    + (usage.get("cache_creation_input_tokens") or 0)
                    + (usage.get("cache_read_input_tokens") or 0)
                )
                if total <= 0:
                    continue
                starts.append(
                    {
                        "file": os.path.basename(path),
                        "model": msg.get("model") or "unknown",
                        "start_tokens": total,
                        "timestamp": rec.get("timestamp"),
                    }
                )
                break  # first assistant turn only
    return starts


def _summary(values):
    values = sorted(values)
    n = len(values)
    if not n:
        return None
    return {
        "n": n,
        "min": values[0],
        "median": int(statistics.median(values)),
        "p90": values[min(n - 1, int(round(0.9 * (n - 1))))],
        "max": values[-1],
    }


# -------------------------------------------------------------------- reporting

def cmd_trigger(args):
    events, files, files_with = read_compactions(args.dir)
    by_model = {}
    for ev in events:
        by_model.setdefault(ev["model"], []).append(ev["pre_tokens"])
    out = {
        "transcripts_scanned": files,
        "transcripts_with_compaction": files_with,
        "compactions": len(events),
        "by_model": {m: _summary(v) for m, v in sorted(by_model.items())},
    }
    if args.json:
        print(json.dumps(out, indent=2))
        return 0
    print(
        "compactions: %d across %d of %d transcripts"
        % (len(events), files_with, files)
    )
    if not events:
        print("no compaction boundaries found - nothing to measure yet")
        return 0
    print()
    print("%-28s %5s %9s %9s %9s %9s" % ("model", "n", "min", "median", "p90", "max"))
    for model, s in out["by_model"].items():
        print(
            "%-28s %5d %9d %9d %9d %9d"
            % (model, s["n"], s["min"], s["median"], s["p90"], s["max"])
        )
    print()
    print("Read the median as your model's real usable window. A value in")
    print("settings.json `autoCompactWindow` above the max here cannot bind.")
    return 0


def cmd_start(args):
    starts = read_session_starts(args.dir)
    by_model = {}
    for st in starts:
        by_model.setdefault(st["model"], []).append(st["start_tokens"])
    out = {
        "sessions": len(starts),
        "by_model": {m: _summary(v) for m, v in sorted(by_model.items())},
    }
    if args.json:
        print(json.dumps(out, indent=2))
        return 0
    print("sessions measured: %d" % len(starts))
    if not starts:
        print("no usage records found")
        return 0
    print()
    print("%-28s %5s %9s %9s %9s %9s" % ("model", "n", "min", "median", "p90", "max"))
    for model, s in out["by_model"].items():
        print(
            "%-28s %5d %9d %9d %9d %9d"
            % (model, s["n"], s["min"], s["median"], s["p90"], s["max"])
        )
    print()
    print("This is spent before your first word: system prompt, tool schemas,")
    print("MCP server instructions, skills, CLAUDE.md, rules, memory index.")
    return 0


def cmd_files(args):
    encoder = _tiktoken_encoder()
    workspace = os.path.expanduser(args.workspace)
    paths = []
    for rel in WORKSPACE_FILES:
        p = os.path.join(workspace, rel)
        if os.path.exists(p):
            paths.append(p)
    for pattern in GLOBAL_GLOBS:
        paths.extend(sorted(glob.glob(os.path.expanduser(pattern))))
    paths.extend(project_memory_index(workspace))

    rows = []
    method = "heuristic"
    for p in paths:
        try:
            with open(p, encoding="utf-8", errors="replace") as fh:
                text = fh.read()
        except OSError:
            continue
        tokens, method = estimate_tokens(text, encoder)
        cyr = sum(1 for c in text if "Ѐ" <= c <= "ӿ")
        rows.append(
            {
                "path": p,
                "chars": len(text),
                "lines": text.count("\n") + 1,
                "tokens": tokens,
                "cyrillic_pct": round(100.0 * cyr / max(len(text), 1), 1),
            }
        )
    total = sum(r["tokens"] for r in rows)
    out = {"method": method, "total_tokens": total, "files": rows}
    if args.json:
        print(json.dumps(out, indent=2))
        return 0
    if not rows:
        print("no memory files found - pass --workspace if yours is elsewhere")
        return 0
    print("token counts via %s" % method)
    print()
    print("%-52s %8s %7s %8s %6s" % ("file", "chars", "lines", "tokens", "cyr%"))
    for r in rows:
        shown = r["path"].replace(os.path.expanduser("~"), "~")
        if len(shown) > 52:
            shown = "..." + shown[-49:]
        print(
            "%-52s %8d %7d %8d %6.1f"
            % (shown, r["chars"], r["lines"], r["tokens"], r["cyrillic_pct"])
        )
    print("%-52s %8s %7s %8d" % ("TOTAL", "", "", total))
    print()
    print("This is the slice of session-start load you can edit today. Trim it by")
    print("moving detail into pointer files, not by deleting facts.")
    return 0


def cmd_all(args):
    print("=" * 72)
    print("1. where compaction actually fires")
    print("=" * 72)
    cmd_trigger(args)
    print()
    print("=" * 72)
    print("2. what a session costs before you type")
    print("=" * 72)
    cmd_start(args)
    print()
    print("=" * 72)
    print("3. the part of that load you control")
    print("=" * 72)
    cmd_files(args)
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Measure the real auto-compaction trigger and your session-start load.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = ap.add_subparsers(dest="cmd")

    for name, fn, needs_dir, needs_ws in (
        ("trigger", cmd_trigger, True, False),
        ("start", cmd_start, True, False),
        ("files", cmd_files, False, True),
        ("all", cmd_all, True, True),
    ):
        p = sub.add_parser(name, help=fn.__doc__ or name)
        p.add_argument("--json", action="store_true", help="machine-readable output")
        if needs_dir:
            p.add_argument(
                "--dir",
                default=DEFAULT_TRANSCRIPT_DIR,
                help="transcript directory or a single .jsonl (default: ~/.claude/projects)",
            )
        if needs_ws:
            p.add_argument(
                "--workspace",
                default="~/Desktop/claude",
                help="workspace holding CLAUDE.md (default: ~/Desktop/claude)",
            )
        p.set_defaults(func=fn)

    args = ap.parse_args(argv)
    if not getattr(args, "func", None):
        ap.print_help()
        return 0
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
