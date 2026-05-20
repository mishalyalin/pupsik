#!/usr/bin/env python3
"""Brand OS integration helper - API-first / local-CLI fallback.

A Brand OS is a versioned repo containing your brand voice, positioning canon,
persuasion tactics, anti-patterns, evidence library, templates - PLUS a
retrieval surface (either a local Python CLI, an HTTP API, or both). See the
pupsik README for a reference implementation.

This helper exposes a single client surface so the customer-comms rules
(`feedback_marketing_panel_default.md` + `feedback_email_nstd.md`) can pull
canon the same way regardless of how the Brand OS is hosted.

DETECTION ORDER (first match wins):
    1. HTTP API mode:
       - env vars BRAND_OS_API_URL + BRAND_OS_API_USER + BRAND_OS_API_PASS
       - OR a credentials file at $BRAND_OS_CREDENTIALS_FILE
         (default ~/.brand-os-credentials) with the same three keys as
         shell-style key=value lines.
    2. Local CLI mode:
       - env var BRAND_OS_PATH points at a Brand OS root containing one of
         tools/marketing_brain.py / tools/brand_brain.py / tools/brand_cli.py
         / brain.py
       - OR a symlink at ~/.brand-os pointing at the root
       - OR a directory under ~/Desktop/claude/projects/ ending in
         "-brand-os" with one of the above CLIs
    3. Otherwise: not configured. Customer-comms rules fall back to their
       inline canon and the helper returns "not configured" silently.

WHY API-FIRST
    The HTTP API mode lets every session (designer, marketer, copywriter,
    Claude session) hit ONE server-side canon copy. No `git clone` drift, no
    "did you pull the latest cocktails?". The local CLI mode stays as the
    fallback for offline use or when the API is unreachable.

CREDENTIALS FILE FORMAT (mode 600, never commit):
    BRAND_OS_API_URL=https://your-brain-host.example.com
    BRAND_OS_API_USER=brand-team
    BRAND_OS_API_PASS=<secret>

    Optional:
    BRAND_OS_API_TIMEOUT=15   # seconds, default 15

CLI:
    python3 tools/brand_os.py status            # detection state + which mode is active
    python3 tools/brand_os.py is-configured     # exit 0 if anything found, 1 if not
    python3 tools/brand_os.py invoke <sub> ...  # call the brain

Subcommand mapping when in API mode (the helper picks the right route):
    invoke stats              -> GET /api/stats
    invoke icp                -> GET /api/icp
    invoke search "<q>"       -> GET /api/search?q=...&top=N
    invoke explain "<q>"      -> GET /api/explain?q=...
    invoke tactic <name>      -> GET /api/tactic/<name>
    invoke for-vector <name>  -> GET /api/for-vector/<name>
    invoke for-stage <name>   -> GET /api/for-stage/<name>
    invoke canon [<school>]   -> GET /api/canon[?school=<school>]
    invoke list-tactics       -> GET /api/list-tactics
    invoke list-stages        -> GET /api/list-stages
    invoke rebuild-index      -> NOT available in API mode (admin op).
                                 Falls through to local CLI if present,
                                 otherwise prints an error pointing at SSH.

In local-CLI mode the args are passed through to the local CLI verbatim.

NETWORK FAILURE BEHAVIOUR
    API timeout / connection error / 5xx -> auto-fallback to local CLI if
    detected. The user sees a stderr line:
        [brand_os] api unreachable, falling back to local CLI

    HTTP 4xx -> error is surfaced to stdout/stderr verbatim; no fallback
    (the request itself was bad, not the transport).

STDLIB ONLY
    No pip dependencies. Uses urllib + base64 + json + os + pathlib +
    subprocess.

Python:
    from brand_os import detect_mode, invoke
    mode, detail = detect_mode()      # ("api", url) | ("local", cli_path) | ("none", None)
    ok, output = invoke("search", "cart abandon", "--top", "5")
"""

from __future__ import annotations

import base64
import json
import os
import ssl
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

