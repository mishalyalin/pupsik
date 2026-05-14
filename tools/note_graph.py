#!/usr/bin/env python3
"""
note_graph.py - Build and query the connection-aware memory graph.

Phase 1 implementation of the note-graph layer. Operates on the 4 tables
created by tools/note_graph_schema.py (entities, notes, note_entity_edges,
note_note_edges) inside contacts.db.

The graph encodes who/what each note touches and how notes relate via shared
entities. Two-hop traversal (note -> entity -> note) surfaces "what else have
I written about this person/company/project/topic" without depending on vector
similarity. ChromaDB stays as a fallback for genuinely semantic neighbours
that share zero entities.

Subcommands:
    backfill              Seed entities + index all md files + compute all edges.
    extract <path>        Re-index a single note (called as a hook from note.py).
    related <slug>        Top-N related notes for a given note.
    entity "Name"         All notes mentioning an entity + co-mention frequency.
    graph <slug>          ASCII-rendered 1/2-hop subgraph from a target note.
    clusters              Connected components over last-N-day notes.
    export-wikilinks      Phase 2: emit a wikilink-injected COPY of the vault for Obsidian.

Usage:
    note_graph.py backfill [--db PATH] [--workspace PATH] [--limit N]
    note_graph.py extract <path> [--db PATH]
    note_graph.py related <slug-or-path> [--limit 10]
    note_graph.py entity "Name" [--limit 20]
    note_graph.py graph <slug-or-path> [--depth 2]
    note_graph.py clusters [--days 7] [--min-notes 3] [--min-weight 0.05] [--top-labels 4] [--max-cluster-size 30]
    note_graph.py export-wikilinks [--output DIR] [--top-n 3]

Paths default to $CLAUDE_WORKSPACE -> $HOME/Desktop/claude.
"""

import argparse
import json
import math
import os
import re
import shutil
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path

# Paths - env override, $HOME fallback (matches memory_search.py + note.py convention).
HOME = Path(os.path.expanduser("~"))
WORKSPACE_DEFAULT = Path(os.environ.get("CLAUDE_WORKSPACE", str(HOME / "Desktop" / "claude")))
DB_PATH_DEFAULT = WORKSPACE_DEFAULT / "data" / "contacts.db"

# Lock file for backfill (concurrent-write guard). Mirrors memory_search.py.
LOCK_STALE_AFTER_SEC = 600

# Notes are walked from these subdirs (skip dotfiles + leading-underscore templates).
NOTE_DIRS = ("memory", "research", "outputs", "briefings")

# Export subcommand: subset of NOTE_DIRS that ships to the Obsidian COPY vault.
# `outputs/` is excluded because it is a bulk-artefact dump (PDFs, dated work
# product) that pollutes the graph view without adding semantic value. A typical
# graph search query is "path:memory OR path:briefings OR path:research".
EXPORT_DIRS = ("memory", "briefings", "research")

# Skip-list of relative-to-workspace paths that should not appear in the export.
# These are infrastructure trees, not memory. Most are already filtered out by
# walk_notes (which only walks NOTE_DIRS), but a defensive guard inside the
# export keeps surprises out if NOTE_DIRS ever expands.
#
# Users: add your own project sub-paths here that contain noisy artefacts
# (e.g. "projects/my-app/", "vendor/", etc.) - they will be excluded from
# the Obsidian export.
EXPORT_SKIP_SUBPATHS = (
    "data/",
    "tools/",
    "mcp-servers/",
    "archived/",
    "state/",
    "logs/",
    "docs/",
    "scripts/",
)

# Default export destination - sibling of workspace so Obsidian "Open vault"
# can point at a single, self-contained directory.
EXPORT_DEFAULT = Path(os.environ.get(
    "CLAUDE_OBSIDIAN_EXPORT",
    str(HOME / "Desktop" / "claude-obsidian-export"),
))

# Per-note neighbour cap (keeps note_note_edges table bounded).
TOP_NEIGHBOURS_PER_NOTE = 50

# Minimum shared entities for an edge to be created.
MIN_SHARED_ENTITIES = 2

# Recency decay: weight halves every ~21 days, drops to e^-1 at 30 days.
RECENCY_DECAY_DAYS = 30.0

# YYYY-MM-DD- prefix detector (matches note.py).
DATE_PREFIX_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-")

# Stop-list of canonical aliases we never auto-promote (would explode false positives).
#
# Users: extend this set with your own personal/project names that show up so
# often in your notes that they would explode the graph if promoted to entities.
# Common candidates: your own first name, your company name, your product name(s).
ALIAS_STOPLIST = {
    "the", "and", "or", "with",
    "for", "from", "into", "onto", "this", "that", "these", "those",
    "have", "has", "had", "will", "would", "could", "should", "their",
    "there", "where", "when", "what", "which", "while", "your", "yours",
    "team", "user", "users", "data", "file", "files", "info", "good",
    "main", "best", "next", "last", "first", "open", "done", "todo",
    "soon", "back", "able", "make", "made", "need", "want", "took",
    "take", "give", "given", "sent", "send", "got", "get", "let",
    "very", "some", "many", "much", "more", "less", "than", "then",
    "also", "even", "ever", "only", "just", "still", "yet", "again",
    "today", "tomorrow", "yesterday", "morning", "evening", "night",
    "work", "works", "working", "worked",
}

# Common English uppercase-first single words we still want to drop (defensive).
# Users: add capitalised versions of your personal/project names here too.
ALIAS_UPPER_STOPLIST = {
    "The", "And", "Or", "With", "For",
    "From", "Into", "Onto", "This", "That", "Have", "Will", "Their",
    "There", "Where", "When", "What", "Which", "While", "Your",
}

# ---------- helpers ----------


def acquire_lock(lock_path: Path, force: bool = False) -> bool:
    """File-based mutex for backfill. JSON payload {pid, started_at}.

    Same semantics as memory_search.py: refuse if a lock < 10min old exists,
    overwrite if it's older (assumed stale), `force=True` always overwrites.
    """
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    if lock_path.exists() and not force:
        try:
            data = json.loads(lock_path.read_text())
            age = time.time() - float(data.get("started_at", 0))
        except Exception:
            age = 0
        if age < LOCK_STALE_AFTER_SEC:
            print(
                f"error: backfill already running (lock at {lock_path}, "
                f"age {int(age)}s). Use --force to override.",
                file=sys.stderr,
            )
            return False
        print(
            f"warn: stale lock at {lock_path} (age {int(age)}s) - overwriting",
            file=sys.stderr,
        )
    try:
        lock_path.write_text(
            json.dumps({"pid": os.getpid(), "started_at": time.time()})
        )
    except Exception as e:
        print(f"error: could not write lock: {e}", file=sys.stderr)
        return False
    return True


def release_lock(lock_path: Path) -> None:
    """Best-effort lock cleanup. Quiet on missing file."""
    try:
        if lock_path.exists():
            lock_path.unlink()
    except Exception as e:
        print(f"warn: could not remove lock: {e}", file=sys.stderr)


def get_db(db_path: Path) -> sqlite3.Connection:
    """Open contacts.db with row_factory + foreign_keys on."""
    if not db_path.exists():
        raise FileNotFoundError(f"contacts.db not found at {db_path}")
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def parse_frontmatter(content: str) -> tuple[dict, str]:
    """Minimal YAML frontmatter parser. Adapted from tools/note.py.

    Returns (fm_dict, body). Supports scalar + inline-list values, which is all
    note.py emits. If frontmatter is malformed or missing, returns ({}, content).
    """
    if not content.startswith("---\n"):
        return {}, content
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
        key, raw = m.group(1), m.group(2).strip()
        if not raw:
            fm[key] = ""
            continue
        if raw.startswith("[") and raw.endswith("]"):
            inner = raw[1:-1].strip()
            if not inner:
                fm[key] = []
                continue
            items: list[str] = []
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
            fm[key] = [
                (it[1:-1].replace('\\"', '"') if it.startswith('"') and it.endswith('"') else it)
                for it in items
            ]
        elif raw.startswith('"') and raw.endswith('"') and len(raw) >= 2:
            fm[key] = raw[1:-1].replace('\\"', '"')
        else:
            fm[key] = raw
    return fm, body.lstrip("\n")


