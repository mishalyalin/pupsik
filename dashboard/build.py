#!/usr/bin/env python3
"""
Morning dashboard. Markdown-in, HTML-out. Python stdlib only.

Pulls from existing workspace artifacts:
  01 Today      <- briefings/briefing-{today}.md   (fallback: most recent)
  02 Projects   <- CLAUDE.md ## Active Projects        (cards w/ checkboxes)
  03 Upcoming   <- CLAUDE.md ## Upcoming               (cards w/ checkboxes)
  04 Pulse      <- dashboard/pulse-deep.md OR briefing ## Pulse section
  05 Architect  <- memory/architect_proposals/latest.md
  06 Knowledge  <- memory/decisions/ + memory/learnings/ (last 7 days)

Checkbox state is persistent in browser localStorage (keyed by stable card
hash, no date prefix - checking a card keeps it checked until uncheck/reset).
Export button downloads dashboard-closed.json into Downloads/; drop the file
in <workspace>/state/dashboard/ for Claude to pick up at next briefing run.

Design language:
  Structure  - six-tab markdown-in pattern adapted from suma-starter
               (github.com/ilyyyyyyya/suma-starter, no LICENSE in source repo;
               this is a clean-room reimplementation of the structural pattern).
  Aesthetic  - impeccable.style numbered-section motif: cream background,
               charcoal text, numbered chips as primary visual rhythm, generous
               whitespace, monospace for commands, no emojis.

Run:  python3 <workspace>/dashboard/build.py
"""

from __future__ import annotations

import datetime as dt
import hashlib
import html
import json
import os
import re
import sys
from pathlib import Path

WORKSPACE = Path(os.environ.get("CLAUDE_WORKSPACE", str(Path.home() / "Desktop" / "claude")))
BRIEFINGS_DIR = WORKSPACE / "briefings"
DECISIONS_DIR = WORKSPACE / "memory" / "decisions"
LEARNINGS_DIR = WORKSPACE / "memory" / "learnings"
ARCHITECT_FILE = WORKSPACE / "memory" / "architect_proposals" / "latest.md"
CLAUDE_MD = WORKSPACE / "CLAUDE.md"
DIGEST_DIR = Path("/tmp")
CLOSED_STATE_DIR = WORKSPACE / "state" / "dashboard"

OUT_DIR = WORKSPACE / "dashboard"
OUT_HTML = OUT_DIR / "index.html"
STYLES_FILE = OUT_DIR / "styles.css"

KNOWLEDGE_WINDOW_DAYS = 7
KNOWLEDGE_MAX_ITEMS = 12
NEWS_BUCKET_LIMIT = 4   # max items per bucket in News tab


# ---------- markdown parsing (minimal, focused) ----------

EMOJI_RE = re.compile(
    "["
    "\U0001F300-\U0001F9FF"  # symbols & pictographs, emoticons, transport
    "\U0001FA70-\U0001FAFF"  # extended pictographs
    "\U00002600-\U000027BF"  # misc symbols, dingbats
    "\U0001F000-\U0001F02F"  # mahjong / domino
    "\U0001F0A0-\U0001F0FF"  # playing cards
    "\U0001F100-\U0001F1FF"  # enclosed alphanum supplement (incl. regional flags, NEW sign)
    "\U0001F200-\U0001F2FF"  # enclosed ideographic supplement
    "︀-️"          # variation selectors (the orphans behind composed emoji)
    "‍"                 # zero-width joiner
    "]+",
    flags=re.UNICODE,
)


def strip_emojis(text: str) -> str:
    """Impeccable.style is emoji-free. Drop them at render time."""
    return EMOJI_RE.sub("", text)


SAFE_URL_RE = re.compile(r"^(https?://|mailto:|#|/)", re.IGNORECASE)


def safe_href(url: str) -> str:
    """Allow only http(s), mailto, fragment, or absolute-path URLs.

    Defends against `javascript:` / `data:` payloads from auto-captured notes
    in memory/decisions/ and memory/learnings/. Unsafe URLs render as plain
    text in the link label, not as a clickable anchor.
    """
    return url if SAFE_URL_RE.match(url.strip()) else ""


