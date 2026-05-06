#!/usr/bin/env python3
"""
note.py — One-shot atomic capture CLI for learnings, decisions, and research.

Phase 2 of the knowledge-capture system. Writes a dated MD file with YAML
frontmatter to the right ~/Desktop/claude/memory/<subdir>/ (or ~/Desktop/claude/research/),
then triggers a ChromaDB reindex via memory_search.py so the new note is
immediately findable by `memory_search.py search`.

Rule: `feedback_capture_knowledge.md`. Trigger: the MOMENT a learning / decision /
research finding emerges — even mid-investigation. If understanding evolves later,
re-run with the SAME title — it UPSERTS the existing note (one note per topic,
kept current). Threshold: "would this matter 3 weeks from now?" Yes → run note.py.

Usage:
    note.py learning "Title" "Body" [--tags "tag1,tag2"] [--project "FLEX"]
    note.py learning "Title" --body-file /tmp/body.md [--tags "..."]
    note.py learning "Title" --body-stdin <<'EOF'
    Body with apostrophes don't break.
    Multi-line works.
    EOF
    note.py decision "Title" "Body" [--alternatives "A,B,C"] [--rationale "..."] [--project "FLEX"]
    note.py research "Title" "Body" [--sources "url1,url2"] [--query "what we searched"] [--tags "..."]
    note.py list [--type learning|decision|research] [--days 7]
    note.py reindex

Body source (exactly one required):
    Positional BODY  Inline string. Cleanest for short bodies without quoting hell.
    --body-file PATH Read body from a file. Avoids shell-escape pain on long/complex bodies.
    --body-stdin     Read body from stdin (pipe-friendly + heredoc-friendly).
                     Use this if your body contains apostrophes, mixed quotes, or unicode.
    If multiple are given, --body-stdin > --body-file > positional (with a warning).

Flags applicable to learning/decision/research:
    --no-reindex     Skip the ChromaDB reindex step.
    --new            Force NEW file (bypass upsert). Rare — only for genuinely
                     unrelated topic that happens to slug-collide with an existing note.
    --append         Append body to existing note instead of overwriting it.
                     Adds a dated "## Update <today>" section above existing body.

Default behavior: UPSERT by slug. If a file with the same slug exists in the
target subdir (regardless of date prefix), it is opened and rewritten:
  - frontmatter `created:` preserved from existing file (or `date:` migrated)
  - frontmatter `updated:` set to today
  - tags MERGED (union, deduped, order-preserved)
  - body REPLACED (clean overwrite — user feedback was that latest state
    being current, not history-keeping). Use --append for evolving research.
Filename keeps the ORIGINAL date prefix (captures when the topic first emerged).
"""

import argparse
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Paths
HOME = Path(os.path.expanduser("~"))
BASE_DIR = HOME / "Desktop" / "claude"
LEARNINGS_DIR = BASE_DIR / "memory" / "learnings"
DECISIONS_DIR = BASE_DIR / "memory" / "decisions"
RESEARCH_DIR = BASE_DIR / "research"
MEMORY_SEARCH = BASE_DIR / "tools" / "memory_search.py"

TYPE_DIRS = {
    "learning": LEARNINGS_DIR,
    "decision": DECISIONS_DIR,
    "research": RESEARCH_DIR,
}

# YYYY-MM-DD- prefix on filenames
DATE_PREFIX_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-")


def slugify(title: str, max_len: int = 50) -> str:
    """Lowercase-hyphen slug, max 50 chars, ASCII-safe."""
    # Lowercase, strip leading/trailing whitespace
    s = title.strip().lower()
    # Replace anything that isn't a-z, 0-9, space, or hyphen with space
    s = re.sub(r"[^a-z0-9\s-]+", " ", s)
    # Collapse whitespace + hyphens to single hyphen
    s = re.sub(r"[\s_-]+", "-", s)
    # Strip leading/trailing hyphens
    s = s.strip("-")
    if not s:
        s = "untitled"
    return s[:max_len].rstrip("-")


def csv_to_list(s: str | None) -> list[str]:
    """Split a comma-separated string into trimmed non-empty entries."""
    if not s:
        return []
    return [p.strip() for p in s.split(",") if p.strip()]


def yaml_list(items: list[str]) -> str:
    """Format a list of strings as a YAML inline array."""
    if not items:
        return "[]"
    # Escape any double-quotes inside items
    escaped = [item.replace('"', '\\"') for item in items]
    return "[" + ", ".join(f'"{item}"' for item in escaped) + "]"


