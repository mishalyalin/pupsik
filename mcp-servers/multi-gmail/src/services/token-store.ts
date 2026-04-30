import crypto from "crypto";
import fs from "fs";
import path from "path";
import os from "os";
import type { AccountConfig, TokenData, StoredAccount } from "../types.js";

const STORE_DIR = path.join(os.homedir(), ".multi-gmail-mcp");
const STORE_FILE = path.join(STORE_DIR, "tokens.enc");
const ALGORITHM = "aes-256-gcm";

interface Store {
  accounts: AccountConfig[];
  tokens: Record<string, TokenData>;
}

function deriveKey(): Buffer {
  const material = `multi-gmail-mcp:${os.hostname()}:${os.userInfo().username}`;
  return crypto.createHash("sha256").update(material).digest();
}

function encrypt(plaintext: string): string {
  const key = deriveKey();
  const iv = crypto.randomBytes(12);
  const cipher = crypto.createCipheriv(ALGORITHM, key, iv);
  const encrypted = Buffer.concat([cipher.update(plaintext, "utf8"), cipher.final()]);
  const authTag = cipher.getAuthTag();
  return `${iv.toString("hex")}:${authTag.toString("hex")}:${encrypted.toString("hex")}`;
}

function decrypt(ciphertext: string): string {
  const key = deriveKey();
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
  try {
    const raw = fs.readFileSync(STORE_FILE, "utf8");
    return JSON.parse(decrypt(raw.trim())) as Store;
  } catch {
    return { accounts: [], tokens: {} };
  }
}

function writeStore(store: Store): void {
  if (!fs.existsSync(STORE_DIR)) fs.mkdirSync(STORE_DIR, { recursive: true, mode: 0o700 });
  fs.writeFileSync(STORE_FILE, encrypt(JSON.stringify(store)), { mode: 0o600 });
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
