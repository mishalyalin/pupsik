#!/usr/bin/env bash
# brand-os-visual-gate.sh - structural enforcement of Brand OS visual spec.
#
# What this gate catches: brand surfaces (favicon.svg, brand-mark SVG, theme
# colours) drifting from the locked Brand OS visual identity. The leak class
# is "I pattern-matched the brand colour from memory and shipped a slightly
# wrong hex" - structurally caught here at build time, not visually caught
# downstream after shipping.
#
# How it works:
#   1. Locate the Brand OS visual spec. Detection chain:
#        - $BRAND_OS_PATH/web/static/favicon.svg
#        - ~/.brand-os/web/static/favicon.svg
#        - first match under ~/Desktop/claude/projects/*-brand-os/web/static/favicon.svg
#   2. If none found, SKIP - print a yellow warning and exit 0 (forks without
#      a Brand OS are not affected; the gate is opt-in by configuration).
#   3. If found, compare bytes of the canonical favicon.svg against this
#      repo's dashboard/favicon.svg. Drift = FAIL with a diff. Match = PASS.
#   4. Also check that the theme-color + mask-icon hex in
#      dashboard/build.py matches the rect fill in the canonical favicon.
#
# Usage (CI / build / morning-dashboard.sh):
#   bash scripts/brand-os-visual-gate.sh
#   bash scripts/brand-os-visual-gate.sh --fix      # rewrite drifted files in-place
#
# Exit codes:
#   0 = pass (or skipped, no spec available)
#   1 = drift detected
#   2 = misuse / spec malformed
#
# Future: when the Brand OS web app exposes /api/visual-spec (returning the
# locked tokens as JSON), this script will gain API-mode parity with the
# brand_os.py helper. Today it relies on a local clone of the Brand OS repo.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DASHBOARD_FAVICON="$ROOT/dashboard/favicon.svg"
DASHBOARD_BUILDPY="$ROOT/dashboard/build.py"
MODE="check"

for arg in "$@"; do
  case "$arg" in
    --fix)   MODE="fix" ;;
    --check) MODE="check" ;;
    -h|--help)
      sed -n '1,30p' "$0"
      exit 0
      ;;
    *) echo "unknown arg: $arg" >&2; exit 2 ;;
  esac
done

red()    { printf "\033[1;31m%s\033[0m\n" "$*"; }
green()  { printf "\033[1;32m%s\033[0m\n" "$*"; }
yellow() { printf "\033[1;33m%s\033[0m\n" "$*"; }
bold()   { printf "\033[1m%s\033[0m\n" "$*"; }

bold "[brand-os-visual-gate] checking dashboard against Brand OS spec"

# ---------- Locate the spec ----------
SPEC_FAVICON=""
candidates=()
if [ -n "${BRAND_OS_PATH:-}" ]; then
  candidates+=("$BRAND_OS_PATH/web/static/favicon.svg")
fi
candidates+=("$HOME/.brand-os/web/static/favicon.svg")
projects_dir="$HOME/Desktop/claude/projects"
if [ -d "$projects_dir" ]; then
  while IFS= read -r d; do
    candidates+=("$d/web/static/favicon.svg")
  done < <(find "$projects_dir" -maxdepth 1 -type d -name "*-brand-os" 2>/dev/null | sort)
fi

for c in "${candidates[@]}"; do
  if [ -f "$c" ]; then
    SPEC_FAVICON="$c"
    break
  fi
done

if [ -z "$SPEC_FAVICON" ]; then
  yellow "no Brand OS visual spec found - gate SKIPPED."
  yellow "  (set BRAND_OS_PATH or symlink ~/.brand-os or place a Brand OS clone under ~/Desktop/claude/projects/<name>-brand-os/)"
  exit 0
fi

green "spec: $SPEC_FAVICON"

# ---------- Check 1: favicon.svg byte-identity ----------
if [ ! -f "$DASHBOARD_FAVICON" ]; then
  red "FAIL: $DASHBOARD_FAVICON missing (expected to mirror $SPEC_FAVICON)"
  if [ "$MODE" = "fix" ]; then
    mkdir -p "$(dirname "$DASHBOARD_FAVICON")"
    cp "$SPEC_FAVICON" "$DASHBOARD_FAVICON"
    green "  fixed: copied spec into $DASHBOARD_FAVICON"
  else
    exit 1
  fi
fi

if cmp -s "$DASHBOARD_FAVICON" "$SPEC_FAVICON"; then
  green "favicon.svg: identical to spec"
else
  red "FAIL: favicon.svg drift detected"
  if command -v diff >/dev/null 2>&1; then
    diff -u "$SPEC_FAVICON" "$DASHBOARD_FAVICON" | sed 's/^/    /' || true
  fi
  if [ "$MODE" = "fix" ]; then
    cp "$SPEC_FAVICON" "$DASHBOARD_FAVICON"
    green "  fixed: $DASHBOARD_FAVICON now matches spec"
  else
    exit 1
  fi
fi

# ---------- Check 2: theme-color / mask-icon hex matches rect fill ----------
# Extract the rect fill from the spec.
SPEC_FILL=$(grep -oE 'rect[^>]*fill="#[0-9a-fA-F]{6}"' "$SPEC_FAVICON" | head -1 | grep -oE '#[0-9a-fA-F]{6}' || true)

if [ -z "$SPEC_FILL" ]; then
  yellow "could not extract rect fill from spec - check 2 skipped"
  exit 0
fi

if [ ! -f "$DASHBOARD_BUILDPY" ]; then
  yellow "no $DASHBOARD_BUILDPY - check 2 skipped"
  exit 0
fi

# Find every line referencing mask-icon or theme-color, then for each line
# extract the first hex colour and compare to spec. (A regex one-liner here
# is hard to get right because the keyword and the hex are separated by an
# attribute value containing quotes.)
BAD_LINES=$(grep -nE 'mask-icon|theme-color' "$DASHBOARD_BUILDPY" 2>/dev/null | while IFS= read -r line; do
  hex=$(printf "%s\n" "$line" | grep -oE '#[0-9a-fA-F]{6}' | head -1)
  if [ -n "$hex" ] && [ "$hex" != "$SPEC_FILL" ]; then
    printf "%s\n" "$line"
  fi
done)

if [ -z "$BAD_LINES" ]; then
  green "build.py: mask-icon + theme-color match spec rect fill ($SPEC_FILL)"
else
  red "FAIL: build.py mask-icon or theme-color hex does not match spec ($SPEC_FILL)"
  echo "$BAD_LINES" | sed 's/^/    /'
  if [ "$MODE" = "fix" ]; then
    # Naive in-place fix: replace any other 6-hex inside mask-icon / theme-color
    # tags with the spec fill. Backs up the original.
    cp "$DASHBOARD_BUILDPY" "$DASHBOARD_BUILDPY.bak"
    python3 - <<PYFIX
import re, sys, pathlib
p = pathlib.Path("$DASHBOARD_BUILDPY")
spec = "$SPEC_FILL"
txt = p.read_text()
def repl_attr(match):
    attr = match.group(1)
    return f'{attr}"{spec}"'
new = re.sub(
    r'(mask-icon[^"]*color=|theme-color[^"]*content=)"#[0-9a-fA-F]{6}"',
    repl_attr,
    txt,
)
p.write_text(new)
print("  fixed: $DASHBOARD_BUILDPY (backup at $DASHBOARD_BUILDPY.bak)")
PYFIX
  else
    exit 1
  fi
fi

green "[brand-os-visual-gate] all checks passed"
exit 0