def yaml_str(s: str) -> str:
    """Format a string as YAML scalar (always quoted to be safe)."""
    if s is None:
        return '""'
    return '"' + s.replace('"', '\\"') + '"'


def unique_path(target: Path) -> Path:
    """If target exists, append -2, -3, etc until a free name is found."""
    if not target.exists():
        return target
    stem = target.stem
    suffix = target.suffix
    parent = target.parent
    n = 2
    while True:
        candidate = parent / f"{stem}-{n}{suffix}"
        if not candidate.exists():
            return candidate
        n += 1


def find_existing_by_slug(target_dir: Path, slug: str) -> Path | None:
    """Find an existing note with the same slug in the subdir, regardless of
    date prefix. Returns the path or None. If multiple match, picks the oldest
    (by filename date prefix lex sort) — that's the "first emergence" file we
    want to keep updating. Skips files with -2/-3 etc suffixes (those came
    from pre-upsert era; we don't want to clobber them).
    """
    if not target_dir.exists():
        return None
    candidates: list[Path] = []
    for p in target_dir.glob("*.md"):
        if not DATE_PREFIX_RE.match(p.name):
            continue
        # Strip "YYYY-MM-DD-" prefix
        rest = p.name[11:]
        # Drop trailing .md
        stem = rest[:-3] if rest.endswith(".md") else rest
        # Reject pre-existing -2/-3 dupes (treat them as separate notes)
        if re.search(r"-\d+$", stem):
            base = re.sub(r"-\d+$", "", stem)
            if base == slug:
                continue  # skip dupe
        if stem == slug:
            candidates.append(p)
    if not candidates:
        return None
    # Sort by filename (lex sort = chronological, since prefix is YYYY-MM-DD).
    # Pick the OLDEST — that's the canonical "first emergence" note.
    candidates.sort(key=lambda p: p.name)
    return candidates[0]


def parse_frontmatter(content: str) -> tuple[dict, str]:
    """Extract YAML frontmatter from markdown content.

    Returns (frontmatter_dict, body_text). If no frontmatter present, returns
    ({}, content). Hand-rolls a minimal YAML reader sufficient for note.py's
    scalar/list keys — does NOT support nested structures.
    """
    if not content.startswith("---\n"):
        return {}, content
    # Find closing ---
    end = content.find("\n---\n", 4)
    if end == -1:
        return {}, content
    yaml_block = content[4:end]
    body = content[end + 5:]
    fm: dict = {}
    for line in yaml_block.split("\n"):
        if not line.strip() or line.startswith("#"):
            continue
        m = re.match(r"^([a-zA-Z_][a-zA-Z0-9_]*)\s*:\s*(.*)$", line)
        if not m:
            continue
        key, raw_value = m.group(1), m.group(2).strip()
        if not raw_value:
            fm[key] = ""
            continue
        # YAML inline list: [ "a", "b" ]
        if raw_value.startswith("[") and raw_value.endswith("]"):
            inner = raw_value[1:-1].strip()
            if not inner:
                fm[key] = []
            else:
                items: list[str] = []
                # Naive split on commas not inside quotes
                cur = ""
                in_quote = False
                for ch in inner:
                    if ch == '"' and (not cur or cur[-1] != "\\"):
                        in_quote = not in_quote
                        cur += ch
                    elif ch == "," and not in_quote:
                        items.append(cur.strip())
                        cur = ""
                    else:
                        cur += ch
                if cur.strip():
                    items.append(cur.strip())
                # Strip surrounding quotes + unescape
                cleaned = []
                for it in items:
                    it = it.strip()
                    if it.startswith('"') and it.endswith('"'):
                        it = it[1:-1].replace('\\"', '"')
                    cleaned.append(it)
                fm[key] = cleaned
        # Quoted scalar
        elif raw_value.startswith('"') and raw_value.endswith('"') and len(raw_value) >= 2:
            fm[key] = raw_value[1:-1].replace('\\"', '"')
        # Plain scalar
        else:
            fm[key] = raw_value
    return fm, body.lstrip("\n")


def merge_tags(existing: list[str], new: list[str]) -> list[str]:
    """Union of tag lists, dedup case-insensitive, preserve order (existing first)."""
    seen = set()
    out: list[str] = []
    for tag in list(existing) + list(new):
        key = tag.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(tag)
    return out


