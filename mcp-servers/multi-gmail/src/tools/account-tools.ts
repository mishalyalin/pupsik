import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import { listAccounts, removeAccount } from "../services/token-store.js";
import { getProfile } from "../services/gmail-client.js";

// ============================================================
// Account Management Tools
// ============================================================

export function registerAccountTools(server: McpServer): void {

  // ── List connected accounts ─────────────────────────────
  server.registerTool(
    "gmail_list_accounts",
    {
      title: "List Connected Gmail Accounts",
      description: `Returns all Gmail accounts currently connected to this MCP server.

Returns:
  Array of account objects with fields:
  - email: Gmail address
  - label: Human label (e.g. "personal", "work", "kids")
  - addedAt: ISO timestamp when account was connected

Use this before calling gmail_search_all or gmail_search to know which accounts are available.`,
      inputSchema: z.object({}),
      annotations: {
        readOnlyHint: true,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: false
      }
    },
    async () => {
      const accounts = await listAccounts();

      if (accounts.length === 0) {
        return {
          content: [{
            type: "text",
            text: "No accounts connected yet. Run: npm run setup add <label>\n" +
              "Example: npm run setup add personal"
          }]
        };
      }

      // Enrich with live profile data (total messages count)
      const enriched = await Promise.allSettled(
        accounts.map(async a => {
          try {
            const profile = await getProfile(a.email);
            return { ...a, messagesTotal: profile.messagesTotal, status: "connected" };
          } catch (err) {
            const errStr = String(err);
            const isPermissionError =
              errStr.includes("Insufficient Permission") ||
              errStr.includes("insufficient_scope") ||
              errStr.includes("403");
            return {
              ...a,
              messagesTotal: null,
              status: "broken",
              error: isPermissionError
                ? "Insufficient Permission — token was granted with wrong or missing OAuth scopes"
                : errStr,
              fix: isPermissionError
                ? `npm run setup reauth ${a.email}`
                : `npm run setup remove ${a.email}  then  npm run setup add <label>`
            };
          }
        })
      );

      const result = enriched.map(r => r.status === "fulfilled" ? r.value : { error: "unknown" });

      // Build human-readable summary
      const lines: string[] = [];
      for (const acc of result) {
        if ("error" in acc && acc.error) {
          lines.push(`❌ ${(acc as { email?: string }).email ?? "unknown"} — BROKEN`);
          lines.push(`   Error: ${(acc as { error?: string }).error}`);
          lines.push(`   Fix:   ${(acc as { fix?: string }).fix ?? "re-add the account"}`);
        } else {
          const a = acc as { email: string; label: string; messagesTotal: number };
          lines.push(`✅ ${a.email} (${a.label}) — ${a.messagesTotal?.toLocaleString() ?? "?"} messages`);
        }
      }

      return {
        content: [{
          type: "text",
          text: lines.join("\n") + "\n\n" + JSON.stringify(result, null, 2)
        }],
        structuredContent: { accounts: result } as { [key: string]: unknown }
      };
    }
  );

  // ── Remove an account ────────────────────────────────────
  server.registerTool(
    "gmail_remove_account",
    {
      title: "Remove Connected Gmail Account",
      description: `Disconnects a Gmail account from this MCP server and deletes its stored tokens from the OS keychain.

Args:
  - email (string): The Gmail address to remove (must match exactly)

Returns:
  Success or error message.

Note: This does NOT revoke Google authorization. To fully revoke, visit:
https://myaccount.google.com/permissions`,
      inputSchema: z.object({
        email: z.string().email().describe("Gmail address to disconnect")
      }),
      annotations: {
        readOnlyHint: false,
        destructiveHint: true,
        idempotentHint: false,
        openWorldHint: false
      }
    },
    async ({ email }) => {
      const removed = await removeAccount(email);
      if (!removed) {
        return {
          content: [{
            type: "text",
            text: `Account not found: ${email}. Use gmail_list_accounts to see connected accounts.`
          }]
        };
      }
      return {
        content: [{
          type: "text",
          text: `✅ Account removed: ${email}\nTokens deleted from keychain.`
        }]
      };
    }
  );
}
