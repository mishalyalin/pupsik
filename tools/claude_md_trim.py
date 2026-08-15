#!/usr/bin/env python3
"""
claude_md_trim.py - Deterministic CLAUDE.md size check + rotation tool.

CLAUDE.md working-memory files grow without bound if nothing polices them -
every session appends a new fact and nothing ever leaves. Two problems compound:
a whole-file token cap that silently stops mattering once one section balloons
past it while the rest of the file stays small, and a "## Last Updated" section
that becomes a linear changelog nobody ever trims because deleting history feels
wrong (and often is - see feedback about archiving instead of deleting).

This tool does two things, both fully deterministic (no LLM calls; safe to run
unattended, in a hook, or in CI):

  check   Token-count the whole file AND every top-level `## `-heading section,
          report WARN/FAIL against soft/hard caps (default 12,000 / 20,000
          tokens, override with --soft/--hard). Always exits 0 (read-only
          diagnostic, mirrors doctor.py's `check` convention) - use --json if
          you want a script to act on the status.

  rotate  Move the CURRENT `## Last Updated` section's body verbatim into a
          dated heading in a separate changelog file, and replace it in
          CLAUDE.md with a one-line pointer to that changelog. Idempotent: a
          no-op if the section already has <=2 non-blank lines (i.e. it's
          already just a pointer). Dry-run by default - pass --apply to
          actually write. Always prints exactly what moved (or would move).

Reuses context_budget.py's estimate_tokens()/_tiktoken_encoder() for token
counting instead of duplicating that logic - see doctor.py's check_claude_md_size()
for the same reuse pattern. Falls back to an inline copy of the same heuristic
if context_budget.py isn't importable (e.g. this file copied out of tools/ on
its own).

No hardcoded personal paths: --file defaults to ./CLAUDE.md (run it from
wherever your CLAUDE.md lives, or pass --file explicitly).
"""
from __future__ import annotations

import argparse
import json as _json
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
  from context_budget import estimate_tokens as _cb_estimate_tokens
  from context_budget import _tiktoken_encoder as _cb_tiktoken_encoder
except Exception:
  _cb_estimate_tokens = None
  _cb_tiktoken_encoder = None

DEFAULT_SOFT = 12_000
DEFAULT_HARD = 20_000

PASS, WARN, FAIL = "PASS", "WARN", "FAIL"

# Top-level (##) markdown headings only - deliberately not ### or deeper, so a
# section's own subsections count toward its total rather than being reported
# separately.
_SECTION_RE = re.compile(r"^## +(.+?)\s*$", re.MULTILINE)


def _estimate_tokens(text: str) -> int:
  """Token estimate for `text`. Delegates to context_budget.py; falls back to
  an inline copy of its Cyrillic-aware chars-per-token heuristic."""
  if not text:
    return 0
  if _cb_estimate_tokens is not None:
    try:
      encoder = _cb_tiktoken_encoder() if _cb_tiktoken_encoder else None
      tokens, _method = _cb_estimate_tokens(text, encoder)
      return tokens
    except Exception:
      pass
  cyr = sum(1 for c in text if "Ѐ" <= c <= "ӿ") / len(text)
  return int(len(text) / (2.15 * cyr + 3.7 * (1 - cyr)))


def _split_sections(text: str):
  """Split `text` into a list of (heading, body_text, start, end) for each
  top-level `## ` section, in document order. Any content before the first
  `## ` heading is returned first with heading=None."""
  matches = list(_SECTION_RE.finditer(text))
  sections = []
  first_start = matches[0].start() if matches else len(text)
  if first_start > 0:
    sections.append((None, text[0:first_start], 0, first_start))
  for i, m in enumerate(matches):
    start = m.start()
    end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
    sections.append((m.group(1).strip(), text[start:end], start, end))
  return sections


def _status_for(tokens: int, soft: int, hard: int) -> str:
  if tokens > hard:
    return FAIL
  if tokens > soft:
    return WARN
  return PASS


