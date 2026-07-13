# Updating pupsik — the dashboard panel + the one-command update

pupsik ships a small "What's new in pupsik" panel at the top of your dashboard's
**Architect** tab. It shows what changed since the version you installed and
gives you a one-button way to update. This doc explains how it works and how to
turn it on, off, or drive it from Claude.

## The pieces

| Piece | What it does |
|---|---|
| `tools/update.sh` | The actual updater (git pull + smart-merge). Never touches your data. This already existed — the panel just points at it. |
| `tools/check-update.sh` | A **read-only** probe: "is my clone behind upstream?". Writes `state/pupsik/update-status.json`. Sends no data anywhere. |
| `dashboard/build.py` | Reads that JSON and renders the panel above the Architect backlog. Makes **no** network call itself. |
| `hooks/session-start-reminder.sh` | Kicks off `check-update.sh` in the background on each session start (throttled, non-blocking) so the panel stays fresh. |
| `templates/update-pupsik-skill.md.template` | An optional Claude skill so "update pupsik" runs the update for you. |

## What the panel shows

- **Behind upstream** → "⬆ What's new in pupsik — N updates since vX → vY", a list
  of the new CHANGELOG entries (version · title · summary), an **Update pupsik**
  button, and the exact command to run.
- **Up to date** → a quiet "✓ pupsik up to date vX".
- **Check hasn't run yet** → a subtle one-liner telling you how to run it.

The **Update pupsik** button copies the update command to your clipboard (the
dashboard is a static file with no server, so it can't literally run a shell —
copy-and-paste is the honest one-click). Or just tell Claude **"update pupsik"**.

## Updating

From inside your clone (this is all the button copies):

```bash
cd ~/code/pupsik && git pull && bash tools/update.sh
```

Or, with the skill installed (see below), say **"update pupsik"** in any Claude
Code session.

## The Claude skill ("update pupsik")

```bash
mkdir -p ~/.claude/skills/update-pupsik
cp templates/update-pupsik-skill.md.template ~/.claude/skills/update-pupsik/SKILL.md
# edit the {{PUPSIK_CLONE}} placeholder if your clone isn't auto-discovered
```

Then "update pupsik" runs `git pull` + `tools/update.sh` and reports what
changed. It never runs on a schedule — only when you ask.

## Privacy

The update check is a **local `git fetch`** on the clone you already have — the
same thing `git pull` does. It sends **no** information about you anywhere. If
run outside a git clone it falls back to a read-only GET of two public files
(`VERSION` + `CHANGELOG.md`) from `raw.githubusercontent.com`. Still nothing
about you leaves the machine. This keeps pupsik's "Local. No telemetry, no cloud
sync" promise intact.

**Opt out** entirely:

```bash
export PUPSIK_NO_UPDATE_CHECK=1   # in your shell profile
```

With that set, `check-update.sh` does nothing and the panel simply shows
"check hasn't run yet".

## Throttling

`check-update.sh` skips the network if it already checked within the last 6
hours (it looks at the mtime of `update-status.json`). Force a fresh check with
`PUPSIK_FORCE_CHECK=1 bash tools/check-update.sh`.

## Weekly cron (optional)

If you already run the optional weekly auto-update cron (see the README's
"Staying up to date"), `tools/update.sh` refreshes the installed-version marker
on every run, so the panel updates itself. You can also add a lighter
check-only cron that just refreshes the panel without pulling:

```
# Every day at 08:00 local — refresh the "What's new" panel (no pull).
0 8 * * * cd ~/code/pupsik && bash tools/check-update.sh >/dev/null 2>&1
```
