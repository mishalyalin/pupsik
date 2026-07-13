#!/usr/bin/env bash
# check-update.sh — lightweight, fail-soft "is my pupsik behind upstream?" probe.
#
# This does NOT update anything. It only WRITES a small status file that the
# dashboard reads to render the "What's new in pupsik" panel. The actual
# update is still `tools/update.sh` (git pull + smart-merge). Think of this as
# the vitrine's data feed, not an updater.
#
#   bash tools/check-update.sh          # check (respects the 6h throttle)
#   PUPSIK_NO_UPDATE_CHECK=1 ...        # opt out entirely (does nothing)
#   PUPSIK_FORCE_CHECK=1 ...            # ignore the 6h throttle for this run
#
# PRIVACY (this is a public, "no telemetry" repo — keep it that way):
#   - The check is a LOCAL `git fetch` against the clone you already have.
#     It sends NO data about you anywhere. git fetch only asks GitHub "what is
#     origin/main?" — the same thing `git pull` does.
#   - If this file is somehow run outside a git clone, it falls back to a
#     read-only GET of two public files (VERSION + CHANGELOG.md) from
#     raw.githubusercontent.com. Still no user data leaves the machine.
#   - Opt out with PUPSIK_NO_UPDATE_CHECK=1 (documented in README).
#
# FAIL-SOFT: any git/network/parse error → write a status with `error` set and
# `behind:false`, then exit 0. This script must NEVER break a session start or
# a dashboard build.
#
# Output: <workspace>/state/pupsik/update-status.json
#   {installed, latest, behind, new_entries:[{version,title,summary}],
#    clone_path, checked_at, source:"git"|"raw"|"none", error?}

set -uo pipefail   # NOTE: deliberately no `-e` — we handle errors explicitly.

# ---------- Opt-out ----------
if [ "${PUPSIK_NO_UPDATE_CHECK:-0}" = "1" ]; then
  exit 0
fi

# ---------- Resolve workspace ----------
WORKSPACE="${CLAUDE_WORKSPACE:-${WORKSPACE:-$HOME/Desktop/claude}}"
STATE_DIR="$WORKSPACE/state/pupsik"
STATUS_JSON="$STATE_DIR/update-status.json"
mkdir -p "$STATE_DIR" 2>/dev/null || true

# ---------- Throttle: skip network if checked < 6h ago ----------
# Use the status file's mtime (portable, no date-parsing). 360 min = 6h.
if [ "${PUPSIK_FORCE_CHECK:-0}" != "1" ] && [ -f "$STATUS_JSON" ]; then
  if [ -n "$(find "$STATUS_JSON" -mmin -360 2>/dev/null)" ]; then
    exit 0
  fi
fi

# ---------- Resolve the pupsik clone ----------
# Priority: PUPSIK_CLONE env → this script's own repo root (natural when run
# from inside the clone) → clone-path.txt recorded by install.sh → none.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd)"
CLONE_PATH=""

is_pupsik_clone() {
  # $1 = candidate dir. True if it's a git repo whose origin looks like pupsik.
  local d="$1"
  [ -n "$d" ] && [ -d "$d" ] || return 1
  git -C "$d" rev-parse --git-dir >/dev/null 2>&1 || return 1
  git -C "$d" remote get-url origin 2>/dev/null | grep -qi "pupsik" || return 1
  return 0
}

for cand in \
  "${PUPSIK_CLONE:-}" \
  "$SCRIPT_DIR/.." \
  "$(cat "$STATE_DIR/clone-path.txt" 2>/dev/null || true)"
do
  if is_pupsik_clone "$cand"; then
    CLONE_PATH="$(cd "$cand" && pwd)"
    break
  fi
done

# ---------- Determine INSTALLED version ----------
# Priority: workspace marker → legacy ~/.pupsik-state → the clone's own VERSION.
INSTALLED=""
if [ -f "$STATE_DIR/installed-version.txt" ]; then
  INSTALLED="$(head -1 "$STATE_DIR/installed-version.txt" 2>/dev/null | tr -d '[:space:]')"
fi
if [ -z "$INSTALLED" ] && [ -f "$HOME/.pupsik-state/last-applied-version" ]; then
  INSTALLED="$(head -1 "$HOME/.pupsik-state/last-applied-version" 2>/dev/null | tr -d '[:space:]')"
fi
if [ -z "$INSTALLED" ] && [ -n "$CLONE_PATH" ] && [ -f "$CLONE_PATH/VERSION" ]; then
  INSTALLED="$(head -1 "$CLONE_PATH/VERSION" 2>/dev/null | tr -d '[:space:]')"
fi

# ---------- Fetch LATEST upstream VERSION + CHANGELOG ----------
SOURCE="none"
ERROR=""
LATEST=""
CHANGELOG_TMP="$(mktemp 2>/dev/null || echo "${TMPDIR:-/tmp}/pupsik-changelog.$$")"
trap 'rm -f "$CHANGELOG_TMP" 2>/dev/null || true' EXIT

RAW_BASE="https://raw.githubusercontent.com/mishalyalin/pupsik/main"

