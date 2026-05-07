#!/usr/bin/env python3
"""
note.py — One-shot atomic capture CLI for learnings, decisions, research, friction.

Phase 2 of Misha's knowledge-capture system. Writes a dated MD file with YAML
frontmatter to the right ~/Desktop/claude/memory/<subdir>/ (or ~/Desktop/claude/research/),
then triggers a ChromaDB reindex via memory_search.py so the new note is
immediately findable by `memory_search.py search`.

Rule: `feedback_capture_knowledge.md`. Trigger: the MOMENT a learning / decision /
research finding emerges — even mid-investigation. If understanding evolves later,
re-run with the SAME title — it UPSERTS the existing note (one note per topic,
kept current). Threshold: "would this matter 3 weeks from now?" Yes → run note.py.

Friction subcommand: see `feedback_friction_protocol.md` and
`memory/friction/_PROTOCOL.md`. Adapted from gbrain by Garry Tan (MIT, 2026-05-07).
Captures friction events (severity + phase + message + hint) for surfacing in
morning briefing AI Architect Lens. Upsert key = phase + severity (counter
increments on recurring pattern; counter >= 3 = bold/red briefing surface).

Usage:
    note.py learning "Title" "Body" [--tags "tag1,tag2"] [--project "FLEX"]
    note.py learning "Title" --body-file /tmp/body.md [--tags "..."]
    note.py learning "Title" --body-stdin <<'EOF'
    Body with apostrophes don't break.
    Multi-line works.
    EOF
    note.py decision "Title" "Body" [--alternatives "A,B,C"] [--rationale "..."] [--project "FLEX"]
    note.py research "Title" "Body" [--sources "url1,url2"] [--query "what we searched"] [--tags "..."]
    note.py friction --severity {blocker|error|confused|nit} --phase "<phase>" --message "<msg>" \
                     [--hint "<hint>"] [--entity "<entity>"] [BODY] [--body-file] [--body-stdin] \
                     [--tags "..."]
    note.py friction summary [--days 7] [--severity X] [--top 3]
    note.py list [--type learning|decision|research|friction] [--days 7]
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
  - body REPLACED (clean overwrite — Misha's correction was about latest state
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
FRICTION_DIR = BASE_DIR / "memory" / "friction"
MEMORY_SEARCH = BASE_DIR / "tools" / "memory_search.py"

TYPE_DIRS = {
    "learning": LEARNINGS_DIR,
    "decision": DECISIONS_DIR,
    "research": RESEARCH_DIR,
    "friction": FRICTION_DIR,
}

# Severity ordering (low -> high) used for sort/aggregation.
FRICTION_SEVERITIES = ("nit", "confused", "error", "blocker")
FRICTION_SEVERITY_RANK = {s: i for i, s in enumerate(FRICTION_SEVERITIES)}
FRICTION_SEVERITY_BADGE = {
    "blocker": "🔴 BLOCKER",
    "error":   "🟠 ERROR",
    "confused": "🟡 CONFUSED",
    "nit":     "⚪️ NIT",
}

# gbrain provenance — repeated on every friction file per Misha's
# attribution rule (set 2026-05-07, see learnings/2026-05-07-open-source-...md).
# We embed in the per-file frontmatter rather than only _PROTOCOL.md so any
# friction file pulled out of context (PR snippet, ChromaDB result, copy/paste
# into a doc) carries its own credit. _PROTOCOL.md holds the long-form notes.
FRICTION_PROVENANCE = {
    "adapted-from": "gbrain",
    "source-url":   "https://github.com/garrytan/gbrain/blob/master/skills/_friction-protocol.md",
    "source-license": "MIT",
    "adaptation-type": "adapted",
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
        # we honor the new type but warn. Misha will rarely change type.
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


# =============================================================================
# Friction protocol (adapted from gbrain by Garry Tan, MIT — 2026-05-07)
# =============================================================================
#
# Schema differs from learning/decision/research:
#   - Upsert key = phase + severity (NOT title-slug). Same phase + severity
#     re-run = counter++. Different severity for the same phase = separate file
#     (escalation pattern: confused -> error -> blocker can sit side-by-side).
#   - Filename = <YYYY-MM-DD>-<severity>-<slug>.md, slug from --phase.
#   - Frontmatter has counter / status / entity / hint / message in addition
#     to standard fields.


def friction_filename(date_str: str, severity: str, phase: str) -> str:
    """Filename = <date>-<severity>-<slug-of-phase>.md."""
    slug = slugify(phase or severity)
    return f"{date_str}-{severity}-{slug}.md"


def find_existing_friction(severity: str, phase: str) -> Path | None:
    """Find an existing friction file by (severity, phase) — the upsert key.

    Filename always begins with `<date>-<severity>-`, followed by the slugged
    phase. We strip the date+severity prefix and compare slugs. Skips `-2/-3`
    legacy duplicates so re-running with a slug-collision does not clobber an
    unrelated old file.
    """
    if not FRICTION_DIR.exists():
        return None
    target_slug = slugify(phase)
    sev_prefix = f"{severity}-"
    candidates: list[Path] = []
    for p in FRICTION_DIR.glob("*.md"):
        if not DATE_PREFIX_RE.match(p.name):
            continue
        rest = p.name[11:]  # strip "YYYY-MM-DD-"
        if not rest.startswith(sev_prefix):
            continue
        stem = rest[len(sev_prefix):]
        stem = stem[:-3] if stem.endswith(".md") else stem
        if re.search(r"-\d+$", stem):
            base = re.sub(r"-\d+$", "", stem)
            if base == target_slug:
                continue  # legacy dupe
        if stem == target_slug:
            candidates.append(p)
    if not candidates:
        return None
    candidates.sort(key=lambda p: p.name)  # oldest first = canonical
    return candidates[0]


def build_friction_frontmatter(
    *,
    severity: str,
    phase: str,
    message: str,
    hint: str | None,
    entity: str | None,
    status: str,
    counter: int,
    created: str,
    updated: str,
    tags: list[str],
) -> str:
    """Build the YAML frontmatter for a friction file.

    Embeds gbrain provenance per the open-source attribution rule.
    """
    lines = ["---"]
    lines.append("type: friction")
    lines.append(f"severity: {severity}")
    lines.append(f"phase: {yaml_str(phase)}")
    lines.append(f"message: {yaml_str(message)}")
    if hint:
        lines.append(f"hint: {yaml_str(hint)}")
    if entity:
        lines.append(f"entity: {yaml_str(entity)}")
    lines.append(f"status: {status}")
    lines.append(f"counter: {counter}")
    lines.append(f"created: {created}")
    lines.append(f"updated: {updated}")
    lines.append(f"tags: {yaml_list(tags)}")
    # Provenance — see FRICTION_PROVENANCE rationale.
    for k, v in FRICTION_PROVENANCE.items():
        lines.append(f"{k}: {yaml_str(v)}")
    lines.append("---")
    return "\n".join(lines)


def write_friction(
    *,
    severity: str,
    phase: str,
    message: str,
    hint: str | None,
    entity: str | None,
    body: str | None,
    tags: list[str],
    do_reindex: bool,
    force_new: bool,
    append: bool,
) -> tuple[Path, str, int]:
    """Write or upsert a friction event. Returns (path, action, counter).

    Action: "wrote" | "updated" | "appended".
    """
    if severity not in FRICTION_SEVERITIES:
        raise ValueError(
            f"unknown severity: {severity!r}. "
            f"must be one of {', '.join(FRICTION_SEVERITIES)}"
        )
    if not phase or not phase.strip():
        raise ValueError("--phase is required and cannot be empty")
    if not message or not message.strip():
        raise ValueError("--message is required and cannot be empty")

    FRICTION_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")

    existing = None if force_new else find_existing_friction(severity, phase)

    if existing is not None:
        action = "appended" if append else "updated"
        existing_content = existing.read_text(encoding="utf-8")
        fm, existing_body = parse_frontmatter(existing_content)

        created_date = fm.get("created") or today
        # Counter increments on every upsert call (it's the recurrence signal).
        try:
            prev_counter = int(fm.get("counter", 1))
        except (ValueError, TypeError):
            prev_counter = 1
        new_counter = prev_counter + 1

        existing_tags = fm.get("tags") if isinstance(fm.get("tags"), list) else []
        merged_tags = merge_tags(existing_tags, tags)

        # Status: never silently flip resolved -> open. If user re-fires with
        # same severity + phase the issue is recurring, so reopen acknowledged
        # but leave resolved alone (caller can edit manually).
        prev_status = fm.get("status") or "open"
        new_status = "open" if prev_status in ("acknowledged",) else prev_status
        if prev_status == "resolved":
            new_status = "open"  # recurrence reopens

        # Honor caller's hint/entity if given, else preserve existing.
        final_hint = hint if hint is not None else fm.get("hint")
        final_entity = entity if entity is not None else fm.get("entity")
        # message = always latest call (this is "what happened THIS time").
        final_message = message

        # Body composition: dated update section if --append, replace otherwise.
        body_block = ""
        if body and body.strip():
            if append:
                body_block = f"## Update {today}\n\n{body.strip()}\n\n" + existing_body.lstrip("\n")
            else:
                body_block = body.strip() + "\n"
        else:
            # No body provided: keep existing body untouched on upsert.
            body_block = existing_body.lstrip("\n")

        new_fm = build_friction_frontmatter(
            severity=severity,
            phase=phase,
            message=final_message,
            hint=final_hint,
            entity=final_entity,
            status=new_status,
            counter=new_counter,
            created=created_date,
            updated=today,
            tags=merged_tags,
        )
        existing.write_text(new_fm + "\n\n" + body_block, encoding="utf-8")
        target_path = existing
        final_counter = new_counter
    else:
        action = "wrote"
        filename = friction_filename(today, severity, phase)
        target_path = unique_path(FRICTION_DIR / filename)

        new_counter = 1
        body_block = (body.strip() + "\n") if (body and body.strip()) else ""

        new_fm = build_friction_frontmatter(
            severity=severity,
            phase=phase,
            message=message,
            hint=hint,
            entity=entity,
            status="open",
            counter=new_counter,
            created=today,
            updated=today,
            tags=tags,
        )
        target_path.write_text(new_fm + "\n\n" + body_block, encoding="utf-8")
        final_counter = new_counter

    if do_reindex:
        reindex(file_path=target_path, background=True)

    return target_path, action, final_counter


def cmd_friction_log(args) -> int:
    """Handler for `note.py friction ...` (logging a friction event)."""
    # Body is OPTIONAL for friction (one-line message often suffices). We only
    # call resolve_body if the user actually provided one of the three sources.
    body: str | None = None
    has_body_source = (
        getattr(args, "body_stdin", False)
        or getattr(args, "body_file", None)
        or getattr(args, "body", None)
    )
    if has_body_source:
        try:
            body = resolve_body(args)
        except Exception as e:
            print(f"error: {e}", file=sys.stderr)
            return 1

    try:
        path, action, counter = write_friction(
            severity=args.severity,
            phase=args.phase,
            message=args.message,
            hint=getattr(args, "hint", None),
            entity=getattr(args, "entity", None),
            body=body,
            tags=csv_to_list(getattr(args, "tags", None)),
            do_reindex=not args.no_reindex,
            force_new=getattr(args, "new", False),
            append=getattr(args, "append", False),
        )
    except Exception as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    print(f"{action}: {path} (counter={counter})")
    return 0


def load_friction_files(days: int | None = None) -> list[dict]:
    """Load all friction files into dicts. Optionally filter by `updated` age."""
    out: list[dict] = []
    if not FRICTION_DIR.exists():
        return out
    cutoff_date: str | None = None
    if days is not None and days > 0:
        cutoff_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    for p in FRICTION_DIR.glob("*.md"):
        if p.name.startswith("_"):
            continue  # skip _PROTOCOL.md and friends
        if not DATE_PREFIX_RE.match(p.name):
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except OSError:
            continue
        fm, _ = parse_frontmatter(text)
        if fm.get("type") != "friction":
            continue
        # Apply --days window on `updated` (recurrence relevance).
        updated = (fm.get("updated") or fm.get("created") or "")
        if cutoff_date and updated and updated < cutoff_date:
            continue
        try:
            counter = int(fm.get("counter", 1))
        except (ValueError, TypeError):
            counter = 1
        out.append({
            "path": p,
            "severity": fm.get("severity") or "nit",
            "phase": fm.get("phase") or "",
            "message": fm.get("message") or "",
            "hint": fm.get("hint") or "",
            "entity": fm.get("entity") or "",
            "status": fm.get("status") or "open",
            "counter": counter,
            "updated": updated,
            "created": fm.get("created") or "",
            "tags": fm.get("tags") if isinstance(fm.get("tags"), list) else [],
        })
    return out


def cmd_friction_summary(args) -> int:
    """Briefing-consumable summary: top-N open friction by counter desc.

    Output format is plain markdown so the morning-briefing skill can embed
    it under the AI Architect Lens directly.
    """
    items = load_friction_files(days=args.days)
    items = [it for it in items if it["status"] != "resolved"]
    if args.severity:
        if args.severity not in FRICTION_SEVERITIES:
            print(f"error: --severity must be one of {', '.join(FRICTION_SEVERITIES)}", file=sys.stderr)
            return 1
        items = [it for it in items if it["severity"] == args.severity]

    # Sort: counter desc (recurrence weight) -> severity rank desc -> updated desc.
    items.sort(
        key=lambda it: (
            it["counter"],
            FRICTION_SEVERITY_RANK.get(it["severity"], 0),
            it["updated"],
        ),
        reverse=True,
    )
    top = items[: max(1, args.top)]

    if not top:
        print(f"No open friction in last {args.days}d"
              + (f" with severity={args.severity}" if args.severity else "")
              + ".")
        return 0

    print(f"## Top {len(top)} open friction (last {args.days}d)\n")
    for it in top:
        badge = FRICTION_SEVERITY_BADGE.get(it["severity"], it["severity"])
        # counter >= 3 = bold/red emphasis (matches existing 🚨 ESCALATED block convention)
        prefix = "**🚨 " if it["counter"] >= 3 else "- "
        suffix = "**" if it["counter"] >= 3 else ""
        line = f"{prefix}{badge} `{it['phase']}` x{it['counter']}"
        if it["entity"]:
            line += f" ({it['entity']})"
        line += f" - last {it['updated']}{suffix}"
        print(line)
        print(f"    msg: {it['message']}")
        if it["hint"]:
            print(f"    hint: {it['hint']}")
        print()
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

    # friction (sub-sub-commands: default = log a new event; summary = aggregate)
    pf = sub.add_parser(
        "friction",
        help="Capture or summarize friction events (adapted from gbrain).",
        description="Capture friction events for surfacing in morning briefing. "
                    "Adapted from gbrain by Garry Tan (MIT). "
                    "See memory/friction/_PROTOCOL.md.",
    )
    pf_sub = pf.add_subparsers(dest="friction_cmd")  # not required: bare `friction` defaults to log

    # `friction log` (also the default when no sub-sub-command given)
    def add_friction_log_args(parser):
        parser.add_argument(
            "--severity",
            required=True,
            choices=list(FRICTION_SEVERITIES),
            help="Severity: blocker (hard stop) | error (unexpected fail) | "
                 "confused (docs/tool mismatch) | nit (polish).",
        )
        parser.add_argument(
            "--phase",
            required=True,
            help="One-line phase/context (e.g. 'morning briefing', 'tupak production confirm'). "
                 "This + severity is the upsert key.",
        )
        parser.add_argument(
            "--message",
            required=True,
            help="One-line concrete description of what happened.",
        )
        parser.add_argument(
            "--hint",
            help="Optional one-line suggestion of what could be better.",
        )
        parser.add_argument(
            "--entity",
            help="Optional person/company/system involved (e.g. 'appointment-system', 'vendor-name').",
        )
        # Body source: optional for friction (the one-line --message often suffices,
        # but --body-* allows longer narrative if user wants one).
        parser.add_argument(
            "body",
            nargs="?",
            default=None,
            help="Optional longer narrative body. Most friction events need only --message.",
        )
        parser.add_argument(
            "--body-file",
            dest="body_file",
            metavar="PATH",
            help="Read body from a file (avoids shell-escape pain).",
        )
        parser.add_argument(
            "--body-stdin",
            dest="body_stdin",
            action="store_true",
            help="Read body from stdin (heredoc-friendly).",
        )
        parser.add_argument("--tags", help="Comma-separated tags (merged on upsert).")
        parser.add_argument("--no-reindex", action="store_true", help="Skip ChromaDB reindex.")
        parser.add_argument(
            "--new",
            action="store_true",
            help="Force NEW file (bypass upsert by phase+severity). Rare.",
        )
        parser.add_argument(
            "--append",
            action="store_true",
            help="Append body to existing note as dated '## Update <today>' section.",
        )

    pf_log = pf_sub.add_parser(
        "log",
        help="Log a friction event. Note: bare `friction ...` (without 'log') "
             "is also accepted as a shorthand and routed here.",
    )
    add_friction_log_args(pf_log)
    pf_log.set_defaults(func=cmd_friction_log)

    # `friction summary`
    pf_sum = pf_sub.add_parser("summary", help="Top-N open friction (briefing-consumable).")
    pf_sum.add_argument("--days", type=int, default=7, help="Window in days (default 7).")
    pf_sum.add_argument(
        "--severity",
        choices=list(FRICTION_SEVERITIES),
        help="Filter by single severity.",
    )
    pf_sum.add_argument("--top", type=int, default=3, help="Top N results (default 3).")
    pf_sum.set_defaults(func=cmd_friction_summary)

    # Default action when bare `friction` (no sub-sub-cmd) is invoked: route to
    # cmd_friction_log via the argv rewrite in main(). If we got here without
    # one of {log, summary} the rewrite already happened in main().
    pf.set_defaults(func=cmd_friction_log)

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


def _rewrite_friction_argv(argv: list[str]) -> list[str]:
    """If user invokes `note.py friction --severity ...` (gbrain bare form),
    rewrite to `note.py friction log --severity ...` so the sub-sub-parser
    routes correctly. Idempotent if user already typed `friction log` or
    `friction summary` (or any other recognized sub-sub-cmd).

    IMPORTANT: only rewrite when `friction` is the SUBCOMMAND position (i.e.
    the first non-flag positional). Otherwise we'd corrupt e.g.
    `note.py list --type friction --days 7`.
    """
    # Find the first positional arg (skipping option flags + their values).
    i = 0
    while i < len(argv):
        tok = argv[i]
        if tok.startswith("-"):
            # Skip a value if present and this isn't a known boolean flag.
            # We don't know note.py's full flag schema here; the safest
            # heuristic is "skip flag, skip next token only if it doesn't
            # start with -". This mirrors how argparse walks short flags
            # with values.
            if "=" in tok:
                i += 1
                continue
            i += 1
            if i < len(argv) and not argv[i].startswith("-"):
                # Could be a flag value OR could be the subcommand. We can't
                # distinguish at this level, so be conservative: don't skip.
                # The top-level parser only has -h/--help as options anyway,
                # so the first positional here IS the subcommand.
                continue
            continue
        break

    if i >= len(argv) or argv[i] != "friction":
        return argv  # not a friction invocation
    next_idx = i + 1
    if next_idx >= len(argv):
        return argv  # `note.py friction` alone - argparse handles
    next_tok = argv[next_idx]
    if next_tok in {"log", "summary", "-h", "--help"}:
        return argv
    return argv[: next_idx] + ["log"] + argv[next_idx:]


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    argv = _rewrite_friction_argv(list(argv))
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