def is_valid_alias(alias: str) -> bool:
    """Aliases must be >=4 chars, not in either stop-list, not all-digits."""
    if not alias or len(alias) < 4:
        return False
    low = alias.lower()
    if low in ALIAS_STOPLIST:
        return False
    if alias in ALIAS_UPPER_STOPLIST:
        return False
    if alias.isdigit():
        return False
    return True


def email_local_part(email: str) -> str | None:
    """Pull the local-part out of `john.doe@example.com` -> `john.doe`."""
    if not email or "@" not in email:
        return None
    return email.split("@", 1)[0].strip()


def first_h1(body: str) -> str | None:
    """First H1 heading in markdown body, or None."""
    for line in body.splitlines():
        m = re.match(r"^#\s+(.+?)\s*$", line)
        if m:
            return m.group(1).strip()
    return None


def derive_note_type(path: Path, fm: dict) -> str:
    """Note type: frontmatter `type` if present, else parent dir name."""
    if fm.get("type"):
        return str(fm["type"]).strip()
    return path.parent.name


def to_json_array(items: list) -> str:
    """JSON-encode a list for SQLite TEXT storage."""
    return json.dumps(items, ensure_ascii=False)


# ---------- entity seeding ----------


def seed_contact_entities(conn: sqlite3.Connection) -> int:
    """Seed entities.kind='person' from contacts table.

    Aliases include: name, full_name (if different), email local-part.
    Skips contacts whose name fails is_valid_alias().
    """
    rows = conn.execute(
        "SELECT id, name, full_name, email, email2 FROM contacts"
    ).fetchall()
    count = 0
    for r in rows:
        name = (r["name"] or "").strip()
        if not is_valid_alias(name):
            continue
        aliases = {name}
        full_name = (r["full_name"] or "").strip()
        if full_name and full_name != name and is_valid_alias(full_name):
            aliases.add(full_name)
            # Also add last word of full_name as an alias if it stands alone.
            parts = full_name.split()
            if len(parts) >= 2:
                last = parts[-1]
                if is_valid_alias(last):
                    aliases.add(last)
        for em in (r["email"], r["email2"]):
            lp = email_local_part(em or "")
            if lp and is_valid_alias(lp):
                aliases.add(lp)
        sorted_aliases = sorted(aliases, key=lambda x: (-len(x), x.lower()))
        conn.execute(
            "INSERT OR IGNORE INTO entities (kind, name, aliases, contact_id) "
            "VALUES (?, ?, ?, ?)",
            ("person", name, to_json_array(sorted_aliases), r["id"]),
        )
        count += 1
    return count


def seed_company_entities(conn: sqlite3.Connection) -> int:
    """Seed entities.kind='company' from companies table.

    Aliases: name + short-form (drop legal suffixes like Ltd/Inc/B.V.).
    """
    rows = conn.execute("SELECT id, name FROM companies").fetchall()
    count = 0
    for r in rows:
        name = (r["name"] or "").strip()
        if not is_valid_alias(name):
            continue
        aliases = {name}
        # Short form: strip common legal suffixes.
        short = re.sub(
            r"\s+(Ltd|Limited|Inc|Inc\.|Corp|Corp\.|LLC|GmbH|B\.V\.|BV|LTD|S\.A\.|S\.L\.|Logistics)\b",
            "",
            name,
            flags=re.IGNORECASE,
        ).strip()
        if short and short != name and is_valid_alias(short):
            aliases.add(short)
        sorted_aliases = sorted(aliases, key=lambda x: (-len(x), x.lower()))
        conn.execute(
            "INSERT OR IGNORE INTO entities (kind, name, aliases, company_id) "
            "VALUES (?, ?, ?, ?)",
            ("company", name, to_json_array(sorted_aliases), r["id"]),
        )
        count += 1
    return count


def seed_project_entities(conn: sqlite3.Connection, workspace: Path) -> int:
    """Seed entities.kind='project' from CLAUDE.md's "## Active Projects" section.

    Parses numbered list (1. **Name** - desc). Aliases include the project name
    + the leading numbered tag + any company-name regex hits found in the
    description body (these are already company entities, but we want to make
    project<->company entity-overlap reflectable too).
    """
    claude_md = workspace / "CLAUDE.md"
    if not claude_md.exists():
        return 0
    text = claude_md.read_text(encoding="utf-8", errors="replace")
    # Slice from "## Active Projects" to next top-level heading or "## Key Decisions" etc.
    start = text.find("## Active Projects")
    if start == -1:
        return 0
    rest = text[start:]
    # Next "## " heading boundary.
    next_h = rest.find("\n## ", 5)
    section = rest if next_h == -1 else rest[:next_h]
    count = 0
    # Match `1. **Name** -- desc` or `1. **Name** ...` (em-dash variants are tolerated
    # in regex even though emit code uses ASCII hyphen only).
    pattern = re.compile(r"^(\d+)\.\s+\*\*([^*]+)\*\*\s*(.*?)$", re.MULTILINE)
    for m in pattern.finditer(section):
        num = m.group(1)
        proj_name = m.group(2).strip().rstrip(":").rstrip("-").strip()
        if not is_valid_alias(proj_name):
            continue
        aliases = {proj_name, f"Project: {proj_name}"}
        # The number is too short to alias on its own (`1` matches everywhere).
        # But "Project N" might be referenced occasionally.
        aliases.add(f"Project {num}")
        sorted_aliases = sorted(aliases, key=lambda x: (-len(x), x.lower()))
        conn.execute(
            "INSERT OR IGNORE INTO entities (kind, name, aliases) "
            "VALUES (?, ?, ?)",
            ("project", proj_name, to_json_array(sorted_aliases)),
        )
        count += 1
    return count


def seed_topic_entities(conn: sqlite3.Connection, workspace: Path) -> int:
    """Seed entities.kind='topic' from memory/projects/*.md and memory/project_*.md.

    `uk-vat-registration.md` -> topic "UK Vat Registration"
    aliases ["UK Vat Registration", "UK Vat", "VAT", ...]
    """
    count = 0
    sources: list[Path] = []
    # Subdir pattern (current convention): memory/projects/<slug>.md
    proj_dir = workspace / "memory" / "projects"
    if proj_dir.exists():
        sources.extend(proj_dir.glob("*.md"))
    # Legacy pattern: memory/project_<slug>.md at root.
    legacy_dir = workspace / "memory"
    if legacy_dir.exists():
        sources.extend(legacy_dir.glob("project_*.md"))
    for path in sources:
        stem = path.stem
        if stem.startswith("project_"):
            rest = stem[len("project_"):]
        else:
            rest = stem
        # Split on underscore / hyphen, title-case each word.
        words = re.split(r"[_\-]+", rest)
        topic_name = " ".join(w.upper() if len(w) <= 3 else w.capitalize() for w in words)
        topic_name = topic_name.strip()
        if not is_valid_alias(topic_name):
            continue
        aliases = {topic_name}
        # Compact form (drop common words).
        compact = " ".join(
            w for w in topic_name.split()
            if w.lower() not in {"the", "of", "and", "registration", "strategy"}
        )
        if compact and compact != topic_name and is_valid_alias(compact):
            aliases.add(compact)
        # Add any short ALLCAPS tokens (UK, VAT, EU, etc.) as separate aliases
        # if they pass is_valid_alias (>= 4 chars). Skip very-short ones.
        for w in topic_name.split():
            if len(w) >= 4 and is_valid_alias(w):
                aliases.add(w)
        sorted_aliases = sorted(aliases, key=lambda x: (-len(x), x.lower()))
        conn.execute(
            "INSERT OR IGNORE INTO entities (kind, name, aliases) "
            "VALUES (?, ?, ?)",
            ("topic", topic_name, to_json_array(sorted_aliases)),
        )
        count += 1
    return count