# Where the helper looks for the Python CLI inside a Brand OS root.
CLI_CANDIDATES = (
    "tools/marketing_brain.py",
    "tools/brand_brain.py",
    "tools/brand_cli.py",
    "brain.py",
)

DEFAULT_CREDENTIALS_FILE = "~/.brand-os-credentials"
DEFAULT_TIMEOUT_SECONDS = 15

# Mapping invoke subcommand -> (method, path-builder). path-builder takes the
# remaining argv after the subcommand and returns the URL path + querystring.
def _build_api_route(sub: str, args: list[str]) -> tuple[str, str] | None:
    """Return (method, path) for a subcommand, or None if not an API route."""
    if sub == "stats":
        return "GET", "/api/stats"
    if sub == "icp":
        return "GET", "/api/icp"
    if sub == "list-tactics":
        return "GET", "/api/list-tactics"
    if sub == "list-stages":
        return "GET", "/api/list-stages"

    if sub == "search":
        q, top = _parse_query_and_top(args)
        if not q:
            return None
        qs = urllib.parse.urlencode({"q": q, "top": top})
        return "GET", f"/api/search?{qs}"

    if sub == "explain":
        q = " ".join(args).strip()
        if not q:
            return None
        qs = urllib.parse.urlencode({"q": q})
        return "GET", f"/api/explain?{qs}"

    if sub == "canon":
        # `invoke canon` or `invoke canon <school>`
        path = "/api/canon"
        if args:
            qs = urllib.parse.urlencode({"school": args[0]})
            path = f"{path}?{qs}"
        return "GET", path

    if sub in ("tactic", "for-vector", "for-stage"):
        if not args:
            return None
        name = urllib.parse.quote(args[0], safe="")
        return "GET", f"/api/{sub}/{name}"

    return None


def _parse_query_and_top(args: list[str]) -> tuple[str, int]:
    """Split argv into a free-text query and an optional --top N."""
    top = 5
    rest: list[str] = []
    i = 0
    while i < len(args):
        token = args[i]
        if token == "--top" and i + 1 < len(args):
            try:
                top = max(1, min(20, int(args[i + 1])))
            except ValueError:
                top = 5
            i += 2
            continue
        rest.append(token)
        i += 1
    return " ".join(rest).strip(), top


def _load_credentials_file(path: Path) -> dict[str, str]:
    """Read a shell-style key=value file. Returns empty dict on any error."""
    if not path.is_file():
        return {}
    out: dict[str, str] = {}
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            out[key.strip()] = value.strip()
    except OSError:
        return {}
    return out


def detect_api() -> dict[str, str] | None:
    """Return {url, user, password, timeout} if API credentials are present.

    Looks first at env vars; if missing, falls back to the credentials file.
    All three of url/user/password must be present to count as configured.
    """
    env = {
        "BRAND_OS_API_URL": os.environ.get("BRAND_OS_API_URL", "").strip(),
        "BRAND_OS_API_USER": os.environ.get("BRAND_OS_API_USER", "").strip(),
        "BRAND_OS_API_PASS": os.environ.get("BRAND_OS_API_PASS", "").strip(),
        "BRAND_OS_API_TIMEOUT": os.environ.get("BRAND_OS_API_TIMEOUT", "").strip(),
    }
    has_env = all(env[k] for k in ("BRAND_OS_API_URL", "BRAND_OS_API_USER", "BRAND_OS_API_PASS"))
    if has_env:
        return _normalise_creds(env)

    creds_path_str = os.environ.get("BRAND_OS_CREDENTIALS_FILE", "").strip() or DEFAULT_CREDENTIALS_FILE
    creds_path = Path(creds_path_str).expanduser()
    file_creds = _load_credentials_file(creds_path)
    if file_creds and all(
        file_creds.get(k) for k in ("BRAND_OS_API_URL", "BRAND_OS_API_USER", "BRAND_OS_API_PASS")
    ):
        return _normalise_creds(file_creds)

    return None


