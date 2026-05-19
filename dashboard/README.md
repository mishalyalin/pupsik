# dashboard

A six-tab single-page HTML dashboard for your morning routine. Pulls live state from existing workspace artifacts; no server required.

## What it shows

- **01 Today** — the latest briefing markdown (`briefings/briefing-{today}.md`)
- **02 Projects** — the `## Active Projects` section of `CLAUDE.md`, rendered as a 3-column grid of cards with checkboxes
- **03 Upcoming** — the `## Upcoming` section of `CLAUDE.md`, same card layout
- **04 Pulse** — curated industry narrative from `dashboard/pulse-deep.md` if present, falling back to the briefing's `## Pulse` section
- **05 Architect** — `memory/architect_proposals/latest.md` (your open backlog)
- **06 Knowledge** — the last 7 days of `memory/decisions/` and `memory/learnings/` entries

## Run

```bash
python3 dashboard/build.py
```

Writes `dashboard/index.html`. Open it in any browser.

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
bash scripts/morning-dashboard.sh
```

The URL `https://your.vps.tld/m-<token>/` is unguessable unless leaked. Use `X-Robots-Tag: noindex` in your nginx block to keep search engines out.

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
