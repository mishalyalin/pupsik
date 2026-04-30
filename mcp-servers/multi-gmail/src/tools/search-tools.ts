import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import { listAccounts } from "../services/token-store.js";
import { searchMessages, readMessage, readThread, listAttachments, downloadAttachment } from "../services/gmail-client.js";
import { MAX_RESULTS_DEFAULT, MAX_RESULTS_LIMIT } from "../constants.js";
import type { EmailMessage, FailedAccount, AggregatedSearchResult } from "../types.js";

// ============================================================
// Gmail Search & Read Tools
// ============================================================

export function registerSearchTools(server: McpServer): void {

  // ── Search across ALL accounts ───────────────────────────
  server.registerTool(
    "gmail_search_all",
    {
      title: "Search All Gmail Accounts",
      description: `Searches across ALL connected Gmail accounts simultaneously and returns aggregated results tagged by account.

This is the primary tool for multi-account inbox triage. Results include which account each email belongs to.

Args:
  - query (string): Gmail search syntax. Examples:
      "after:2026/03/12 -category:promotions"
      "is:unread from:boss@company.com"
      "subject:invoice after:2026/01/01"
  - max_per_account (number): Max messages per account (1–${MAX_RESULTS_LIMIT}, default: ${MAX_RESULTS_DEFAULT})

Returns:
  {
    accounts_searched: string[],     // emails successfully searched
    accounts_failed: [               // accounts that errored (token expired etc)
      { email: string, error: string }
    ],
    total_messages: number,
    messages: [
      {
        id: string,
        threadId: string,
        account: string,             // ← which Gmail this came from
        from: string,
        to: string,
        subject: string,
        date: string,
        snippet: string,
        body: string,
        labelIds: string[],
        isUnread: boolean,
        hasAttachment: boolean
      }
    ]
  }

Use this for gmail-summary across all accounts. Filter by account label if needed using gmail_list_accounts first.`,
      inputSchema: z.object({
        query: z.string()
          .min(1)
          .describe("Gmail search query, e.g. 'after:2026/03/12 -category:promotions'"),
        max_per_account: z.number()
          .int()
          .min(1)
          .max(MAX_RESULTS_LIMIT)
          .default(MAX_RESULTS_DEFAULT)
          .describe("Maximum messages to fetch per account")
      }),
      annotations: {
        readOnlyHint: true,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: true
      }
    },
    async ({ query, max_per_account }) => {
      const accounts = await listAccounts();

      if (accounts.length === 0) {
        return {
          content: [{
            type: "text",
            text: "No accounts connected. Run: npm run setup add <label>"
          }]
        };
      }

      const results = await Promise.allSettled(
        accounts.map(a => searchMessages(a.email, query, max_per_account))
      );

      const allMessages: EmailMessage[] = [];
      const accountsSearched: string[] = [];
      const accountsFailed: FailedAccount[] = [];

      results.forEach((result, i) => {
        const email = accounts[i].email;
        if (result.status === "fulfilled") {
          accountsSearched.push(email);
          allMessages.push(...result.value);
        } else {
          accountsFailed.push({
            email,
            error: result.reason instanceof Error ? result.reason.message : String(result.reason)
          });
        }
      });

      // Sort all messages by date descending
      allMessages.sort((a, b) => {
        const da = new Date(a.date).getTime();
        const db = new Date(b.date).getTime();
        return db - da;
      });

      const output: AggregatedSearchResult = {
        accounts_searched: accountsSearched,
        accounts_failed: accountsFailed,
        total_messages: allMessages.length,
        messages: allMessages
      };

      return {
        content: [{
          type: "text",
          text: JSON.stringify(output, null, 2)
        }],
        structuredContent: output as unknown as { [key: string]: unknown }
      };
    }
  );

  // ── Search a single specific account ────────────────────
  server.registerTool(
    "gmail_search",
    {
      title: "Search Single Gmail Account",
      description: `Searches a specific Gmail account by email address.

Use this when you want to search one account specifically instead of all accounts.

Args:
  - email (string): The Gmail address to search (must be a connected account)
  - query (string): Gmail search syntax
  - max_results (number): Max messages to return (default: ${MAX_RESULTS_DEFAULT})

Returns: Array of email message objects tagged with the account.`,
      inputSchema: z.object({
        email: z.string().email().describe("The Gmail account to search"),
        query: z.string().min(1).describe("Gmail search query"),
        max_results: z.number()
          .int()
          .min(1)
          .max(MAX_RESULTS_LIMIT)
          .default(MAX_RESULTS_DEFAULT)
          .describe("Maximum messages to return")
      }),
      annotations: {
        readOnlyHint: true,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: true
      }
    },
    async ({ email, query, max_results }) => {
      try {
        const messages = await searchMessages(email, query, max_results);
        return {
          content: [{
            type: "text",
            text: JSON.stringify({ account: email, count: messages.length, messages }, null, 2)
          }],
          structuredContent: { account: email, count: messages.length, messages } as { [key: string]: unknown }
        };
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        return {
          content: [{
            type: "text",
            text: `Error searching ${email}: ${msg}`
          }]
        };
      }
    }
  );

  // ── Read full message ────────────────────────────────────
  server.registerTool(
    "gmail_read_message",
    {
      title: "Read Gmail Message",
      description: `Retrieves the full content of a specific Gmail message.

Args:
  - email (string): The Gmail account the message belongs to
  - message_id (string): The message ID (from gmail_search_all or gmail_search results)

Returns: Full email message with decoded body text.`,
      inputSchema: z.object({
        email: z.string().email().describe("Gmail account the message belongs to"),
        message_id: z.string().min(1).describe("Message ID from search results")
      }),
      annotations: {
        readOnlyHint: true,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: false
      }
    },
    async ({ email, message_id }) => {
      try {
        const message = await readMessage(email, message_id);
        return {
          content: [{
            type: "text",
            text: JSON.stringify(message, null, 2)
          }],
          structuredContent: message as unknown as { [key: string]: unknown }
        };
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        return {
          content: [{ type: "text", text: `Error reading message: ${msg}` }]
        };
      }
    }
  );

  // ── List attachments on a message ────────────────────────
  server.registerTool(
    "gmail_list_attachments",
    {
      title: "List Gmail Attachments",
      description: `Lists all attachments in a specific Gmail message with metadata needed to download them.

Args:
  - email (string): Gmail account the message belongs to
  - message_id (string): Message ID (from gmail_search_all/gmail_search results)

Returns:
  {
    account: string,
    messageId: string,
    attachments: [
      { attachmentId: string, filename: string, mimeType: string, size: number, partId?: string }
    ]
  }

Pass the attachmentId (or filename) to gmail_download_attachment to save the file locally.`,
      inputSchema: z.object({
        email: z.string().email().describe("Gmail account the message belongs to"),
        message_id: z.string().min(1).describe("Message ID from search results")
      }),
      annotations: {
        readOnlyHint: true,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: false
      }
    },
    async ({ email, message_id }) => {
      try {
        const attachments = await listAttachments(email, message_id);
        const output = { account: email, messageId: message_id, attachments };
        return {
          content: [{ type: "text", text: JSON.stringify(output, null, 2) }],
          structuredContent: output as unknown as { [key: string]: unknown }
        };
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        return { content: [{ type: "text", text: `Error listing attachments: ${msg}` }] };
      }
    }
  );

  // ── Download an attachment to disk ───────────────────────
  server.registerTool(
    "gmail_download_attachment",
    {
      title: "Download Gmail Attachment",
      description: `Downloads a Gmail attachment and saves it to the local filesystem.

Either pass attachment_id (from gmail_list_attachments or gmail_read_message attachments field) or filename to select which attachment to download. If the message has exactly one attachment, both can be omitted.

Specify output_path for an exact destination, or output_dir to drop the attachment (keeping its original filename) into a directory. If neither is given, defaults to ~/Desktop/claude/outputs/gmail-attachments/.

Output path supports leading ~ for home directory expansion. Parent directories are created automatically.

Args:
  - email (string): Gmail account the message belongs to
  - message_id (string): Message ID
  - attachment_id (string, optional): Gmail attachment ID
  - filename (string, optional): Attachment filename (exact or case-insensitive match)
  - output_path (string, optional): Full destination path (overrides output_dir)
  - output_dir (string, optional): Directory to save into (uses original filename, sanitized)

Returns: { account, messageId, attachmentId, filename, mimeType, size, outputPath }`,
      inputSchema: z.object({
        email: z.string().email().describe("Gmail account the message belongs to"),
        message_id: z.string().min(1).describe("Message ID"),
        attachment_id: z.string().optional().describe("Gmail attachment ID (preferred)"),
        filename: z.string().optional().describe("Attachment filename (fallback selector)"),
        output_path: z.string().optional().describe("Full destination path, overrides output_dir"),
        output_dir: z.string().optional().describe("Directory to save into; uses original filename")
      }),
      annotations: {
        readOnlyHint: false,
        destructiveHint: false,
        idempotentHint: false,
        openWorldHint: true
      }
    },
    async ({ email, message_id, attachment_id, filename, output_path, output_dir }) => {
      try {
        const result = await downloadAttachment(email, message_id, {
          attachmentId: attachment_id,
          filename,
          outputPath: output_path,
          outputDir: output_dir
        });
        return {
          content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
          structuredContent: result as unknown as { [key: string]: unknown }
        };
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        return { content: [{ type: "text", text: `Error downloading attachment: ${msg}` }] };
      }
    }
  );

  // ── Read full thread ─────────────────────────────────────
  server.registerTool(
    "gmail_read_thread",
    {
      title: "Read Gmail Thread",
      description: `Retrieves a full email conversation thread with all messages in order.

Args:
  - email (string): The Gmail account the thread belongs to
  - thread_id (string): The thread ID (from search results)

Returns: Thread with all messages decoded and in chronological order.`,
      inputSchema: z.object({
        email: z.string().email().describe("Gmail account the thread belongs to"),
        thread_id: z.string().min(1).describe("Thread ID from search results")
      }),
      annotations: {
        readOnlyHint: true,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: false
      }
    },
    async ({ email, thread_id }) => {
      try {
        const thread = await readThread(email, thread_id);
        return {
          content: [{
            type: "text",
            text: JSON.stringify(thread, null, 2)
          }],
          structuredContent: thread as unknown as { [key: string]: unknown }
        };
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        return {
          content: [{ type: "text", text: `Error reading thread: ${msg}` }]
        };
      }
    }
  );
}