def _normalise_creds(raw: dict[str, str]) -> dict[str, str]:
    url = raw["BRAND_OS_API_URL"].rstrip("/")
    try:
        timeout = int(raw.get("BRAND_OS_API_TIMEOUT") or DEFAULT_TIMEOUT_SECONDS)
    except ValueError:
        timeout = DEFAULT_TIMEOUT_SECONDS
    return {
        "url": url,
        "user": raw["BRAND_OS_API_USER"],
        "password": raw["BRAND_OS_API_PASS"],
        "timeout": str(max(1, timeout)),
    }


def detect_local_cli() -> Path | None:
    """Return the Path to a local Brand OS CLI, or None.

    Search order: BRAND_OS_PATH env > ~/.brand-os symlink > auto-detect under
    ~/Desktop/claude/projects/*-brand-os.
    """
    env_path = os.environ.get("BRAND_OS_PATH", "").strip()
    if env_path:
        root = Path(env_path).expanduser().resolve()
        cli = _find_cli(root)
        if cli:
            return cli

    sym = Path.home() / ".brand-os"
    if sym.exists():
        root = sym.resolve()
        cli = _find_cli(root)
        if cli:
            return cli

    projects = Path.home() / "Desktop" / "claude" / "projects"
    if projects.is_dir():
        for child in sorted(projects.iterdir()):
            if child.is_dir() and child.name.endswith("-brand-os"):
                cli = _find_cli(child)
                if cli:
                    return cli

    return None


def _find_cli(root: Path) -> Path | None:
    if not root.is_dir():
        return None
    for relpath in CLI_CANDIDATES:
        candidate = root / relpath
        if candidate.is_file():
            return candidate
    return None


def detect_mode() -> tuple[str, str | None]:
    """Return (mode, detail) where mode is one of api / local / none.

    detail is the URL (api) or CLI path (local) or None (not configured).
    """
    api = detect_api()
    if api:
        return "api", api["url"]
    cli = detect_local_cli()
    if cli:
        return "local", str(cli)
    return "none", None


def _ssl_context() -> ssl.SSLContext:
    """Build an SSL context that works on macOS-Python.org installs too.

    Python.org-installed Python on macOS often ships without the Install
    Certificates.command being run, leaving `ssl.create_default_context()`
    with an empty trust store. If `certifi` happens to be installed (very
    common - bundled with `requests`, `pip` itself, etc), use its cafile to
    fill the gap. Falls back to the default context otherwise.
    """
    try:
        import certifi  # type: ignore
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def _api_request(creds: dict[str, str], method: str, path: str) -> tuple[int, str, str | None]:
    """Send an HTTP request to the Brand OS API.

    Returns (status_code, body_text, error_message_or_None). The body is
    returned even for non-2xx so callers can surface server-side error JSON.
    """
    url = creds["url"] + path
    timeout = int(creds["timeout"])
    auth = base64.b64encode(f"{creds['user']}:{creds['password']}".encode("utf-8")).decode("ascii")
    req = urllib.request.Request(url, method=method)
    req.add_header("Authorization", f"Basic {auth}")
    req.add_header("Accept", "application/json")
    ctx = _ssl_context()
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return resp.status, body, None
    except urllib.error.HTTPError as exc:
        body = ""
        try:
            body = exc.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        return exc.code, body, None
    except urllib.error.URLError as exc:
        return 0, "", f"network error: {exc.reason}"
    except TimeoutError as exc:
        return 0, "", f"timeout after {timeout}s: {exc}"


