#!/usr/bin/env python3
"""Key management for the telegram-readonly MCP server.

The encrypted-session-at-rest pattern is mirrored from multi-gmail: a STABLE keyfile on
disk encrypts the secret, so it survives hostname/Wi-Fi changes (no re-login from travel).
Here the secret is the Telethon StringSession, encrypted with Fernet (AES-128-CBC + HMAC).

Key location:   ~/.telegram-readonly-mcp/key   (dir 0700, file 0600)
Encrypted out:  session.enc                     (in the server dir, file 0600)

The key is NEVER printed, logged, or returned by any tool. Only the encrypt/decrypt
helpers touch it, and they return bytes/str of the *payload*, never the key itself.
"""
from __future__ import annotations

import os
import pathlib

from cryptography.fernet import Fernet

# Stable key directory + file. Dedicated to this server, outside the workspace.
KEY_DIR = pathlib.Path.home() / ".telegram-readonly-mcp"
KEY_FILE = KEY_DIR / "key"

# Where the encrypted StringSession lives (next to this module).
SERVER_DIR = pathlib.Path(__file__).resolve().parent
SESSION_ENC = SERVER_DIR / "session.enc"


def _load_or_create_key() -> bytes:
    """Return the Fernet key bytes, creating it on first use.

    Dir is created mode 0700, keyfile written mode 0600. We never print the key.
    """
    if KEY_FILE.exists():
        # Defensively re-assert tight perms in case they drifted.
        try:
            os.chmod(KEY_FILE, 0o600)
        except OSError:
            pass
        return KEY_FILE.read_bytes()

    KEY_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    # If the dir pre-existed with looser perms, tighten it.
    try:
        os.chmod(KEY_DIR, 0o700)
    except OSError:
        pass

    key = Fernet.generate_key()
    # Create with 0600 from the start: open with O_CREAT|O_EXCL|O_WRONLY at mode 0600,
    # so the secret never momentarily exists world-readable.
    fd = os.open(KEY_FILE, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        os.write(fd, key)
    finally:
        os.close(fd)
    os.chmod(KEY_FILE, 0o600)
    return key


def _fernet() -> Fernet:
    return Fernet(_load_or_create_key())


def encrypt_session(session_string: str) -> None:
    """Fernet-encrypt the StringSession and write it to session.enc (mode 0600)."""
    token = _fernet().encrypt(session_string.encode("utf-8"))
    # Write atomically-ish with tight perms from creation.
    if SESSION_ENC.exists():
        os.chmod(SESSION_ENC, 0o600)
    fd = os.open(SESSION_ENC, os.O_CREAT | os.O_TRUNC | os.O_WRONLY, 0o600)
    try:
        os.write(fd, token)
    finally:
        os.close(fd)
    os.chmod(SESSION_ENC, 0o600)


def decrypt_session() -> str | None:
    """Return the decrypted StringSession, or None if no session.enc exists yet."""
    if not SESSION_ENC.exists():
        return None
    token = SESSION_ENC.read_bytes()
    return _fernet().decrypt(token).decode("utf-8")


def session_exists() -> bool:
    return SESSION_ENC.exists()
