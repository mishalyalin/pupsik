#!/usr/bin/env bash
# install-git-hooks.sh - opt-in installer for pupsik git hooks.
#
# Hooks live in .githooks/ (tracked) so the source is reviewable + diffable.
# This script copies (or symlinks) them into .git/hooks/ where git actually
# looks. We do not use `git config core.hooksPath` so each developer can
# choose to install or skip - the hooks are not silently active just because
# you cloned the repo.
#
# Usage:
#   bash scripts/install-git-hooks.sh          # symlink (default - hooks auto-update with pulls)
#   bash scripts/install-git-hooks.sh --copy   # copy (frozen at install time)
#   bash scripts/install-git-hooks.sh --remove # uninstall
#
# Hooks installed:
#   pre-commit  - runs .github/scripts/privacy-check.sh --include-untracked
#                 before each commit. Aborts the commit on any privacy fail.
#                 Bypass for emergencies: PUPSIK_SKIP_PRIVACY_CHECK=1 git commit ...

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="$ROOT/.githooks"
DST="$ROOT/.git/hooks"

if [ ! -d "$ROOT/.git" ]; then
  echo "error: $ROOT does not look like a git repo (.git/ missing)" >&2
  exit 2
fi
if [ ! -d "$SRC" ]; then
  echo "error: $SRC missing - re-clone or pull" >&2
  exit 2
fi

mode="symlink"
for arg in "$@"; do
  case "$arg" in
    --copy)   mode="copy" ;;
    --symlink) mode="symlink" ;;
    --remove) mode="remove" ;;
    -h|--help)
      sed -n '1,25p' "$0"
      exit 0
      ;;
    *) echo "unknown arg: $arg" >&2; exit 2 ;;
  esac
done

mkdir -p "$DST"

install_one() {
  local name="$1"
  local src="$SRC/$name"
  local dst="$DST/$name"
  if [ ! -f "$src" ]; then
    echo "  skip: $src missing"
    return 0
  fi
  rm -f "$dst"
  if [ "$mode" = "symlink" ]; then
    ln -s "../../.githooks/$name" "$dst"
    echo "  symlinked: $dst -> ../../.githooks/$name"
  else
    cp "$src" "$dst"
    chmod +x "$dst"
    echo "  copied: $src -> $dst"
  fi
}

remove_one() {
  local name="$1"
  local dst="$DST/$name"
  if [ -L "$dst" ] || [ -f "$dst" ]; then
    rm -f "$dst"
    echo "  removed: $dst"
  fi
}

if [ "$mode" = "remove" ]; then
  echo "[install-git-hooks] removing hooks..."
  for f in "$SRC"/*; do
    [ -f "$f" ] || continue
    remove_one "$(basename "$f")"
  done
  echo "done."
  exit 0
fi

echo "[install-git-hooks] installing pupsik hooks (mode=$mode)..."
for f in "$SRC"/*; do
  [ -f "$f" ] || continue
  chmod +x "$f"
  install_one "$(basename "$f")"
done
echo "done. Test it: try committing a file containing a known-leak string."
