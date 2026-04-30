#!/usr/bin/env tsx
/**
 * Setup script for managing Google Calendar accounts.
 * Usage:
 *   npm run setup add <alias> <email>
 *   npm run setup remove <alias>
 *   npm run setup reauth <alias>
 *   npm run setup list
 */

import http from "http";
import { URL } from "url";
import { exec } from "child_process";
import { createOAuth2Client, loadTokens, saveTokens, getAuthUrl } from "./auth.js";

const args = process.argv.slice(2);
const command = args[0];

async function addAccount(alias: string, email: string): Promise<void> {
  const client = createOAuth2Client();
  const url = getAuthUrl(client);

  console.log(`\nOpen this URL in your browser (log in as ${email}):\n`);
  console.log(url);
  console.log("\nWaiting for OAuth callback on http://localhost:3456/callback ...\n");

  return new Promise((resolve, reject) => {
    const server = http.createServer(async (req, res) => {
      try {
        const reqUrl = new URL(req.url || "", "http://localhost:3456");
        if (reqUrl.pathname !== "/callback") {
          res.writeHead(404);
          res.end("Not found");
          return;
        }

        const code = reqUrl.searchParams.get("code");
        if (!code) {
          res.writeHead(400);
          res.end("No code in callback");
          return;
        }

        const { tokens } = await client.getToken(code);
        client.setCredentials(tokens);

        const store = loadTokens();
        store[alias] = {
          email,
          tokens: tokens as any,
        };
        saveTokens(store);

        res.writeHead(200, { "Content-Type": "text/html" });
        res.end(`<h1>Success!</h1><p>Account "${alias}" (${email}) added to multi-gcal-mcp.</p><p>You can close this tab.</p>`);

        console.log(`Account "${alias}" (${email}) added successfully!`);
        server.close();
        resolve();
      } catch (err) {
        res.writeHead(500);
        res.end("Error processing callback");
        console.error("Error:", err);
        server.close();
        reject(err);
      }
    });

    server.listen(3456, () => {
      // Auto-open URL in browser on macOS
      exec(`open "${url}"`);
      console.log("Opening browser...");
    });

    server.on("error", (err: NodeJS.ErrnoException) => {
      if (err.code === "EADDRINUSE") {
        console.error("Port 3456 busy. Killing previous process...");
        exec("lsof -ti:3456 | xargs kill -9 2>/dev/null", () => {
          // Retry after killing
          setTimeout(() => {
            server.listen(3456, () => {
              exec(`open "${url}"`);
              console.log("Opening browser...");
            });
          }, 500);
        });
        return;
      }
      reject(err);
    });
  });
}

async function removeAccount(alias: string): Promise<void> {
  const store = loadTokens();
  if (!store[alias]) {
    console.error(`Account "${alias}" not found.`);
    process.exit(1);
  }
  const email = store[alias].email;
  delete store[alias];
  saveTokens(store);
  console.log(`Account "${alias}" (${email}) removed.`);
}

async function listAccountsFn(): Promise<void> {
  const store = loadTokens();
  const entries = Object.entries(store);
  if (entries.length === 0) {
    console.log("No accounts configured. Run: npm run setup add <alias> <email>");
    return;
  }
  console.log("\nConfigured accounts:");
  for (const [alias, data] of entries) {
    console.log(`  ${alias}: ${data.email}`);
  }
  console.log("");
}

async function main(): Promise<void> {
  switch (command) {
    case "add": {
      const alias = args[1];
      const email = args[2];
      if (!alias || !email) {
        console.error("Usage: npm run setup add <alias> <email>");
        process.exit(1);
      }
      await addAccount(alias, email);
      break;
    }
    case "remove": {
      const alias = args[1];
      if (!alias) {
        console.error("Usage: npm run setup remove <alias>");
        process.exit(1);
      }
      await removeAccount(alias);
      break;
    }
    case "reauth": {
      const alias = args[1];
      if (!alias) {
        console.error("Usage: npm run setup reauth <alias>");
        process.exit(1);
      }
      const store = loadTokens();
      if (!store[alias]) {
        console.error(`Account "${alias}" not found.`);
        process.exit(1);
      }
      await addAccount(alias, store[alias].email);
      break;
    }
    case "list":
      await listAccountsFn();
      break;
    default:
      console.error("Commands: add, remove, reauth, list");
      console.error("  npm run setup add <alias> <email>");
      console.error("  npm run setup remove <alias>");
      console.error("  npm run setup reauth <alias>");
      console.error("  npm run setup list");
      process.exit(1);
  }
}

main().catch((err) => {
  console.error("Fatal error:", err);
  process.exit(1);
});