def inline(text: str) -> str:
    """Render inline markdown: links, bold, italic, code."""
    text = html.escape(text)
    # Inline code first so its content isn't bolded
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    # Links [text](url) - safe schemes only
    def _link_sub(m: re.Match[str]) -> str:
        label, raw = m.group(1), m.group(2)
        url = safe_href(raw)
        if not url:
            return label  # drop unsafe link, keep label as plain text
        return f'<a href="{html.escape(url, quote=True)}">{label}</a>'

    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", _link_sub, text)
    # Bold + italic
    text = re.sub(r"\*\*\*([^*]+)\*\*\*", r"<strong><em>\1</em></strong>", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<!\*)\*(?!\*)([^*\n]+?)(?<!\*)\*(?!\*)", r"<em>\1</em>", text)
    return text


def render_markdown(md: str) -> str:
    """Render a focused markdown subset. Returns HTML."""
    md = strip_emojis(md)
    lines = md.splitlines()
    out: list[str] = []
    i = 0
    in_list: str | None = None  # 'ul' or 'ol'
    in_code = False
    code_buf: list[str] = []

    def close_list() -> None:
        nonlocal in_list
        if in_list:
            out.append(f"</{in_list}>")
            in_list = None

    while i < len(lines):
        line = lines[i]

        # Fenced code
        if line.startswith("```"):
            if not in_code:
                close_list()
                in_code = True
                code_buf = []
            else:
                in_code = False
                joined = "\n".join(code_buf)
                out.append(f"<pre><code>{html.escape(joined)}</code></pre>")
                code_buf = []
            i += 1
            continue
        if in_code:
            code_buf.append(line)
            i += 1
            continue

        # Headings
        m = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
        if m:
            close_list()
            level = min(len(m.group(1)) + 1, 6)  # H1 in markdown -> H2 in dashboard (H1 reserved)
            out.append(f"<h{level}>{inline(m.group(2))}</h{level}>")
            i += 1
            continue

        # Horizontal rule
        if re.match(r"^[-*_]{3,}\s*$", line):
            close_list()
            out.append("<hr>")
            i += 1
            continue

        # Unordered list
        m = re.match(r"^\s*[-*]\s+(.+)$", line)
        if m:
            if in_list != "ul":
                close_list()
                out.append("<ul>")
                in_list = "ul"
            out.append(f"<li>{inline(m.group(1))}</li>")
            i += 1
            continue

        # Ordered list
        m = re.match(r"^\s*\d+\.\s+(.+)$", line)
        if m:
            if in_list != "ol":
                close_list()
                out.append("<ol>")
                in_list = "ol"
            out.append(f"<li>{inline(m.group(1))}</li>")
            i += 1
            continue

        # Blockquote
        if line.startswith("> "):
            close_list()
            out.append(f"<blockquote>{inline(line[2:])}</blockquote>")
            i += 1
            continue

        # Blank line
        if not line.strip():
            close_list()
            i += 1
            continue

        # Paragraph (collect adjacent non-block lines)
        close_list()
        para = [line]
        i += 1
        while i < len(lines) and lines[i].strip() and not re.match(
            r"^(#{1,6}\s|[-*_]{3,}\s*$|\s*[-*]\s|\s*\d+\.\s|>\s|```)", lines[i]
        ):
            para.append(lines[i])
            i += 1
        out.append(f"<p>{inline(' '.join(para))}</p>")

    close_list()
    if in_code and code_buf:
        out.append(f"<pre><code>{html.escape(chr(10).join(code_buf))}</code></pre>")
    return "\n".join(out)


# ---------- section extractors ----------