def build_frontmatter(
    note_type: str,
    title: str,
    date_str: str,
    tags: list[str],
    project: str | None,
    sources: list[str] | None = None,
    alternatives: list[str] | None = None,
    rationale: str | None = None,
    query: str | None = None,
    created: str | None = None,
    updated: str | None = None,
) -> str:
    """Construct the YAML frontmatter block.

    If `created` is provided (existing file), emit `created:` + `updated:` instead
    of `date:`. Otherwise emit just `date:` (new file convention).
    """
    lines = ["---"]
    if created:
        lines.append(f"created: {created}")
        if updated:
            lines.append(f"updated: {updated}")
    else:
        lines.append(f"date: {date_str}")
    lines.append(f"type: {note_type}")
    lines.append(f"title: {yaml_str(title)}")
    lines.append(f"tags: {yaml_list(tags)}")
    if project:
        lines.append(f"project: {yaml_str(project)}")
    if note_type == "research":
        lines.append(f"sources: {yaml_list(sources or [])}")
        if query:
            lines.append(f"query: {yaml_str(query)}")
    if note_type == "decision":
        lines.append(f"alternatives: {yaml_list(alternatives or [])}")
        if rationale:
            lines.append(f"rationale: {yaml_str(rationale)}")
    lines.append("---")
    return "\n".join(lines)


def reindex(file_path: Path | None = None, background: bool = True) -> None:
    """Trigger ChromaDB reindex.

    If `file_path` is given, do a surgical single-file upsert (fast, ~1s).
    Otherwise full rebuild of all 9 collections (slow). By default
    fire-and-forget via Popen so the caller (Claude) doesn't block.
    """
    if not MEMORY_SEARCH.exists():
        print(f"warn: {MEMORY_SEARCH} not found — skipping reindex", file=sys.stderr)
        return
    cmd = [sys.executable, str(MEMORY_SEARCH), "index"]
    if file_path is not None:
        cmd += ["--file", str(file_path)]
    try:
        if background:
            # Fire-and-forget. Surgical upsert is fast; full reindex can take
            # >30s on large corpora — caller does not need to wait either way.
            subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            kind = "single-file" if file_path else "full"
            print(f"reindex: started in background ({kind})")
        else:
            subprocess.run(cmd, check=False)
    except Exception as e:
        print(f"warn: reindex failed: {e}", file=sys.stderr)


def write_note(
    note_type: str,
    title: str,
    body: str,
    tags: list[str],
    project: str | None,
    sources: list[str] | None,
    alternatives: list[str] | None,
    rationale: str | None,
    query: str | None,
    do_reindex: bool,
    force_new: bool = False,
    append: bool = False,
) -> tuple[Path, str]:
    """Write or upsert the note file. Returns (path, action) where action is
    one of: "wrote" (new file), "updated" (upserted body), "appended" (added section)."""
    if note_type not in TYPE_DIRS:
        raise ValueError(f"unknown note type: {note_type}")
    if not title.strip():
        raise ValueError("title cannot be empty")
    if not body.strip():
        raise ValueError("body cannot be empty")

    target_dir = TYPE_DIRS[note_type]
    target_dir.mkdir(parents=True, exist_ok=True)

    today = datetime.now().strftime("%Y-%m-%d")
    slug = slugify(title)

    existing = None if force_new else find_existing_by_slug(target_dir, slug)

    if existing is not None:
        # UPSERT path
        action = "appended" if append else "updated"
        existing_content = existing.read_text(encoding="utf-8")
        fm, existing_body = parse_frontmatter(existing_content)

        # Preserve original creation date
        created_date = fm.get("created") or fm.get("date") or today

        # Merge tags
        existing_tags = fm.get("tags") if isinstance(fm.get("tags"), list) else []
        merged_tags = merge_tags(existing_tags, tags)

        # Keep existing project unless caller passed a new one
        final_project = project if project else fm.get("project") or None

        # Type drift guard: if existing file's type differs from current call,
        # we honor the new type but warn. Type changes are rare in normal use.
        if fm.get("type") and fm.get("type") != note_type:
            print(
                f"warn: type changed {fm['type']} -> {note_type} for {existing.name}",
                file=sys.stderr,
            )

        # Build new body
        if append:
            # Prepend a dated update section, keep prior body below
            update_section = f"## Update {today}\n\n{body.strip()}\n"
            new_body = update_section + "\n" + existing_body.lstrip("\n")
        else:
            new_body = body.strip() + "\n"

        # For research type, merge sources too
        final_sources = sources or []
        if note_type == "research":
            existing_sources = fm.get("sources") if isinstance(fm.get("sources"), list) else []
            final_sources = merge_tags(existing_sources, final_sources)

        # For decision, prefer caller's alternatives/rationale if provided, else existing
        final_alternatives = alternatives if alternatives else (
            fm.get("alternatives") if isinstance(fm.get("alternatives"), list) else []
        )
        final_rationale = rationale if rationale else fm.get("rationale") or None
        final_query = query if query else fm.get("query") or None

        new_fm = build_frontmatter(
            note_type=note_type,
            title=title,
            date_str=today,
            tags=merged_tags,
            project=final_project,
            sources=final_sources,
            alternatives=final_alternatives,
            rationale=final_rationale,
            query=final_query,
            created=created_date,
            updated=today,
        )
        existing.write_text(new_fm + "\n\n" + new_body, encoding="utf-8")
        target_path = existing
    else:
        # NEW file path (original behavior, but we still use unique_path() in
        # case of an unrelated -2 dupe pre-existing on disk)
        action = "wrote"
        filename = f"{today}-{slug}.md"
        target_path = unique_path(target_dir / filename)

        frontmatter = build_frontmatter(
            note_type=note_type,
            title=title,
            date_str=today,
            tags=tags,
            project=project,
            sources=sources,
            alternatives=alternatives,
            rationale=rationale,
            query=query,
        )

        content = f"{frontmatter}\n\n{body.strip()}\n"
        target_path.write_text(content, encoding="utf-8")

    if do_reindex:
        reindex(file_path=target_path, background=True)

    return target_path, action


