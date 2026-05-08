#!/usr/bin/env python3
"""
Semantic Memory Search - ChromaDB layer over your knowledge base.

Indexes:
  - contacts          - contact DB (contacts, companies, relationships)
  - interactions      - emails/meetings logged in contacts.db
  - memory_files      - CLAUDE.md, MEMORY.md, memory/*.md (feedback rules, project docs)
  - chat_archives     - WhatsApp / Telegram exports
  - briefings         - daily morning briefings (~/Desktop/claude/briefings/*.md)
  - outputs           - everything Claude+Misha produced (~/Desktop/claude/outputs/**/*.md)
  - journal           - daily journal entries (~/Desktop/claude/memory/journal/*.md)
  - knowledge         - atomic learnings + decisions (memory/learnings + memory/decisions)
  - research          - long-form research notes (~/Desktop/claude/research/**/*.md)

Usage:
    python3 memory_search.py index                       # (Re)build all indexes
    python3 memory_search.py index --file <abs_path>     # Surgical single-file upsert
    python3 memory_search.py search "query"              # Search across ALL collections
    python3 memory_search.py search "query" --collection outputs  # Narrow to one collection
    python3 memory_search.py search "query" --top 10     # More results
    python3 memory_search.py wake-up                     # Generate L0+L1 context (~200 tokens)
    python3 memory_search.py stats                       # Index statistics
"""

import hashlib
import sqlite3
import sys
import os
import json
import glob
import time
from pathlib import Path
from datetime import datetime

import chromadb
from chromadb.config import Settings

# Paths - derived from $HOME so this works for any user
HOME = Path(os.path.expanduser("~"))
BASE_DIR = HOME / "Desktop" / "claude"
DB_PATH = BASE_DIR / "data" / "contacts.db"
CHROMA_PATH = BASE_DIR / "data" / "chroma"
LOCK_PATH = CHROMA_PATH / ".index.lock"
LOCK_STALE_AFTER_SEC = 600  # 10 minutes
# Claude Code's per-project memory dir uses a sanitized project-path slug
_PROJECT_SLUG = str(BASE_DIR).replace("/", "-")
MEMORY_DIR = HOME / ".claude" / "projects" / _PROJECT_SLUG / "memory"
CLAUDE_MD = BASE_DIR / "CLAUDE.md"
MEMORY_MD = BASE_DIR / "MEMORY.md"
CHAT_ARCHIVES_DIR = BASE_DIR  # Chat archives might be in various places

# Phase 1 expansion paths
BRIEFINGS_DIR = BASE_DIR / "briefings"
OUTPUTS_DIR = BASE_DIR / "outputs"
JOURNAL_DIR = BASE_DIR / "memory" / "journal"
LEARNINGS_DIR = BASE_DIR / "memory" / "learnings"
DECISIONS_DIR = BASE_DIR / "memory" / "decisions"
RESEARCH_DIR = BASE_DIR / "research"
FRICTION_DIR = BASE_DIR / "memory" / "friction"

# Collections
COLL_CONTACTS = "contacts"
COLL_MEMORY = "memory_files"
COLL_INTERACTIONS = "interactions"
COLL_CHATS = "chat_archives"
COLL_BRIEFINGS = "briefings"
COLL_OUTPUTS = "outputs"
COLL_JOURNAL = "journal"
COLL_KNOWLEDGE = "knowledge"
COLL_RESEARCH = "research"

# All collections searched by default
ALL_COLLECTIONS = [
    COLL_CONTACTS, COLL_MEMORY, COLL_INTERACTIONS, COLL_CHATS,
    COLL_BRIEFINGS, COLL_OUTPUTS, COLL_JOURNAL, COLL_KNOWLEDGE, COLL_RESEARCH,
]


def get_chroma():
    """Get ChromaDB client with persistent storage."""
    return chromadb.PersistentClient(
        path=str(CHROMA_PATH),
        settings=Settings(anonymized_telemetry=False)
    )