fetch_raw() {
  # $1 = url, $2 = out file. ~3s timeout. curl, else python urllib. Returns 0 on success.
  local url="$1" out="$2"
  if command -v curl >/dev/null 2>&1; then
    curl -fsSL --max-time 3 "$url" -o "$out" 2>/dev/null && [ -s "$out" ] && return 0
  fi
  python3 - "$url" "$out" <<'PYEOF' 2>/dev/null && [ -s "$out" ] && return 0
import sys, urllib.request
url, out = sys.argv[1], sys.argv[2]
try:
    with urllib.request.urlopen(url, timeout=3) as r:
        data = r.read()
    with open(out, "wb") as f:
        f.write(data)
except Exception:
    sys.exit(1)
PYEOF
  return 1
}

if [ -n "$CLONE_PATH" ]; then
  # LOCAL git path — the privacy-preferred route. No user data sent.
  if git -C "$CLONE_PATH" fetch --quiet origin main 2>/dev/null; then
    LATEST="$(git -C "$CLONE_PATH" show origin/main:VERSION 2>/dev/null | head -1 | tr -d '[:space:]')"
    git -C "$CLONE_PATH" show origin/main:CHANGELOG.md >"$CHANGELOG_TMP" 2>/dev/null || : > "$CHANGELOG_TMP"
    if [ -n "$LATEST" ]; then
      SOURCE="git"
    else
      ERROR="could not read origin/main:VERSION"
    fi
  else
    ERROR="git fetch failed (offline or no network)"
  fi
fi

if [ -z "$LATEST" ]; then
  # Fallback: read-only GET of two public files. Still no user data leaves.
  if fetch_raw "$RAW_BASE/VERSION" "$STATE_DIR/.version.tmp"; then
    LATEST="$(head -1 "$STATE_DIR/.version.tmp" 2>/dev/null | tr -d '[:space:]')"
    rm -f "$STATE_DIR/.version.tmp" 2>/dev/null || true
    fetch_raw "$RAW_BASE/CHANGELOG.md" "$CHANGELOG_TMP" || : > "$CHANGELOG_TMP"
    if [ -n "$LATEST" ]; then
      SOURCE="raw"
      ERROR=""
    fi
  else
    [ -z "$ERROR" ] && ERROR="offline: could not reach github raw"
  fi
fi

# If we still have nothing, fall back installed→installed so the panel can say
# "up to date" rather than break. Record the error for transparency.
if [ -z "$LATEST" ]; then
  LATEST="$INSTALLED"
fi

# ---------- Compute behind + new_entries, write JSON (stdlib python) ----------
python3 - "$STATUS_JSON" "$INSTALLED" "$LATEST" "${CLONE_PATH:-}" "$SOURCE" "$ERROR" "$CHANGELOG_TMP" <<'PYEOF' 2>/dev/null
import sys, re, json, datetime

out_path, installed, latest, clone_path, source, error, changelog_path = sys.argv[1:8]

def norm(v):
    return (v or "").strip()

installed = norm(installed)
latest = norm(latest)

# Date-based versions (YYYY-MM-DD[.N]) sort correctly under plain string compare.
behind = bool(installed) and bool(latest) and (latest > installed) and (source != "none")

new_entries = []
try:
    with open(changelog_path, encoding="utf-8") as f:
        text = f.read()
except OSError:
    text = ""

if text and behind:
    # Match "## [YYYY-MM-DD[.N]] - title"
    pat = re.compile(r"^## \[(\d{4}-\d{2}-\d{2}(?:\.\d+)?)\][ \t]*-?[ \t]*(.*)$", re.MULTILINE)
    matches = list(pat.finditer(text))
    for i, m in enumerate(matches):
        ver = m.group(1)
        title = (m.group(2) or "").strip()
        # Only entries strictly newer than what's installed.
        if not (installed and ver > installed):
            continue
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end]
        # Summary: first meaningful line — a lede paragraph, else first bullet.
        summary = ""
        for raw_line in body.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith("### "):
                continue  # skip Added/Changed/Fixed subheaders, keep scanning
            if line.startswith("- "):
                line = line[2:].strip()
            # Strip markdown emphasis/code/links to a plain summary.
            line = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", line)  # links -> text
            line = line.replace("**", "").replace("`", "").replace("*", "")
            line = re.sub(r"\s+", " ", line).strip()
            if line:
                summary = line
                break
        if len(summary) > 160:
            summary = summary[:157].rstrip() + "..."
        new_entries.append({"version": ver, "title": title, "summary": summary})
    # Newest first.
    new_entries.sort(key=lambda e: e["version"], reverse=True)

status = {
    "installed": installed,
    "latest": latest,
    "behind": behind,
    "new_entries": new_entries,
    "clone_path": clone_path,
    "checked_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "source": source,
}
if error:
    status["error"] = error

with open(out_path, "w", encoding="utf-8") as f:
    json.dump(status, f, indent=2)
    f.write("\n")
PYEOF

# Last-ditch fail-soft: if the status writer itself failed and left no file,
# hand-write a minimal error status so the dashboard always has something valid.
if [ ! -f "$STATUS_JSON" ]; then
  printf '{"installed":"%s","latest":"%s","behind":false,"new_entries":[],"clone_path":"%s","source":"%s","error":"status-writer failed","checked_at":"%s"}\n' \
    "${INSTALLED}" "${LATEST}" "${CLONE_PATH:-}" "${SOURCE}" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$STATUS_JSON" 2>/dev/null || true
fi

exit 0
