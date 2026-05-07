#!/usr/bin/env python3
"""
doctor.py - Deterministic health-check + safe-auto-fix for Misha's system.

Adapted from gbrain (Garry Tan, MIT) `gbrain doctor` / `gbrain orphans` /
`gbrain repair-jsonb` command suite.
 Source: https://github.com/garrytan/gbrain
 License: MIT (verified 2026-05-07 via gh api)
 Adaptation type: adapted

Adapted for Misha's stack:
 - File-system + ChromaDB + SQLite contacts.db (no Postgres, no JSONB)
 - SAFE auto-fixes ONLY (no LLM-driven content rewrites; per AI Architect
  Lens MODIFY verdict 2026-05-07)
 - Specific checks derived from observed failure modes in Misha's system
  (orphan ChromaDB rows, broken symlinks, dead scheduled tasks)

See:
 - memory/THIRD_PARTY_ATTRIBUTIONS.md (central tracker)
 - memory/learnings/2026-05-07-open-source-attribution-rule-for-imported-patterns.md

Usage:
  doctor.py check [--json]      # read-only, exit 0 always
  doctor.py fix-safe [--dry-run] [--json]
  doctor.py orphans [--json]     # read-only orphan listing

Exit codes:
  check / orphans -> always 0 (safe in cron, even on FAIL)
  fix-safe    -> 0 always (errors recorded inline in JSON / output)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

# -----------------------------------------------------------------------------
# Paths / constants
# -----------------------------------------------------------------------------

HOME = Path(os.path.expanduser("~"))
BASE_DIR = HOME / "Desktop" / "claude"
TOOLS_DIR = BASE_DIR / "tools"
MEMORY_DIR_LOCAL = BASE_DIR / "memory"
LEARNINGS_DIR = MEMORY_DIR_LOCAL / "learnings"
DECISIONS_DIR = MEMORY_DIR_LOCAL / "decisions"
FRICTION_DIR = MEMORY_DIR_LOCAL / "friction"
OUTBOUND_PENDING_DIR = MEMORY_DIR_LOCAL / "outbound_pending"
RESEARCH_DIR = BASE_DIR / "research"
CHROMA_PATH = BASE_DIR / "data" / "chroma"
CHROMA_LOCK = CHROMA_PATH / ".index.lock"

# Project-slug-derived per-project memory dir (matches memory_search.py logic)
_PROJECT_SLUG = str(BASE_DIR).replace("/", "-")
PROJECT_MEMORY_DIR = HOME / ".claude" / "projects" / _PROJECT_SLUG / "memory"
CRITICAL_RULES = HOME / ".claude" / "rules" / "critical-rules.md"
CLAUDE_MD = BASE_DIR / "CLAUDE.md"
MEMORY_MD = PROJECT_MEMORY_DIR / "MEMORY.md"
SCHEDULED_TASKS_DIR = HOME / ".claude" / "scheduled-tasks"

PUPSIK_PRIVACY_CHECK = HOME / "pupsik" / ".github" / "scripts" / "privacy-check.sh"

# Defensive limits
MAX_LINES_TARGET = 200
LOCK_STALE_SEC = 3600 # 1 hour
CHROMA_LOCK_STALE_SEC = 600 # 10 min, matches memory_search.py LOCK_STALE_AFTER_SEC

# Status labels
PASS = "PASS"
FAIL = "FAIL"
WARN = "WARN"
SKIP = "SKIP"

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------


def _now() -> str:
  return datetime.now().isoformat(timespec="seconds")


def _safe(label: str, fn, *args, **kwargs) -> dict:
  """Wrap a check function so unexpected exceptions become FAIL rather than
  crashing the whole script. The caller's check function must return a dict
  of the form {status, summary, details(optional), fixable(optional)}.
  """
  try:
    result = fn(*args, **kwargs)
    if not isinstance(result, dict):
      result = {"status": FAIL, "summary": f"check {label} returned non-dict"}
  except Exception as exc: # noqa: BLE001
    result = {
      "status": FAIL,
      "summary": f"unhandled exception in {label}: {exc!r}",
      "exception": repr(exc),
    }
  result["check"] = label
  return result


def _is_pid_alive(pid: int) -> bool:
  """Return True if a process with this PID exists. macOS-friendly."""
  if pid <= 0:
    return False
  try:
    os.kill(pid, 0)
  except ProcessLookupError:
    return False
  except PermissionError:
    # Process exists but we can't signal it
    return True
  except OSError:
    return False
  return True


def _wc_lines(path: Path) -> int:
  """Count lines in a file. Returns -1 if unreadable."""
  try:
    with open(path, "r", encoding="utf-8", errors="replace") as f:
      return sum(1 for _ in f)
  except OSError:
    return -1


def _read_text(path: Path) -> str:
  try:
    return path.read_text(encoding="utf-8", errors="replace")
  except OSError:
    return ""


# -----------------------------------------------------------------------------
# SAFE checks (1-8) - auto-fixable in fix-safe mode, plus a few report-only
# -----------------------------------------------------------------------------


def check_broken_symlinks() -> dict:
  """1. Find broken symlinks under workspace + per-project memory dir.

  fix-safe action: remove the broken symlink (deterministic, reversible by
  re-running whatever created it).
  """
  broken: list[str] = []
  scan_roots = [BASE_DIR, PROJECT_MEMORY_DIR]
  for root in scan_roots:
    if not root.exists():
      continue
    # Use find for speed and to avoid Python recursion on huge trees.
    try:
      out = subprocess.run(
        [
          "find", str(root),
          "-type", "l",
          "!", "-exec", "test", "-e", "{}", ";",
          "-print",
        ],
        capture_output=True,
        text=True,
        timeout=30,
      )
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
      return {
        "status": FAIL,
        "summary": f"find failed: {exc!r}",
        "fixable": False,
      }
    for line in out.stdout.splitlines():
      line = line.strip()
      if line:
        broken.append(line)
  if not broken:
    return {"status": PASS, "summary": "no broken symlinks", "fixable": False}
  return {
    "status": FAIL,
    "summary": f"{len(broken)} broken symlink(s)",
    "details": broken,
    "fixable": True,
  }


def fix_broken_symlinks(dry_run: bool) -> dict:
  """Remove broken symlinks reported by check_broken_symlinks."""
  res = check_broken_symlinks()
  targets = res.get("details", []) if res.get("status") == FAIL else []
  actions: list[dict] = []
  for path_str in targets:
    p = Path(path_str)
    action = {"path": path_str, "action": "unlink"}
    if dry_run:
      action["status"] = "would-do"
    else:
      try:
        p.unlink()
        action["status"] = "done"
      except FileNotFoundError:
        action["status"] = "already-gone"
      except OSError as exc:
        action["status"] = f"error:{exc!r}"
    actions.append(action)
  return {
    "fix": "broken_symlinks",
    "count": len(actions),
    "dry_run": dry_run,
    "actions": actions,
  }


def check_stale_lockfiles() -> dict:
  """2. Look for .lock files in workspace older than 1h or with dead PID.

  Auto-fix: remove stale ones (PID dead OR mtime > 1h).
  Includes the ChromaDB index lock (own TTL of 10 min from memory_search.py).
  """
  candidates: list[Path] = []
  # Walk workspace for *.lock files (shallow + curated paths).
  for root in [BASE_DIR, CHROMA_PATH]:
    if not root.exists():
      continue
    try:
      for p in root.rglob("*.lock"):
        # Skip irrelevant noise (pipenv, npm) - only ours.
        if ".git" in p.parts:
          continue
        candidates.append(p)
    except OSError:
      continue
  # Also consider the named ChromaDB index lock + .index.lock.
  extras = [CHROMA_LOCK, CHROMA_PATH / ".note.lock"]
  for e in extras:
    if e.exists() and e not in candidates:
      candidates.append(e)

  stale: list[dict] = []
  fresh: list[str] = []
  for lock in candidates:
    try:
      mtime = lock.stat().st_mtime
    except OSError:
      continue
    age = time.time() - mtime
    ttl = CHROMA_LOCK_STALE_SEC if lock == CHROMA_LOCK else LOCK_STALE_SEC
    # Try to read PID for staleness via dead-process signal.
    pid_alive = None
    pid_value = None
    try:
      data = json.loads(lock.read_text())
      pid_value = int(data.get("pid", 0)) if isinstance(data, dict) else None
      if pid_value:
        pid_alive = _is_pid_alive(pid_value)
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
      pid_alive = None
      pid_value = None
    is_stale = (age > ttl) or (pid_alive is False)
    info = {
      "path": str(lock),
      "age_sec": int(age),
      "ttl_sec": ttl,
      "pid": pid_value,
      "pid_alive": pid_alive,
      "stale": is_stale,
    }
    if is_stale:
      stale.append(info)
    else:
      fresh.append(str(lock))

  if not candidates:
    return {"status": PASS, "summary": "no lockfiles found", "fixable": False}
  if not stale:
    return {
      "status": PASS,
      "summary": f"{len(candidates)} lockfile(s), all fresh",
      "details": fresh,
      "fixable": False,
    }
  return {
    "status": FAIL,
    "summary": f"{len(stale)} stale lockfile(s) of {len(candidates)} total",
    "details": stale,
    "fixable": True,
  }


def fix_stale_lockfiles(dry_run: bool) -> dict:
  res = check_stale_lockfiles()
  targets = res.get("details", []) if res.get("status") == FAIL else []
  actions: list[dict] = []
  for info in targets:
    if not isinstance(info, dict):
      continue
    path_str = info.get("path", "")
    action = {"path": path_str, "action": "remove"}
    if dry_run:
      action["status"] = "would-do"
    else:
      try:
        Path(path_str).unlink()
        action["status"] = "done"
      except FileNotFoundError:
        action["status"] = "already-gone"
      except OSError as exc:
        action["status"] = f"error:{exc!r}"
    actions.append(action)
  return {
    "fix": "stale_lockfiles",
    "count": len(actions),
    "dry_run": dry_run,
    "actions": actions,
  }


def check_empty_files() -> dict:
  """3. 0-byte files in dirs where empty = corruption signal. Report only."""
  scan_dirs = [
    LEARNINGS_DIR, DECISIONS_DIR, FRICTION_DIR, OUTBOUND_PENDING_DIR,
    RESEARCH_DIR,
  ]
  empties: list[str] = []
  for d in scan_dirs:
    if not d.exists():
      continue
    try:
      for p in d.rglob("*.md"):
        try:
          if p.stat().st_size == 0:
            empties.append(str(p))
        except OSError:
          continue
    except OSError:
      continue
  # Additionally scan feedback_*.md in per-project memory
  if PROJECT_MEMORY_DIR.exists():
    try:
      for p in PROJECT_MEMORY_DIR.glob("feedback_*.md"):
        try:
          if p.stat().st_size == 0:
            empties.append(str(p))
        except OSError:
          continue
    except OSError:
      pass

  if not empties:
    return {"status": PASS, "summary": "no empty markdown files", "fixable": False}
  return {
    "status": WARN,
    "summary": f"{len(empties)} empty markdown file(s) (could be in-progress writes)",
    "details": empties,
    "fixable": False, # too risky to auto-delete
  }


def _chroma_orphan_rows() -> tuple[list[dict], int]:
  """Walk all ChromaDB collections; return [(coll, id, source_path)] for
  rows whose meta.source/path points at a missing file. Also returns total
  row count scanned.

  Source-path interpretation per collection (mirrors memory_search.py):
   - memory_files: meta.source = filename (look up under PROJECT_MEMORY_DIR
    or BASE_DIR root for CLAUDE.md / MEMORY.md); orphan iff none exist.
   - briefings:  meta.source = filename under BASE_DIR/briefings/
   - outputs:   meta.source = relative path under BASE_DIR/outputs/
   - journal:   meta.source = filename under BASE_DIR/memory/journal/
   - knowledge:  meta.source = filename under learnings or decisions
   - research:   meta.source = relative path under BASE_DIR/research/
   - friction is folded into memory_files (category=friction); same logic.

  contacts / interactions / chat_archives: skip - they live in SQLite, not
  on disk as paths.
  """
  try:
    import chromadb
    from chromadb.config import Settings
  except ImportError:
    return ([], 0)

  if not CHROMA_PATH.exists():
    return ([], 0)

  try:
    client = chromadb.PersistentClient(
      path=str(CHROMA_PATH),
      settings=Settings(anonymized_telemetry=False),
    )
  except Exception:
    return ([], 0)

  orphans: list[dict] = []
  total = 0

  # Resolve canonical source dirs
  BRIEFINGS_DIR = BASE_DIR / "briefings"
  OUTPUTS_DIR = BASE_DIR / "outputs"
  JOURNAL_DIR = BASE_DIR / "memory" / "journal"

  def _resolve_path(coll_name: str, source: str) -> Path | None:
    if not source:
      return None
    if coll_name == "memory_files":
      # Could be CLAUDE.md or MEMORY.md (workspace root) or a file in
      # PROJECT_MEMORY_DIR or FRICTION_DIR.
      candidates = [
        BASE_DIR / source,
        PROJECT_MEMORY_DIR / source,
        FRICTION_DIR / source,
      ]
      for c in candidates:
        if c.exists():
          return c
      return PROJECT_MEMORY_DIR / source # representative missing path
    if coll_name == "briefings":
      return BRIEFINGS_DIR / source
    if coll_name == "outputs":
      return OUTPUTS_DIR / source
    if coll_name == "journal":
      return JOURNAL_DIR / source
    if coll_name == "knowledge":
      for d in (LEARNINGS_DIR, DECISIONS_DIR):
        p = d / source
        if p.exists():
          return p
      return LEARNINGS_DIR / source
    if coll_name == "research":
      return RESEARCH_DIR / source
    return None

  skip_names = {"contacts", "interactions", "chat_archives"}

  try:
    collections = client.list_collections()
  except Exception:
    return ([], 0)

  for coll in collections:
    name = getattr(coll, "name", None)
    if not name or name in skip_names:
      continue
    try:
      data = coll.get(include=["metadatas"])
    except Exception:
      continue
    ids = data.get("ids") or []
    metas = data.get("metadatas") or []
    for i, meta in enumerate(metas):
      total += 1
      if not isinstance(meta, dict):
        continue
      source = meta.get("source") or meta.get("path") or ""
      if not source:
        continue
      resolved = _resolve_path(name, source)
      if resolved is None:
        continue
      if not resolved.exists():
        orphans.append({
          "collection": name,
          "id": ids[i] if i < len(ids) else None,
          "source": source,
          "expected_path": str(resolved),
        })
  return orphans, total


def check_chroma_orphans() -> dict:
  """4. ChromaDB rows whose meta.source/path file no longer exists."""
  orphans, total = _chroma_orphan_rows()
  if total == 0:
    return {
      "status": WARN,
      "summary": "ChromaDB unavailable or empty (chromadb missing or 0 rows scanned)",
      "fixable": False,
    }
  if not orphans:
    return {
      "status": PASS,
      "summary": f"no orphan rows ({total} rows scanned)",
      "fixable": False,
    }
  return {
    "status": FAIL,
    "summary": f"{len(orphans)} orphan row(s) of {total} scanned",
    "details": orphans[:50], # truncate for sanity
    "total_orphans": len(orphans),
    "fixable": True,
  }


def fix_chroma_orphans(dry_run: bool) -> dict:
  """Delete rows in ChromaDB whose source file is missing."""
  orphans, _ = _chroma_orphan_rows()
  if not orphans:
    return {
      "fix": "chroma_orphans",
      "count": 0,
      "dry_run": dry_run,
      "actions": [],
    }
  actions: list[dict] = []
  if dry_run:
    for o in orphans:
      actions.append({**o, "status": "would-delete"})
    return {
      "fix": "chroma_orphans",
      "count": len(actions),
      "dry_run": True,
      "actions": actions[:200],
    }
  try:
    import chromadb
    from chromadb.config import Settings
  except ImportError:
    return {
      "fix": "chroma_orphans",
      "count": 0,
      "dry_run": False,
      "actions": [],
      "error": "chromadb not installed",
    }
  try:
    client = chromadb.PersistentClient(
      path=str(CHROMA_PATH),
      settings=Settings(anonymized_telemetry=False),
    )
  except Exception as exc:
    return {
      "fix": "chroma_orphans",
      "count": 0,
      "dry_run": False,
      "actions": [],
      "error": f"could not open chroma: {exc!r}",
    }
  by_coll: dict[str, list[str]] = {}
  for o in orphans:
    coll_name = o["collection"]
    oid = o.get("id")
    if oid is None:
      continue
    by_coll.setdefault(coll_name, []).append(oid)
  for coll_name, ids in by_coll.items():
    try:
      coll = client.get_collection(coll_name)
      coll.delete(ids=ids)
      for oid in ids:
        actions.append({"collection": coll_name, "id": oid, "status": "deleted"})
    except Exception as exc:
      for oid in ids:
        actions.append({
          "collection": coll_name,
          "id": oid,
          "status": f"error:{exc!r}",
        })
  return {
    "fix": "chroma_orphans",
    "count": len(actions),
    "dry_run": False,
    "actions": actions[:200],
  }


def check_chroma_lock() -> dict:
  """5. Stale ChromaDB lockfile.

  Folded into stale-lockfile check for safety, but kept as standalone for
  spec-mapping clarity. Reports separately whether CHROMA_LOCK exists and
  is stale.
  """
  if not CHROMA_LOCK.exists():
    return {"status": PASS, "summary": "no chroma lockfile", "fixable": False}
  try:
    mtime = CHROMA_LOCK.stat().st_mtime
  except OSError:
    return {
      "status": FAIL,
      "summary": "chroma lock unreadable",
      "fixable": False,
    }
  age = time.time() - mtime
  pid_alive = None
  pid_value: int | None = None
  try:
    data = json.loads(CHROMA_LOCK.read_text())
    pid_value = int(data.get("pid", 0))
    pid_alive = _is_pid_alive(pid_value)
  except (OSError, ValueError, TypeError, json.JSONDecodeError):
    pass
  stale = (age > CHROMA_LOCK_STALE_SEC) or (pid_alive is False)
  info = {
    "path": str(CHROMA_LOCK),
    "age_sec": int(age),
    "pid": pid_value,
    "pid_alive": pid_alive,
  }
  if stale:
    return {
      "status": FAIL,
      "summary": f"chroma lock stale (age {int(age)}s, pid_alive={pid_alive})",
      "details": info,
      "fixable": True,
    }
  return {
    "status": PASS,
    "summary": f"chroma lock fresh (age {int(age)}s)",
    "details": info,
    "fixable": False,
  }


def fix_chroma_lock(dry_run: bool) -> dict:
  res = check_chroma_lock()
  if res.get("status") != FAIL:
    return {
      "fix": "chroma_lock",
      "count": 0,
      "dry_run": dry_run,
      "actions": [],
    }
  action = {"path": str(CHROMA_LOCK), "action": "remove"}
  if dry_run:
    action["status"] = "would-do"
  else:
    try:
      CHROMA_LOCK.unlink()
      action["status"] = "done"
    except FileNotFoundError:
      action["status"] = "already-gone"
    except OSError as exc:
      action["status"] = f"error:{exc!r}"
  return {
    "fix": "chroma_lock",
    "count": 1,
    "dry_run": dry_run,
    "actions": [action],
  }


def check_memory_md_size() -> dict:
  """6. MEMORY.md size > 200 lines (hard limit per CLAUDE.md). Report only."""
  if not MEMORY_MD.exists():
    return {
      "status": FAIL,
      "summary": f"MEMORY.md not found at {MEMORY_MD}",
      "fixable": False,
    }
  n = _wc_lines(MEMORY_MD)
  if n < 0:
    return {"status": FAIL, "summary": "MEMORY.md unreadable", "fixable": False}
  if n > MAX_LINES_TARGET:
    return {
      "status": FAIL,
      "summary": f"MEMORY.md is {n} lines (>{MAX_LINES_TARGET}); structural fix required",
      "details": {"path": str(MEMORY_MD), "lines": n, "limit": MAX_LINES_TARGET},
      "fixable": False,
    }
  return {
    "status": PASS,
    "summary": f"MEMORY.md size OK ({n} lines)",
    "fixable": False,
  }


def check_claude_md_size() -> dict:
  """7. CLAUDE.md size > 200 lines (target). Report only."""
  if not CLAUDE_MD.exists():
    return {
      "status": FAIL,
      "summary": f"CLAUDE.md not found at {CLAUDE_MD}",
      "fixable": False,
    }
  n = _wc_lines(CLAUDE_MD)
  if n < 0:
    return {"status": FAIL, "summary": "CLAUDE.md unreadable", "fixable": False}
  if n > MAX_LINES_TARGET:
    return {
      "status": WARN,
      "summary": f"CLAUDE.md is {n} lines (>{MAX_LINES_TARGET}); consider trimming",
      "details": {"path": str(CLAUDE_MD), "lines": n, "limit": MAX_LINES_TARGET},
      "fixable": False,
    }
  return {
    "status": PASS,
    "summary": f"CLAUDE.md size OK ({n} lines)",
    "fixable": False,
  }


def check_pupsik_privacy() -> dict:
  """8. pupsik privacy-check.sh exit code."""
  if not PUPSIK_PRIVACY_CHECK.exists():
    return {
      "status": SKIP,
      "summary": f"pupsik privacy-check script not found at {PUPSIK_PRIVACY_CHECK}",
      "fixable": False,
    }
  try:
    out = subprocess.run(
      ["bash", str(PUPSIK_PRIVACY_CHECK)],
      capture_output=True,
      text=True,
      timeout=60,
      cwd=str(PUPSIK_PRIVACY_CHECK.parents[2]),
    )
  except subprocess.TimeoutExpired:
    return {"status": FAIL, "summary": "privacy-check.sh timed out (>60s)", "fixable": False}
  except Exception as exc: # noqa: BLE001
    return {
      "status": FAIL,
      "summary": f"privacy-check.sh failed to execute: {exc!r}",
      "fixable": False,
    }
  if out.returncode == 0:
    return {
      "status": PASS,
      "summary": "pupsik privacy-check passed",
      "fixable": False,
    }
  return {
    "status": FAIL,
    "summary": f"pupsik privacy-check exit {out.returncode}",
    "details": {
      "exit": out.returncode,
      "stdout_tail": out.stdout[-2000:],
      "stderr_tail": out.stderr[-2000:],
    },
    "fixable": False,
  }


# -----------------------------------------------------------------------------
# Orphan checks (9-13) - read-only via `orphans` subcommand
# -----------------------------------------------------------------------------


def _list_feedback_files() -> list[Path]:
  if not PROJECT_MEMORY_DIR.exists():
    return []
  return sorted(PROJECT_MEMORY_DIR.glob("feedback_*.md"))


def orphan_feedback_in_critical_rules() -> dict:
  """9. feedback_*.md not referenced anywhere in critical-rules.md."""
  if not CRITICAL_RULES.exists():
    return {
      "status": FAIL,
      "summary": f"critical-rules.md not found at {CRITICAL_RULES}",
    }
  crit_text = _read_text(CRITICAL_RULES)
  fbs = _list_feedback_files()
  orphans: list[str] = []
  for fb in fbs:
    if fb.name not in crit_text:
      orphans.append(str(fb))
  if not orphans:
    return {
      "status": PASS,
      "summary": f"all {len(fbs)} feedback files referenced in critical-rules.md",
    }
  return {
    "status": FAIL,
    "summary": f"{len(orphans)} feedback file(s) NOT referenced in critical-rules.md",
    "details": orphans,
  }


def orphan_feedback_in_memory_md() -> dict:
  """10. feedback_*.md not referenced in MEMORY.md."""
  if not MEMORY_MD.exists():
    return {"status": FAIL, "summary": f"MEMORY.md not found at {MEMORY_MD}"}
  text = _read_text(MEMORY_MD)
  fbs = _list_feedback_files()
  orphans: list[str] = []
  for fb in fbs:
    if fb.name not in text:
      orphans.append(str(fb))
  if not orphans:
    return {
      "status": PASS,
      "summary": f"all {len(fbs)} feedback files referenced in MEMORY.md",
    }
  return {
    "status": FAIL,
    "summary": f"{len(orphans)} feedback file(s) NOT referenced in MEMORY.md",
    "details": orphans,
  }


_REF_PATTERN = re.compile(
  r"""(?:`|\(|/| )            # boundary
    (?P<path>(?:memory/|~/Desktop/claude/memory/|/Users/[^/\s)]+/memory/|projects/|outputs/)?
    [a-zA-Z0-9_./-]+\.md)       # the path
  """,
  re.VERBOSE,
)


def orphan_dangling_pointers() -> dict:
  """11. Memory files referenced from CLAUDE.md / critical-rules.md /
  MEMORY.md but missing on disk. Heuristic - looks for `.md` paths cited
  in those three files and checks existence under either workspace memory
  or project memory dir.
  """
  sources = [CLAUDE_MD, CRITICAL_RULES, MEMORY_MD]
  seen: dict[str, list[str]] = {}
  for src in sources:
    if not src.exists():
      continue
    text = _read_text(src)
    for m in _REF_PATTERN.finditer(text):
      ref = m.group("path").strip()
      # Filter out URL fragments (http) - they are not file references.
      if "://" in ref:
        continue
      seen.setdefault(ref, []).append(src.name)

  missing: list[dict] = []
  seen_keys = list(seen.keys())
  for ref in seen_keys:
    # Skip refs that look like generic patterns (feedback_*.md etc)
    if "*" in ref:
      continue
    # Expand `~` if present
    ref_expanded = ref.replace("~", str(HOME)) if ref.startswith("~") else ref
    # Try all reasonable resolution roots
    candidates: list[Path] = [
      Path(ref_expanded) if ref_expanded.startswith("/") else None,
      BASE_DIR / ref_expanded,
      BASE_DIR / "memory" / ref_expanded,
      PROJECT_MEMORY_DIR / ref_expanded,
      HOME / ref_expanded,
      HOME / ".claude" / ref_expanded,
      HOME / ".claude" / "rules" / ref_expanded,
      BASE_DIR / "memory" / Path(ref_expanded).name,
      PROJECT_MEMORY_DIR / Path(ref_expanded).name,
    ]
    candidates = [c for c in candidates if c is not None]
    if any(c.exists() for c in candidates):
      continue
    missing.append({"ref": ref, "cited_in": seen[ref]})

  if not missing:
    return {"status": PASS, "summary": "no dangling memory file references"}
  return {
    "status": FAIL,
    "summary": f"{len(missing)} dangling reference(s)",
    "details": missing[:50],
    "total": len(missing),
  }


def orphan_dead_scheduled_tasks() -> dict:
  """12. Scheduled tasks whose SKILL.md doesn't exist."""
  if not SCHEDULED_TASKS_DIR.exists():
    return {
      "status": SKIP,
      "summary": f"scheduled-tasks dir not found at {SCHEDULED_TASKS_DIR}",
    }
  dead: list[str] = []
  total = 0
  for entry in sorted(SCHEDULED_TASKS_DIR.iterdir()):
    if not entry.is_dir():
      continue
    total += 1
    skill = entry / "SKILL.md"
    if not skill.exists():
      dead.append(str(entry))
  if not dead:
    return {
      "status": PASS,
      "summary": f"{total} scheduled task(s), all have SKILL.md",
    }
  return {
    "status": FAIL,
    "summary": f"{len(dead)} dead scheduled task dir(s)",
    "details": dead,
  }


def orphan_unindexed_recent_notes() -> dict:
  """13. learnings/decisions/research notes from past 30 days not in ChromaDB.

  Implemented via the ChromaDB collection listing instead of re-running
  `memory_search.py search` for each (faster, deterministic). For each
  recent file, check if any document in the relevant collection has
  metadata source matching the filename.
  """
  try:
    import chromadb
    from chromadb.config import Settings
  except ImportError:
    return {
      "status": WARN,
      "summary": "chromadb not installed; cannot verify indexing",
    }
  if not CHROMA_PATH.exists():
    return {
      "status": WARN,
      "summary": "ChromaDB not initialized",
    }

  cutoff = time.time() - 30 * 86400
  recent: list[Path] = []
  for d in (LEARNINGS_DIR, DECISIONS_DIR, RESEARCH_DIR):
    if not d.exists():
      continue
    try:
      for p in d.rglob("*.md"):
        try:
          if p.stat().st_mtime >= cutoff:
            recent.append(p)
        except OSError:
          continue
    except OSError:
      continue
  if not recent:
    return {
      "status": PASS,
      "summary": "no recent notes (last 30 days) to verify",
    }

  try:
    client = chromadb.PersistentClient(
      path=str(CHROMA_PATH),
      settings=Settings(anonymized_telemetry=False),
    )
  except Exception as exc:
    return {
      "status": WARN,
      "summary": f"could not open ChromaDB: {exc!r}",
    }

  # Pull source values from candidate collections.
  sources_seen: set[str] = set()
  for coll_name in ("knowledge", "research", "memory_files"):
    try:
      coll = client.get_collection(coll_name)
    except Exception:
      continue
    try:
      data = coll.get(include=["metadatas"])
    except Exception:
      continue
    for meta in data.get("metadatas") or []:
      if not isinstance(meta, dict):
        continue
      src = meta.get("source")
      if isinstance(src, str) and src:
        sources_seen.add(src)
        # outputs/research store path-style sources; also add basename
        sources_seen.add(Path(src).name)

  missing: list[str] = []
  for p in recent:
    keys = {p.name}
    if RESEARCH_DIR in p.parents:
      try:
        keys.add(str(p.relative_to(RESEARCH_DIR)))
      except ValueError:
        pass
    if not (keys & sources_seen):
      missing.append(str(p))

  if not missing:
    return {
      "status": PASS,
      "summary": f"all {len(recent)} recent notes appear in ChromaDB",
    }
  return {
    "status": FAIL,
    "summary": f"{len(missing)} recent note(s) not yet indexed",
    "details": missing[:50],
    "total": len(missing),
    "remediation": "run `python3 ~/Desktop/claude/tools/memory_search.py index`",
  }


# -----------------------------------------------------------------------------
# Subcommand handlers
# -----------------------------------------------------------------------------


CHECKS = [
  ("1_broken_symlinks",    check_broken_symlinks,      True), # safe
  ("2_stale_lockfiles",    check_stale_lockfiles,      True),
  ("3_empty_files",      check_empty_files,        False),
  ("4_chroma_orphans",    check_chroma_orphans,      True),
  ("5_chroma_lock",      check_chroma_lock,        True),
  ("6_memory_md_size",    check_memory_md_size,      False),
  ("7_claude_md_size",    check_claude_md_size,      False),
  ("8_pupsik_privacy",    check_pupsik_privacy,      False),
]

ORPHAN_CHECKS = [
  ("9_feedback_in_critical_rules",  orphan_feedback_in_critical_rules),
  ("10_feedback_in_memory_md",    orphan_feedback_in_memory_md),
  ("11_dangling_pointers",      orphan_dangling_pointers),
  ("12_dead_scheduled_tasks",    orphan_dead_scheduled_tasks),
  ("13_unindexed_recent_notes",   orphan_unindexed_recent_notes),
]

# Map check_name -> (fix_function). Only checks that flagged "fixable" in spec.
SAFE_FIXES = [
  ("1_broken_symlinks",  fix_broken_symlinks),
  ("2_stale_lockfiles",  fix_stale_lockfiles),
  ("4_chroma_orphans",  fix_chroma_orphans),
  ("5_chroma_lock",    fix_chroma_lock),
]


def run_check(json_output: bool) -> int:
  results = [_safe(name, fn) for (name, fn, _) in CHECKS]
  summary = {
    "command": "check",
    "timestamp": _now(),
    "totals": {
      "PASS": sum(1 for r in results if r.get("status") == PASS),
      "FAIL": sum(1 for r in results if r.get("status") == FAIL),
      "WARN": sum(1 for r in results if r.get("status") == WARN),
      "SKIP": sum(1 for r in results if r.get("status") == SKIP),
    },
    "checks": results,
  }
  if json_output:
    print(json.dumps(summary, indent=2, default=str))
  else:
    _print_check_human(summary)
  # Always exit 0 (cron-safe)
  return 0


def _print_check_human(summary: dict) -> None:
  t = summary["totals"]
  print(f"doctor.py check at {summary['timestamp']}")
  print(f" PASS={t['PASS']} FAIL={t['FAIL']} WARN={t['WARN']} SKIP={t['SKIP']}")
  print()
  for r in summary["checks"]:
    status = r.get("status", "?")
    marker = {
      PASS: "[PASS]",
      FAIL: "[FAIL]",
      WARN: "[WARN]",
      SKIP: "[SKIP]",
    }.get(status, "[?]  ")
    print(f"{marker} {r.get('check')}: {r.get('summary', '')}")
    if status in (FAIL, WARN) and r.get("details"):
      details = r["details"]
      if isinstance(details, list):
        for d in details[:8]:
          if isinstance(d, dict):
            print(f"    {d}")
          else:
            print(f"    {d}")
        if len(details) > 8:
          print(f"    ... and {len(details) - 8} more")
      elif isinstance(details, dict):
        print(f"    {details}")


def run_fix_safe(dry_run: bool, json_output: bool) -> int:
  fix_results: list[dict] = []
  for (name, fn) in SAFE_FIXES:
    try:
      fix_results.append({"check": name, **fn(dry_run)})
    except Exception as exc: # noqa: BLE001
      fix_results.append({
        "check": name,
        "fix": name,
        "error": repr(exc),
        "dry_run": dry_run,
        "actions": [],
      })
  summary = {
    "command": "fix-safe",
    "dry_run": dry_run,
    "timestamp": _now(),
    "fixes": fix_results,
  }
  if json_output:
    print(json.dumps(summary, indent=2, default=str))
  else:
    _print_fix_human(summary)
  return 0


def _print_fix_human(summary: dict) -> None:
  print(
    f"doctor.py fix-safe ({'dry-run' if summary['dry_run'] else 'live'})"
    f" at {summary['timestamp']}"
  )
  for fix in summary["fixes"]:
    actions = fix.get("actions", [])
    n = fix.get("count", len(actions))
    print(f" {fix.get('check', fix.get('fix'))}: {n} action(s)")
    for a in actions[:5]:
      print(f"   {a}")
    if len(actions) > 5:
      print(f"   ... and {len(actions) - 5} more")


def run_orphans(json_output: bool) -> int:
  results = [_safe(name, fn) for (name, fn) in ORPHAN_CHECKS]
  summary = {
    "command": "orphans",
    "timestamp": _now(),
    "checks": results,
    "totals": {
      "PASS": sum(1 for r in results if r.get("status") == PASS),
      "FAIL": sum(1 for r in results if r.get("status") == FAIL),
      "WARN": sum(1 for r in results if r.get("status") == WARN),
      "SKIP": sum(1 for r in results if r.get("status") == SKIP),
    },
  }
  if json_output:
    print(json.dumps(summary, indent=2, default=str))
  else:
    _print_check_human(summary)
  return 0


def build_parser() -> argparse.ArgumentParser:
  p = argparse.ArgumentParser(
    prog="doctor.py",
    description=(
      "Deterministic health-check + safe-auto-fix for Misha's system. "
      "Adapted from gbrain (MIT)."
    ),
  )
  sub = p.add_subparsers(dest="cmd", required=True)

  pc = sub.add_parser("check", help="Read-only diagnostics. Exit 0 even on FAIL.")
  pc.add_argument("--json", action="store_true", help="Emit JSON output.")

  pf = sub.add_parser("fix-safe", help="Apply SAFE auto-fixes (default: live).")
  pf.add_argument("--dry-run", action="store_true",
          help="Show what would happen without acting.")
  pf.add_argument("--json", action="store_true", help="Emit JSON output.")

  po = sub.add_parser("orphans", help="List orphan entities (read-only).")
  po.add_argument("--json", action="store_true", help="Emit JSON output.")

  return p


def main(argv: list[str] | None = None) -> int:
  parser = build_parser()
  args = parser.parse_args(argv)
  json_output = bool(getattr(args, "json", False))
  if args.cmd == "check":
    return run_check(json_output)
  if args.cmd == "fix-safe":
    return run_fix_safe(bool(args.dry_run), json_output)
  if args.cmd == "orphans":
    return run_orphans(json_output)
  parser.error(f"unknown command: {args.cmd}")
  return 2


if __name__ == "__main__":
  sys.exit(main())
