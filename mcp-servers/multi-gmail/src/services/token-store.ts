import crypto from "crypto";
import fs from "fs";
import path from "path";
import os from "os";
import type { AccountConfig, TokenData, StoredAccount } from "../types.js";

const STORE_DIR = path.join(os.homedir(), ".multi-gmail-mcp");
const STORE_FILE = path.join(STORE_DIR, "tokens.enc");
const KEY_FILE = path.join(STORE_DIR, "key");
const ALGORITHM = "aes-256-gcm";

interface Store {
  accounts: AccountConfig[];
  tokens: Record<string, TokenData>;
}

function ensureDir(): void {
  if (!fs.existsSync(STORE_DIR)) fs.mkdirSync(STORE_DIR, { recursive: true, mode: 0o700 });
}

// Stable per-install key, persisted to ~/.multi-gmail-mcp/key (0600), generated
// once on first use. Unlike the old os.hostname()-derived key, this does NOT
// change when the laptop moves between WiFi networks (DHCP-assigned hostname
// changes) — so encrypted tokens survive travel instead of silently becoming
// undecryptable.
function stableKey(): Buffer {
  ensureDir();
  try {
    const hex = fs.readFileSync(KEY_FILE, "utf8").trim();
    if (hex.length === 64) return Buffer.from(hex, "hex");
  } catch { /* fall through to generate */ }
  const key = crypto.randomBytes(32);
  fs.writeFileSync(KEY_FILE, key.toString("hex"), { mode: 0o600 });
  return key;
}

// Legacy hostname-derived key — used ONLY to read + migrate stores written by
// the old build. Never used to write.
function legacyKey(): Buffer {
  const material = `multi-gmail-mcp:${os.hostname()}:${os.userInfo().username}`;
  return crypto.createHash("sha256").update(material).digest();
}

function encryptWith(key: Buffer, plaintext: string): string {
  const iv = crypto.randomBytes(12);
  const cipher = crypto.createCipheriv(ALGORITHM, key, iv);
  const encrypted = Buffer.concat([cipher.update(plaintext, "utf8"), cipher.final()]);
  const authTag = cipher.getAuthTag();
  return `${iv.toString("hex")}:${authTag.toString("hex")}:${encrypted.toString("hex")}`;
}

function decryptWith(key: Buffer, ciphertext: string): string {
  const [ivHex, tagHex, dataHex] = ciphertext.split(":");
  if (!ivHex || !tagHex || !dataHex) throw new Error("Invalid token store format");
  const iv = Buffer.from(ivHex, "hex");
  const tag = Buffer.from(tagHex, "hex");
  const data = Buffer.from(dataHex, "hex");
  const decipher = crypto.createDecipheriv(ALGORITHM, key, iv);
  decipher.setAuthTag(tag);
  return decipher.update(data) + decipher.final("utf8");
}

function readStore(): Store {
  if (!fs.existsSync(STORE_FILE)) return { accounts: [], tokens: {} };
  const raw = fs.readFileSync(STORE_FILE, "utf8").trim();
  // 1. Try the stable key (normal path once migrated).
  try {
    return JSON.parse(decryptWith(stableKey(), raw)) as Store;
  } catch (e1) {
    // 2. Fall back to the legacy hostname key. If it still decrypts (hostname
    //    hasn't drifted since the store was written), migrate to the stable key
    //    in place so this never bites again.
    try {
      const store = JSON.parse(decryptWith(legacyKey(), raw)) as Store;
      try {
        fs.writeFileSync(STORE_FILE, encryptWith(stableKey(), JSON.stringify(store)), { mode: 0o600 });
        process.stderr.write("[multi-gmail] migrated tokens.enc: legacy hostname key -> stable key\n");
      } catch (mErr) {
        process.stderr.write(`[multi-gmail] legacy decrypt OK but re-encrypt failed: ${String(mErr)}\n`);
      }
      return store;
    } catch {
      // 3. Neither key works. LOG it loudly — never silently mask a decrypt
      //    failure as "no accounts" (a silent catch here can hide the problem
      //    for days while the server reports zero accounts).
      process.stderr.write(
        `[multi-gmail] tokens.enc could not be decrypted (stable + legacy both failed). ` +
        `Re-auth needed: npm run setup reauth. (${String(e1)})\n`
      );
      return { accounts: [], tokens: {} };
    }
  }
}

function writeStore(store: Store): void {
  ensureDir();
  fs.writeFileSync(STORE_FILE, encryptWith(stableKey(), JSON.stringify(store)), { mode: 0o600 });
}

export async function listAccounts(): Promise<AccountConfig[]> {
  return readStore().accounts;
}

export async function saveAccountConfig(config: AccountConfig): Promise<void> {
  const store = readStore();
  const idx = store.accounts.findIndex(a => a.email === config.email);
  if (idx >= 0) { store.accounts[idx] = config; } else { store.accounts.push(config); }
  writeStore(store);
}

export async function saveTokens(email: string, tokens: TokenData): Promise<void> {
  const store = readStore();
  store.tokens[email] = tokens;
  writeStore(store);
}

export async function getTokens(email: string): Promise<TokenData | null> {
  return readStore().tokens[email] ?? null;
}

export async function getStoredAccount(email: string): Promise<StoredAccount | null> {
  const store = readStore();
  const config = store.accounts.find(a => a.email === email);
  if (!config) return null;
  const tokens = store.tokens[email];
  if (!tokens) return null;
  return { config, tokens };
}

export async function removeAccount(email: string): Promise<boolean> {
  const store = readStore();
  const before = store.accounts.length;
  store.accounts = store.accounts.filter(a => a.email !== email);
  if (store.accounts.length === before) return false;
  delete store.tokens[email];
  writeStore(store);
  return true;
}