def list_notes(note_type: str | None, days: int) -> list[tuple[Path, datetime, str]]:
    """List recent capture notes. Returns [(path, mtime, type), ...] sorted newest first."""
    cutoff = datetime.now() - timedelta(days=days)
    types_to_check = [note_type] if note_type else list(TYPE_DIRS.keys())
    rows = []
    for t in types_to_check:
        d = TYPE_DIRS[t]
        if not d.exists():
            continue
        for p in d.glob("*.md"):
            try:
                mtime = datetime.fromtimestamp(p.stat().st_mtime)
            except OSError:
                continue
            if mtime >= cutoff:
                rows.append((p, mtime, t))
    rows.sort(key=lambda r: r[1], reverse=True)
    return rows


def resolve_body(args) -> str:
    """Resolve note body from one of three sources:
        1. --body-stdin  (highest precedence — pipe / heredoc / interactive)
        2. --body-file PATH
        3. positional BODY argument

    If multiple sources are given, higher precedence wins and a warning is
    printed to stderr. If none are given, ValueError is raised.

    Designed to fix the shell-escape pain that made apostrophe/quote-heavy
    bodies fail (5 May 2026 precedent: session gave up on capture after
    `python3 note.py learning "T" "body with 'inside'"` broke the shell quote).
    """
    sources_provided = []
    if getattr(args, "body_stdin", False):
        sources_provided.append("--body-stdin")
    if getattr(args, "body_file", None):
        sources_provided.append("--body-file")
    if getattr(args, "body", None):
        sources_provided.append("positional")

    if not sources_provided:
        raise ValueError(
            "no body source given. Provide one of: positional BODY, "
            "--body-file PATH, or --body-stdin (pipe/heredoc)."
        )

    if len(sources_provided) > 1:
        winner = sources_provided[0]  # list order = precedence order
        losers = ", ".join(sources_provided[1:])
        print(
            f"warn: multiple body sources given ({', '.join(sources_provided)}); "
            f"using {winner}, ignoring {losers}",
            file=sys.stderr,
        )

    if getattr(args, "body_stdin", False):
        body = sys.stdin.read()
    elif getattr(args, "body_file", None):
        body_path = Path(args.body_file).expanduser()
        if not body_path.exists():
            raise ValueError(f"--body-file path does not exist: {body_path}")
        body = body_path.read_text(encoding="utf-8")
    else:
        body = args.body

    if not body or not body.strip():
        raise ValueError("body is empty after reading from chosen source")

    return body


def cmd_capture(args, note_type: str) -> int:
    """Shared handler for learning/decision/research subcommands."""
    try:
        body = resolve_body(args)
        path, action = write_note(
            note_type=note_type,
            title=args.title,
            body=body,
            tags=csv_to_list(getattr(args, "tags", None)),
            project=getattr(args, "project", None),
            sources=csv_to_list(getattr(args, "sources", None)),
            alternatives=csv_to_list(getattr(args, "alternatives", None)),
            rationale=getattr(args, "rationale", None),
            query=getattr(args, "query", None),
            do_reindex=not args.no_reindex,
            force_new=getattr(args, "new", False),
            append=getattr(args, "append", False),
        )
    except Exception as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    print(f"{action}: {path}")
    return 0


