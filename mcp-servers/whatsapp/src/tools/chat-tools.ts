import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import {
  openWA,
  listChats,
  findChats,
  getMessagesForSession,
  searchMessages,
  phoneFromJid,
  type WAChat,
  type WAMessage,
} from "../services/wa-reader.js";
import { openContacts, matchContact } from "../services/contact-matcher.js";

function chatLine(c: WAChat): string {
  const tag = c.isGroup ? "[group]" : c.sessionType === 3 ? "[status]" : "[dm]";
  const name = c.partnerName || c.jid || "(unknown)";
  const unread = c.unreadCount > 0 ? ` 🔴${c.unreadCount}` : "";
  const last = c.lastMessageDate ? ` · ${c.lastMessageDate}` : "";
  const preview = c.lastMessageText ? ` · ${c.lastMessageText.slice(0, 80)}` : "";
  return `${tag} **${name}** (${c.jid})${unread}${last}${preview}`;
}

function msgLine(m: WAMessage): string {
  const who = m.fromMe ? "→ me" : `← ${m.pushName || m.fromJid || "?"}`;
  const when = m.date ? m.date.slice(0, 19).replace("T", " ") : "?";
  const text = m.text ? m.text.slice(0, 400) : `(no text, messageType=${m.messageType})`;
  return `${when}  ${who}:  ${text}`;
}

export function registerChatTools(server: McpServer): void {
  server.registerTool(
    "whatsapp_list_chats",
    {
      title: "List WhatsApp Chats",
      description:
        "List recent WhatsApp chats (DMs and groups) ordered by last message date. Skips status broadcasts.",
      inputSchema: {
        limit: z.number().int().min(1).max(500).default(50).describe("Max chats to return"),
        since: z.string().optional().describe("ISO date — only chats with activity after this"),
        onlyBusinessContacts: z
          .boolean()
          .default(false)
          .describe("If true, only return chats where partner is in contacts.db (filters out personal)"),
        includeGroups: z.boolean().default(true).describe("Include groups"),
      },
    },
    async ({ limit, since, onlyBusinessContacts, includeGroups }) => {
      const db = openWA();
      try {
        const chats = listChats(db, { limit: onlyBusinessContacts ? 500 : limit, since });
        let filtered = chats;
        if (!includeGroups) filtered = filtered.filter((c) => !c.isGroup);

        if (onlyBusinessContacts) {
          const cdb = openContacts();
          try {
            const withMatches = filtered.map((c) => {
              const phone = phoneFromJid(c.jid);
              const match = matchContact(cdb, c.partnerName, phone);
              return { chat: c, match };
            });
            const businessOnly = withMatches.filter((x) => x.match);
            const lines = businessOnly.slice(0, limit).map(
              (x) => `${chatLine(x.chat)}\n    → matched: **${x.match!.name}** (${x.match!.category || "?"})`
            );
            return {
              content: [
                {
                  type: "text",
                  text: `# WhatsApp — Business contacts (${businessOnly.length} matched out of ${filtered.length} chats)\n\n${lines.join("\n\n")}`,
                },
              ],
            };
          } finally {
            cdb.close();
          }
        }

        const lines = filtered.slice(0, limit).map(chatLine);
        return {
          content: [
            {
              type: "text",
              text: `# WhatsApp — ${filtered.length} chats\n\n${lines.join("\n")}`,
            },
          ],
        };
      } finally {
        db.close();
      }
    }
  );

  server.registerTool(
    "whatsapp_messages_with",
    {
      title: "Get Messages with a Contact",
      description:
        "Fetch message history with a specific chat. Provide either a JID (e.g. '15555550100@s.whatsapp.net') or a partner name substring (e.g. 'Alice').",
      inputSchema: {
        chat: z.string().describe("JID or partner-name substring"),
        limit: z.number().int().min(1).max(500).default(50),
        since: z.string().optional().describe("ISO date — only messages after this"),
      },
    },
    async ({ chat, limit, since }) => {
      const db = openWA();
      try {
        const matches = findChats(db, chat, 5);
        if (matches.length === 0) {
          return { content: [{ type: "text", text: `No chat found matching "${chat}".` }] };
        }
        if (matches.length > 1) {
          const list = matches.map(chatLine).join("\n");
          return {
            content: [
              { type: "text", text: `Multiple matches for "${chat}". Be more specific:\n\n${list}` },
            ],
          };
        }
        const target = matches[0];
        const messages = getMessagesForSession(db, target.sessionId, { limit, since });
        const body = messages
          .slice()
          .reverse()
          .map(msgLine)
          .join("\n");
        return {
          content: [
            {
              type: "text",
              text: `# ${target.partnerName || target.jid}\n${target.isGroup ? "(group)" : "(DM)"} · ${target.jid}\n\n${body || "(no messages)"}`,
            },
          ],
        };
      } finally {
        db.close();
      }
    }
  );

  server.registerTool(
    "whatsapp_search",
    {
      title: "Search WhatsApp Messages",
      description: "Full-text search across all WhatsApp messages (text only). Returns matching messages with chat context.",
      inputSchema: {
        query: z.string().min(1),
        limit: z.number().int().min(1).max(200).default(30),
        since: z.string().optional(),
      },
    },
    async ({ query, limit, since }) => {
      const db = openWA();
      try {
        const results = searchMessages(db, query, { limit, since });
        if (results.length === 0) {
          return { content: [{ type: "text", text: `No matches for "${query}".` }] };
        }
        // Group by chat
        const byChat = new Map<number, WAMessage[]>();
        for (const m of results) {
          if (!byChat.has(m.sessionId)) byChat.set(m.sessionId, []);
          byChat.get(m.sessionId)!.push(m);
        }
        const out: string[] = [];
        for (const [sid, msgs] of byChat) {
          const chatInfo = findChats(db, "", 1); // not ideal, but get header via jid
          const jid = msgs[0]?.jid || "?";
          const sessionRow = db
            .prepare(`SELECT ZPARTNERNAME as n FROM ZWACHATSESSION WHERE Z_PK = ?`)
            .get(sid) as { n: string | null } | undefined;
          const name = sessionRow?.n || jid;
          out.push(`## ${name} (${jid})\n${msgs.map(msgLine).join("\n")}`);
          void chatInfo;
        }
        return {
          content: [
            { type: "text", text: `# Search: "${query}" — ${results.length} matches\n\n${out.join("\n\n")}` },
          ],
        };
      } finally {
        db.close();
      }
    }
  );
}
