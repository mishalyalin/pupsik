import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { registerChatTools } from "./tools/chat-tools.js";
import { registerSyncTools } from "./tools/sync-tools.js";

// ============================================================
// WhatsApp MCP Server
// Reads ~/Library/Group Containers/group.net.whatsapp.WhatsApp.shared/ChatStorage.sqlite
// (readonly) and syncs business-contact interactions into ~/Desktop/claude/data/contacts.db.
// No new logins — uses the already-signed-in desktop WhatsApp app's local data.
// ============================================================

const server = new McpServer({
  name: "whatsapp-mcp-server",
  version: "1.0.0",
});

registerChatTools(server);
registerSyncTools(server);

// Crash guards — keep the MCP alive through unexpected errors so Claude Code doesn't mark it disconnected.
process.on("uncaughtException", (err) => {
  console.error("[whatsapp-mcp] uncaughtException:", err);
});
process.on("unhandledRejection", (reason) => {
  console.error("[whatsapp-mcp] unhandledRejection:", reason);
});

async function main(): Promise<void> {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error("[whatsapp-mcp] Server started via stdio");
}

main().catch((err) => {
  console.error("[whatsapp-mcp] Fatal error in main:", err);
});
