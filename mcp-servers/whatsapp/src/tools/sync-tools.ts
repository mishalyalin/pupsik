import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import {
  openWA,
  listChats,
  getMessagesForSession,
  phoneFromJid,
} from "../services/wa-reader.js";
import {
  openContacts,
  matchContact,
  insertInteraction,
  interactionExists,
  updateLastInteraction,
} from "../services/contact-matcher.js";

/**
 * Summarize a batch of messages for a given day into one interaction row.
 * Keeps the log compact — one line per direction per day per chat.
 */
function summarizeDay(
  dayMessages: Array<{ text: string | null; fromMe: boolean; date: string | null }>
): { direction: "inbound" | "outbound" | "mutual"; summary: string } {
  const mine = dayMessages.filter((m) => m.fromMe);
  const theirs = dayMessages.filter((m) => !m.fromMe);
  const direction: "inbound" | "outbound" | "mutual" =
    mine.length > 0 && theirs.length > 0 ? "mutual" : mine.length > 0 ? "outbound" : "inbound";

  // Build a tight summary: count + first meaningful line from each side
  const parts: string[] = [];
  if (theirs.length > 0) {
    const firstTheirs = theirs.find((m) => m.text && m.text.trim())?.text || "(media)";
    parts.push(`← ${theirs.length}: "${firstTheirs.slice(0, 120)}"`);
  }
  if (mine.length > 0) {
    const firstMine = mine.find((m) => m.text && m.text.trim())?.text || "(media)";
    parts.push(`→ ${mine.length}: "${firstMine.slice(0, 120)}"`);
  }
  return { direction, summary: parts.join("  ||  ") };
}

function ymd(iso: string): string {
  return iso.slice(0, 10);
}

export function registerSyncTools(server: McpServer): void {
  server.registerTool(
    "whatsapp_sync_to_contacts_db",
    {
      title: "Sync WhatsApp activity to contacts.db",
      description:
        "Scan recent WhatsApp chats, match to contacts in contacts.db (by phone/name), and insert one 'whatsapp' interaction per contact per day. " +
        "Only business contacts (those already in contacts.db) are logged — personal chats are ignored. Safe to re-run: skips duplicates.",
      inputSchema: {
        since: z
          .string()
          .describe("ISO date — only messages since this (e.g. '2026-04-01T00:00:00Z')"),
        dryRun: z
          .boolean()
          .default(false)
          .describe("If true, show what would be synced without writing"),
        maxChats: z
          .number()
          .int()
          .min(1)
          .max(2000)
          .default(500)
          .describe("Max chats to scan"),
      },
    },
    async ({ since, dryRun, maxChats }) => {
      const wa = openWA();
      const cdb = openContacts();
      const report: string[] = [];
      let matched = 0;
      let inserted = 0;
      let skippedDup = 0;

      try {
        const chats = listChats(wa, { limit: maxChats, since });
        report.push(`Scanning ${chats.length} chats active since ${since}`);

        for (const chat of chats) {
          if (chat.sessionType === 3) continue; // status
          // For groups: match on partner name only (group name), not phone
          const phone = chat.isGroup ? null : phoneFromJid(chat.jid);
          const match = matchContact(cdb, chat.partnerName, phone);
          if (!match) continue;
          matched++;

          const messages = getMessagesForSession(wa, chat.sessionId, { since, limit: 1000 });
          if (messages.length === 0) continue;

          // Group messages by day
          const byDay = new Map<string, typeof messages>();
          for (const m of messages) {
            if (!m.date) continue;
            const d = ymd(m.date);
            if (!byDay.has(d)) byDay.set(d, []);
            byDay.get(d)!.push(m);
          }

          for (const [day, dayMsgs] of byDay) {
            const { direction, summary } = summarizeDay(dayMsgs);
            const subject = chat.isGroup
              ? `WhatsApp group: ${chat.partnerName || chat.jid}`
              : `WhatsApp: ${match.name}`;

            if (interactionExists(cdb, match.id, day, summary)) {
              skippedDup++;
              continue;
            }
            if (!dryRun) {
              insertInteraction(cdb, {
                contactId: match.id,
                date: day,
                direction,
                subject,
                summary,
                source: "whatsapp",
              });
              updateLastInteraction(cdb, match.id, day);
            }
            inserted++;
            report.push(
              `${dryRun ? "[DRY]" : "[+]"} ${day}  ${match.name.padEnd(30)}  ${direction.padEnd(8)}  ${summary.slice(0, 100)}`
            );
          }
        }

        report.push("");
        report.push(
          `Summary: matched ${matched} contacts · ${dryRun ? "would insert" : "inserted"} ${inserted} interactions · skipped ${skippedDup} duplicates`
        );
      } finally {
        wa.close();
        cdb.close();
      }

      return { content: [{ type: "text", text: report.join("\n") }] };
    }
  );
}
