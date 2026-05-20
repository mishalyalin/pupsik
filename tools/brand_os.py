#!/usr/bin/env python3
"""Brand OS integration helper - opt-in canon retrieval.

If you maintain a Brand OS repo (single source of truth for your brand voice,
positioning canon, persuasion tactics, touchpoint copy), this helper lets
Claude pull from it before drafting customer comms. Without a Brand OS, the
inline canon in feedback_email_nstd.md + feedback_marketing_panel_default.md
remains the fallback.

What is a Brand OS:
    A versioned repo containing your brand voice, positioning, persuasion
    tactics, anti-patterns, evidence library, and templates - PLUS a Python
    CLI that exposes structured retrieval over the canon. See the pupsik
    README for a reference implementation. Typical CLI subcommands a Brand
    OS exposes: `icp`, `for-vector`, `tactic`, `search`, `canon`.

How to wire it:
    Option 1 (recommended) - set env var:
        export BRAND_OS_PATH=/path/to/your/brand-os
    Option 2 - drop a symlink:
        ln -s /path/to/your/brand-os ~/.brand-os
    Option 3 - keep your Brand OS under ~/Desktop/claude/projects/ and the
        helper will auto-detect any directory ending in `-brand-os`.

Detection requires a Python CLI at one of these paths inside the Brand OS:
    tools/marketing_brain.py
    tools/brand_brain.py
    tools/brand_cli.py
    brain.py
The first match wins.

CLI:
    python3 tools/brand_os.py status                   # show detection state
    python3 tools/brand_os.py invoke <subcommand> ...  # pass through to brain
    python3 tools/brand_os.py is-configured            # exit 0 if found, 1 if not

Python:
    from brand_os import detect_brand_os, invoke
    path = detect_brand_os()  # Path | None
    found, output = invoke("icp")  # (bool, str | None)
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

# Where the helper looks for the Python CLI inside a Brand OS root.
CLI_CANDIDATES = (
    "tools/marketing_brain.py",
    "tools/brand_brain.py",
    "tools/brand_cli.py",
    "brain.py",
)


def detect_brand_os() -> Path | None:
    """Return the Path to the Brand OS CLI, or None.

    Search order: BRAND_OS_PATH env > ~/.brand-os symlink > auto-detect
    under ~/Desktop/claude/projects/*-brand-os.
    """
    # 1. Explicit env var
    env_path = os.environ.get("BRAND_OS_PATH", "").strip()
    if env_path:
        root = Path(env_path).expanduser().resolve()
        cli = _find_cli(root)
        if cli:
            return cli

    # 2. Conventional symlink
    sym = Path.home() / ".brand-os"
    if sym.exists():
        root = sym.resolve()
        cli = _find_cli(root)
        if cli:
            return cli

    # 3. Auto-detect under ~/Desktop/claude/projects/
    projects = Path.home() / "Desktop" / "claude" / "projects"
    if projects.is_dir():
        for child in sorted(projects.iterdir()):
            if child.is_dir() and child.name.endswith("-brand-os"):
                cli = _find_cli(child)
                if cli:
                    return cli

    return None


def _find_cli(root: Path) -> Path | None:
    """Find the first viable Brand OS CLI inside a candidate root."""
    if not root.is_dir():
        return None
    for relpath in CLI_CANDIDATES:
        candidate = root / relpath
        if candidate.is_file():
            return candidate
    return None


def invoke(*args: str, timeout: int = 60) -> tuple[bool, str | None]:
    """Invoke the Brand OS CLI with the given subcommand + args.

    Returns (True, stdout) on success, (False, None) if no Brand OS configured,
    (True, stderr) if the CLI ran but errored (so caller can surface why).
    """
    cli = detect_brand_os()
    if cli is None:
        return (False, None)
    try:
        result = subprocess.run(
            [sys.executable, str(cli), *args],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return (True, f"[brand_os] CLI timed out after {timeout}s: {cli} {' '.join(args)}")
    out = result.stdout.strip()
    err = result.stderr.strip()
    if result.returncode == 0:
        return (True, out)
    payload = out + (("\n[stderr]\n" + err) if err else "")
    return (True, payload.strip() or f"[brand_os] CLI exit {result.returncode}")


def cmd_status() -> int:
    cli = detect_brand_os()
    if cli is None:
        print("brand_os: NOT configured")
        print("  - set BRAND_OS_PATH env var to your brand-os repo, or")
        print("  - symlink ~/.brand-os to it, or")
        print("  - keep it under ~/Desktop/claude/projects/<name>-brand-os/")
        return 1
    print(f"brand_os: configured")
    print(f"  cli:  {cli}")
    print(f"  root: {cli.parent.parent if cli.parent.name == 'tools' else cli.parent}")
    # Probe CLI for a help message to confirm it's responsive.
    try:
        r = subprocess.run(
            [sys.executable, str(cli), "--help"],
            capture_output=True, text=True, timeout=10, check=False,
        )
        first_line = (r.stdout or r.stderr).splitlines()[:1]
        if first_line:
            print(f"  responds: {first_line[0][:100]}")
    except (subprocess.TimeoutExpired, IndexError):
        print("  responds: (no help output)")
    return 0


def cmd_invoke(args: list[str]) -> int:
    if not args:
        print("usage: brand_os.py invoke <subcommand> [args...]", file=sys.stderr)
        return 2
    found, out = invoke(*args)
    if not found:
        print("[brand_os] not configured - cannot invoke", file=sys.stderr)
        return 1
    if out is not None:
        print(out)
    return 0


def cmd_is_configured() -> int:
    return 0 if detect_brand_os() is not None else 1


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    cmd = sys.argv[1]
    if cmd in ("status", "-s", "--status"):
        return cmd_status()
    if cmd == "is-configured":
        return cmd_is_configured()
    if cmd == "invoke":
        return cmd_invoke(sys.argv[2:])
    print(f"unknown command: {cmd}", file=sys.stderr)
    print("commands: status / is-configured / invoke <subcommand> ...", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