def cmd_check(args) -> int:
  path = Path(args.file)
  if not path.exists():
    print(f"error: {path} not found", file=sys.stderr)
    return 0
  text = path.read_text(encoding="utf-8", errors="replace")
  soft, hard = args.soft, args.hard

  total = _estimate_tokens(text)
  overall = _status_for(total, soft, hard)

  section_rows = []
  for heading, body, _start, _end in _split_sections(text):
    if heading is None:
      continue
    tok = _estimate_tokens(body)
    section_rows.append({
      "heading": heading,
      "tokens": tok,
      "status": _status_for(tok, soft, hard),
    })
  flagged = [r for r in section_rows if r["status"] != PASS]

  if args.json:
    print(_json.dumps({
      "file": str(path),
      "soft": soft,
      "hard": hard,
      "total_tokens": total,
      "status": overall,
      "sections": section_rows,
    }, indent=2))
  else:
    print(f"{path}: ~{total} tokens (soft={soft}, hard={hard}) -> {overall}")
    if flagged:
      for r in flagged:
        print(f"  {r['status']}  ## {r['heading']}  (~{r['tokens']} tokens)")
    else:
      print("  no individual section exceeds the soft cap")

  return 0  # read-only diagnostic - always succeeds; check .status / --json for the verdict


def cmd_rotate(args) -> int:
  path = Path(args.file)
  if not path.exists():
    print(f"error: {path} not found", file=sys.stderr)
    return 1
  text = path.read_text(encoding="utf-8", errors="replace")

  target = None
  for heading, body, start, end in _split_sections(text):
    if heading and heading.strip().lower() == "last updated":
      target = (heading, body, start, end)
      break

  if target is None:
    print(f"no '## Last Updated' section found in {path}; nothing to rotate")
    return 0

  _heading, body, start, end = target
  # body's first line is the "## Last Updated" heading line itself.
  content_lines = body.splitlines()[1:]
  non_blank = [ln for ln in content_lines if ln.strip()]

  if len(non_blank) <= 2:
    print(f"'## Last Updated' in {path} is already <=2 lines ({len(non_blank)}); nothing to rotate")
    return 0

  today = date.today().isoformat()
  changelog_path = Path(args.changelog)
  changelog_heading = f"## {today}"
  moved_body = "\n".join(content_lines).strip("\n")

  pointer = (
    "## Last Updated\n"
    f"See `{changelog_path}` for history - entry moved there {today} by "
    "claude_md_trim.py rotate.\n"
  )
  new_text = text[:start] + pointer + text[end:]
  changelog_entry = f"\n{changelog_heading}\n\n{moved_body}\n"

  print(f"Rotating '## Last Updated' in {path} ({len(non_blank)} line(s) of content):")
  print("  -- moved body --")
  for ln in moved_body.splitlines():
    print(f"  | {ln}")
  print(f"  -> appended to {changelog_path} under '{changelog_heading}'")
  print(f"  -> {path} '## Last Updated' replaced with a one-line pointer")

  if not args.apply:
    print("\n(dry-run - pass --apply to write)")
    return 0

  changelog_path.parent.mkdir(parents=True, exist_ok=True)
  with open(changelog_path, "a", encoding="utf-8") as f:
    f.write(changelog_entry)
  path.write_text(new_text, encoding="utf-8")
  print(f"\nApplied: wrote {path} and appended to {changelog_path}.")
  return 0


def build_parser() -> argparse.ArgumentParser:
  p = argparse.ArgumentParser(
    prog="claude_md_trim.py",
    description="Deterministic CLAUDE.md token-budget check + '## Last Updated' rotation.",
  )
  p.add_argument("--file", default="./CLAUDE.md", help="Path to CLAUDE.md (default: ./CLAUDE.md)")
  sub = p.add_subparsers(dest="cmd", required=True)

  pc = sub.add_parser("check", help="Token-count whole file + each ## section vs soft/hard caps. Exit 0 even on FAIL.")
  pc.add_argument("--soft", type=int, default=DEFAULT_SOFT, help=f"Soft cap in tokens (default {DEFAULT_SOFT})")
  pc.add_argument("--hard", type=int, default=DEFAULT_HARD, help=f"Hard cap in tokens (default {DEFAULT_HARD})")
  pc.add_argument("--json", action="store_true", help="Emit JSON output.")
  pc.set_defaults(func=cmd_check)

  pr = sub.add_parser("rotate", help="Move '## Last Updated' body verbatim into a dated changelog entry.")
  pr.add_argument("--changelog", required=True, help="Path to the changelog file to append the dated entry to.")
  pr.add_argument("--apply", action="store_true", help="Actually write changes (default: dry-run, prints what would move).")
  pr.set_defaults(func=cmd_rotate)

  return p


def main(argv=None) -> int:
  args = build_parser().parse_args(argv)
  return args.func(args)


if __name__ == "__main__":
  raise SystemExit(main())
