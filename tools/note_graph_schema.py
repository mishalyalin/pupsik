#!/usr/bin/env python3
"""
note_graph_schema.py - Idempotent migration for the connection-aware memory graph.

Phase 1 of the note-graph layer. Adds 4 SQLite tables to contacts.db:
  entities          - superset of contacts + companies + projects + topical tags
  notes             - every md file in memory/, research/, outputs/, briefings/
  note_entity_edges - graph edges from notes to entities
  note_note_edges   - graph edges between notes (undirected, a_id < b_id)

Re-running is safe: every CREATE uses IF NOT EXISTS. No data is touched on
existing tables (contacts, interactions, companies, projects, relationships,
tags, contact_companies, project_contacts).

Usage:
    python3 note_graph_schema.py                  # default DB path
    python3 note_graph_schema.py --db /tmp/x.db   # override
"""

import argparse
import sqlite3
import sys
from pathlib import Path

DB_PATH_DEFAULT = Path(__file__).parent.parent / "data" / "contacts.db"

EXPECTED_TABLES = ("entities", "notes", "note_entity_edges", "note_note_edges")

SCHEMA = """
-- Entities: superset of contacts + companies + projects + topical tags
CREATE TABLE IF NOT EXISTS entities (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    kind          TEXT NOT NULL,
    name          TEXT NOT NULL,
    aliases       TEXT,
    contact_id    INTEGER REFERENCES contacts(id) ON DELETE SET NULL,
    company_id    INTEGER REFERENCES companies(id) ON DELETE SET NULL,
    project_id    INTEGER REFERENCES projects(id) ON DELETE SET NULL,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(kind, name)
);
CREATE INDEX IF NOT EXISTS idx_entities_kind ON entities(kind);
CREATE INDEX IF NOT EXISTS idx_entities_name ON entities(name COLLATE NOCASE);

-- Notes: every md file in memory/, research/, outputs/, briefings/
CREATE TABLE IF NOT EXISTS notes (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    path          TEXT NOT NULL UNIQUE,
    title         TEXT,
    type          TEXT,
    tags          TEXT,
    mtime         REAL,
    indexed_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_notes_type ON notes(type);
CREATE INDEX IF NOT EXISTS idx_notes_mtime ON notes(mtime);

-- The graph: edges from notes to entities
CREATE TABLE IF NOT EXISTS note_entity_edges (
    note_id       INTEGER NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
    entity_id     INTEGER NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    mention_count INTEGER NOT NULL DEFAULT 1,
    source        TEXT,
    confidence    REAL DEFAULT 1.0,
    PRIMARY KEY (note_id, entity_id)
);
CREATE INDEX IF NOT EXISTS idx_nee_entity ON note_entity_edges(entity_id);

CREATE TABLE IF NOT EXISTS note_note_edges (
    a_id          INTEGER NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
    b_id          INTEGER NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
    shared_count  INTEGER NOT NULL,
    shared_kinds  TEXT,
    weight        REAL,
    computed_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (a_id, b_id),
    CHECK (a_id < b_id)
);
CREATE INDEX IF NOT EXISTS idx_nne_weight ON note_note_edges(weight DESC);
"""


def list_tables(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    return {r[0] for r in rows}


def migrate(db_path: Path) -> int:
    if not db_path.exists():
        print(f"ERROR: database not found at {db_path}", file=sys.stderr)
        return 2

    try:
        conn = sqlite3.connect(str(db_path))
        # Foreign keys: enable so REFERENCES clauses are enforced going forward.
        conn.execute("PRAGMA foreign_keys = ON")

        before = list_tables(conn)
        conn.executescript(SCHEMA)
        conn.commit()
        after = list_tables(conn)
    except sqlite3.Error as e:
        print(f"ERROR: sqlite failure: {e}", file=sys.stderr)
        return 3
    finally:
        try:
            conn.close()
        except Exception:
            pass

    missing = [t for t in EXPECTED_TABLES if t not in after]
    if missing:
        print(f"ERROR: tables missing after migration: {missing}", file=sys.stderr)
        return 4

    created = [t for t in EXPECTED_TABLES if t not in before]
    existed = [t for t in EXPECTED_TABLES if t in before]

    print(f"DB: {db_path}")
    print(f"Created (new):       {created if created else '(none)'}")
    print(f"Already existed:     {existed if existed else '(none)'}")
    print(f"All 4 tables verified present: {sorted(EXPECTED_TABLES)}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Idempotent migration: add 4 note-graph tables to contacts.db"
    )
    ap.add_argument(
        "--db",
        type=Path,
        default=DB_PATH_DEFAULT,
        help=f"path to contacts.db (default: {DB_PATH_DEFAULT})",
    )
    args = ap.parse_args()
    return migrate(args.db.expanduser().resolve())


if __name__ == "__main__":
    sys.exit(main())
