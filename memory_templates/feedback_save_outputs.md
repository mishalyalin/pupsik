---
name: Save all generated files to ~/Desktop/claude/outputs/ with date prefix
description: Every generated file (reports, emails, exports, images) goes to `~/Desktop/claude/outputs/YYYY-MM-DD-<topic>/`. Never drop files in root or random paths.
type: feedback
---

# Save outputs to `outputs/` with date prefix

All generated artifacts land in `~/Desktop/claude/outputs/`.

## Naming convention

```
~/Desktop/claude/outputs/YYYY-MM-DD-<topic>/<filename>
```

Examples:

- `~/Desktop/claude/outputs/2026-04-24-vendor-comparison/matrix.md`
- `~/Desktop/claude/outputs/2026-04-24-vendor-comparison/summary.html`
- `~/Desktop/claude/outputs/2026-04-24-morning-briefing.md` (single-file case — no subdir required)

## Rules

- **Always** prefix with today's date (`YYYY-MM-DD`) — makes chronological scanning trivial.
- **Topic slug** should be short, lowercase, hyphenated.
- Multi-file outputs go in a subdirectory under that date-topic.
- Don't drop files in the user's home, `/tmp`, `Downloads`, or project root unless explicitly told.
- Overwriting a same-day file? Fine. Overwriting an older dated file? Never.

## Why

- The user navigates outputs chronologically.
- Date-prefixed names sort cleanly in any file manager.
- Flat unstructured drops become impossible to find within a week.

## Exceptions

- Files the user explicitly asks to save elsewhere (e.g., "put the report in the project folder").
- Intermediate debug files: write to `/tmp/` and delete after.
