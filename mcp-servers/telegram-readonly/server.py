#!/usr/bin/env python3
"""telegram-readonly — a LOCAL, READ-ONLY Telegram MCP server (FastMCP, stdio).

Security model (a reviewer will red-team this — it is read-only BY CONSTRUCTION):
  * The session this uses is account-powerful, so this process must make account theft /
    any write action IMPOSSIBLE. It therefore exposes EXACTLY three tools, all read-only,
    all gated by a static allowlist:
        - telegram_list_allowed_chats()  -> the configured allowlist (no account enumeration)
        - telegram_read_chat(chat, limit)
        - telegram_search_chat(chat, query, limit)
  * No tool/function reachable by the MCP client can send, edit, delete, forward,
    mark-as-read, join, leave, change settings, or log in. No such helper is even imported
    or defined. Only Telethon's read path (client.get_messages) is ever called.
  * The allowlist is enforced on EVERY read. A chat not on the allowlist is never read;
    the tool refuses and reads nothing. Allowlist usernames/ids are resolved to entities
    ONCE at connect time (internal get_entity); get_dialogs / full-account enumeration is
    NEVER exposed through any tool.
  * The session string and the encryption key are never logged, printed, or returned.
  * No network egress except Telegram MTProto (Telethon). No telemetry / http / analytics.

Registration JSON for ~/Desktop/claude/.claude/settings.json mcpServers (or ~/.claude.json)
(use YOUR absolute paths — Claude Code does not expand ~ or $HOME here):

  "telegram-readonly": {
    "command": "/Users/<you>/code/mcp-servers/telegram-readonly/.venv/bin/python",
    "args": ["/Users/<you>/code/mcp-servers/telegram-readonly/server.py"]
  }

The server STILL STARTS if session.enc is absent — every tool then returns a clear
"not logged in yet, run login.py" message instead of crashing. MCP registers on the next
Claude Code restart (no hot-reload).
"""
from __future__ import annotations

import json
import pathlib
from typing import Any, Optional

from mcp.server.fastmcp import FastMCP

import keystore

SERVER_DIR = pathlib.Path(__file__).resolve().parent
CONFIG = SERVER_DIR / "config.json"

MAX_TEXT = 2000  # truncate each message body to keep payloads sane
NOT_LOGGED_IN = (
    "Not logged in yet — run: .venv/bin/python login.py "
    "(from ~/code/mcp-servers/telegram-readonly)"
)

mcp = FastMCP("telegram-readonly")


# ============================================================
# config + allowlist (loaded lazily, cached)
# ============================================================
def _load_config() -> dict:
    if not CONFIG.exists():
        return {"api_id": 0, "api_hash": "", "allowlist": []}
    try:
        return json.loads(CONFIG.read_text())
    except (ValueError, OSError):
        return {"api_id": 0, "api_hash": "", "allowlist": []}


_CFG = _load_config()
_ALLOWLIST: list[dict] = _CFG.get("allowlist", []) or []

# Lazily-built Telethon client + a map from each allowlist entry to its resolved entity.
# Resolution happens once, on first tool use that needs the network.
_client = None  # type: ignore[var-annotated]
_resolved: dict[int, Any] = {}  # index in _ALLOWLIST -> resolved Telethon entity
_connect_error: Optional[str] = None


def _config_ready() -> Optional[str]:
    """Return an error string if config still has placeholders, else None."""
    api_id = _CFG.get("api_id")
    api_hash = _CFG.get("api_hash")
    if not api_id or api_id == 0 or not api_hash or api_hash == "PUT_API_HASH_HERE":
        return (
            "config.json still has placeholder api_id / api_hash. "
            "Create an app at https://my.telegram.org/apps and fill them in."
        )
    return None


def _get_client():
    """Build + connect the Telethon client from the encrypted session, and resolve the
    allowlist to entities ONCE. Returns (client, None) or (None, error_message).

    This is the only place the network is touched. It uses Telethon's read path only.
    """
    global _client, _connect_error

    if _client is not None:
        return _client, None
    if _connect_error is not None:
        return None, _connect_error

    if not keystore.session_exists():
        return None, NOT_LOGGED_IN
    cfg_err = _config_ready()
    if cfg_err:
        return None, cfg_err

    # Import Telethon lazily so the server can import + start with no deps issues
    # and so `import server` in a smoke test never needs a live session.
    from telethon.sync import TelegramClient
    from telethon.sessions import StringSession

    session_string = keystore.decrypt_session()
    if not session_string:
        return None, NOT_LOGGED_IN

    api_id = int(_CFG["api_id"])
    api_hash = str(_CFG["api_hash"])

    client = TelegramClient(StringSession(session_string), api_id, api_hash)
    try:
        client.connect()  # read-only network connect; does NOT log in / send a code
    except Exception as e:  # noqa: BLE001 — surface a clean message, never the session
        _connect_error = f"Could not connect to Telegram: {type(e).__name__}"
        return None, _connect_error

    if not client.is_user_authorized():
        # Session present but not authorized (e.g. terminated from Settings -> Devices).
        try:
            client.disconnect()
        except Exception:  # noqa: BLE001
            pass
        _connect_error = (
            "Session is not authorized (it may have been terminated from "
            "Telegram Settings -> Devices). Re-run login.py to create a new one."
        )
        return None, _connect_error

    # Resolve each allowlist entry to a concrete entity, ONCE. Internal get_entity only —
    # we never enumerate the account's dialogs, and this is never exposed as a tool.
    for i, entry in enumerate(_ALLOWLIST):
        ident = entry.get("id") if entry.get("id") not in (None, "") else entry.get("username")
        if ident in (None, ""):
            continue
        try:
            _resolved[i] = client.get_entity(ident)
        except Exception:  # noqa: BLE001 — a bad allowlist entry must not break the server
            # Leave it unresolved; reads against it will refuse with a clear message.
            continue

    _client = client
    return _client, None


