#!/usr/bin/env node
/**
 * Setup CLI — add/remove/list Gmail accounts
 * Usage:
 *   npm run setup list
 *   npm run setup add personal
 *   npm run setup add work
 *   npm run setup remove john@gmail.com
 */

import { addAccount, reAuthAccount } from "./services/auth.js";
import { listAccounts, removeAccount } from "./services/token-store.js";

const [, , command, arg] = process.argv;

async function run(): Promise<void> {
  switch (command) {
    case "list": {
      const accounts = await listAccounts();
      if (accounts.length === 0) {
        console.log("No accounts connected yet.");
        console.log("Run: npm run setup add <label>");
        console.log("Example labels: personal, work, kids, school");
      } else {
        console.log(`\nConnected accounts (${accounts.length}):\n`);
        accounts.forEach(a => {
          console.log(`  📧 ${a.email}  [${a.label}]  added: ${new Date(a.addedAt).toLocaleDateString()}`);
        });
        console.log();
      }
      break;
    }

    case "add": {
      const label = arg || "personal";
      console.log(`\nAdding account with label: "${label}"`);
      console.log("Make sure GMAIL_CLIENT_ID and GMAIL_CLIENT_SECRET are set.\n");
      const email = await addAccount(label);
      console.log(`\nSuccess! ${email} is now connected as "${label}".`);
      console.log("Run 'npm run setup list' to see all accounts.\n");
      break;
    }

    case "remove": {
      if (!arg) {
        console.error("Usage: npm run setup remove <email>");
        process.exit(1);
      }
      const removed = await removeAccount(arg);
      if (removed) {
        console.log(`✅ Removed: ${arg}`);
      } else {
        console.error(`❌ Account not found: ${arg}`);
        process.exit(1);
      }
      break;
    }

    case "reauth": {
      if (!arg) {
        console.error("Usage: npm run setup reauth <email>");
        console.error("Example: npm run setup reauth alice@example.com");
        process.exit(1);
      }
      console.log(`\nRe-authorizing account: ${arg}`);
      console.log("This will remove the stale token and open a fresh Google sign-in.\n");
      const email = await reAuthAccount(arg);
      console.log(`\n✅ Success! ${email} has been re-authorized with correct scopes.`);
      console.log("Run 'npm run setup list' to confirm.\n");
      break;
    }

    default:
      console.log(`
Multi-Gmail MCP Server — Account Setup

Commands:
  npm run setup list              List all connected accounts
  npm run setup add <label>       Add a new Gmail account
  npm run setup remove <email>    Remove a connected account
  npm run setup reauth <email>    Re-authorize a broken account (fixes Insufficient Permission)

Examples:
  npm run setup add personal
  npm run setup add work
  npm run setup add kids
  npm run setup remove john@gmail.com
  npm run setup reauth john@gmail.com

Prerequisites:
  1. Create a Google Cloud project at https://console.cloud.google.com
  2. Enable the Gmail API
  3. Create OAuth 2.0 credentials (Desktop app)
  4. Set environment variables:
     export GMAIL_CLIENT_ID=your_client_id
     export GMAIL_CLIENT_SECRET=your_client_secret
      `);
  }
}



run().catch(err => {
  console.error("Setup error:", err.message);
  process.exit(1);
});