# ---------- note ingestion ----------


def walk_notes(workspace: Path, limit: int | None = None) -> list[Path]:
    """Walk every .md file under NOTE_DIRS at workspace.

    Skips:
    - dotfiles (.foo.md)
    - leading-underscore templates (_PROTOCOL.md)
    - files outside the 4 whitelisted top-level dirs

    Returns absolute paths.
    """
    out: list[Path] = []
    for top in NOTE_DIRS:
        root = workspace / top
        if not root.exists():
            continue
        for p in root.rglob("*.md"):
            if p.name.startswith(".") or p.name.startswith("_"):
                continue
            try:
                out.append(p.resolve())
            except OSError:
                continue
    out.sort()
    if limit is not None:
        out = out[:limit]
    return out


def index_note(conn: sqlite3.Connection, path: Path) -> tuple[int, str, str, list[str]]:
    """Upsert a note row. Returns (note_id, title, type, body) for downstream use."""
    text = path.read_text(encoding="utf-8", errors="replace")
    fm, body = parse_frontmatter(text)
    title = (
        fm.get("title")
        or first_h1(body)
        or path.stem.replace("-", " ").strip()
    )
    note_type = derive_note_type(path, fm)
    tags = fm.get("tags") if isinstance(fm.get("tags"), list) else []
    try:
        mtime = float(os.path.getmtime(path))
    except OSError:
        mtime = 0.0
    abs_path = str(path)
    conn.execute(
        """
        INSERT INTO notes (path, title, type, tags, mtime, indexed_at)
        VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(path) DO UPDATE SET
            title=excluded.title,
            type=excluded.type,
            tags=excluded.tags,
            mtime=excluded.mtime,
            indexed_at=CURRENT_TIMESTAMP
        """,
        (abs_path, title, note_type, to_json_array(tags), mtime),
    )
    row = conn.execute("SELECT id FROM notes WHERE path = ?", (abs_path,)).fetchone()
    return row["id"], title, note_type, tags


# ---------- entity extraction ----------


def load_entities(conn: sqlite3.Connection) -> list[dict]:
    """Load all entities with aliases. Returns list of dicts."""
    rows = conn.execute(
        "SELECT id, kind, name, aliases FROM entities ORDER BY id"
    ).fetchall()
    out = []
    for r in rows:
        try:
            aliases = json.loads(r["aliases"] or "[]")
        except (json.JSONDecodeError, TypeError):
            aliases = [r["name"]]
        if not aliases:
            aliases = [r["name"]]
        out.append({
            "id": r["id"],
            "kind": r["kind"],
            "name": r["name"],
            "aliases": [a for a in aliases if is_valid_alias(a)],
        })
    return out


def build_alias_index(entities: list[dict]) -> tuple[re.Pattern | None, dict[str, list[int]]]:
    """Compile one mega-regex covering every valid alias.

    Returns (compiled_pattern, alias_lower -> [entity_ids]). Multiple entities
    can share an alias (e.g. "Apex" matched both an Apex Project and an Apex
    topic), so the value is a list.

    Aliases are sorted longest-first inside the regex so a longer match wins
    over a shorter contained one (e.g. "Joe Lound" beats "Lound").
    """
    alias_to_ids: dict[str, list[int]] = {}
    for e in entities:
        for alias in e["aliases"]:
            key = alias.lower()
            alias_to_ids.setdefault(key, []).append(e["id"])
    if not alias_to_ids:
        return None, {}
    sorted_aliases = sorted(alias_to_ids.keys(), key=lambda s: (-len(s), s))
    pattern_str = r"\b(" + "|".join(re.escape(a) for a in sorted_aliases) + r")\b"
    try:
        pattern = re.compile(pattern_str, re.IGNORECASE)
    except re.error as e:
        print(f"warn: alias regex compile failed: {e}", file=sys.stderr)
        return None, alias_to_ids
    return pattern, alias_to_ids


def extract_mentions(
    body: str,
    pattern: re.Pattern | None,
    alias_to_ids: dict[str, list[int]],
    note_tags: list[str],
) -> dict[int, dict]:
    """Run the mega-regex over the body. Return {entity_id: {count, source, confidence}}.

    `source` priorities (in order if multiple sources match):
        "frontmatter" - alias appears verbatim in note_tags
        "tag-derived" - alias is an entity name and entity name itself is in note_tags
        "body-regex"  - default
    Confidence is 1.0 for direct regex match in Phase 1 (fuzzy reserved for Phase 2).
    """
    counts: dict[int, int] = {}
    sources: dict[int, str] = {}
    if pattern is None:
        return {}
    tag_set_lower = {t.lower() for t in note_tags}
    for match in pattern.finditer(body):
        alias = match.group(1)
        ids = alias_to_ids.get(alias.lower(), [])
        for eid in ids:
            counts[eid] = counts.get(eid, 0) + 1
            if eid not in sources:
                sources[eid] = "body-regex"
                if alias.lower() in tag_set_lower:
                    sources[eid] = "frontmatter"
    # Promote "tag-derived" for entities whose canonical name is itself a tag.
    return {
        eid: {"count": cnt, "source": sources[eid], "confidence": 1.0}
        for eid, cnt in counts.items()
    }


def write_note_entity_edges(
    conn: sqlite3.Connection,
    note_id: int,
    mentions: dict[int, dict],
) -> int:
    """Replace edges for one note. Returns # edges written."""
    conn.execute("DELETE FROM note_entity_edges WHERE note_id = ?", (note_id,))
    for eid, info in mentions.items():
        conn.execute(
            """
            INSERT INTO note_entity_edges (note_id, entity_id, mention_count, source, confidence)
            VALUES (?, ?, ?, ?, ?)
            """,
            (note_id, eid, info["count"], info["source"], info["confidence"]),
        )
    return len(mentions)


# ---------- note-note edge computation ----------


