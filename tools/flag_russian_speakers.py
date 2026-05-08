#!/usr/bin/env python3
"""
flag_russian_speakers.py - Multi-signal heuristic to flag contacts likely to
chat with you on Telegram (Russian-speakers, Russian-context business contacts).

source: original
License: MIT (matches pupsik repo license)
Adaptation type: original work (NOT adapted from gbrain or any external
project). Designed 2026-05-08 alongside Pass 4 of the contact-enrichment-weekly
scheduled task.

Why this exists
---------------
The contact-enrichment-weekly task's Pass 4 reads correspondence from email
and WhatsApp to synthesize a private `relationship_context` summary. For
contacts likely to be more active on Telegram than on email/WhatsApp, the
synthesis is grounded only in non-TG channels and may miss the dominant
context. Telegram CANNOT be auto-read by Claude (the upstream rule
`feedback_telegram_manual.md` blocks all OpenTele/tdata/export automation
because Misha's TG account is irreplaceable; manual paste only).

Instead, this tool sets a `tg_manual_paste_recommended` flag on contacts the
heuristic identifies as Russian-speaking or Russian-context. Pass 4's run
summary then surfaces these flagged contacts as "TG manual-paste candidates"
so the operator can paste a relevant snippet into a one-off prompt for any
specific contact and get the relationship_context refreshed.

Multi-signal heuristic (any one matches)
----------------------------------------
1. Cyrillic in name or full_name field
2. First-name token matches a Latin transliteration of a Russian name
   (Nikolay, Vlad, Aleksey, Andrey, Dasha, Ilya, Anna, Igor, etc.)
3. Last-name token ends with a Russian surname suffix
   (-ov / -ova / -ev / -eva / -in / -ina / -sky / -skaya / -enko / -uk etc.)
4. Email matches a Russian-context domain pattern
   (.ru, .by, .kz, .ua, mail.ru, yandex.ru, etc.)
5. Company contains a configured Russian-context organisation
   (configurable via $RUSSIAN_CONTEXT_COMPANIES env var, comma-separated;
   leave unset to disable signal 5)

Signal 5 is opt-in because Russian-context companies are operator-specific
(your network's Russian gaming studios, Russian-speaking law firms, family
office entities, etc.). Set `RUSSIAN_CONTEXT_COMPANIES` to a comma-separated
list of substrings (case-insensitive) to enable.

Idempotency
-----------
Only flips `tg_manual_paste_recommended` from 0 -> 1; never clobbers a manual
override (1 -> 0 is preserved). Re-running is safe and cheap. Designed to be
called from contact-enrichment-weekly's Step 0.5 to refresh flags for any
newly-added contacts before each Sunday's enrichment pass.

Privacy guards (mirrored from the cron task filter)
---------------------------------------------------
- Skips `category IN ('personal', 'tenancy', 'events')`.
- Skips id=1 (the operator themself; flagging the operator's own row is
  meaningless and would surface their own contact in TG-paste suggestions).

Usage
-----
  python3 flag_russian_speakers.py            # dry-run, prints diff
  python3 flag_russian_speakers.py --apply    # apply UPDATE statements

Default DB path resolution order:
  1. $CLAUDE_WORKSPACE/data/contacts.db if set
  2. $HOME/Desktop/claude/data/contacts.db (the pupsik default)

Schema requirement: the contacts table needs the
`tg_manual_paste_recommended INTEGER DEFAULT 0` column. If your contacts.db
was created from an older pupsik schema (pre-2026-05-08), run the helper
once: `python3 tools/enrichment_schema_migrate.py`.

Exit codes:
  0 - success (dry-run report or apply complete)
  1 - DB file not found or other unrecoverable error
"""

from __future__ import annotations

import os
import re
import sqlite3
import sys
from pathlib import Path


