/**
 * OAuth2 authentication manager for multiple Google accounts.
 * Stores tokens in ~/.multi-gcal-mcp/tokens.json
 */

import { google } from "googleapis";
import { OAuth2Client } from "google-auth-library";
import fs from "fs";
import path from "path";
import os from "os";

const SCOPES = [
  "https://www.googleapis.com/auth/calendar.readonly",
  "https://www.googleapis.com/auth/calendar.events",
];

const TOKEN_DIR = path.join(os.homedir(), ".multi-gcal-mcp");
const TOKEN_FILE = path.join(TOKEN_DIR, "tokens.json");

export interface AccountTokens {
  access_token: string;
  refresh_token: string;
  scope: string;
  token_type: string;
  expiry_date: number;
}

export interface TokenStore {
  [alias: string]: {
    email: string;
    tokens: AccountTokens;
  };
}

function getClientId(): string {
  const id = process.env.GCAL_CLIENT_ID || process.env.GMAIL_CLIENT_ID;
  if (!id) throw new Error("GCAL_CLIENT_ID or GMAIL_CLIENT_ID env var required");
  return id;
}

function getClientSecret(): string {
  const secret = process.env.GCAL_CLIENT_SECRET || process.env.GMAIL_CLIENT_SECRET;
  if (!secret) throw new Error("GCAL_CLIENT_SECRET or GMAIL_CLIENT_SECRET env var required");
  return secret;
}

export function createOAuth2Client(): OAuth2Client {
  return new google.auth.OAuth2(
    getClientId(),
    getClientSecret(),
    "http://localhost:3456/callback"
  );
}

export function loadTokens(): TokenStore {
  if (!fs.existsSync(TOKEN_FILE)) return {};
  try {
    return JSON.parse(fs.readFileSync(TOKEN_FILE, "utf-8"));
  } catch {
    return {};
  }
}

export function saveTokens(store: TokenStore): void {
  if (!fs.existsSync(TOKEN_DIR)) {
    fs.mkdirSync(TOKEN_DIR, { recursive: true });
  }
  fs.writeFileSync(TOKEN_FILE, JSON.stringify(store, null, 2));
}

export function getAuthClientForAccount(alias: string): OAuth2Client {
  const store = loadTokens();
  const account = store[alias];
  if (!account) {
    throw new Error(`Account "${alias}" not found. Available: ${Object.keys(store).join(", ") || "none"}`);
  }
  const client = createOAuth2Client();
  client.setCredentials(account.tokens);

  // CRITICAL: persist auto-refreshed tokens. Without this listener, googleapis
  // refreshes tokens in memory during API calls but never writes them to disk.
  // After a server restart, the stale on-disk token fails.
  client.on("tokens", (newTokens) => {
    try {
      const currentStore = loadTokens();
      const cur = currentStore[alias];
      if (!cur) return;
      currentStore[alias] = {
        email: cur.email,
        tokens: {
          access_token: newTokens.access_token ?? cur.tokens.access_token,
          refresh_token: newTokens.refresh_token ?? cur.tokens.refresh_token,
          scope: newTokens.scope ?? cur.tokens.scope,
          token_type: newTokens.token_type ?? cur.tokens.token_type,
          expiry_date: newTokens.expiry_date ?? cur.tokens.expiry_date,
        },
      };
      saveTokens(currentStore);
      console.error(`[auth] Auto-saved refreshed tokens for ${alias}`);
    } catch (err) {
      console.error(`[auth] Failed to persist refreshed tokens for ${alias}:`, err);
    }
  });

  return client;
}

export function listAccounts(): Array<{ alias: string; email: string }> {
  const store = loadTokens();
  return Object.entries(store).map(([alias, data]) => ({
    alias,
    email: data.email,
  }));
}

export function getAuthUrl(client: OAuth2Client): string {
  return client.generateAuthUrl({
    access_type: "offline",
    scope: SCOPES,
    prompt: "consent",
  });
}

export { SCOPES, TOKEN_DIR, TOKEN_FILE };