# ============================================================
# allowlist matching (read paths MUST go through this)
# ============================================================
def _match_allowlist(chat: str) -> Optional[int]:
    """Return the allowlist index matching `chat` (by label / id / username), or None.

    Matching is case-insensitive for label/username; exact for numeric id. A chat that
    does not match ANY allowlist entry returns None and must NOT be read.
    """
    if chat is None:
        return None
    needle = str(chat).strip()
    needle_l = needle.lstrip("@").lower()

    for i, entry in enumerate(_ALLOWLIST):
        label = str(entry.get("label", "") or "").strip().lower()
        username = str(entry.get("username", "") or "").strip().lstrip("@").lower()
        ent_id = entry.get("id")

        if label and needle.lower() == label:
            return i
        if username and needle_l == username:
            return i
        if ent_id not in (None, "") and needle == str(ent_id):
            return i
    return None


def _resolve_for_read(chat: str):
    """Return (entity, None) for an allowlisted, resolvable chat, else (None, message)."""
    idx = _match_allowlist(chat)
    if idx is None:
        return None, "Refused: chat not in allowlist"

    client, err = _get_client()
    if err:
        return None, err

    entity = _resolved.get(idx)
    if entity is None:
        # Allowlisted but resolution failed at connect (bad id/username, or no access).
        label = _ALLOWLIST[idx].get("label", chat)
        return None, f"Refused: allowlisted chat '{label}' could not be resolved on this account"
    return entity, None


def _fmt_message(m) -> dict:
    """Shape one Telethon message into a small read-only dict."""
    text = getattr(m, "message", None) or getattr(m, "text", None) or ""
    if len(text) > MAX_TEXT:
        text = text[:MAX_TEXT] + "…[truncated]"
    sender_id = getattr(m, "sender_id", None)
    date = getattr(m, "date", None)
    return {
        "date": date.isoformat() if date is not None else None,
        "sender": sender_id,
        "text": text,
    }


# ============================================================
# THE ONLY THREE TOOLS — all read-only, all allowlist-gated
# ============================================================
@mcp.tool()
def telegram_list_allowed_chats() -> dict:
    """List the chats this server is permitted to read (the configured allowlist).

    Returns each entry's human label plus its id/username as configured. Does NOT
    enumerate the account's other chats — only what is explicitly allowlisted.
    """
    if not _ALLOWLIST:
        return {"allowlist": [], "note": "Allowlist is empty — edit config.json to add chats."}
    out = []
    for entry in _ALLOWLIST:
        out.append(
            {
                "label": entry.get("label"),
                "id": entry.get("id"),
                "username": entry.get("username"),
            }
        )
    return {"allowlist": out, "count": len(out)}


@mcp.tool()
def telegram_read_chat(chat: str, limit: int = 30) -> dict:
    """Read the most recent messages from an ALLOWLISTED chat (read-only).

    `chat` must match an allowlist entry by label, id, or username. If it matches nothing
    on the allowlist, this refuses and reads nothing.

    Args:
        chat: label / numeric id / username of an allowlisted chat.
        limit: how many recent messages to return (1–100, default 30).
    """
    try:
        limit = max(1, min(int(limit), 100))
    except (TypeError, ValueError):
        limit = 30

    entity, err = _resolve_for_read(chat)
    if err:
        return {"error": err, "messages": []}

    client = _client
    try:
        msgs = client.get_messages(entity, limit=limit)  # READ ONLY
    except Exception as e:  # noqa: BLE001
        return {"error": f"Read failed: {type(e).__name__}", "messages": []}

    return {"chat": chat, "count": len(msgs), "messages": [_fmt_message(m) for m in msgs]}


@mcp.tool()
def telegram_search_chat(chat: str, query: str, limit: int = 30) -> dict:
    """Search messages within an ALLOWLISTED chat for `query` (read-only).

    `chat` must match an allowlist entry by label, id, or username. If it matches nothing
    on the allowlist, this refuses and reads nothing.

    Args:
        chat: label / numeric id / username of an allowlisted chat.
        query: text to search for inside that chat.
        limit: how many matching messages to return (1–100, default 30).
    """
    try:
        limit = max(1, min(int(limit), 100))
    except (TypeError, ValueError):
        limit = 30

    if not query or not str(query).strip():
        return {"error": "query is required", "messages": []}

    entity, err = _resolve_for_read(chat)
    if err:
        return {"error": err, "messages": []}

    client = _client
    try:
        msgs = client.get_messages(entity, search=str(query), limit=limit)  # READ ONLY
    except Exception as e:  # noqa: BLE001
        return {"error": f"Search failed: {type(e).__name__}", "messages": []}

    return {
        "chat": chat,
        "query": query,
        "count": len(msgs),
        "messages": [_fmt_message(m) for m in msgs],
    }


if __name__ == "__main__":
    mcp.run()  # stdio transport, like the other local MCP servers