def _local_invoke(cli: Path, args: list[str], timeout: int = 60) -> tuple[bool, str]:
    """Run the local CLI and return (ran, stdout_or_stderr)."""
    try:
        result = subprocess.run(
            [sys.executable, str(cli), *args],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return True, f"[brand_os] local CLI timed out after {timeout}s: {cli} {' '.join(args)}"
    out = (result.stdout or "").strip()
    err = (result.stderr or "").strip()
    if result.returncode == 0:
        return True, out
    payload = out + (("\n[stderr]\n" + err) if err else "")
    return True, payload.strip() or f"[brand_os] local CLI exit {result.returncode}"


def invoke(*args: str) -> tuple[bool, str | None]:
    """Invoke the Brand OS with a CLI-style subcommand + args.

    Returns (found, output).
        found=False, output=None         -> Brand OS not configured at all.
        found=True,  output=str          -> success or surfaced error.
    """
    if not args:
        return True, "usage: invoke <subcommand> [args...]"

    sub, sub_args = args[0], list(args[1:])
    mode, detail = detect_mode()
    if mode == "none":
        return False, None

    # 1. API mode (with local CLI as soft fallback).
    if mode == "api":
        creds = detect_api()
        if creds is None:
            # Defensive: detect_mode said api but detect_api now says no.
            return _fall_back_to_local(sub, sub_args, reason="api credentials disappeared")

        if sub == "rebuild-index":
            # Admin operation; not exposed via API by design. Try local CLI.
            return _fall_back_to_local(sub, sub_args, reason="rebuild-index not supported in API mode")

        route = _build_api_route(sub, sub_args)
        if route is None:
            # Unknown subcommand or missing required arg. Try local CLI so the
            # local error message guides the user.
            return _fall_back_to_local(sub, sub_args, reason=f"no API route for `{sub}`")

        method, path = route
        status, body, err = _api_request(creds, method, path)
        if err:
            print(f"[brand_os] api unreachable ({err}), falling back to local CLI", file=sys.stderr)
            return _fall_back_to_local(sub, sub_args, reason=err)

        if 500 <= status < 600:
            print(f"[brand_os] api {status}, falling back to local CLI", file=sys.stderr)
            return _fall_back_to_local(sub, sub_args, reason=f"http {status}")

        # 2xx, 3xx, 4xx: surface the JSON body verbatim. Pretty-print if
        # parseable so terminal users see structured output.
        try:
            pretty = json.dumps(json.loads(body), indent=2, ensure_ascii=False)
        except (json.JSONDecodeError, ValueError):
            pretty = body
        return True, pretty

    # 2. Local CLI mode.
    cli = Path(detail) if detail else detect_local_cli()
    if cli is None:
        return False, None
    return _local_invoke(cli, [sub, *sub_args])


def _fall_back_to_local(sub: str, sub_args: list[str], reason: str) -> tuple[bool, str | None]:
    cli = detect_local_cli()
    if cli is None:
        return True, f"[brand_os] {reason}; no local CLI available either"
    return _local_invoke(cli, [sub, *sub_args])


# ---------------------------------------------------------------------------
# CLI entry points
# ---------------------------------------------------------------------------

def cmd_status() -> int:
    mode, detail = detect_mode()
    if mode == "none":
        print("brand_os: NOT configured")
        print("  Configure via API:")
        print(f"    write {DEFAULT_CREDENTIALS_FILE} (mode 600) with:")
        print("      BRAND_OS_API_URL=https://your-brain-host.example.com")
        print("      BRAND_OS_API_USER=<user>")
        print("      BRAND_OS_API_PASS=<password>")
        print("    OR export BRAND_OS_API_URL + BRAND_OS_API_USER + BRAND_OS_API_PASS as env vars")
        print("  Or configure via local CLI:")
        print("    export BRAND_OS_PATH=/path/to/your/brand-os repo")
        print("    OR symlink ~/.brand-os to it")
        print("    OR keep it under ~/Desktop/claude/projects/<name>-brand-os/")
        return 1

    if mode == "api":
        print("brand_os: configured (api mode)")
        print(f"  url:    {detail}")
        # Confirm health via a quick GET /healthz
        creds = detect_api()
        if creds:
            status, body, err = _api_request(creds, "GET", "/healthz")
            if err:
                print(f"  health: UNREACHABLE - {err}")
            else:
                print(f"  health: HTTP {status} - {body.strip()[:80] or '(no body)'}")
        # Also report whether a local CLI is available as fallback.
        local = detect_local_cli()
        if local:
            print(f"  local-fallback: {local}")
        else:
            print("  local-fallback: (none - API outage = no canon)")
        return 0

    # mode == local
    print("brand_os: configured (local CLI mode)")
    print(f"  cli:  {detail}")
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
    mode, _ = detect_mode()
    return 0 if mode != "none" else 1


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
