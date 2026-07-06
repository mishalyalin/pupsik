#!/usr/bin/env python3
"""telegram-readonly — ONE-TIME interactive login (run by the user, never by the assistant).

What it does:
  1. Reads api_id / api_hash from config.json.
  2. Starts a Telethon client with an empty StringSession. Telethon then INTERACTIVELY
     prompts in this terminal for your phone number, the login code Telegram sends you,
     and (if enabled) your Two-Step-Verification password. You type them here, by hand.
  3. On success, saves the resulting session STRING, Fernet-encrypts it, and writes
     session.enc (mode 0600). The plaintext session string is never printed or stored.

Hard rules baked in:
  * Phone / code / 2FA are accepted ONLY through Telethon's interactive prompts.
    This script intentionally does NOT read them from argv or environment variables.
  * It prints nothing sensitive — not the session string, phone, code, or password.

Usage:
    cd ~/code/mcp-servers/telegram-readonly
    .venv/bin/python login.py
"""
from __future__ import annotations

import json
import pathlib
import sys

from telethon.sync import TelegramClient
from telethon.sessions import StringSession

import keystore

CONFIG = pathlib.Path(__file__).resolve().parent / "config.json"


def _load_config() -> tuple[int, str]:
    if not CONFIG.exists():
        sys.exit("config.json not found. Copy config.example.json -> config.json and fill it in.")
    cfg = json.loads(CONFIG.read_text())
    api_id = cfg.get("api_id")
    api_hash = cfg.get("api_hash")
    if not api_id or api_id == 0 or not api_hash or api_hash == "PUT_API_HASH_HERE":
        sys.exit(
            "api_id / api_hash are still placeholders in config.json.\n"
            "Create an app at https://my.telegram.org/apps and paste the real values first."
        )
    return int(api_id), str(api_hash)


def main() -> None:
    # Guard: refuse if anyone tried to smuggle credentials via argv. Login is interactive-only.
    if len(sys.argv) > 1:
        sys.exit(
            "login.py takes no arguments. Phone, code, and 2FA password are entered "
            "interactively when Telegram prompts — never via the command line."
        )

    api_id, api_hash = _load_config()

    # Empty StringSession -> Telethon will prompt for phone, code, and 2FA password
    # interactively on stdin/stdout. client.start() blocks on those prompts.
    with TelegramClient(StringSession(), api_id, api_hash) as client:
        client.start()  # interactive: phone -> code -> (optional) 2FA password
        session_string = client.session.save()

    # Encrypt + persist. The plaintext session string stays only in this local variable.
    keystore.encrypt_session(session_string)

    # Only a non-sensitive success line.
    print("\n✅ Login OK. Session encrypted to session.enc. You can now use the MCP.")


if __name__ == "__main__":
    main()