def cmd_list(args) -> int:
    rows = list_notes(args.type, args.days)
    if not rows:
        scope = args.type or "all types"
        print(f"no captures in {scope} for last {args.days} days")
        return 0
    for path, mtime, t in rows:
        print(f"{mtime.strftime('%Y-%m-%d %H:%M')}  [{t:<8}]  {path}")
    return 0


def cmd_reindex(args) -> int:
    # `note.py reindex` keeps existing semantics: full rebuild. Use
    # `note.py reindex --file <path>` for surgical single-file upsert.
    file_path = Path(args.file).expanduser().resolve() if args.file else None
    reindex(file_path=file_path, background=not args.foreground)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="note.py",
        description="Atomic knowledge capture CLI (learnings / decisions / research). "
                    "Default behavior: upsert by title slug.",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    def add_common(parser):
        parser.add_argument("title", help="Short title for the note (slug = upsert key).")
        parser.add_argument(
            "body",
            nargs="?",
            default=None,
            help="Body text (2-5 sentences ideal). Optional if --body-file or "
                 "--body-stdin is used. Positional is cleanest for short bodies "
                 "without quoting hell; switch to --body-stdin / --body-file when "
                 "the body contains apostrophes, mixed quotes, or unicode.",
        )
        parser.add_argument(
            "--body-file",
            dest="body_file",
            metavar="PATH",
            help="Read body from a file instead of the positional argument. "
                 "Avoids shell-escape pain on long/complex bodies.",
        )
        parser.add_argument(
            "--body-stdin",
            dest="body_stdin",
            action="store_true",
            help="Read body from stdin (pipe-friendly + heredoc-friendly). "
                 "Apostrophes, quotes, unicode all pass through cleanly.",
        )
        parser.add_argument("--no-reindex", action="store_true", help="Skip ChromaDB reindex.")
        parser.add_argument(
            "--new",
            action="store_true",
            help="Force NEW file (bypass upsert). Use only for genuinely "
                 "unrelated topic that slug-collides with existing note.",
        )
        parser.add_argument(
            "--append",
            action="store_true",
            help="Append to existing note as a dated '## Update <today>' section "
                 "instead of overwriting body. Useful for evolving research.",
        )

    # learning
    pl = sub.add_parser("learning", help="Capture a learning/insight.")
    add_common(pl)
    pl.add_argument("--tags", help="Comma-separated tags (merged with existing on upsert).")
    pl.add_argument("--project", help="Optional project name.")
    pl.set_defaults(func=lambda a: cmd_capture(a, "learning"))

    # decision
    pd = sub.add_parser("decision", help="Capture a decision.")
    add_common(pd)
    pd.add_argument("--alternatives", help="Comma-separated alternatives considered.")
    pd.add_argument("--rationale", help="Why this option won.")
    pd.add_argument("--tags", help="Comma-separated tags (merged with existing on upsert).")
    pd.add_argument("--project", help="Optional project name.")
    pd.set_defaults(func=lambda a: cmd_capture(a, "decision"))

    # research
    pr = sub.add_parser("research", help="Capture a research finding.")
    add_common(pr)
    pr.add_argument("--sources", help="Comma-separated source URLs (merged on upsert).")
    pr.add_argument("--query", help="What we searched / asked.")
    pr.add_argument("--tags", help="Comma-separated tags (merged with existing on upsert).")
    pr.add_argument("--project", help="Optional project name.")
    pr.set_defaults(func=lambda a: cmd_capture(a, "research"))

    # list
    pls = sub.add_parser("list", help="List recent captures.")
    pls.add_argument("--type", choices=list(TYPE_DIRS.keys()), help="Filter by type.")
    pls.add_argument("--days", type=int, default=7, help="Days back to include (default 7).")
    pls.set_defaults(func=cmd_list)

    # reindex
    pri = sub.add_parser("reindex", help="Trigger ChromaDB reindex.")
    pri.add_argument("--foreground", action="store_true", help="Wait for reindex to finish.")
    pri.add_argument("--file", help="Surgical single-file upsert (fast). Default: full rebuild.")
    pri.set_defaults(func=cmd_reindex)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
