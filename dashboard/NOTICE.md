# Dashboard - attribution

## Structure

The six-tab markdown-in HTML-out pattern is adapted from
[ilyyyyyyya/suma-starter](https://github.com/ilyyyyyyya/suma-starter)
(recon 2026-05-19). The source repo carries no LICENSE file at the time of
adaptation. This is a clean-room implementation - none of the upstream Python,
HTML, or CSS is copied. The shared idea is the structural pattern: one Python
script, six tabs, no server, source files in plain markdown.

## Aesthetic

The visual language - cream background, charcoal text, numbered section chips
(`01`, `02`, `03`, ...), generous whitespace, monospace for commands, emoji-free
copy - is adapted from [impeccable.style](https://impeccable.style/). No assets
copied. The vocabulary is what was borrowed: numbered rhythm, restraint,
sentence-case labels.

## Local files

- `build.py` - the renderer. Python stdlib only.
- `styles.css` - the visual layer.
- `index.html` - generated output (rebuilt each run).
- `NOTICE.md` - this file.

Run:

    python3 ~/Desktop/claude/dashboard/build.py

Or use the morning launcher:

    bash ~/Desktop/claude/scripts/morning-dashboard.sh