# Russian first names in Latin transliteration. Lowercase, normalised.
# Covers common Cyrillic -> Latin variants you encounter in business contexts:
# both "Aleksey" and "Alexey" forms, Soviet-era Helen/Eugene/Peter Anglicisations,
# diminutives that are commonly used as register names (Sasha, Misha, Dima).
RUSSIAN_FIRST_NAMES = {
    # Male
    "aleksey", "alexey", "alexei", "aleksei", "lyosha",
    "aleksandr", "alexander", "sasha", "sashka",
    "andrey", "andrei", "andrew",
    "anton",
    "arkady", "arkadiy",
    "artem", "artyom",
    "boris", "borya",
    "daniel", "danil", "danila", "danya",
    "denis",
    "dmitry", "dmitri", "dima",
    "egor", "yegor",
    "evgeny", "evgeni", "yevgeny", "zhenya", "eugene",
    "fedor", "fyodor", "fedya",
    "gennady", "gena", "genya",
    "georgy", "georgi", "zhora",
    "gleb",
    "grigory", "grisha",
    "igor",
    "ilya", "ilia", "iliya",
    "ivan", "vanya",
    "kirill",
    "konstantin", "kostya",
    "lev", "leva",
    "maxim", "maksim",
    "mikhail", "misha", "mishka",
    "nikita",
    "nikolay", "nikolai", "kolya", "nicolai",
    "oleg", "olezhka",
    "pavel", "pasha",
    "pyotr", "petr", "petya",
    "roman", "roma",
    "ruslan",
    "sergey", "sergei", "serguei", "seryozha",
    "stanislav", "stas",
    "stepan", "styopa",
    "timofey", "timofei", "timon", "tima",
    "timur",
    "valentin", "valya",
    "valery", "valera",
    "vasily", "vasili", "vasya",
    "viktor",
    "vitaly", "vitaliy", "vitya",
    "vladimir", "vladislav", "vlad", "volodya", "vova",
    "vsevolod", "seva",
    "yaroslav", "yarik",
    "yefim", "efim",
    "yury", "yuri", "yura",
    "zakhar",
    # Female
    "aleksandra",
    "alena", "alyona",
    "alina",
    "alisa",
    "alla",
    "anastasia", "nastya", "anastasiya",
    "angelina",
    "anna", "anya", "anyuta",
    "antonina",
    "daria", "darya", "dasha",
    "diana",
    "ekaterina", "katya", "katherine",
    "elena", "lena", "helen",
    "elizaveta", "liza",
    "galina", "galya",
    "inna",
    "irina", "ira",
    "ksenia", "kseniya", "ksu", "ksusha",
    "larisa", "lara",
    "lyudmila", "lyuda",
    "maria", "masha", "mariya",
    "marina",
    "nadezhda", "nadya",
    "natalya", "natalia", "natasha",
    "nina",
    "olga", "olya",
    "polina", "polya",
    "sofia", "sonya",
    "svetlana", "sveta",
    "tamara",
    "tatyana", "tatiana", "tanya",
    "valentina",
    "valeria", "lera",
    "varvara", "varya",
    "vera",
    "veronika", "nika",
    "viktoria", "vika",
    "yana",
    "yulia", "yulya", "julia",
    "zinaida", "zina",
    "zoya",
}

# Surname suffixes. If the last token of the name ends with one of these, the
# contact is likely Russian-speaking. Order matters: check longer suffixes
# first to avoid false matches (e.g. "ovich" matches before "ich").
SURNAME_SUFFIXES = (
    "ovich", "evich",
    "nikov", "nikova",
    "skaya", "tskaya",
    "skiy", "tskiy", "skii",
    "enko",
    "shev", "sheva",
    "yev", "yeva",
    "aev", "aeva",
    "sky", "ski",
    "tsky",
    "yuk", "chuk",
    "ova", "eva",
    "ina", "yna",
    "ich",
    "ov", "ev",
    "in", "yn",
    "uk",
)

# Email-domain heuristic patterns (lowercase, used as substring/suffix matches).
# Anchored with leading "." or "@" where appropriate to avoid false positives
# (e.g. ".ru" matches misha.ru but not mailgun.run).
RUSSIAN_EMAIL_PATTERNS = (
    ".ru", ".by", ".kz", ".ua",
    "@mail.ru", "@yandex.ru", "@yandex.com",
)


def normalise(s: str) -> str:
    """Lowercase, strip punctuation, normalise whitespace."""
    if not s:
        return ""
    return re.sub(r"[^a-zA-Z\s\-]", "", s).lower().strip()


def get_context_companies() -> tuple[str, ...]:
    """Read $RUSSIAN_CONTEXT_COMPANIES env var (comma-separated, optional)."""
    raw = os.environ.get("RUSSIAN_CONTEXT_COMPANIES", "").strip()
    if not raw:
        return ()
    return tuple(s.strip().lower() for s in raw.split(",") if s.strip())