def compute_note_note_edges_for_target(
    conn: sqlite3.Connection,
    target_id: int,
) -> int:
    """Recompute note_note_edges for a single note (incremental, used by `extract`).

    Drops edges where target is either side, then recomputes against all other
    notes that share >= MIN_SHARED_ENTITIES entities with target.
    Returns # edges written for this target.
    """
    # Build target's entity set.
    target_entities = {
        r["entity_id"]
        for r in conn.execute(
            "SELECT entity_id FROM note_entity_edges WHERE note_id = ?",
            (target_id,),
        )
    }
    if len(target_entities) < MIN_SHARED_ENTITIES:
        conn.execute(
            "DELETE FROM note_note_edges WHERE a_id = ? OR b_id = ?",
            (target_id, target_id),
        )
        return 0

    target_mtime = (
        conn.execute("SELECT mtime FROM notes WHERE id = ?", (target_id,)).fetchone()
        or {"mtime": 0.0}
    )["mtime"] or 0.0

    # Global entity frequencies for inverse-frequency weighting.
    freq_rows = conn.execute(
        "SELECT entity_id, COUNT(*) AS c FROM note_entity_edges GROUP BY entity_id"
    ).fetchall()
    freq = {r["entity_id"]: max(1, r["c"]) for r in freq_rows}

    # Entity-id IN placeholder list. SQLite parameter limit (~999) usually fine.
    ph = ",".join("?" * len(target_entities))
    other_rows = conn.execute(
        f"""
        SELECT note_id, GROUP_CONCAT(entity_id) AS eids
        FROM note_entity_edges
        WHERE entity_id IN ({ph}) AND note_id != ?
        GROUP BY note_id
        """,
        (*target_entities, target_id),
    ).fetchall()

    candidates: list[tuple[int, float, int, list[dict]]] = []
    target_size = len(target_entities)
    for r in other_rows:
        other_id = r["note_id"]
        other_eids = {int(x) for x in (r["eids"] or "").split(",") if x}
        shared = target_entities & other_eids
        if len(shared) < MIN_SHARED_ENTITIES:
            continue
        # Full count of other note's entities (for jaccard denominator).
        cnt_other = conn.execute(
            "SELECT COUNT(*) AS c FROM note_entity_edges WHERE note_id = ?",
            (other_id,),
        ).fetchone()["c"]
        union_size = target_size + cnt_other - len(shared)
        if union_size <= 0:
            continue
        jaccard = len(shared) / union_size
        other_mtime = (
            conn.execute(
                "SELECT mtime FROM notes WHERE id = ?", (other_id,)
            ).fetchone()["mtime"] or 0.0
        )
        max_mtime = max(target_mtime, other_mtime)
        days_since = max(0.0, (time.time() - max_mtime) / 86400.0)
        recency = math.exp(-days_since / RECENCY_DECAY_DAYS)
        # Inverse-frequency: a shared entity that appears in many notes is
        # less informative. Compute mean(1 / log(1 + freq)) over shared.
        inv_terms = [1.0 / math.log(1.0 + freq.get(eid, 1)) for eid in shared]
        # Guard log(2)~0.69 floor.
        inv_factor = sum(inv_terms) / len(inv_terms) if inv_terms else 1.0
        weight = jaccard * recency * inv_factor
        shared_kinds: list[dict] = []
        for eid in shared:
            ek = conn.execute(
                "SELECT kind FROM entities WHERE id = ?", (eid,)
            ).fetchone()
            shared_kinds.append({
                "entity_id": eid,
                "kind": ek["kind"] if ek else "unknown",
            })
        candidates.append((other_id, weight, len(shared), shared_kinds))

    candidates.sort(key=lambda t: t[1], reverse=True)
    top = candidates[:TOP_NEIGHBOURS_PER_NOTE]

    # Wipe old edges that touch target, then insert new.
    conn.execute(
        "DELETE FROM note_note_edges WHERE a_id = ? OR b_id = ?",
        (target_id, target_id),
    )
    written = 0
    for other_id, weight, shared_count, shared_kinds in top:
        a_id, b_id = (target_id, other_id) if target_id < other_id else (other_id, target_id)
        conn.execute(
            """
            INSERT OR REPLACE INTO note_note_edges
                (a_id, b_id, shared_count, shared_kinds, weight, computed_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (a_id, b_id, shared_count, to_json_array(shared_kinds), weight),
        )
        written += 1
    return written


def compute_all_note_note_edges(conn: sqlite3.Connection) -> int:
    """Full recompute over every note (used by backfill).

    Strategy: per-note loop calling compute_note_note_edges_for_target() is
    O(N^2) in worst case but bounded by entity sparsity and TOP_NEIGHBOURS cap.
    For ~400 notes this is well under 60s on a laptop. Wipe all edges first to
    keep the second-pass deletes from being lossy.
    """
    conn.execute("DELETE FROM note_note_edges")
    note_ids = [r["id"] for r in conn.execute("SELECT id FROM notes ORDER BY id")]
    total = 0
    for nid in note_ids:
        total += compute_note_note_edges_for_target(conn, nid)
    return total


# ---------- subcommand: backfill ----------


def cmd_backfill(args) -> int:
    """Full backfill: seed entities, ingest notes, compute edges."""
    db_path = args.db.expanduser().resolve()
    workspace = args.workspace.expanduser().resolve()
    lock_path = db_path.parent / ".note_graph.lock"
    if not acquire_lock(lock_path, force=args.force):
        return 1
    try:
        conn = get_db(db_path)
        try:
            t0 = time.time()
            print(f"backfill: db={db_path}")
            print(f"          workspace={workspace}")

            # Entities.
            with conn:
                n_contacts = seed_contact_entities(conn)
                n_companies = seed_company_entities(conn)
                n_projects = seed_project_entities(conn, workspace)
                n_topics = seed_topic_entities(conn, workspace)
            total_entities = n_contacts + n_companies + n_projects + n_topics
            print(
                f"entities seeded: person={n_contacts} company={n_companies} "
                f"project={n_projects} topic={n_topics} (total={total_entities})"
            )

            # Aliases + regex.
            entities = load_entities(conn)
            pattern, alias_to_ids = build_alias_index(entities)
            if pattern is None:
                print("error: no valid aliases - aborting", file=sys.stderr)
                return 2

            # Notes + entity edges.
            paths = walk_notes(workspace, limit=args.limit)
            print(f"notes to ingest: {len(paths)}")
            edge_total = 0
            with conn:
                for i, path in enumerate(paths, 1):
                    try:
                        note_id, _, _, tags = index_note(conn, path)
                        text = path.read_text(encoding="utf-8", errors="replace")
                        _, body = parse_frontmatter(text)
                        mentions = extract_mentions(body, pattern, alias_to_ids, tags)
                        edge_total += write_note_entity_edges(conn, note_id, mentions)
                    except Exception as e:
                        print(f"warn: failed {path}: {e}", file=sys.stderr)
                        continue
                    if i % 50 == 0:
                        print(f"  ... {i}/{len(paths)} notes ingested")
            print(f"note_entity_edges written: {edge_total}")

            # Note-note edges.
            print("computing note_note_edges (this is the slow part)...")
            with conn:
                nn_total = compute_all_note_note_edges(conn)
            print(f"note_note_edges written: {nn_total}")

            dt = time.time() - t0
            print(f"backfill complete in {dt:.1f}s")
            return 0
        finally:
            conn.close()
    finally:
        release_lock(lock_path)


# ---------- subcommand: extract ----------


def cmd_extract(args) -> int:
    """Re-index a single note (hook from note.py after write).

    Performance target <100ms. Skips the full-graph recompute - only rewrites
    this note's entity edges + its own neighbour set.
    """
    db_path = args.db.expanduser().resolve()
    path = Path(args.path).expanduser().resolve()
    if not path.exists():
        print(f"error: file not found: {path}", file=sys.stderr)
        return 1
    conn = get_db(db_path)
    try:
        with conn:
            note_id, _, _, tags = index_note(conn, path)
            text = path.read_text(encoding="utf-8", errors="replace")
            _, body = parse_frontmatter(text)
            entities = load_entities(conn)
            pattern, alias_to_ids = build_alias_index(entities)
            if pattern is None:
                print("warn: no entities seeded yet - run backfill first", file=sys.stderr)
                return 0
            mentions = extract_mentions(body, pattern, alias_to_ids, tags)
            n_ent = write_note_entity_edges(conn, note_id, mentions)
            n_nn = compute_note_note_edges_for_target(conn, note_id)
        print(f"extract: {path.name} -> entity_edges={n_ent} note_neighbours={n_nn}")
        return 0
    finally:
        conn.close()


# ---------- helpers shared by query subcommands ----------


def resolve_note(conn: sqlite3.Connection, slug_or_path: str) -> sqlite3.Row | None:
    """Find a single notes row by exact path or filename-slug match.

    Slug matching: case-insensitive substring on filename. Returns most recent
    match if multiple hit. Returns None if no match.
    """
    # Exact path first.
    row = conn.execute(
        "SELECT * FROM notes WHERE path = ?", (str(Path(slug_or_path).expanduser()),)
    ).fetchone()
    if row:
        return row
    # Filename substring match.
    rows = conn.execute(
        "SELECT * FROM notes WHERE LOWER(path) LIKE LOWER(?) ORDER BY mtime DESC",
        (f"%{slug_or_path}%",),
    ).fetchall()
    return rows[0] if rows else None


def fetch_entity_by_name(conn: sqlite3.Connection, name: str) -> list[sqlite3.Row]:
    """Find entities matching `name` on canonical name OR alias.

    Returns ordered list (most-specific match first). Case-insensitive.
    """
    # Exact canonical name first.
    exact = conn.execute(
        "SELECT * FROM entities WHERE name = ? COLLATE NOCASE", (name,)
    ).fetchall()
    if exact:
        return exact
    # Alias match: scan + JSON-decode. For <300 entities this is cheap.
    out: list[sqlite3.Row] = []
    all_ent = conn.execute("SELECT * FROM entities").fetchall()
    name_low = name.lower()
    for r in all_ent:
        try:
            aliases = json.loads(r["aliases"] or "[]")
        except (json.JSONDecodeError, TypeError):
            continue
        if any(a.lower() == name_low for a in aliases):
            out.append(r)
    return out


# ---------- subcommand: related ----------


def cmd_related(args) -> int:
    """Top-N related notes for a given slug/path."""
    db_path = args.db.expanduser().resolve()
    conn = get_db(db_path)
    try:
        note = resolve_note(conn, args.target)
        if not note:
            print(f"note not found: {args.target}")
            return 0
        nid = note["id"]
        print(f"related: {note['path']}")
        print()
        # Entity-linked: pull note_note_edges where this note is one side.
        rel_rows = conn.execute(
            """
            SELECT
                CASE WHEN a_id = ? THEN b_id ELSE a_id END AS other_id,
                shared_count, weight, shared_kinds
            FROM note_note_edges
            WHERE a_id = ? OR b_id = ?
            ORDER BY weight DESC
            LIMIT ?
            """,
            (nid, nid, nid, args.limit),
        ).fetchall()
        if rel_rows:
            avg_shared = sum(r["shared_count"] for r in rel_rows) // max(1, len(rel_rows))
            print(f"ENTITY-LINKED ({avg_shared} avg shared entities each):")
            for r in rel_rows:
                other = conn.execute(
                    "SELECT path FROM notes WHERE id = ?", (r["other_id"],)
                ).fetchone()
                if not other:
                    continue
                rel_path = relativize(Path(other["path"]), args.workspace)
                print(f"  [{r['weight']:.2f}] {rel_path}  (shared={r['shared_count']})")
        else:
            print("ENTITY-LINKED: (no shared-entity neighbours)")
        print()

        # Entities in this note.
        ent_rows = conn.execute(
            """
            SELECT e.id, e.kind, e.name, nee.mention_count
            FROM note_entity_edges nee
            JOIN entities e ON e.id = nee.entity_id
            WHERE nee.note_id = ?
            ORDER BY nee.mention_count DESC, e.name
            """,
            (nid,),
        ).fetchall()
        if ent_rows:
            labels = [f"{r['name']} ({r['kind']})" for r in ent_rows]
            print("ENTITIES IN THIS NOTE:", ", ".join(labels))
            print()

        # Semantic neighbours via memory_search.py (best-effort).
        semantic_paths = fetch_semantic_neighbours(args.workspace, note["path"], args.limit)
        linked_ids = {r["other_id"] for r in rel_rows}
        linked_paths = {
            conn.execute("SELECT path FROM notes WHERE id = ?", (oid,)).fetchone()["path"]
            for oid in linked_ids
            if conn.execute("SELECT path FROM notes WHERE id = ?", (oid,)).fetchone()
        }
        novel = [p for p in semantic_paths if p not in linked_paths and p != note["path"]]
        if novel:
            print("SEMANTIC NEIGHBOURS (low entity overlap, high vector sim):")
            for p in novel[: args.limit]:
                print(f"  {relativize(Path(p), args.workspace)}")
        return 0
    finally:
        conn.close()


def relativize(path: Path, workspace: Path) -> str:
    """Strip workspace prefix if present. Otherwise return abs path."""
    try:
        return str(path.relative_to(workspace))
    except (ValueError, AttributeError):
        return str(path)


def fetch_semantic_neighbours(workspace: Path, target_path: str, limit: int) -> list[str]:
    """Best-effort: call memory_search.py search to get vector-similar notes.

    Returns absolute paths. Returns [] if memory_search.py isn't installed or
    chromadb isn't available - the related subcommand handles that gracefully.
    """
    ms = workspace / "tools" / "memory_search.py"
    if not ms.exists():
        return []
    try:
        # Use the note's filename stem as the query - lightweight proxy for the
        # note's "topic" without re-reading body. Phase 2 could chunk and search.
        query = Path(target_path).stem.replace("-", " ")
        import subprocess
        result = subprocess.run(
            [sys.executable, str(ms), "search", query, "--top", str(limit * 2)],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return []
        # memory_search.py output format includes lines like "  /abs/path.md".
        # Greedy extraction: any line containing the workspace root that ends in .md.
        out: list[str] = []
        for line in result.stdout.splitlines():
            line = line.strip()
            if line.endswith(".md") and str(workspace) in line:
                idx = line.find(str(workspace))
                out.append(line[idx:].strip())
        return out
    except Exception:
        return []


# ---------- subcommand: entity ----------


def cmd_entity(args) -> int:
    """All notes mentioning an entity + co-mention frequency."""
    db_path = args.db.expanduser().resolve()
    conn = get_db(db_path)
    try:
        matches = fetch_entity_by_name(conn, args.name)
        if not matches:
            print(f"entity not found: {args.name}")
            return 0
        ent = matches[0]
        print(f"entity: {ent['name']} ({ent['kind']})")
        print()

        # Notes mentioning this entity.
        note_rows = conn.execute(
            """
            SELECT n.path, n.title, n.mtime, nee.mention_count
            FROM note_entity_edges nee
            JOIN notes n ON n.id = nee.note_id
            WHERE nee.entity_id = ?
            ORDER BY n.mtime DESC
            LIMIT ?
            """,
            (ent["id"], args.limit),
        ).fetchall()
        total = conn.execute(
            "SELECT COUNT(*) AS c FROM note_entity_edges WHERE entity_id = ?",
            (ent["id"],),
        ).fetchone()["c"]
        print(f"MENTIONED IN {total} NOTES (most recent first):")
        for r in note_rows:
            date = (
                datetime.fromtimestamp(r["mtime"]).strftime("%Y-%m-%d")
                if r["mtime"] else "????-??-??"
            )
            rel_path = relativize(Path(r["path"]), args.workspace)
            print(f"  [{date}] {rel_path} ({r['mention_count']} mentions)")
        print()

        # Co-mentioned entities.
        co_rows = conn.execute(
            """
            SELECT e2.id, e2.kind, e2.name, COUNT(DISTINCT nee2.note_id) AS co_count
            FROM note_entity_edges nee1
            JOIN note_entity_edges nee2 ON nee2.note_id = nee1.note_id
            JOIN entities e2 ON e2.id = nee2.entity_id
            WHERE nee1.entity_id = ? AND nee2.entity_id != ?
            GROUP BY e2.id
            ORDER BY co_count DESC
            LIMIT ?
            """,
            (ent["id"], ent["id"], args.limit),
        ).fetchall()
        if co_rows:
            print("CO-MENTIONED WITH:")
            for r in co_rows:
                label = f"{r['name']}" + (
                    f" ({r['kind']})" if r["kind"] != "person" else ""
                )
                print(f"  {label} ({r['co_count']} notes)")
        return 0
    finally:
        conn.close()


# ---------- subcommand: graph ----------


def cmd_graph(args) -> int:
    """ASCII-rendered 1- or 2-hop subgraph from a target note."""
    db_path = args.db.expanduser().resolve()
    conn = get_db(db_path)
    try:
        note = resolve_note(conn, args.target)
        if not note:
            print(f"note not found: {args.target}")
            return 0
        nid = note["id"]
        nlabel = relativize(Path(note["path"]), args.workspace)
        print(f"[note] {nlabel}")
        ent_rows = conn.execute(
            """
            SELECT e.id, e.kind, e.name, nee.mention_count
            FROM note_entity_edges nee
            JOIN entities e ON e.id = nee.entity_id
            WHERE nee.note_id = ?
            ORDER BY nee.mention_count DESC, e.name
            """,
            (nid,),
        ).fetchall()
        if not ent_rows:
            print("  (no entities)")
            return 0
        for er in ent_rows:
            print(f"  +- [entity:{er['kind']}] {er['name']}  (x{er['mention_count']})")
            if args.depth >= 2:
                next_notes = conn.execute(
                    """
                    SELECT n.id, n.path, nee.mention_count
                    FROM note_entity_edges nee
                    JOIN notes n ON n.id = nee.note_id
                    WHERE nee.entity_id = ? AND n.id != ?
                    ORDER BY n.mtime DESC
                    LIMIT 5
                    """,
                    (er["id"], nid),
                ).fetchall()
                for nn in next_notes:
                    rel = relativize(Path(nn["path"]), args.workspace)
                    print(f"  |    +- [note] {rel}")
        return 0
    finally:
        conn.close()


# ---------- subcommand: clusters ----------


def _cluster_via_louvain(
    nodes: set[int], edges: list[tuple[int, int, float]]
) -> list[list[int]] | None:
    """Run networkx Louvain modularity clustering on weighted graph.

    Returns list of node-id lists, or None if networkx unavailable.
    Louvain finds densely-connected sub-communities even when the broader graph
    is connected, so it cleanly splits the 202-note blob into topic clusters.
    """
    try:
        import networkx as nx
        from networkx.algorithms import community as nx_community
    except ImportError:
        return None
    if not hasattr(nx_community, "louvain_communities"):
        return None
    g = nx.Graph()
    g.add_nodes_from(nodes)
    for a, b, w in edges:
        g.add_edge(a, b, weight=w)
    # resolution=1.0 is default; higher = more, smaller clusters. Seed for stability.
    communities = nx_community.louvain_communities(g, weight="weight", seed=42)
    return [list(c) for c in communities]


def _cluster_via_components(
    nodes: set[int], edges: list[tuple[int, int, float]]
) -> list[list[int]]:
    """Pure-python union-find fallback when networkx is unavailable.

    Operates on the already-weight-filtered edge list, so even this fallback
    produces smaller, more coherent clusters than the old no-threshold version.
    """
    parent: dict[int, int] = {nid: nid for nid in nodes}

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x: int, y: int) -> None:
        rx, ry = find(x), find(y)
        if rx != ry:
            parent[rx] = ry

    for a, b, _w in edges:
        union(a, b)
    out: dict[int, list[int]] = {}
    for nid in nodes:
        out.setdefault(find(nid), []).append(nid)
    return list(out.values())


def _compute_cluster_label(
    cluster: list[int],
    cluster_idx: int,
    all_cluster_entity_sets: list[dict[int, int]],
    entity_meta: dict[int, dict],
    top_labels: int,
) -> str:
    """Pick top-N entities for this cluster using TF-ICF + kind-preference.

    Score formula (per entity in this cluster):
        tf  = notes_in_cluster_mentioning_entity / cluster_size
        icf = log(N_clusters / N_clusters_mentioning_entity)
        kind_boost = 1.5 if kind in (project, topic) else 1.0 for company else 0.7 for person
        score = tf * icf * kind_boost

    Entities with icf <= 0 (mentioned in every cluster) get filtered out -
    those are pure-noise labels like "Ben Thompson" that appear everywhere.
    """
    n_clusters = max(1, len(all_cluster_entity_sets))
    this_set = all_cluster_entity_sets[cluster_idx]
    if not this_set:
        return "(unlabeled)"
    cluster_size = max(1, len(cluster))
    kind_weight = {
        "project": 1.5,
        "topic": 1.5,
        "company": 1.0,
        "person": 0.7,
    }
    scored: list[tuple[float, str, str]] = []
    for eid, notes_with_entity in this_set.items():
        n_clusters_with = sum(
            1 for s in all_cluster_entity_sets if eid in s
        )
        if n_clusters_with <= 0:
            continue
        icf = math.log(n_clusters / n_clusters_with) if n_clusters_with < n_clusters else 0.0
        if icf <= 0:
            # Entity appears in every cluster - generic, skip.
            continue
        tf = notes_with_entity / cluster_size
        meta = entity_meta.get(eid, {"name": f"entity#{eid}", "kind": "unknown"})
        boost = kind_weight.get(meta["kind"], 1.0)
        score = tf * icf * boost
        scored.append((score, meta["name"], meta["kind"]))
    if not scored:
        # All entities are generic - fall back to most-frequent within cluster.
        fallback = sorted(
            this_set.items(), key=lambda kv: kv[1], reverse=True
        )[:top_labels]
        names = []
        seen: set[str] = set()
        for eid, _ in fallback:
            nm = entity_meta.get(eid, {}).get("name", f"entity#{eid}")
            if nm.lower() in seen:
                continue
            seen.add(nm.lower())
            names.append(nm)
        return " / ".join(names) if names else "(unlabeled)"
    scored.sort(key=lambda t: t[0], reverse=True)
    # Dedup by lowercased name - we seed project + topic entities with identical
    # names, and we don't want "Fundraising / Fundraising" in the label.
    out_names: list[str] = []
    seen_names: set[str] = set()
    for _s, name, _k in scored:
        key = name.lower()
        if key in seen_names:
            continue
        seen_names.add(key)
        out_names.append(name)
        if len(out_names) >= top_labels:
            break
    return " / ".join(out_names)


def cmd_clusters(args) -> int:
    """Modularity-based clustering over weight-thresholded note_note_edges.

    Strategy: prune edges below --min-weight, then run Louvain community
    detection (or fall back to connected-components if networkx missing).
    Label each cluster via TF-ICF: entities that concentrate in this cluster
    AND don't appear in every cluster, with kind-preference for project/topic.
    """
    db_path = args.db.expanduser().resolve()
    conn = get_db(db_path)
    try:
        cutoff = time.time() - args.days * 86400
        active_ids = {
            r["id"] for r in conn.execute(
                "SELECT id FROM notes WHERE mtime >= ?", (cutoff,)
            )
        }
        if not active_ids:
            print(f"no notes touched in last {args.days}d")
            return 0
        ph = ",".join("?" * len(active_ids))
        edge_rows = conn.execute(
            f"""
            SELECT a_id, b_id, weight FROM note_note_edges
            WHERE a_id IN ({ph}) AND b_id IN ({ph}) AND weight >= ?
            """,
            (*active_ids, *active_ids, args.min_weight),
        ).fetchall()
        edges: list[tuple[int, int, float]] = [
            (r["a_id"], r["b_id"], r["weight"]) for r in edge_rows
        ]

        # Try Louvain modularity first, fall back to weight-thresholded components.
        clusters = _cluster_via_louvain(active_ids, edges)
        method = "louvain"
        if clusters is None:
            clusters = _cluster_via_components(active_ids, edges)
            method = "components"

        big = [c for c in clusters if len(c) >= args.min_notes]
        big.sort(key=len, reverse=True)
        if not big:
            print(
                f"no clusters with >= {args.min_notes} notes in last {args.days}d"
            )
            return 0

        # Per-cluster entity-occurrence sets (entity_id -> #notes-in-cluster).
        # Needed for ICF (inverse cluster frequency) labeling.
        all_cluster_entity_sets: list[dict[int, int]] = []
        for c in big:
            ph2 = ",".join("?" * len(c))
            rows = conn.execute(
                f"""
                SELECT entity_id, COUNT(DISTINCT note_id) AS n
                FROM note_entity_edges
                WHERE note_id IN ({ph2})
                GROUP BY entity_id
                """,
                tuple(c),
            ).fetchall()
            all_cluster_entity_sets.append({r["entity_id"]: r["n"] for r in rows})

        # Pre-load entity metadata (name + kind) for all entities seen.
        all_eids = {eid for s in all_cluster_entity_sets for eid in s}
        entity_meta: dict[int, dict] = {}
        if all_eids:
            ph3 = ",".join("?" * len(all_eids))
            for r in conn.execute(
                f"SELECT id, name, kind FROM entities WHERE id IN ({ph3})",
                tuple(all_eids),
            ):
                entity_meta[r["id"]] = {"name": r["name"], "kind": r["kind"]}

        print(
            f"Active clusters (last {args.days}d, >={args.min_notes} notes, "
            f"method={method}, min-weight={args.min_weight}):"
        )
        for idx, c in enumerate(big):
            label = _compute_cluster_label(
                c, idx, all_cluster_entity_sets, entity_meta, args.top_labels,
            )
            # Truncate display label note-count if oversized cluster.
            size_note = ""
            if len(c) > args.max_cluster_size:
                size_note = f" [oversized, top entities by centrality]"
            ph2 = ",".join("?" * len(c))
            last_touched_row = conn.execute(
                f"SELECT MAX(mtime) AS m FROM notes WHERE id IN ({ph2})",
                tuple(c),
            ).fetchone()
            last_date = (
                datetime.fromtimestamp(last_touched_row["m"]).strftime("%Y-%m-%d")
                if last_touched_row and last_touched_row["m"] else "n/a"
            )
            print(
                f"  {label} ({len(c)} notes, last touched {last_date}){size_note}"
            )
        return 0
    finally:
        conn.close()


# ---------- subcommand: export-wikilinks ----------


# Obsidian basename: strip directory + .md extension, keep filename intact so
# `[[basename]]` resolves cleanly inside the COPY vault. Obsidian dedupes by
# filename across folders, so collisions are possible but rare in this corpus.
def obsidian_basename(path_str: str) -> str:
    """Filename without .md extension. Used as `[[basename]]` target."""
    return Path(path_str).stem


# Per-entity wrap: substitute the FIRST occurrence of an entity name in `body`
# with `[[Entity Name]]`, skipping if the name already sits inside `[[ ]]`.
# Returns the modified body. Idempotent: re-running on already-wrapped text is
# a no-op because the inside-link guard short-circuits.
def inject_entity_wikilink(body: str, entity_name: str) -> str:
    """Wrap first occurrence of `entity_name` with `[[entity_name]]`.

    Skips if the name is already inside an existing `[[...]]`. Match is
    case-insensitive on word boundary; replacement uses the canonical
    `entity_name` (not the matched casing) so the wikilink target is stable.
    """
    if not entity_name or not entity_name.strip():
        return body
    name = entity_name.strip()
    # Already-wrapped guard: any [[...name...]] occurrence.
    guard = re.compile(
        r"\[\[[^\]]*" + re.escape(name) + r"[^\]]*\]\]",
        re.IGNORECASE,
    )
    if guard.search(body):
        return body
    # Word-boundary match on the bare name.
    pattern = re.compile(r"\b" + re.escape(name) + r"\b", re.IGNORECASE)
    if not pattern.search(body):
        return body
    return pattern.sub(f"[[{name}]]", body, count=1)


def is_skipped_path(rel_path: str) -> bool:
    """Defensive skip-list check against EXPORT_SKIP_SUBPATHS."""
    norm = rel_path.replace("\\", "/")
    for skip in EXPORT_SKIP_SUBPATHS:
        if norm.startswith(skip):
            return True
    return False


def build_export_graph_json() -> dict:
    """Mirror of the live vault's graph.json, scoped to export dirs."""
    return {
        "collapse-filter": False,
        "search": "path:memory OR path:briefings OR path:research",
        "showTags": True,
        "showAttachments": False,
        "hideUnresolved": False,
        "showOrphans": True,
        "collapse-color-groups": False,
        "colorGroups": [
            {"query": "path:memory/people", "color": {"a": 1, "rgb": 14589241}},
            {"query": "path:memory/decisions", "color": {"a": 1, "rgb": 5470719}},
            {"query": "path:memory/learnings", "color": {"a": 1, "rgb": 6986069}},
            {"query": "path:memory/research OR path:research",
             "color": {"a": 1, "rgb": 16763904}},
            {"query": "path:briefings", "color": {"a": 1, "rgb": 14474410}},
            {"query": "file:feedback_", "color": {"a": 1, "rgb": 13724009}},
            {"query": "path:memory/architect_proposals OR path:memory/friction",
             "color": {"a": 1, "rgb": 11500474}},
            {"query": "path:memory/journal", "color": {"a": 1, "rgb": 8421504}},
        ],
        "collapse-display": False,
        "showArrow": True,
        "textFadeMultiplier": 0,
        "nodeSizeMultiplier": 1.4,
        "lineSizeMultiplier": 1,
        "collapse-forces": False,
        "centerStrength": 0.25,
        "repelStrength": 20,
        "linkStrength": 1,
        "linkDistance": 80,
        "scale": 0.068,
        "close": True,
    }


def write_obsidian_config(output_dir: Path, workspace: Path) -> None:
    """Drop .obsidian/{graph,appearance}.json + optional vault-colors snippet.

    Plugins are intentionally NOT copied: this is a read-only export, user can
    install via Obsidian UI if they want extras.
    """
    obs = output_dir / ".obsidian"
    obs.mkdir(parents=True, exist_ok=True)
    (obs / "graph.json").write_text(
        json.dumps(build_export_graph_json(), indent=2),
        encoding="utf-8",
    )
    appearance = {
        "accentColor": "",
        "enabledCssSnippets": ["vault-colors"],
    }
    (obs / "appearance.json").write_text(
        json.dumps(appearance, indent=2),
        encoding="utf-8",
    )
    src_snip = workspace / ".obsidian" / "snippets" / "vault-colors.css"
    if src_snip.exists():
        dst_snip = obs / "snippets" / "vault-colors.css"
        dst_snip.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_snip, dst_snip)


