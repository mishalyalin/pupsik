import { DatabaseSync } from "node:sqlite";
import fs from "fs";
import { WA_DB_PATH, APPLE_EPOCH_OFFSET, JID_STATUS } from "../constants.js";

// Open WhatsApp DB readonly so we can never corrupt it.
export function openWA(): DatabaseSync {
  if (!fs.existsSync(WA_DB_PATH)) {
    throw new Error(
      `WhatsApp database not found at ${WA_DB_PATH}. ` +
        `Is the WhatsApp desktop app installed and signed in?`
    );
  }
  return new DatabaseSync(WA_DB_PATH, { readOnly: true });
}

export function appleToIso(appleSeconds: number | null): string | null {
  if (appleSeconds == null) return null;
  const unixMs = (appleSeconds + APPLE_EPOCH_OFFSET) * 1000;
  return new Date(unixMs).toISOString();
}

export function isoToAppleSeconds(iso: string): number {
  const unixMs = new Date(iso).getTime();
  return unixMs / 1000 - APPLE_EPOCH_OFFSET;
}

export interface WAChat {
  sessionId: number;
  jid: string;
  partnerName: string | null;
  sessionType: number; // 0 = DM, 1 = group, 3 = status
  lastMessageDate: string | null; // ISO
  lastMessageText: string | null;
  unreadCount: number;
  isGroup: boolean;
}

export interface WAMessage {
  id: number;
  sessionId: number;
  jid: string; // chat JID
  fromJid: string | null;
  toJid: string | null;
  fromMe: boolean;
  text: string | null;
  date: string | null; // ISO
  messageType: number; // 0=text, 1=image, 2=video, 3=audio, 4=contact, 5=location, 7=call, 8=sticker, 10=document, 15=group event, etc.
  pushName: string | null; // sender's name as shown in WA
}

export function listChats(
  db: DatabaseSync,
  opts: { limit?: number; since?: string; includeStatus?: boolean } = {}
): WAChat[] {
  const { limit = 100, since, includeStatus = false } = opts;
  const filters: string[] = ["ZREMOVED = 0 OR ZREMOVED IS NULL"];
  const params: Record<string, string | number | bigint | null | Uint8Array> = {};

  if (!includeStatus) {
    filters.push(`(ZCONTACTJID IS NULL OR ZCONTACTJID NOT LIKE '%${JID_STATUS}')`);
  }
  if (since) {
    params.since = isoToAppleSeconds(since);
    filters.push("ZLASTMESSAGEDATE >= @since");
  }

  const sql = `
    SELECT Z_PK as sessionId, ZCONTACTJID as jid, ZPARTNERNAME as partnerName,
           ZSESSIONTYPE as sessionType, ZLASTMESSAGEDATE as lastDate,
           ZLASTMESSAGETEXT as lastText, ZUNREADCOUNT as unread
    FROM ZWACHATSESSION
    WHERE ${filters.join(" AND ")}
    ORDER BY ZLASTMESSAGEDATE DESC
    LIMIT @limit
  `;
  params.limit = limit;

  const rows = db.prepare(sql).all(params) as Array<{
    sessionId: number;
    jid: string;
    partnerName: string | null;
    sessionType: number;
    lastDate: number | null;
    lastText: string | null;
    unread: number;
  }>;

  return rows.map((r) => ({
    sessionId: r.sessionId,
    jid: r.jid ?? "",
    partnerName: r.partnerName,
    sessionType: r.sessionType,
    lastMessageDate: appleToIso(r.lastDate),
    lastMessageText: r.lastText,
    unreadCount: r.unread ?? 0,
    isGroup: r.sessionType === 1,
  }));
}

export function findChats(db: DatabaseSync, nameOrJid: string, limit = 10): WAChat[] {
  const needle = `%${nameOrJid}%`;
  const sql = `
    SELECT Z_PK as sessionId, ZCONTACTJID as jid, ZPARTNERNAME as partnerName,
           ZSESSIONTYPE as sessionType, ZLASTMESSAGEDATE as lastDate,
           ZLASTMESSAGETEXT as lastText, ZUNREADCOUNT as unread
    FROM ZWACHATSESSION
    WHERE (ZPARTNERNAME LIKE @needle OR ZCONTACTJID LIKE @needle)
      AND (ZCONTACTJID IS NULL OR ZCONTACTJID NOT LIKE '%${JID_STATUS}')
    ORDER BY ZLASTMESSAGEDATE DESC
    LIMIT @limit
  `;
  const rows = db.prepare(sql).all({ needle, limit }) as Array<{
    sessionId: number;
    jid: string;
    partnerName: string | null;
    sessionType: number;
    lastDate: number | null;
    lastText: string | null;
    unread: number;
  }>;
  return rows.map((r) => ({
    sessionId: r.sessionId,
    jid: r.jid ?? "",
    partnerName: r.partnerName,
    sessionType: r.sessionType,
    lastMessageDate: appleToIso(r.lastDate),
    lastMessageText: r.lastText,
    unreadCount: r.unread ?? 0,
    isGroup: r.sessionType === 1,
  }));
}