def chunk_text(text, chunk_size=800, overlap=100):
    """Split text into overlapping chunks."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        if chunk.strip():
            chunks.append(chunk.strip())
        start += chunk_size - overlap
    return chunks


def acquire_lock(force: bool = False) -> bool:
    """Try to acquire the index lock. Returns True on success.

    Lock semantics:
      - File at LOCK_PATH (JSON: {pid, started_at}). Exclusive create.
      - If lock exists and is < LOCK_STALE_AFTER_SEC old: refuse.
      - If lock exists and is older than that: assume stale, overwrite.
      - `force=True` always overwrites.
    """
    CHROMA_PATH.mkdir(parents=True, exist_ok=True)
    if LOCK_PATH.exists() and not force:
        try:
            data = json.loads(LOCK_PATH.read_text())
            started = data.get("started_at", 0)
            age = time.time() - started
        except Exception:
            age = 0
        if age < LOCK_STALE_AFTER_SEC:
            print(
                f"error: index already running (lock at {LOCK_PATH}, age {int(age)}s). "
                f"Use --force to override.",
                file=sys.stderr,
            )
            return False
        else:
            print(
                f"warn: stale lock at {LOCK_PATH} (age {int(age)}s) - overwriting",
                file=sys.stderr,
            )
    payload = json.dumps({"pid": os.getpid(), "started_at": time.time()})
    try:
        # x mode = exclusive create. If race lost, fall through to overwrite.
        with open(LOCK_PATH, "w") as f:
            f.write(payload)
    except Exception as e:
        print(f"error: could not write lock: {e}", file=sys.stderr)
        return False
    return True


def release_lock() -> None:
    """Best-effort lock removal. Quiet on missing file."""
    try:
        if LOCK_PATH.exists():
            os.remove(LOCK_PATH)
    except Exception as e:
        print(f"warn: could not remove lock: {e}", file=sys.stderr)


def index_contacts(client):
    """Index all contacts, companies, and relationships from SQLite."""
    coll = client.get_or_create_collection(
        name=COLL_CONTACTS,
        metadata={"hnsw:space": "cosine"}
    )
    # Clear existing
    try:
        all_ids = coll.get()['ids']
        if all_ids:
            coll.delete(ids=all_ids)
    except:
        pass

    db = sqlite3.connect(str(DB_PATH))
    db.row_factory = sqlite3.Row

    docs = []
    metas = []
    ids = []

    # Contacts
    contacts = db.execute("""
        SELECT c.*, GROUP_CONCAT(DISTINCT t.tag) as tags
        FROM contacts c
        LEFT JOIN tags t ON t.contact_id = c.id
        GROUP BY c.id
    """).fetchall()

    for c in contacts:
        # Build rich text document for each contact
        parts = [f"Contact: {c['name']}"]
        if c['full_name']: parts.append(f"Full name: {c['full_name']}")
        if c['email']: parts.append(f"Email: {c['email']}")
        if c['email2']: parts.append(f"Email2: {c['email2']}")
        if c['phone']: parts.append(f"Phone: {c['phone']}")
        if c['company']: parts.append(f"Company: {c['company']}")
        if c['role']: parts.append(f"Role: {c['role']}")
        if c['location']: parts.append(f"Location: {c['location']}")
        if c['category']: parts.append(f"Category: {c['category']}")
        if c['notes']: parts.append(f"Notes: {c['notes']}")
        if c['tags']: parts.append(f"Tags: {c['tags']}")
        if c['status']: parts.append(f"Status: {c['status']}")

        # Add relationships
        rels = db.execute("""
            SELECT c2.name, r.type, r.context
            FROM relationships r
            JOIN contacts c2 ON c2.id = CASE WHEN r.from_id = ? THEN r.to_id ELSE r.from_id END
            WHERE r.from_id = ? OR r.to_id = ?
        """, (c['id'], c['id'], c['id'])).fetchall()

        if rels:
            rel_text = "; ".join(f"{r['name']} ({r['type']}: {r['context'] or ''})" for r in rels)
            parts.append(f"Relationships: {rel_text}")

        doc = "\n".join(parts)
        docs.append(doc)
        metas.append({
            "source": "contacts_db",
            "type": "contact",
            "name": c['name'],
            "category": c['category'] or "unknown",
            "status": c['status'] or "active",
            "company": c['company'] or ""
        })
        ids.append(f"contact_{c['id']}")

    # Companies
    companies = db.execute("SELECT * FROM companies").fetchall()
    for co in companies:
        parts = [f"Company: {co['name']}"]
        if co['type']: parts.append(f"Type: {co['type']}")
        if co['country']: parts.append(f"Country: {co['country']}")
        if co['city']: parts.append(f"City: {co['city']}")
        if co['address']: parts.append(f"Address: {co['address']}")
        if co['notes']: parts.append(f"Notes: {co['notes']}")

        doc = "\n".join(parts)
        docs.append(doc)
        metas.append({
            "source": "contacts_db",
            "type": "company",
            "name": co['name'],
            "category": co['type'] or "unknown",
            "status": "active",
            "company": co['name']
        })
        ids.append(f"company_{co['id']}")

    if docs:
        coll.upsert(documents=docs, metadatas=metas, ids=ids)

    db.close()
    return len(docs)


def _memory_md_chunks(md_file: Path):
    """Yield (id, doc, meta) tuples for a single memory_files .md file.

    Used by both the bulk indexer and the surgical single-file path so that
    IDs/metadata stay in sync.
    """
    text = md_file.read_text()
    if len(text) < 50:
        return
    chunks = chunk_text(text, 800, 100)
    fname = md_file.name
    # Detect friction by parent dir (memory/friction/) since file names like
    # `2026-05-07-blocker-foo.md` don't carry "friction" as a substring.
    parent_name = md_file.parent.name if md_file.parent else ""
    for i, chunk in enumerate(chunks):
        cat = "general"
        if parent_name == "friction" or "friction" in fname: cat = "friction"
        elif "feedback" in fname: cat = "feedback"
        elif "project" in fname: cat = "project"
        elif "travel" in fname: cat = "travel"
        elif "shopify" in fname: cat = "shopify"
        elif "user" in fname: cat = "user"
        elif "reference" in fname: cat = "reference"
        elif "flight" in fname: cat = "travel"
        meta = {"source": fname, "type": "memory", "chunk": i, "category": cat}
        yield (f"mem_{fname}_{i}", chunk, meta)


def _claude_md_chunks(md_file: Path):
    """Yield (id, doc, meta) tuples for CLAUDE.md (and MEMORY.md, same scheme)."""
    text = md_file.read_text()
    chunks = chunk_text(text, 1200, 200)
    # Use a distinct id prefix per file so CLAUDE.md and MEMORY.md don't collide.
    if md_file.name == "CLAUDE.md":
        prefix = "claude_md"
    elif md_file.name == "MEMORY.md":
        prefix = "memory_md"
    else:
        prefix = f"mem_root_{md_file.stem.lower()}"
    for i, chunk in enumerate(chunks):
        meta = {"source": md_file.name, "type": "project_context", "chunk": i, "category": "core"}
        yield (f"{prefix}_{i}", chunk, meta)


def index_memory_files(client):
    """Index all memory markdown files."""
    coll = client.get_or_create_collection(
        name=COLL_MEMORY,
        metadata={"hnsw:space": "cosine"}
    )
    # Clear
    try:
        all_ids = coll.get()['ids']
        if all_ids:
            coll.delete(ids=all_ids)
    except:
        pass

    docs = []
    metas = []
    ids = []

    # Index CLAUDE.md
    if CLAUDE_MD.exists():
        for cid, chunk, meta in _claude_md_chunks(CLAUDE_MD):
            docs.append(chunk)
            metas.append(meta)
            ids.append(cid)

    # Index memory/*.md
    for md_file in MEMORY_DIR.glob("*.md"):
        for cid, chunk, meta in _memory_md_chunks(md_file):
            docs.append(chunk)
            metas.append(meta)
            ids.append(cid)

    # Index ~/Desktop/claude/memory/friction/*.md (friction events get folded
    # into memory_files collection with category=friction so they cross-search
    # alongside feedback rules).
    if FRICTION_DIR.exists():
        for md_file in FRICTION_DIR.glob("*.md"):
            if md_file.name.startswith("_") and md_file.name != "_PROTOCOL.md":
                continue
            for cid, chunk, meta in _memory_md_chunks(md_file):
                docs.append(chunk)
                metas.append(meta)
                ids.append(cid)

    if docs:
        coll.upsert(documents=docs, metadatas=metas, ids=ids)

    return len(docs)


def index_interactions(client):
    """Index all email/meeting interactions."""
    coll = client.get_or_create_collection(
        name=COLL_INTERACTIONS,
        metadata={"hnsw:space": "cosine"}
    )
    try:
        all_ids = coll.get()['ids']
        if all_ids:
            coll.delete(ids=all_ids)
    except:
        pass

    db = sqlite3.connect(str(DB_PATH))
    db.row_factory = sqlite3.Row

    interactions = db.execute("""
        SELECT i.*, c.name as contact_name, c.company, c.category
        FROM interactions i
        JOIN contacts c ON c.id = i.contact_id
        ORDER BY i.date DESC
    """).fetchall()

    docs = []
    metas = []
    ids = []

    for inter in interactions:
        parts = [f"Interaction with {inter['contact_name']}"]
        if inter['company']: parts.append(f"Company: {inter['company']}")
        parts.append(f"Date: {inter['date']}")
        parts.append(f"Type: {inter['type']}")
        if inter['direction']: parts.append(f"Direction: {inter['direction']}")
        if inter['subject']: parts.append(f"Subject: {inter['subject']}")
        if inter['summary']: parts.append(f"Summary: {inter['summary']}")

        doc = "\n".join(parts)
        docs.append(doc)
        metas.append({
            "source": inter['source'] or "unknown",
            "type": "interaction",
            "contact": inter['contact_name'],
            "date": inter['date'],
            "category": inter['category'] or "unknown"
        })
        ids.append(f"interaction_{inter['id']}")

    if docs:
        coll.upsert(documents=docs, metadatas=metas, ids=ids)

    db.close()
    return len(docs)


def index_chat_archives(client):
    """Index WhatsApp/Telegram chat exports."""
    coll = client.get_or_create_collection(
        name=COLL_CHATS,
        metadata={"hnsw:space": "cosine"}
    )
    try:
        all_ids = coll.get()['ids']
        if all_ids:
            coll.delete(ids=all_ids)
    except:
        pass

    # Find chat archive files. Restrict to text-like extensions so that image
    # attachments named "WhatsApp Image YYYY-MM-DD at HH.MM.SS.jpeg" (which the
    # old globs picked up) are not read as text and chunked into garbage.
    TEXT_EXTS = {".txt", ".json", ".csv", ".md", ".html", ".htm"}
    chat_files: set[Path] = set()
    for pattern in ["**/*WhatsApp*", "**/*telegram*", "**/*chat*export*"]:
        for f in BASE_DIR.glob(pattern):
            if f.is_file() and f.suffix.lower() in TEXT_EXTS:
                chat_files.add(f.resolve())

    # Also check common locations
    for extra_dir in [Path.home() / "Downloads", BASE_DIR / "data"]:
        if extra_dir.exists():
            for pattern in ["*WhatsApp*.txt", "*telegram*.txt", "*chat*.json"]:
                for f in extra_dir.glob(pattern):
                    if f.is_file():
                        chat_files.add(f.resolve())

    docs = []
    metas = []
    ids = []

    for chat_file in sorted(chat_files):
        if chat_file.stat().st_size > 10_000_000:  # Skip files > 10MB
            continue
        try:
            text = chat_file.read_text(errors='replace')
            chunks = chunk_text(text, 1000, 150)
            # Collision-free ID: hash of absolute path + chunk index. Two files
            # with the same stem in different directories no longer collide.
            path_hash = hashlib.sha1(str(chat_file).encode()).hexdigest()[:12]
            for i, chunk in enumerate(chunks):
                docs.append(chunk)
                metas.append({
                    "source": chat_file.name,
                    "path": str(chat_file.relative_to(BASE_DIR)) if BASE_DIR in chat_file.parents else str(chat_file),
                    "type": "chat_archive",
                    "chunk": i,
                    "category": "chat"
                })
                ids.append(f"chat_{path_hash}_{i}")
        except Exception as e:
            print(f"  Skipped {chat_file.name}: {e}")

    if docs:
        coll.upsert(documents=docs, metadatas=metas, ids=ids)

    return len(docs)


# ---------------------------------------------------------------------------
# Phase 1 expansion: briefings, outputs, journal, knowledge, research
# ---------------------------------------------------------------------------


def _extract_date_from_filename(fname):
    """Pull a YYYY-MM-DD prefix out of a filename if present, else ''."""
    import re
    m = re.search(r'(\d{4}-\d{2}-\d{2})', fname)
    return m.group(1) if m else ""


def _stem_safe_for(md_file: Path) -> str:
    """Compute the same path-stem suffix the bulk indexer uses for IDs.

    Mirrors `_index_md_dir`: relative-to-BASE_DIR path with / and spaces
    replaced. Single-file upsert path uses this so IDs converge.
    """
    rel = md_file.relative_to(BASE_DIR) if BASE_DIR in md_file.parents else md_file
    return str(rel).replace("/", "_").replace(" ", "_")


def _md_dir_chunks(md_file: Path, *, build_meta, id_prefix,
                   chunk_size: int, overlap: int, min_size: int = 50):
    """Yield (id, doc, meta) tuples for a single .md file using the shared
    chunk/meta scheme. Mirrors what `_index_md_dir` writes per-file.
    """
    try:
        text = md_file.read_text(errors='replace')
    except Exception as e:
        print(f"  Skipped {md_file.name}: {e}")
        return
    if len(text) < min_size:
        return
    chunks = chunk_text(text, chunk_size, overlap)
    meta_base = build_meta(md_file)
    stem_safe = _stem_safe_for(md_file)
    for i, chunk in enumerate(chunks):
        meta = dict(meta_base)
        meta["chunk"] = i
        yield (f"{id_prefix}_{stem_safe}_{i}", chunk, meta)


def _index_md_dir(client, coll_name, files, *, build_meta, id_prefix,
                  chunk_size=1200, overlap=150, min_size=50):
    """Generic helper: index a list of .md Path objects into `coll_name`.

    `build_meta(path)` returns the dict of metadata for each file.
    `id_prefix` keeps document IDs unique across collections.
    Long files are chunked with chunk_text(); chunk index lives in metadata.
    """
    coll = client.get_or_create_collection(
        name=coll_name,
        metadata={"hnsw:space": "cosine"}
    )
    # Clear existing
    try:
        all_ids = coll.get()['ids']
        if all_ids:
            coll.delete(ids=all_ids)
    except Exception:
        pass

    docs = []
    metas = []
    ids = []

    for md_file in files:
        for cid, chunk, meta in _md_dir_chunks(
            md_file,
            build_meta=build_meta,
            id_prefix=id_prefix,
            chunk_size=chunk_size,
            overlap=overlap,
            min_size=min_size,
        ):
            docs.append(chunk)
            metas.append(meta)
            ids.append(cid)

    if docs:
        coll.upsert(documents=docs, metadatas=metas, ids=ids)

    return len(docs)


# Per-collection meta builders + chunk params, exposed so the surgical
# single-file path can reuse them.

def _briefings_meta(p: Path):
    return {
        "source": p.name,
        "type": "briefing",
        "category": "briefing",
        "date": _extract_date_from_filename(p.name),
    }


def _outputs_meta(p: Path):
    rel = p.relative_to(OUTPUTS_DIR)
    parts = rel.parts
    category = parts[0] if len(parts) > 1 else "general"
    return {
        "source": str(rel),
        "type": "output",
        "category": category,
        "date": _extract_date_from_filename(p.name),
    }


def _journal_meta(p: Path):
    return {
        "source": p.name,
        "type": "journal",
        "category": "journal",
        "date": _extract_date_from_filename(p.name),
    }


def _knowledge_meta_for(p: Path):
    """Knowledge collection covers learnings + decisions; subtype derived from path."""
    if LEARNINGS_DIR in p.parents or p.parent == LEARNINGS_DIR:
        subtype = "learning"
    elif DECISIONS_DIR in p.parents or p.parent == DECISIONS_DIR:
        subtype = "decision"
    else:
        subtype = "knowledge"
    return {
        "source": p.name,
        "type": "knowledge",
        "subtype": subtype,
        "category": subtype,
        "date": _extract_date_from_filename(p.name),
    }


def _research_meta(p: Path):
    rel = p.relative_to(RESEARCH_DIR)
    parts = rel.parts
    category = parts[0] if len(parts) > 1 else "general"
    return {
        "source": str(rel),
        "type": "research",
        "category": category,
        "date": _extract_date_from_filename(p.name),
    }


# Chunk params per collection (must match bulk indexer kwargs).
_COLL_PARAMS = {
    COLL_BRIEFINGS: {"id_prefix": "brief", "chunk_size": 1200, "overlap": 150,
                     "build_meta": _briefings_meta},
    COLL_OUTPUTS: {"id_prefix": "out", "chunk_size": 1200, "overlap": 150,
                   "build_meta": _outputs_meta},
    COLL_JOURNAL: {"id_prefix": "journal", "chunk_size": 1000, "overlap": 120,
                   "build_meta": _journal_meta},
    COLL_KNOWLEDGE: {"id_prefix": "know", "chunk_size": 900, "overlap": 120,
                     "build_meta": _knowledge_meta_for},
    COLL_RESEARCH: {"id_prefix": "research", "chunk_size": 1200, "overlap": 200,
                    "build_meta": _research_meta},
}


def index_briefings(client):
    """Index daily briefings from ~/Desktop/claude/briefings/*.md."""
    if not BRIEFINGS_DIR.exists():
        return 0
    files = sorted(BRIEFINGS_DIR.glob("*.md"))
    return _index_md_dir(
        client, COLL_BRIEFINGS, files,
        **_COLL_PARAMS[COLL_BRIEFINGS],
    )


def index_outputs(client):
    """Index everything we produced - ~/Desktop/claude/outputs/**/*.md (recursive).

    Subdirectory becomes `category` so search can filter by topic.
    """
    if not OUTPUTS_DIR.exists():
        return 0
    files = sorted(OUTPUTS_DIR.rglob("*.md"))
    return _index_md_dir(
        client, COLL_OUTPUTS, files,
        **_COLL_PARAMS[COLL_OUTPUTS],
    )


def index_journal(client):
    """Index daily journal entries from ~/Desktop/claude/memory/journal/*.md."""
    if not JOURNAL_DIR.exists():
        return 0
    files = sorted(JOURNAL_DIR.glob("*.md"))
    return _index_md_dir(
        client, COLL_JOURNAL, files,
        **_COLL_PARAMS[COLL_JOURNAL],
    )


def index_knowledge(client):
    """Index atomic learnings + decisions into one `knowledge` collection."""
    files = []
    if LEARNINGS_DIR.exists():
        files.extend(sorted(LEARNINGS_DIR.glob("*.md")))
    if DECISIONS_DIR.exists():
        files.extend(sorted(DECISIONS_DIR.glob("*.md")))
    if not files:
        return 0
    return _index_md_dir(
        client, COLL_KNOWLEDGE, files,
        **_COLL_PARAMS[COLL_KNOWLEDGE],
    )


def index_research(client):
    """Index long-form research from ~/Desktop/claude/research/**/*.md (recursive)."""
    if not RESEARCH_DIR.exists():
        return 0
    files = sorted(RESEARCH_DIR.rglob("*.md"))
    return _index_md_dir(
        client, COLL_RESEARCH, files,
        **_COLL_PARAMS[COLL_RESEARCH],
    )


# ---------------------------------------------------------------------------
# Surgical single-file upsert
# ---------------------------------------------------------------------------


def _detect_collection_for(path: Path) -> str | None:
    """Map a file path to the collection it belongs to. None if unsupported."""
    try:
        path = path.resolve()
    except Exception:
        return None
    parents = list(path.parents)

    # Specific files first
    if path == CLAUDE_MD.resolve() or path == MEMORY_MD.resolve():
        return COLL_MEMORY

    if BRIEFINGS_DIR in parents and path.suffix == ".md":
        return COLL_BRIEFINGS
    if OUTPUTS_DIR in parents and path.suffix == ".md":
        return COLL_OUTPUTS
    if JOURNAL_DIR in parents and path.suffix == ".md":
        return COLL_JOURNAL
    if (LEARNINGS_DIR in parents or DECISIONS_DIR in parents) and path.suffix == ".md":
        return COLL_KNOWLEDGE
    if RESEARCH_DIR in parents and path.suffix == ".md":
        return COLL_RESEARCH
    if FRICTION_DIR in parents and path.suffix == ".md":
        # Friction events live in memory_files collection with category=friction.
        # Per spec: keep changes minimal, don't add a new collection.
        return COLL_MEMORY
    if MEMORY_DIR in parents and path.suffix == ".md":
        return COLL_MEMORY
    return None


def index_single_file(client, file_path: Path) -> tuple[str | None, int]:
    """Upsert a single file into its detected collection. Returns (coll_name, n_docs).

    On unknown file type returns (None, 0) and prints a warning.
    """
    if not file_path.exists():
        print(f"error: file not found: {file_path}", file=sys.stderr)
        return (None, 0)
    coll_name = _detect_collection_for(file_path)
    if coll_name is None:
        print(
            f"warn: no collection mapping for {file_path}; skipping",
            file=sys.stderr,
        )
        return (None, 0)

    coll = client.get_or_create_collection(
        name=coll_name,
        metadata={"hnsw:space": "cosine"},
    )

    docs: list[str] = []
    metas: list[dict] = []
    ids: list[str] = []

    if coll_name == COLL_MEMORY:
        if file_path.name in ("CLAUDE.md", "MEMORY.md"):
            for cid, chunk, meta in _claude_md_chunks(file_path):
                ids.append(cid); docs.append(chunk); metas.append(meta)
        else:
            for cid, chunk, meta in _memory_md_chunks(file_path):
                ids.append(cid); docs.append(chunk); metas.append(meta)
    else:
        params = _COLL_PARAMS[coll_name]
        for cid, chunk, meta in _md_dir_chunks(
            file_path,
            build_meta=params["build_meta"],
            id_prefix=params["id_prefix"],
            chunk_size=params["chunk_size"],
            overlap=params["overlap"],
        ):
            ids.append(cid); docs.append(chunk); metas.append(meta)

    if not docs:
        print(f"warn: no chunks produced for {file_path} (too short?)", file=sys.stderr)
        return (coll_name, 0)

    # Optional: clear any prior chunks of this file that no longer fit
    # (e.g., file shrank). Cheap because we filter by source metadata.
    try:
        # Match by source metadata when available; for memory_files use filename.
        source_match = file_path.name if coll_name == COLL_MEMORY else None
        if source_match is None:
            # outputs / research use rel path as source
            try:
                if coll_name == COLL_OUTPUTS:
                    source_match = str(file_path.resolve().relative_to(OUTPUTS_DIR.resolve()))
                elif coll_name == COLL_RESEARCH:
                    source_match = str(file_path.resolve().relative_to(RESEARCH_DIR.resolve()))
                else:
                    source_match = file_path.name
            except Exception:
                source_match = file_path.name
        prior = coll.get(where={"source": source_match})
        prior_ids = set(prior.get("ids") or [])
        new_ids = set(ids)
        stale = list(prior_ids - new_ids)
        if stale:
            coll.delete(ids=stale)
    except Exception:
        # If `where` filter unsupported or anything else, skip cleanup.
        pass

    coll.upsert(ids=ids, documents=docs, metadatas=metas)
    return (coll_name, len(docs))


def index_all():
    """Build all indexes."""
    client = get_chroma()
    print("Indexing contacts...")
    n_contacts = index_contacts(client)
    print(f"  {n_contacts} contact documents indexed")

    print("Indexing memory files...")
    n_memory = index_memory_files(client)
    print(f"  {n_memory} memory chunks indexed")

    print("Indexing interactions...")
    n_interactions = index_interactions(client)
    print(f"  {n_interactions} interaction documents indexed")

    print("Indexing chat archives...")
    n_chats = index_chat_archives(client)
    print(f"  {n_chats} chat chunks indexed")

    print("Indexing briefings...")
    n_briefings = index_briefings(client)
    print(f"  {n_briefings} briefing chunks indexed")

    print("Indexing outputs...")
    n_outputs = index_outputs(client)
    print(f"  {n_outputs} output chunks indexed")

    print("Indexing journal...")
    n_journal = index_journal(client)
    print(f"  {n_journal} journal chunks indexed")

    print("Indexing knowledge (learnings + decisions)...")
    n_knowledge = index_knowledge(client)
    print(f"  {n_knowledge} knowledge chunks indexed")

    print("Indexing research...")
    n_research = index_research(client)
    print(f"  {n_research} research chunks indexed")

    total = (n_contacts + n_memory + n_interactions + n_chats
             + n_briefings + n_outputs + n_journal + n_knowledge + n_research)
    print(f"\nTotal: {total} documents indexed in ChromaDB at {CHROMA_PATH}")
    return total


def search(query, collection=None, top_k=5):
    """Search across all or specific collections."""
    client = get_chroma()
    results = []

    collections_to_search = [collection] if collection else ALL_COLLECTIONS

    for coll_name in collections_to_search:
        try:
            coll = client.get_collection(coll_name)
            if coll.count() == 0:
                continue

            res = coll.query(
                query_texts=[query],
                n_results=min(top_k, coll.count())
            )

            for i in range(len(res['ids'][0])):
                results.append({
                    'collection': coll_name,
                    'id': res['ids'][0][i],
                    'document': res['documents'][0][i],
                    'metadata': res['metadatas'][0][i],
                    'distance': res['distances'][0][i] if res.get('distances') else 0
                })
        except Exception as e:
            pass  # Collection might not exist yet

    # Sort by distance (lower = more relevant)
    results.sort(key=lambda x: x['distance'])
    return results[:top_k]


def wake_up():
    """Generate minimal L0+L1 context for session start (~200 tokens).

    L0 identity is loaded from ~/Desktop/claude/memory/wakeup_l0.txt if it
    exists (a 2-5 line identity seed describing the user). If missing,
    falls back to a short generic placeholder.
    """
    # L0: Identity - read from wakeup_l0.txt template if present
    l0_path = BASE_DIR / "memory" / "wakeup_l0.txt"
    if l0_path.exists():
        l0 = l0_path.read_text().strip()
    else:
        l0 = "(No L0 identity configured - see memory/wakeup_l0.txt)"

    # L1: Top importance items (from contacts DB)
    db = sqlite3.connect(str(DB_PATH))
    db.row_factory = sqlite3.Row

    # Recent interactions
    recent = db.execute("""
        SELECT c.name, c.company, i.date, i.summary
        FROM interactions i
        JOIN contacts c ON c.id = i.contact_id
        ORDER BY i.date DESC LIMIT 5
    """).fetchall()

    # Active projects
    projects = db.execute("SELECT name, status FROM projects WHERE status='active'").fetchall()

    # Stale contacts (>14 days) - exclude personal, team, events (focus on
    # external business contacts). "Self" rows should be tagged category='self'
    # in the DB so they're automatically excluded.
    stale = db.execute("""
        SELECT name, company,
            CAST(julianday('now') - julianday(COALESCE(last_interaction, created_at)) AS INTEGER) as days
        FROM contacts
        WHERE status = 'active'
            AND category NOT IN ('personal', 'events', 'team', 'self')
            AND last_interaction IS NOT NULL
            AND julianday('now') - julianday(last_interaction) > 14
        ORDER BY days DESC LIMIT 5
    """).fetchall()

    db.close()

    l1_parts = ["\nRecent:"]
    for r in recent:
        l1_parts.append(f"- {r['date']}: {r['name']} ({r['company'] or '?'}) - {r['summary']}")

    l1_parts.append("\nActive projects: " + ", ".join(p['name'] for p in projects))

    if stale:
        l1_parts.append("\nStale (>14d): " + ", ".join(f"{s['name']}({s['days']}d)" for s in stale))

    # L1+: latest knowledge (decisions/learnings) and journal - file-system
    # backed, no Chroma roundtrip. Token-cheap: just titles, max 3 each.
    def _latest(dir_path, n=3):
        if not dir_path.exists():
            return []
        # Sort by mtime DESC so most recently touched bubbles up regardless
        # of whether the filename is date-prefixed.
        files = sorted(dir_path.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
        return files[:n]

    know_titles = []
    for d, label in [(DECISIONS_DIR, "decision"), (LEARNINGS_DIR, "learning")]:
        for p in _latest(d, 2):
            know_titles.append(f"{label}:{p.stem}")
    if know_titles:
        l1_parts.append("\nKnowledge: " + ", ".join(know_titles))

    journal_files = _latest(JOURNAL_DIR, 3)
    if journal_files:
        l1_parts.append("\nJournal: " + ", ".join(p.stem for p in journal_files))

    return l0 + "\n".join(l1_parts)


def stats():
    """Show index statistics."""
    client = get_chroma()
    colls = client.list_collections()
    total = 0
    for c in colls:
        count = c.count()
        total += count
        print(f"  {c.name}: {count} documents")
    print(f"  Total: {total} documents")
    print(f"  Storage: {CHROMA_PATH}")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return

    cmd = sys.argv[1]

    if cmd == 'index':
        # Parse flags: --file <path>, --force, --collection <name>
        file_arg: str | None = None
        force = False
        collection_arg: str | None = None
        argv = sys.argv[2:]
        i = 0
        while i < len(argv):
            a = argv[i]
            if a == "--file" and i + 1 < len(argv):
                file_arg = argv[i + 1]
                i += 2
            elif a == "--force":
                force = True
                i += 1
            elif a == "--collection" and i + 1 < len(argv):
                collection_arg = argv[i + 1]
                i += 2
            else:
                i += 1

        if file_arg:
            # Surgical path - no lock (single-doc upsert is fast and cheap)
            client = get_chroma()
            path = Path(file_arg).expanduser().resolve()
            coll_name, n = index_single_file(client, path)
            if coll_name and n > 0:
                print(f"upserted: {coll_name}/{path.name} ({n} doc{'s' if n != 1 else ''})")
                sys.exit(0)
            elif coll_name and n == 0:
                print(f"upserted: {coll_name}/{path.name} (0 docs - file too small or empty)")
                sys.exit(0)
            else:
                sys.exit(1)
        else:
            # Full reindex - take the lock
            if not acquire_lock(force=force):
                sys.exit(2)
            try:
                index_all()
            finally:
                release_lock()

    elif cmd == 'search':
        if len(sys.argv) < 3:
            print("Usage: search 'query' [--collection name] [--top N]")
            return
        query = sys.argv[2]
        collection = None
        top_k = 5
        for i, arg in enumerate(sys.argv[3:], 3):
            if arg == '--collection' and i + 1 < len(sys.argv):
                collection = sys.argv[i + 1]
            elif arg == '--top' and i + 1 < len(sys.argv):
                top_k = int(sys.argv[i + 1])

        results = search(query, collection, top_k)
        if not results:
            print("No results found. Run 'index' first?")
            return

        for i, r in enumerate(results, 1):
            print(f"\n--- [{i}] {r['collection']} (distance: {r['distance']:.3f}) ---")
            meta = r['metadata']
            if meta.get('name'):
                print(f"  Name: {meta['name']}")
            if meta.get('source'):
                print(f"  Source: {meta['source']}")
            if meta.get('date'):
                print(f"  Date: {meta['date']}")
            # Truncate long documents
            doc = r['document']
            if len(doc) > 300:
                doc = doc[:300] + "..."
            print(f"  {doc}")

    elif cmd == 'wake-up':
        print(wake_up())

    elif cmd == 'stats':
        stats()

    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)


if __name__ == '__main__':
    main()
