# dashboard

A six-tab single-page HTML dashboard for your morning routine. Pulls live state from existing workspace artifacts; no server required.

## What it shows

- **01 Today** — the latest briefing markdown (`briefings/briefing-{today}.md`). If no briefing exists for today's date, the most recent one is shown **with a visible STALE note** (in the tab and in the subtitle) — the dashboard never silently presents yesterday's agenda as today's.
- **02 Projects** — the `## Active Projects` section of `CLAUDE.md`, rendered as a 3-column grid of cards with checkboxes
- **03 Upcoming** — the `## Upcoming` section of `CLAUDE.md`, same card layout
- **04 Pulse** — curated industry narrative from `dashboard/pulse-deep.md` if present, falling back to the briefing's `## Pulse` section
- **05 Architect** — a **"What's new in pupsik"** panel at the top (from `state/pupsik/update-status.json`, written by `tools/check-update.sh`), above `memory/architect_proposals/latest.md` (your open backlog). The panel shows what changed since you installed and copies the one-command update to your clipboard. `build.py` only **reads** the status JSON — it makes no network call; the git-fetch lives in `check-update.sh`. Missing/malformed JSON degrades to a quiet line. See [`docs/UPDATE_PUPSIK.md`](../docs/UPDATE_PUPSIK.md).
- **06 Knowledge** — the last 7 days of `memory/decisions/` and `memory/learnings/` entries

The header carries a **pupsik** wordmark (rounded system font + brand gradient, no external/CDN font) with a quiet byline linking to `github.com/mishalyalin/pupsik`. The `favicon.svg`, `mask-icon`, and `theme-color` are intentionally left untouched — they're byte-checked by `scripts/brand-os-visual-gate.sh`.

## Run

```bash
python3 dashboard/build.py
```

Writes `dashboard/index.html`. Open it in any browser.

Linked assets (`styles.css`, `favicon.svg`) carry a `?v=<build-timestamp>` cache-buster, so every rebuild serves fresh CSS/favicon — no stale styles lingering behind a browser cache until a manual hard-reload (this matters once you push the dashboard to a VPS).

For a one-liner that rebuilds and opens:

```bash
bash scripts/morning-dashboard.sh
```

`install.sh` also wires a `dash` shortcut into `~/.local/bin/` if that directory is on your PATH.

## Checkboxes

Each Projects + Upcoming card has a checkbox in the top-right corner. Click it and the card fades, the title gets a strikethrough, and the card relocates to a collapsed "closed" zone at the bottom of the section.

State is stored in `localStorage`, keyed by a stable hash of section + card title. It persists across page reloads and across days. The only ways a card "comes back":

- you uncheck it manually
- the title in `CLAUDE.md` changes (which yields a new card hash → fresh card)
- you click **reset**, which wipes the persistent state

The toolbar at the top of the page also has **export state** — downloads `dashboard-closed.json` listing every closed card id with its first-checked timestamp. Drop the file in `state/dashboard/` and your morning-briefing skill can pick it up to update trackers and `CLAUDE.md` automatically.

### Trust, but verify the ticks

A checkbox records that you *believe* you did the thing — humans mis-remember. `templates/scheduled-tasks/verify-ticks.md.template` is an optional, **manual-only** agent skill that takes the exported closed state and verifies each checked item against your real communications (sent mail + chat read-MCPs), returning per-item verdicts: ✅ verified (with a quoted message as evidence), ⚠️ no evidence found, or ℹ️ not verifiable. It never runs on a schedule and never invents proof.

## Pulse — deep research

Want richer Pulse content than the briefing's summary? Generate it separately via an agent (WebSearch competitors + new launches + interviews + case studies) and write the output to `dashboard/pulse-deep.md`. `build.py` prefers that file over the briefing extract.

Use `DASHBOARD_PULSE_HEADERS` env var to point at a different section heading in your briefing if you don't use `## Pulse`:

```bash
DASHBOARD_PULSE_HEADERS="📰 My Industry Pulse|Industry Pulse" python3 dashboard/build.py
```

## Status keywords

Words like `DELIVERED`, `OVERDUE`, `PAID`, `BLOCKED`, `ACTIVE` get highlighted inline as small monospace pills so your eye catches state at a glance. Override the list with `DASHBOARD_STATUS_KEYWORDS` (comma-separated) — useful if your CLAUDE.md uses other vocabulary:

```bash
DASHBOARD_STATUS_KEYWORDS="SHIPPED,WAITING,SIGNED,READY" python3 dashboard/build.py
```

## Optional: push to VPS for Telegram-web bookmark

Want the dashboard accessible from your phone via Telegram? Push the rebuilt HTML to your own VPS behind a secret-path token, bookmark the URL in Telegram web.

1. On your VPS: generate a random token (`python3 -c "import secrets; print(secrets.token_hex(16))"`), create `/var/www/m-<token>/`, add a `location /m-<token>/ { alias /var/www/m-<token>/; }` block to your nginx config behind HTTPS.
2. On your laptop: export the VPS target so `morning-dashboard.sh` syncs after each build.

```bash
export DASHBOARD_VPS_HOST="root@your.vps.tld"
export DASHBOARD_VPS_PATH="/var/www/m-<token>/"
export DASHBOARD_VPS_URL="https://your.vps.tld/m-<token>/"   # optional: enables the smoke test
bash scripts/morning-dashboard.sh
```

The URL `https://your.vps.tld/m-<token>/` is unguessable unless leaked. Use `X-Robots-Tag: noindex` in your nginx block to keep search engines out.

Two deploy-reliability details baked into the script:

- **`rsync --chmod=D755,F644`** — forces web-readable permissions on the VPS. Without it, `rsync -a` faithfully preserves a local `600` on `styles.css` or `favicon.svg`, nginx serves 403, and the dashboard loads *unstyled* with no error anywhere on the laptop side.
- **Post-deploy smoke test** — when `DASHBOARD_VPS_URL` is set, the script curls each shipped asset (`index.html`, `styles.css`, `favicon.svg`) and expects HTTP 200. "Uploaded" is not "served": a 403/404 here catches perms, nginx-alias, and cert problems the moment they happen instead of the next time you open the bookmark on your phone.

## Design

- **Structure** — six tabs, markdown-in HTML-out, Python stdlib only, no server. Pattern adapted from [ilyyyyyyya/suma-starter](https://github.com/ilyyyyyyya/suma-starter) (clean-room — source repo carries no LICENSE at time of adaptation).
- **Aesthetic** — cream `#faf8f3` background, charcoal `#1a1a1a` text, numbered section chips (`01 / 02 / 03`), monospace for commands, no emojis. Vocabulary adapted from [impeccable.style](https://impeccable.style/).
- **Favicon** — red rounded square with cream "P". Default colour is `#DD3D1F`; edit `dashboard/favicon.svg` to change it.

## Files

```
dashboard/
  build.py        - renderer (Python stdlib only)
  styles.css      - the visual layer
  favicon.svg     - default red "P" mark
  NOTICE.md       - attribution
  README.md       - this file
  index.html      - generated output (rebuilt each run)

scripts/
  morning-dashboard.sh  - one-shot launcher
```
