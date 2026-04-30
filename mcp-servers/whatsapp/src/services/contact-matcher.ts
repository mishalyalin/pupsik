import { DatabaseSync } from "node:sqlite";
import fs from "fs";
import { CONTACTS_DB_PATH } from "../constants.js";

// Open contacts.db read-write so we can INSERT interactions.
export function openContacts(): DatabaseSync {
  if (!fs.existsSync(CONTACTS_DB_PATH)) {
    throw new Error(
      `Contacts DB not found at ${CONTACTS_DB_PATH}. ` +
        `Expected to exist in the workspace.`
    );
  }
  return new DatabaseSync(CONTACTS_DB_PATH);
}

// Normalize a phone string to digits only. Handles "+447...", "44 7...", "(44) 7...", etc.
export function normalizePhone(p: string | null | undefined): string | null {
  if (!p) return null;
  const digits = p.replace(/\D+/g, "");
  return digits.length >= 8 ? digits : null;
}

export interface ContactMatch {
  id: number;
  name: string;
  company: string | null;
  category: string | null;
}

/**
 * Match a WhatsApp chat to a contact in contacts.db.
 *
 * Strategy, in order of preference:
 *   1. Phone match on normalized digits
 *   2. Name match on partnerName == contacts.name (case-insensitive)
 *   3. Partial name match: partnerName contains contact surname or vice versa
 *
 * Returns null if no confident match — we deliberately DO NOT invent contacts.
 * Casual / personal contacts are not in the DB, and skipping them is the whole point.
 */
export function matchContact(
  cdb: DatabaseSync,
  partnerName: string | null,
  phone: string | null
): ContactMatch | null {
  // 1. Phone match
  if (phone) {
    const normalized = normalizePhone(phone);
    if (normalized) {
      const rows = cdb
        .prepare(
          `SELECT id, name, company, category FROM contacts WHERE phone IS NOT NULL AND phone != ''`
        )
        .all() as Array<{ id: number; name: string; company: string | null; category: string | null; phone?: string }>;
      // Fetch with phone for comparison
      const all = cdb
        .prepare(`SELECT id, name, company, category, phone FROM contacts WHERE phone IS NOT NULL`)
        .all() as Array<{ id: number; name: string; company: string | null; category: string | null; phone: string }>;
      for (const c of all) {
        const cn = normalizePhone(c.phone);
        if (cn && (cn === normalized || cn.endsWith(normalized) || normalized.endsWith(cn))) {
          return { id: c.id, name: c.name, company: c.company, category: c.category };
        }
      }
      void rows;
    }
  }

  // 2. Exact name match (case-insensitive)
  if (partnerName && partnerName.trim().length > 1) {
    const exact = cdb
      .prepare(`SELECT id, name, company, category FROM contacts WHERE LOWER(name) = LOWER(?) LIMIT 1`)
      .get(partnerName.trim()) as ContactMatch | undefined;
    if (exact) return exact;

    // 3. Partial match — ONLY when contact name has ≥2 words (first+last) or is ≥8 chars.
    //    This avoids matching short names ("Ap", "All", etc.) as substrings of random group names.
    //    Additionally, the contact name must appear as a whole-word boundary match.
    const candidates = cdb
      .prepare(
        `SELECT id, name, company, category FROM contacts
         WHERE (instr(LOWER(?), LOWER(name)) > 0 AND (length(name) >= 8 OR instr(name, ' ') > 0))
            OR (instr(LOWER(name), LOWER(?)) > 0 AND length(?) >= 5)
         LIMIT 5`
      )
      .all(partnerName.trim(), partnerName.trim(), partnerName.trim()) as unknown as ContactMatch[];
    // Word-boundary filter: only accept if the contact name appears bounded by non-letter or start/end
    const pnLower = partnerName.trim().toLowerCase();
    const wordMatches = candidates.filter((c) => {
      const nameLower = c.name.toLowerCase();
      if (pnLower === nameLower) return true;
      if (pnLower.includes(nameLower)) {
        const idx = pnLower.indexOf(nameLower);
        const before = idx === 0 ? " " : pnLower[idx - 1];
        const after = idx + nameLower.length >= pnLower.length ? " " : pnLower[idx + nameLower.length];
        return !/[a-zа-яё]/i.test(before) && !/[a-zа-яё]/i.test(after);
      }
      if (nameLower.includes(pnLower) && pnLower.length >= 5) {
        return true;
      }
      return false;
    });
    if (wordMatches.length === 1) return wordMatches[0];

    // 4. Company-aware fallback: partnerName starts with a first-name token that matches a contact's
    //    first name, AND the contact's company name appears somewhere in partnerName.
    //    Example: partnerName "Alice @acme" → contact "Alice Smith" at "Acme Corp" → match.
    const firstToken = partnerName.trim().split(/\s+/)[0]?.toLowerCase();
    if (firstToken && firstToken.length >= 3) {
      const nameCandidates = cdb
        .prepare(
          `SELECT id, name, company, category FROM contacts
           WHERE company IS NOT NULL AND company != ''
             AND LOWER(name) LIKE LOWER(?) || '%'`
        )
        .all(firstToken) as unknown as ContactMatch[];
      const coMatches = nameCandidates.filter((c) => {
        if (!c.company) return false;
        const coLower = c.company.toLowerCase();
        const pnLower2 = partnerName.toLowerCase();
        const tokens = coLower.split(/[\s&,.-]+/).filter((t) => t.length >= 3);
        return tokens.some((t) => pnLower2.includes(t));
      });
      if (coMatches.length === 1) return coMatches[0];
    }
    // Multiple candidates = ambiguous, bail rather than guess
  }

  return null;
}

export interface InteractionInsert {
  contactId: number;
  date: string; // YYYY-MM-DD
  direction: "inbound" | "outbound" | "mutual";
  subject: string | null;
  summary: string;
  source: "whatsapp";
}

export function insertInteraction(
  cdb: DatabaseSync,
  i: InteractionInsert
): number {
  const stmt = cdb.prepare(
    `INSERT INTO interactions (contact_id, date, type, direction, subject, summary, source)
     VALUES (?, ?, 'whatsapp', ?, ?, ?, 'whatsapp')`
  );
  const r = stmt.run(i.contactId, i.date, i.direction, i.subject, i.summary);
  return Number(r.lastInsertRowid);
}

// Avoid duplicates when re-syncing: check if an interaction with the same summary already exists on that date.
export function interactionExists(
  cdb: DatabaseSync,
  contactId: number,
  date: string,
  summary: string
): boolean {
  const row = cdb
    .prepare(
      `SELECT 1 FROM interactions WHERE contact_id = ? AND date = ? AND source = 'whatsapp' AND summary = ?`
    )
    .get(contactId, date, summary);
  return !!row;
}

export function updateLastInteraction(cdb: DatabaseSync, contactId: number, date: string): void {
  cdb.prepare(`UPDATE contacts SET last_interaction = MAX(COALESCE(last_interaction, ''), ?) WHERE id = ?`).run(date, contactId);
}