def read_file(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def extract_h2_section(md: str, heading: str) -> str:
    """Return the body of '## <heading>' until the next H1/H2."""
    pattern = re.compile(
        rf"^##\s+{re.escape(heading)}\s*$(.*?)(?=^#{{1,2}}\s|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    m = pattern.search(md)
    return m.group(1).strip() if m else ""


def latest_changelog_entry(md: str) -> str:
    """Return only the most recent version block under '## Last Updated'."""
    section = extract_h2_section(md, "Last Updated")
    if not section:
        return ""
    blocks = re.split(r"\n(?=\d{4}-\d{2}-\d{2}\s+v\d)", section)
    return blocks[0].strip() if blocks else section


def todays_briefing() -> tuple[str, str]:
    """Return (label, body) for today, falling back to most recent .md."""
    today = dt.date.today().isoformat()
    todays = BRIEFINGS_DIR / f"briefing-{today}.md"
    if todays.exists():
        return f"briefing-{today}.md", todays.read_text(encoding="utf-8")
    candidates = sorted(
        [p for p in BRIEFINGS_DIR.glob("briefing-*.md") if not p.name.endswith("-final.md")],
        reverse=True,
    )
    if candidates:
        return candidates[0].name, candidates[0].read_text(encoding="utf-8")
    return "no briefing found", "_No briefing file in `briefings/`._"


def recent_knowledge() -> str:
    """Last KNOWLEDGE_WINDOW_DAYS of decisions + learnings, ordered newest first."""
    cutoff = dt.date.today() - dt.timedelta(days=KNOWLEDGE_WINDOW_DAYS)
    items: list[tuple[dt.date, str, Path]] = []

    for source, label in ((DECISIONS_DIR, "decision"), (LEARNINGS_DIR, "learning")):
        if not source.exists():
            continue
        for path in source.glob("*.md"):
            m = re.match(r"^(\d{4}-\d{2}-\d{2})", path.name)
            if not m:
                continue
            try:
                d = dt.date.fromisoformat(m.group(1))
            except ValueError:
                continue
            if d >= cutoff:
                items.append((d, label, path))

    items.sort(key=lambda x: x[0], reverse=True)
    items = items[:KNOWLEDGE_MAX_ITEMS]

    if not items:
        return "_No decisions or learnings captured in the last "f"{KNOWLEDGE_WINDOW_DAYS} days._"

    lines: list[str] = []
    for d, label, path in items:
        title = path.stem
        # strip date prefix and trailing slug fragments for readability
        title = re.sub(r"^\d{4}-\d{2}-\d{2}-", "", title)
        title = title.replace("-", " ")
        lines.append(f"- **{d.isoformat()}** [{label}] {title}")
    return "\n".join(lines)


# ---------- card-list renderer (for Projects + Upcoming) ----------

CARD_LEDE_CHARS = 320
STATUS_KEYWORDS = (
    # Status words highlighted inline as small monospace pills so the eye
    # picks up state at a glance. Customise by overriding the env var
    # DASHBOARD_STATUS_KEYWORDS (comma-separated) or editing this tuple.
    "DELIVERED", "DONE", "PAID", "ACTIVE", "SHIPPED", "LOCKED",
    "CONFIRMED", "RESOLVED", "REJECTED",
    "BLOCKED", "OVERDUE", "PENDING", "MISSED", "ESCALATED",
    "STILL OUTSTANDING",
)
_env_kws = os.environ.get("DASHBOARD_STATUS_KEYWORDS", "").strip()
if _env_kws:
    STATUS_KEYWORDS = tuple(k.strip() for k in _env_kws.split(",") if k.strip())


def split_card_items(md: str) -> list[str]:
    """Split a markdown numbered/bulleted block into individual items.

    Each item starts with '1. ' / '2. ' / etc., OR '- '. Returns raw
    item bodies (without the bullet prefix).
    """
    md = strip_emojis(md).strip()
    if not md:
        return []
    # Greedy split on bullet starts at column 0
    parts = re.split(r"\n(?=(?:\d+\.\s|\-\s+))", md)
    items: list[str] = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        # strip bullet
        part = re.sub(r"^(?:\d+\.\s|\-\s+)", "", part)
        items.append(part)
    return items


def clean_title(t: str) -> str:
    """Collapse whitespace + strip trailing dashes/periods/commas left over after
    emoji stripping or markdown noise."""
    t = re.sub(r"\s+", " ", t).strip()
    t = t.rstrip(" .,;:-—")
    return t


def extract_card_title_and_body(item: str) -> tuple[str, str]:
    """From '**Name** - rest of content' return ('Name', 'rest of content').

    Falls back to first ~60 chars if no leading bold.
    """
    m = re.match(r"^\*\*([^*]+)\*\*\s*[-—]?\s*(.*)$", item, re.DOTALL)
    if m:
        return clean_title(m.group(1)), m.group(2).strip()
    # no leading bold - take first sentence or 60 chars
    first = item.split(". ", 1)
    if len(first) == 2 and len(first[0]) < 80:
        return clean_title(first[0]), first[1].strip()
    return clean_title(item[:60]) + ("..." if len(item) > 60 else ""), item


def highlight_status(html_text: str) -> str:
    """Wrap status keywords in a subtle status pill so the eye finds state fast."""
    for kw in STATUS_KEYWORDS:
        html_text = re.sub(
            rf"\b{re.escape(kw)}\b",
            f'<span class="status">{kw}</span>',
            html_text,
        )
    return html_text


def card_id(section: str, title: str) -> str:
    """Stable id for a card so localStorage + Claude-side state survive across rebuilds."""
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:50]
    h = hashlib.sha256(f"{section}|{title}".encode()).hexdigest()[:8]
    return f"{section}-{slug}-{h}"


def render_card_list(md: str, section: str) -> str:
    """Render Projects / Upcoming as scannable cards.

    Each card: title (bold name) + lede (~320 chars) + collapsible detail.
    Status keywords highlighted inline so 'ЗАВЕРШЕНО / OVERDUE / ACTIVE' jump out.
    Each card carries data-card-id so JS can hydrate checkbox state from localStorage.
    Output wraps cards in an active-zone (3-col grid) plus a collapsible
    closed-zone at bottom; JS moves checked cards between zones.
    """
    items = split_card_items(md)
    if not items:
        return render_markdown(md)

    cards: list[str] = []
    for order_index, raw in enumerate(items):
        title, body = extract_card_title_and_body(raw)
        cid = card_id(section, title)
        check_html = (
            f'<label class="card-check" title="mark done">'
            f'<input type="checkbox" data-card-id="{cid}">'
            f'<span class="check-glyph" aria-hidden="true"></span>'
            f"</label>"
        )

        # Short item - no need to collapse
        if len(body) <= CARD_LEDE_CHARS + 40:
            body_html = highlight_status(render_markdown(body))
            cards.append(
                f'<article class="card" data-card-id="{cid}" data-order="{order_index}">\n'
                f'  <header class="card-head">\n'
                f'    <h3 class="card-title">{html.escape(title)}</h3>\n'
                f'    {check_html}\n'
                f"  </header>\n"
                f'  <div class="card-body">{body_html}</div>\n'
                f"</article>"
            )
            continue

        # Long item - split at a sentence boundary near CARD_LEDE_CHARS
        cutoff = body.rfind(". ", 0, CARD_LEDE_CHARS)
        if cutoff < CARD_LEDE_CHARS // 2:
            cutoff = body.rfind(" ", 0, CARD_LEDE_CHARS)
        if cutoff < 0:
            cutoff = CARD_LEDE_CHARS
        lede = body[: cutoff + 1].strip()
        rest = body[cutoff + 1 :].strip()

        lede_html = highlight_status(render_markdown(lede))
        rest_html = highlight_status(render_markdown(rest))

        cards.append(
            f'<article class="card" data-card-id="{cid}" data-order="{order_index}">\n'
            f'  <header class="card-head">\n'
            f'    <h3 class="card-title">{html.escape(title)}</h3>\n'
            f'    {check_html}\n'
            f"  </header>\n"
            f'  <div class="card-lede">{lede_html}</div>\n'
            f"  <details class=\"card-detail\">\n"
            f"    <summary>more</summary>\n"
            f"    {rest_html}\n"
            f"  </details>\n"
            f"</article>"
        )

    # active zone is a 3-col grid; closed zone is a collapsed details/summary
    # at the bottom. JS moves cards between zones on check/uncheck.
    return (
        f'<div class="card-zones" data-section="{section}">\n'
        f'  <div class="cards active-zone">\n'
        + "\n".join(cards)
        + "\n  </div>\n"
        f'  <details class="closed-zone" hidden>\n'
        f'    <summary><span class="closed-zone-count">0</span> closed - click to expand</summary>\n'
        f'    <div class="cards closed-cards"></div>\n'
        f"  </details>\n"
        f"</div>"
    )


# ---------- Pulse tab (curated industry narrative) ----------
# Source priority: dashboard/pulse-deep.md > briefing's ## Pulse section.
# Customise PULSE_HEADERS env var if your briefing uses a different heading.

PULSE_HEADERS = [
    "📰 Pulse",
    "Pulse",
    "📰 Internet Pulse",
    "Internet Pulse",
]
_env_headers = os.environ.get("DASHBOARD_PULSE_HEADERS", "").strip()
if _env_headers:
    PULSE_HEADERS = [h.strip() for h in _env_headers.split("|") if h.strip()]


def extract_pulse_section(briefing_md: str) -> str:
    """Return body of '## 📰 PranaSalt Internet Pulse' section from briefing.

    The morning-briefing skill curates this section with PranaSalt context
    applied: competitor moves, product launches, regulatory shifts, supplier
    signals, channel partners. Each insight has reasoning + cited sources.
    Raw HN/Reddit keyword dumps are intentionally NOT here - that's noise.
    """
    for header in PULSE_HEADERS:
        # Match `## <header>` (with optional trailing decoration like "(week)")
        # up to the next H2.
        pattern = re.compile(
            rf"^##\s+{re.escape(header)}[^\n]*$(.*?)(?=^##\s|\Z)",
            re.MULTILINE | re.DOTALL,
        )
        m = pattern.search(briefing_md)
        if m:
            return m.group(1).strip()
    return ""


def fallback_pulse_from_recent_briefings() -> tuple[str, str]:
    """If today's briefing has no Pulse section yet, scan recent briefings."""
    candidates = sorted(
        BRIEFINGS_DIR.glob("briefing-*.md"), reverse=True
    )
    for path in candidates[:5]:
        if path.name.endswith("-final.md"):
            continue
        body = read_file(path)
        pulse = extract_pulse_section(body)
        if pulse:
            return path.name, pulse
    return "", ""


PULSE_DEEP_FILE = OUT_DIR / "pulse-deep.md"


def render_pulse_section() -> str:
    """Pulse tab - curated industry narrative.

    Source priority:
      1. dashboard/pulse-deep.md - explicit deep-research output (preferred)
      2. briefings/briefing-{today}.md ## 📰 PranaSalt Internet Pulse section
      3. fallback: most recent briefing with a Pulse section
    """
    # 1. Deep-research file (preferred)
    if PULSE_DEEP_FILE.exists():
        try:
            deep = PULSE_DEEP_FILE.read_text(encoding="utf-8").strip()
            if deep:
                mtime = dt.datetime.fromtimestamp(
                    PULSE_DEEP_FILE.stat().st_mtime
                ).strftime("%Y-%m-%d %H:%M")
                meta = (
                    f'<p class="pulse-meta">source: <code>pulse-deep.md</code> '
                    f"&middot; updated {html.escape(mtime)}</p>"
                )
                # The deep file already starts with `## Pulse - deep`, so strip
                # leading H2 to avoid heading-duplication with the section chip.
                deep_body = re.sub(r"^##\s+Pulse[^\n]*\n+", "", deep, count=1)
                body_html = render_markdown(deep_body)
                return f'{meta}\n<div class="pulse-body">{body_html}</div>'
        except OSError:
            pass

    # 2. Today's briefing Pulse section
    today_label, today_body = todays_briefing()
    pulse = extract_pulse_section(today_body) if today_body else ""
    source_label = today_label

    if not pulse:
        # 3. Most recent briefing with a Pulse section
        fallback_label, fallback_pulse = fallback_pulse_from_recent_briefings()
        if fallback_pulse:
            pulse = fallback_pulse
            source_label = f"{fallback_label} (today's briefing has no Pulse section)"

    if not pulse:
        return (
            "<p>No Pulse content available. Generate via deep-research worker "
            "writing to <code>dashboard/pulse-deep.md</code>, or run morning-briefing "
            "to populate the briefing's <code>## 📰 PranaSalt Internet Pulse</code> "
            "section.</p>"
        )

    meta = (
        f'<p class="pulse-meta">source: <code>{html.escape(source_label)}</code></p>'
    )
    body_html = render_markdown(pulse)
    return f'{meta}\n<div class="pulse-body">{body_html}</div>'


# ---------- closed-state log (for Claude to see what Misha checked off) ----------

def previously_closed_today() -> list[str]:
    """Return persistent closed card_ids from state/dashboard/.

    Persistent state file: `dashboard-closed.json` (no date - state survives
    across days until Misha unchecks the card or it disappears from CLAUDE.md).
    Legacy dated files `dashboard-closed-YYYY-MM-DD.json` are still merged for
    backwards compat (one-time pickup; archive happens via morning-briefing).
    """
    closed_ids: set[str] = set()
    # Persistent
    persistent = CLOSED_STATE_DIR / "dashboard-closed.json"
    if persistent.exists():
        try:
            data = json.loads(persistent.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                closed_ids.update(data.get("closed", []))
            elif isinstance(data, list):
                closed_ids.update(data)
        except (OSError, json.JSONDecodeError):
            pass
    # Legacy dated files (merged but never wiped here)
    for legacy in CLOSED_STATE_DIR.glob("dashboard-closed-*.json"):
        try:
            data = json.loads(legacy.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                closed_ids.update(data.get("closed", []))
            elif isinstance(data, list):
                closed_ids.update(data)
        except (OSError, json.JSONDecodeError):
            continue
    return sorted(closed_ids)


# ---------- HTML assembly ----------

SECTIONS = [
    ("01", "Today", "today"),
    ("02", "Projects", "projects"),
    ("03", "Upcoming", "upcoming"),
    ("04", "Pulse", "pulse"),
    ("05", "Architect", "architect"),
    ("06", "Knowledge", "knowledge"),
]

# Sections rendered as scannable cards instead of straight markdown.
CARD_SECTIONS = {"projects", "upcoming"}


def build_html() -> str:
    claude_md = read_file(CLAUDE_MD)

    today_label, today_body = todays_briefing()
    projects_body = extract_h2_section(claude_md, "Active Projects")
    upcoming_body = extract_h2_section(claude_md, "Upcoming")
    architect_body = read_file(ARCHITECT_FILE)
    knowledge_body = recent_knowledge()

    bodies = {
        "today": today_body or "_No briefing for today._",
        "projects": projects_body or "_No Active Projects section._",
        "upcoming": upcoming_body or "_No Upcoming section._",
        "pulse": "",  # rendered by render_pulse_section() below
        "architect": architect_body or "_No architect_proposals/latest.md._",
        "knowledge": knowledge_body,
    }
    closed_today = previously_closed_today()

    # subtitle line
    today = dt.date.today()
    weekday = today.strftime("%A")
    subtitle = f"{weekday}, {today.isoformat()}  -  source: {today_label}"

    nav_html = "\n".join(
        f'<a class="nav-item" href="#{anchor}"><span class="num">{num}</span>'
        f'<span class="label">{label}</span></a>'
        for num, label, anchor in SECTIONS
    )

    sections_html_parts: list[str] = []
    for num, label, anchor in SECTIONS:
        body_md = bodies[anchor]
        if anchor == "pulse":
            body_html = render_pulse_section()
        elif anchor in CARD_SECTIONS:
            body_html = render_card_list(body_md, anchor)
        else:
            body_html = render_markdown(body_md)
        sections_html_parts.append(
            f'<section id="{anchor}" class="section">\n'
            f'  <header class="section-head">\n'
            f'    <span class="chip">{num}</span>\n'
            f'    <h2>{label}</h2>\n'
            f"  </header>\n"
            f'  <div class="section-body">\n{body_html}\n  </div>\n'
            f"</section>"
        )
    sections_html = "\n\n".join(sections_html_parts)

    build_ts = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    today_iso = today.isoformat()
    preloaded_closed_json = json.dumps(closed_today)

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Dashboard - {today_iso}</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="icon" type="image/svg+xml" href="favicon.svg">
<link rel="mask-icon" href="favicon.svg" color="#DD3D1F">
<meta name="theme-color" content="#DD3D1F">
<link rel="stylesheet" href="styles.css">
</head>
<body>
<main class="page">
  <header class="masthead">
    <h1>Dashboard</h1>
    <p class="subtitle">{html.escape(subtitle)}</p>
  </header>

  <nav class="tabs">
    {nav_html}
  </nav>

  <div class="closed-strip" id="closed-strip" hidden>
    <span class="closed-count" id="closed-count">0</span>
    <span class="closed-label">closed (persistent)</span>
    <button type="button" class="export-btn" id="export-btn">export state</button>
    <button type="button" class="reset-btn" id="reset-btn">reset</button>
  </div>

  {sections_html}

  <footer class="foot">
    <p>built {build_ts}  -  python3 dashboard/build.py</p>
  </footer>
</main>

<script>
(function() {{
  var TODAY = "{today_iso}";
  // Persistent storage: state is keyed by card_id (which is a stable
  // SHA256 of section+title). No date prefix - if Misha checked something
  // last week, it stays checked until he unchecks it. The card resurfaces
  // only if its title changes in CLAUDE.md (which yields a new card_id).
  var STORAGE_PREFIX = "dash-closed-";
  var PRELOADED_CLOSED = {preloaded_closed_json};

  // One-time migration: any old date-scoped keys "dash-closed-YYYY-MM-DD-<id>"
  // collapse into the new undated form "dash-closed-<id>".
  (function migrateDatedKeys() {{
    var migrated = 0;
    for (var i = localStorage.length - 1; i >= 0; i--) {{
      var key = localStorage.key(i);
      if (!key) continue;
      // Match "dash-closed-YYYY-MM-DD-<rest>"
      var m = key.match(/^dash-closed-(\\d{{4}}-\\d{{2}}-\\d{{2}})-(.+)$/);
      if (m) {{
        var id = m[2];
        var ts = localStorage.getItem(key);
        var newKey = STORAGE_PREFIX + id;
        if (!localStorage.getItem(newKey)) {{
          localStorage.setItem(newKey, ts || new Date().toISOString());
          migrated++;
        }}
        localStorage.removeItem(key);
      }}
    }}
    if (migrated > 0) console.log("[dash] migrated", migrated, "dated keys -> persistent");
  }})();

  // Merge any preloaded (server-side) closed ids into localStorage.
  PRELOADED_CLOSED.forEach(function(id) {{
    if (!localStorage.getItem(STORAGE_PREFIX + id)) {{
      localStorage.setItem(STORAGE_PREFIX + id, new Date().toISOString());
    }}
  }});

  function allClosedIds() {{
    var ids = [];
    for (var i = 0; i < localStorage.length; i++) {{
      var key = localStorage.key(i);
      // Exclude any leftover dated keys; only undated count.
      if (key && key.indexOf(STORAGE_PREFIX) === 0
          && !/^dash-closed-\\d{{4}}-\\d{{2}}-\\d{{2}}-/.test(key)) {{
        ids.push(key.slice(STORAGE_PREFIX.length));
      }}
    }}
    return ids;
  }}

  function applyCardState(card, isClosed) {{
    if (isClosed) card.classList.add("card-closed");
    else card.classList.remove("card-closed");
  }}

  // Move a card into its section's closed-zone (appended in checked-order).
  function moveToClosedZone(card) {{
    var zones = card.closest(".card-zones");
    if (!zones) return;
    var closedCards = zones.querySelector(".closed-cards");
    if (closedCards && card.parentNode !== closedCards) {{
      closedCards.appendChild(card);
    }}
    updateClosedZone(zones);
  }}

  // Move a card back into active-zone at its original sorted slot
  // (preserves the source-document order so re-opens land in the right place).
  function moveToActiveZone(card) {{
    var zones = card.closest(".card-zones");
    if (!zones) return;
    var active = zones.querySelector(".active-zone");
    if (!active) return;
    var order = parseInt(card.getAttribute("data-order") || "0", 10);
    var siblings = Array.prototype.slice.call(active.querySelectorAll(":scope > .card"));
    var inserted = false;
    for (var i = 0; i < siblings.length; i++) {{
      var sib = siblings[i];
      var sibOrder = parseInt(sib.getAttribute("data-order") || "0", 10);
      if (sibOrder > order) {{
        active.insertBefore(card, sib);
        inserted = true;
        break;
      }}
    }}
    if (!inserted) active.appendChild(card);
    updateClosedZone(zones);
  }}

  function updateClosedZone(zones) {{
    var closedCards = zones.querySelector(".closed-cards");
    var details = zones.querySelector(".closed-zone");
    var count = zones.querySelector(".closed-zone-count");
    var n = closedCards ? closedCards.querySelectorAll(":scope > .card").length : 0;
    if (count) count.textContent = n;
    if (details) details.hidden = n === 0;
  }}

  function updateClosedStrip() {{
    var ids = allClosedIds();
    var strip = document.getElementById("closed-strip");
    var count = document.getElementById("closed-count");
    count.textContent = ids.length;
    strip.hidden = ids.length === 0;
  }}

  // Hydrate checkboxes from localStorage on load
  document.querySelectorAll(".card[data-card-id]").forEach(function(card) {{
    var id = card.getAttribute("data-card-id");
    var box = card.querySelector('input[type="checkbox"]');
    if (!box) return;
    var stored = localStorage.getItem(STORAGE_PREFIX + id);
    if (stored) {{
      box.checked = true;
      applyCardState(card, true);
      moveToClosedZone(card);
    }}
    box.addEventListener("change", function() {{
      if (box.checked) {{
        localStorage.setItem(STORAGE_PREFIX + id, new Date().toISOString());
        applyCardState(card, true);
        moveToClosedZone(card);
      }} else {{
        localStorage.removeItem(STORAGE_PREFIX + id);
        applyCardState(card, false);
        moveToActiveZone(card);
      }}
      updateClosedStrip();
    }});
  }});
  // Initialise closed-zone counters per section after hydration
  document.querySelectorAll(".card-zones").forEach(updateClosedZone);
  updateClosedStrip();

  // Export state - download dashboard-closed.json (all closed items, with
  // first-checked timestamps). Misha drops file into
  // ~/Desktop/claude/state/dashboard/ for Claude to pick up next briefing.
  document.getElementById("export-btn").addEventListener("click", function() {{
    var closed = [];
    document.querySelectorAll(".card[data-card-id]").forEach(function(card) {{
      var id = card.getAttribute("data-card-id");
      var ts = localStorage.getItem(STORAGE_PREFIX + id);
      if (ts) {{
        closed.push({{
          id: id,
          title: (card.querySelector(".card-title") || {{}}).textContent || "",
          closed_at: ts
        }});
      }}
    }});
    var payload = {{
      exported_at: new Date().toISOString(),
      closed: closed.map(function(c) {{ return c.id; }}),
      detail: closed
    }};
    var blob = new Blob([JSON.stringify(payload, null, 2)], {{type: "application/json"}});
    var url = URL.createObjectURL(blob);
    var a = document.createElement("a");
    a.href = url;
    a.download = "dashboard-closed.json";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }});

  // Reset - clears all closed items (persistent state wipe).
  document.getElementById("reset-btn").addEventListener("click", function() {{
    if (!confirm("Reset ALL closed items? This wipes the persistent checked state.")) return;
    allClosedIds().forEach(function(id) {{ localStorage.removeItem(STORAGE_PREFIX + id); }});
    document.querySelectorAll(".card[data-card-id]").forEach(function(card) {{
      var box = card.querySelector('input[type="checkbox"]');
      if (box) box.checked = false;
      applyCardState(card, false);
      moveToActiveZone(card);
    }});
    document.querySelectorAll(".card-zones").forEach(updateClosedZone);
    updateClosedStrip();
  }});
}})();
</script>
</body>
</html>
"""


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    html_out = build_html()
    OUT_HTML.write_text(html_out, encoding="utf-8")
    size_kb = OUT_HTML.stat().st_size / 1024
    print(f"wrote {OUT_HTML}  ({size_kb:.1f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