export function getMessagesForSession(
  db: DatabaseSync,
  sessionId: number,
  opts: { limit?: number; since?: string } = {}
): WAMessage[] {
  const { limit = 100, since } = opts;
  const params: Record<string, string | number | bigint | null | Uint8Array> = { sessionId, limit };
  let dateFilter = "";
  if (since) {
    params.since = isoToAppleSeconds(since);
    dateFilter = "AND m.ZMESSAGEDATE >= @since";
  }

  const sql = `
    SELECT m.Z_PK as id, m.ZCHATSESSION as sessionId, s.ZCONTACTJID as jid,
           m.ZFROMJID as fromJid, m.ZTOJID as toJid, m.ZISFROMME as fromMe,
           m.ZTEXT as text, m.ZMESSAGEDATE as date, m.ZMESSAGETYPE as mtype,
           m.ZPUSHNAME as pushName
    FROM ZWAMESSAGE m
    JOIN ZWACHATSESSION s ON s.Z_PK = m.ZCHATSESSION
    WHERE m.ZCHATSESSION = @sessionId ${dateFilter}
    ORDER BY m.ZMESSAGEDATE DESC
    LIMIT @limit
  `;

  const rows = db.prepare(sql).all(params) as Array<{
    id: number;
    sessionId: number;
    jid: string;
    fromJid: string | null;
    toJid: string | null;
    fromMe: number;
    text: string | null;
    date: number | null;
    mtype: number;
    pushName: string | null;
  }>;

  return rows.map((r) => ({
    id: r.id,
    sessionId: r.sessionId,
    jid: r.jid ?? "",
    fromJid: r.fromJid,
    toJid: r.toJid,
    fromMe: !!r.fromMe,
    text: r.text,
    date: appleToIso(r.date),
    messageType: r.mtype,
    pushName: r.pushName,
  }));
}

export function searchMessages(
  db: DatabaseSync,
  query: string,
  opts: { limit?: number; since?: string } = {}
): WAMessage[] {
  const { limit = 50, since } = opts;
  const params: Record<string, string | number | bigint | null | Uint8Array> = { q: `%${query}%`, limit };
  let dateFilter = "";
  if (since) {
    params.since = isoToAppleSeconds(since);
    dateFilter = "AND m.ZMESSAGEDATE >= @since";
  }

  const sql = `
    SELECT m.Z_PK as id, m.ZCHATSESSION as sessionId, s.ZCONTACTJID as jid,
           m.ZFROMJID as fromJid, m.ZTOJID as toJid, m.ZISFROMME as fromMe,
           m.ZTEXT as text, m.ZMESSAGEDATE as date, m.ZMESSAGETYPE as mtype,
           m.ZPUSHNAME as pushName
    FROM ZWAMESSAGE m
    JOIN ZWACHATSESSION s ON s.Z_PK = m.ZCHATSESSION
    WHERE m.ZTEXT LIKE @q ${dateFilter}
      AND (s.ZCONTACTJID IS NULL OR s.ZCONTACTJID NOT LIKE '%${JID_STATUS}')
    ORDER BY m.ZMESSAGEDATE DESC
    LIMIT @limit
  `;

  const rows = db.prepare(sql).all(params) as Array<{
    id: number;
    sessionId: number;
    jid: string;
    fromJid: string | null;
    toJid: string | null;
    fromMe: number;
    text: string | null;
    date: number | null;
    mtype: number;
    pushName: string | null;
  }>;

  return rows.map((r) => ({
    id: r.id,
    sessionId: r.sessionId,
    jid: r.jid ?? "",
    fromJid: r.fromJid,
    toJid: r.toJid,
    fromMe: !!r.fromMe,
    text: r.text,
    date: appleToIso(r.date),
    messageType: r.mtype,
    pushName: r.pushName,
  }));
}

// Extract phone number from a JID like "1234567890@s.whatsapp.net" or "1234567890@lid".
// Returns digits only, or null if JID is a group or unparseable.
export function phoneFromJid(jid: string | null | undefined): string | null {
  if (!jid) return null;
  if (jid.endsWith("@g.us")) return null; // group
  if (jid.endsWith("@status")) return null; // status
  const m = jid.match(/^(\d+)@/);
  return m ? m[1] : null;
}
