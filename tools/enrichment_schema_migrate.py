#!/usr/bin/env python3
"""
enrichment_schema_migrate.py - Idempotent schema migration to add the 12
contact-enrichment columns to an existing pupsik contacts.db.

source: original
License: MIT (matches pupsik repo license)
Adaptation type: original work (NOT adapted from gbrain or any external
project). Designed 2026-05-08 alongside the contact-enrichment-weekly
scheduled task.

The contact-enrichment-weekly task expects 11 columns on the `contacts`
table: linkedin, twitter, github, website, instagram, bio,
enrichment_source, enrichment_date, enrichment_confidence,
last_enriched, relationship_context.
If your contacts.db was created from an older pupsik schema (pre-enrichment
or pre-Pass-4), run this script once to add them. `relationship_context`
was added 2026-05-08 alongside Pass 4 (email + WhatsApp correspondence scan).

The script is safe to re-run. Already-existing columns are detected
via SQLite's `OperationalError: duplicate column name` and reported
as already present rather than failing.

Usage:
  enrichment_schema_migrate.py [path/to/contacts.db]

Default DB path resolution order:
  1. Argument 1 if provided.
  2. $CLAUDE_WORKSPACE/data/contacts.db if set.
  3. $HOME/Desktop/claude/data/contacts.db (the pupsik default).

Exit codes:
  0 - success (all columns present after run, whether added or already there)
  1 - DB file not found, or other unrecoverable error

After a successful run, install the cron template:
  cp ~/pupsik/templates/scheduled-tasks/contact-enrichment-weekly.md.template \\
     ~/.claude/scheduled-tasks/contact-enrichment-weekly/SKILL.md
"""

from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path

# The 11 enrichment columns the contact-enrichment-weekly task expects.
# Order matters only for human readability; SQLite stores them by name.
# `relationship_context` was added 2026-05-08 alongside Pass 4 (correspondence
# scan): a 2-4 sentence private summary distilled from email + WhatsApp
# correspondence. Stays in local DB only; never exported.
ENRICHMENT_COLUMNS = [
    ("linkedin", "TEXT"),
    ("twitter", "TEXT"),
    ("github", "TEXT"),
    ("website", "TEXT"),
    ("instagram", "TEXT"),
    ("bio", "TEXT"),
    ("enrichment_source", "TEXT"),
    ("enrichment_date", "DATE"),
    ("enrichment_confidence", "TEXT"),
    ("last_enriched", "DATE"),
    ("relationship_context", "TEXT"),
]


def resolve_db_path(argv: list[str]) -> Path:
    """Pick the contacts.db path: arg, $CLAUDE_WORKSPACE, or pupsik default."""
    if len(argv) >= 2 and argv[1]:
        return Path(argv[1]).expanduser()
    workspace = os.environ.get("CLAUDE_WORKSPACE")
    if workspace:
        return Path(workspace).expanduser() / "data" / "contacts.db"
    home = os.environ.get("HOME") or str(Path.home())
    return Path(home) / "Desktop" / "claude" / "data" / "contacts.db"


def migrate(db_path: Path) -> int:
    if not db_path.exists():
        print(f"ERROR: contacts.db not found at {db_path}", file=sys.stderr)
        print(
            "Pass the path explicitly: "
            "enrichment_schema_migrate.py /path/to/contacts.db",
            file=sys.stderr,
        )
        return 1

    print(f"[enrichment-migrate] target: {db_path}")
    conn = sqlite3.connect(str(db_path))
    try:
        cursor = conn.cursor()
        # Sanity: ensure the contacts table exists.
        cursor.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name='contacts'"
        )
        if cursor.fetchone() is None:
            print(
                "ERROR: 'contacts' table not found. "
                "Initialize the DB with `contacts_db.py init` first.",
                file=sys.stderr,
            )
            return 1

        added: list[str] = []
        already: list[str] = []
        for col, col_type in ENRICHMENT_COLUMNS:
            try:
                cursor.execute(
                    f"ALTER TABLE contacts ADD COLUMN {col} {col_type}"
                )
                added.append(col)
            except sqlite3.OperationalError as exc:
                msg = str(exc).lower()
                if "duplicate column" in msg:
                    already.append(col)
                else:
                    raise
        conn.commit()

        print(f"[enrichment-migrate] added: {len(added)} column(s)")
        for col in added:
            print(f"  + {col}")
        print(
            f"[enrichment-migrate] already present: {len(already)} column(s)"
        )
        for col in already:
            print(f"  = {col}")

        # Verify all 12 are now there.
        cursor.execute("PRAGMA table_info(contacts)")
        present_cols = {row[1] for row in cursor.fetchall()}
        missing = [c for c, _ in ENRICHMENT_COLUMNS if c not in present_cols]
        if missing:
            print(
                f"ERROR: post-migration verify FAILED, missing: {missing}",
                file=sys.stderr,
            )
            return 1

        print(
            "[enrichment-migrate] OK - all 12 enrichment columns present."
        )
        print(
            "Next: install the cron template at "
            "~/.claude/scheduled-tasks/contact-enrichment-weekly/SKILL.md "
            "(see templates/scheduled-tasks/contact-enrichment-weekly.md.template)."
        )
        return 0
    finally:
        conn.close()


def main(argv: list[str]) -> int:
    db_path = resolve_db_path(argv)
    return migrate(db_path)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