def is_russian(
    name: str,
    full_name: str = "",
    email: str = "",
    company: str = "",
    context_companies: tuple[str, ...] = (),
) -> tuple[bool, str]:
    """Multi-signal Russian-speaker heuristic. Returns (is_russian, reason).

    Signals (any one matches):
      1. Cyrillic in name or full_name
      2. First-name token matches Latin transliteration of a Russian name
      3. Last-name token ends with a Russian surname suffix
      4. Email matches Russian-domain pattern
      5. Company contains a configured Russian-context organisation
    """
    # Signal 1: Cyrillic
    for s in (name, full_name):
        if s and re.search(r"[А-Яа-яЁё]", s):
            return True, "cyrillic"

    # Signal 2 + 3: name-token analysis
    candidates = [normalise(name), normalise(full_name)]
    for cand in candidates:
        if not cand:
            continue
        tokens = cand.split()
        # Signal 2: first-name match
        if tokens and tokens[0] in RUSSIAN_FIRST_NAMES:
            return True, f"first_name={tokens[0]}"
        # Signal 3: surname suffix (only check on multi-token names to avoid
        # false matches on single Western names that happen to end in -in)
        if len(tokens) >= 2:
            last = tokens[-1]
            for suf in SURNAME_SUFFIXES:
                if last.endswith(suf) and len(last) > len(suf) + 1:
                    return True, f"surname_suffix={suf}"

    # Signal 4: email pattern
    if email:
        e = email.lower()
        for pat in RUSSIAN_EMAIL_PATTERNS:
            if pat in e:
                return True, f"email_pattern={pat}"

    # Signal 5: company match (opt-in via env var)
    if company and context_companies:
        c = company.lower()
        for org in context_companies:
            if org in c:
                return True, f"company={org}"

    return False, ""


def resolve_db_path(argv: list[str]) -> Path:
    """Resolve DB path: argv[1] -> $CLAUDE_WORKSPACE -> $HOME/Desktop/claude."""
    candidates = []
    if len(argv) > 1 and not argv[1].startswith("-"):
        candidates.append(Path(argv[1]).expanduser())
    workspace = os.environ.get("CLAUDE_WORKSPACE")
    if workspace:
        candidates.append(Path(workspace) / "data" / "contacts.db")
    candidates.append(Path.home() / "Desktop" / "claude" / "data" / "contacts.db")
    for c in candidates:
        if c.exists():
            return c
    return candidates[0] if candidates else Path("contacts.db")


def main() -> int:
    args = [a for a in sys.argv[1:] if a not in ("--apply", "--help", "-h")]
    apply = "--apply" in sys.argv
    if "--help" in sys.argv or "-h" in sys.argv:
        print(__doc__)
        return 0

    db_path = resolve_db_path([sys.argv[0]] + args)
    if not db_path.exists():
        print(f"DB not found: {db_path}", file=sys.stderr)
        return 1

    context_companies = get_context_companies()
    if context_companies:
        print(f"Signal 5 enabled (RUSSIAN_CONTEXT_COMPANIES): {context_companies}")
    else:
        print("Signal 5 disabled (set RUSSIAN_CONTEXT_COMPANIES env var to enable)")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Check schema has the column
    cur.execute("PRAGMA table_info(contacts)")
    cols = [r[1] for r in cur.fetchall()]
    if "tg_manual_paste_recommended" not in cols:
        print(
            "Schema missing tg_manual_paste_recommended column.\n"
            "Run: python3 tools/enrichment_schema_migrate.py",
            file=sys.stderr,
        )
        return 1

    # Privacy filter same as cron task Step 1.
    cur.execute(
        """
        SELECT id, name, full_name, email, company, tg_manual_paste_recommended
        FROM contacts
        WHERE tg_manual_paste_recommended = 0
          AND (category IS NULL OR category NOT IN ('personal','tenancy','events'))
          AND id != 1
        """
    )
    rows = cur.fetchall()

    to_flag = []
    for r in rows:
        rus, reason = is_russian(
            r["name"] or "",
            r["full_name"] or "",
            r["email"] or "",
            r["company"] or "",
            context_companies,
        )
        if rus:
            to_flag.append((r["id"], r["name"], reason))

    print(f"Candidates not yet flagged: {len(rows)}")
    print(f"Newly matched as Russian-speaker: {len(to_flag)}")

    if to_flag:
        print("\nSample (first 20):")
        for fid, fname, freason in to_flag[:20]:
            print(f"  id={fid} {fname!s:40} -> {freason}")
        print()

    if apply:
        for fid, _, _ in to_flag:
            cur.execute(
                "UPDATE contacts SET tg_manual_paste_recommended = 1 WHERE id = ?",
                (fid,),
            )
        conn.commit()
        print(f"\nApplied: {len(to_flag)} rows updated.")
    else:
        print("\nDry-run. Pass --apply to update DB.")

    cur.execute("SELECT COUNT(*) FROM contacts WHERE tg_manual_paste_recommended = 1")
    total = cur.fetchone()[0]
    print(f"Total tg_manual_paste_recommended=1: {total}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