def cmd_export_wikilinks(args) -> int:
    """Emit a wikilink-injected COPY of memory/briefings/research for Obsidian.

    Source files are NEVER touched. Output dir is wiped + recreated on each run
    for idempotency. Performance target: <30s for ~700 notes.
    """
    db_path = args.db.expanduser().resolve()
    workspace = args.workspace.expanduser().resolve()
    output_dir = Path(args.output).expanduser().resolve()
    top_n = max(1, args.top_n)

    # Safety guard: never let `output` point at workspace (would clobber source).
    if output_dir == workspace or workspace in output_dir.parents:
        print(
            f"error: output dir {output_dir} is inside workspace {workspace} "
            f"- refusing to export (would risk overwriting source)",
            file=sys.stderr,
        )
        return 1
    if workspace == output_dir.parent and output_dir.name in EXPORT_DIRS:
        print(
            f"error: output dir name {output_dir.name} collides with a source "
            f"subdir - refusing to export",
            file=sys.stderr,
        )
        return 1

    conn = get_db(db_path)
    try:
        t0 = time.time()
        # Idempotency: wipe + recreate output dir.
        if output_dir.exists():
            shutil.rmtree(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Pre-fetch all notes once. Filter to EXPORT_DIRS only.
        rows = conn.execute(
            "SELECT id, path, title FROM notes ORDER BY path"
        ).fetchall()
        export_rows = []
        for r in rows:
            try:
                rel = Path(r["path"]).resolve().relative_to(workspace)
            except (ValueError, OSError):
                continue
            rel_str = str(rel)
            top = rel_str.split("/", 1)[0] if "/" in rel_str else rel_str
            if top not in EXPORT_DIRS:
                continue
            if is_skipped_path(rel_str):
                continue
            if not rel_str.endswith(".md"):
                continue
            export_rows.append((r["id"], r["path"], rel_str))

        # Pre-build {note_id -> basename} map for `## Related` rendering.
        id_to_basename: dict[int, str] = {}
        for nid, npath, _ in export_rows:
            id_to_basename[nid] = obsidian_basename(npath)
        # Also include neighbours that live outside export dirs (e.g. outputs/)
        # so we can still render their basenames as wikilinks - Obsidian will
        # render them as unresolved which is fine for graph context.
        all_rows = conn.execute("SELECT id, path FROM notes").fetchall()
        for r in all_rows:
            id_to_basename.setdefault(r["id"], obsidian_basename(r["path"]))

        written = 0
        skipped_missing = 0
        for nid, src_path, rel_str in export_rows:
            src = Path(src_path)
            if not src.exists():
                skipped_missing += 1
                continue
            try:
                text = src.read_text(encoding="utf-8", errors="replace")
            except OSError as e:
                print(f"warn: read {src}: {e}", file=sys.stderr)
                continue
            fm, body = parse_frontmatter(text)

            # Top entities (person|company only) by mention_count desc, cap 10.
            ent_rows = conn.execute(
                """
                SELECT e.name, e.kind, nee.mention_count
                FROM note_entity_edges nee
                JOIN entities e ON e.id = nee.entity_id
                WHERE nee.note_id = ? AND e.kind IN ('person', 'company')
                ORDER BY nee.mention_count DESC, e.name
                LIMIT 10
                """,
                (nid,),
            ).fetchall()

            # Inject [[Entity Name]] on first occurrence of each entity.
            # Sort longest-first so "Steve Aylott" wraps before bare "Steve".
            entity_names = sorted(
                {er["name"] for er in ent_rows},
                key=lambda n: (-len(n), n),
            )
            new_body = body
            for ename in entity_names:
                new_body = inject_entity_wikilink(new_body, ename)

            # Top-N related notes by note_note_edges.weight.
            rel_rows = conn.execute(
                """
                SELECT
                    CASE WHEN a_id = ? THEN b_id ELSE a_id END AS other_id,
                    weight
                FROM note_note_edges
                WHERE a_id = ? OR b_id = ?
                ORDER BY weight DESC
                LIMIT ?
                """,
                (nid, nid, nid, top_n),
            ).fetchall()
            related_basenames: list[str] = []
            seen: set[str] = set()
            for rr in rel_rows:
                bn = id_to_basename.get(rr["other_id"])
                if not bn or bn in seen:
                    continue
                seen.add(bn)
                related_basenames.append(bn)

            # Append `## Related` section if we have any neighbours.
            if related_basenames:
                related_block = "\n## Related\n\n" + "\n".join(
                    f"- [[{bn}]]" for bn in related_basenames
                ) + "\n"
                new_body = new_body.rstrip() + "\n" + related_block

            # Rebuild file: original frontmatter (verbatim) + modified body.
            if text.startswith("---\n"):
                fm_end = text.find("\n---\n", 4)
                if fm_end != -1:
                    fm_block = text[: fm_end + 5]
                    out_text = fm_block + new_body
                else:
                    out_text = new_body
            else:
                out_text = new_body

            dst = output_dir / rel_str
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_text(out_text, encoding="utf-8")
            written += 1

        # .obsidian config (graph.json + appearance + snippet).
        write_obsidian_config(output_dir, workspace)

        dt = time.time() - t0
        print(f"export-wikilinks: wrote {written} notes to {output_dir}")
        if skipped_missing:
            print(f"  skipped {skipped_missing} missing source files")
        print(f"  runtime: {dt:.1f}s")
        return 0
    finally:
        conn.close()


# ---------- argparse ----------


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="note_graph.py",
        description="Build and query the note-graph layer over contacts.db. "
                    "Phase 1: deterministic entity-mention graph with optional "
                    "ChromaDB semantic fallback.",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    def add_common(parser):
        parser.add_argument(
            "--db", type=Path, default=DB_PATH_DEFAULT,
            help=f"path to contacts.db (default: {DB_PATH_DEFAULT})",
        )
        parser.add_argument(
            "--workspace", type=Path, default=WORKSPACE_DEFAULT,
            help=f"workspace root (default: {WORKSPACE_DEFAULT})",
        )

    pb = sub.add_parser("backfill", help="Seed entities + index all md notes + compute all edges.")
    add_common(pb)
    pb.add_argument(
        "--limit", type=int, default=None,
        help="Only ingest first N notes (for smoke tests).",
    )
    pb.add_argument(
        "--force", action="store_true",
        help="Override an existing backfill lock.",
    )
    pb.set_defaults(func=cmd_backfill)

    px = sub.add_parser("extract", help="Re-index a single note (incremental).")
    add_common(px)
    px.add_argument("path", help="Absolute path to a .md note file.")
    px.set_defaults(func=cmd_extract)

    pr = sub.add_parser("related", help="Top-N related notes for a target.")
    add_common(pr)
    pr.add_argument("target", help="Filename slug or absolute path.")
    pr.add_argument("--limit", type=int, default=10, help="Max results (default 10).")
    pr.set_defaults(func=cmd_related)

    pe = sub.add_parser("entity", help="All notes mentioning an entity + co-mention frequency.")
    add_common(pe)
    pe.add_argument("name", help="Entity name or alias (case-insensitive).")
    pe.add_argument("--limit", type=int, default=20, help="Max notes + co-entities (default 20).")
    pe.set_defaults(func=cmd_entity)

    pg = sub.add_parser("graph", help="ASCII-rendered 1- or 2-hop subgraph.")
    add_common(pg)
    pg.add_argument("target", help="Filename slug or absolute path.")
    pg.add_argument("--depth", type=int, default=2, choices=[1, 2], help="Hop depth (1 or 2).")
    pg.set_defaults(func=cmd_graph)

    pc = sub.add_parser("clusters", help="Modularity-based clustering over last-N-day notes.")
    add_common(pc)
    pc.add_argument("--days", type=int, default=7, help="Recency window (default 7d).")
    pc.add_argument("--min-notes", type=int, default=3, help="Min cluster size (default 3).")
    pc.add_argument(
        "--min-weight", type=float, default=0.05,
        help="Edge-weight threshold below which edges are ignored (default 0.05).",
    )
    pc.add_argument(
        "--top-labels", type=int, default=4,
        help="Top-N entities used to label each cluster (default 4).",
    )
    pc.add_argument(
        "--max-cluster-size", type=int, default=30,
        help="Soft cap; oversized clusters get an annotation (default 30).",
    )
    pc.set_defaults(func=cmd_clusters)

    pw = sub.add_parser(
        "export-wikilinks",
        help="Emit a wikilink-injected COPY of memory/briefings/research for Obsidian.",
    )
    add_common(pw)
    pw.add_argument(
        "--output", type=Path, default=EXPORT_DEFAULT,
        help=f"output dir (default: {EXPORT_DEFAULT})",
    )
    pw.add_argument(
        "--top-n", type=int, default=3,
        help="Number of related notes per `## Related` section (default 3).",
    )
    pw.set_defaults(func=cmd_export_wikilinks)

    return p


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
