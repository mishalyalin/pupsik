#!/usr/bin/env node
/**
 * Multi-account Google Calendar MCP Server.
 * Supports multiple Google accounts via OAuth2.
 * Transport: stdio (for local Claude Code / Cowork integration).
 *
 * Environment variables (reuses Gmail MCP credentials if set):
 *   GCAL_CLIENT_ID or GMAIL_CLIENT_ID
 *   GCAL_CLIENT_SECRET or GMAIL_CLIENT_SECRET
 */

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { google, calendar_v3 } from "googleapis";
import { z } from "zod";
import { getAuthClientForAccount, listAccounts } from "./auth.js";

const server = new McpServer({
  name: "multi-gcal-mcp-server",
  version: "1.0.0",
});

// ─── Helpers ────────────────────────────────────────────────────────

function getCalendar(account: string): calendar_v3.Calendar {
  const auth = getAuthClientForAccount(account);
  return google.calendar({ version: "v3", auth });
}

function formatDateTime(dt: string | null | undefined, tz?: string): string {
  if (!dt) return "N/A";
  try {
    const d = new Date(dt);
    return d.toLocaleString("en-GB", {
      timeZone: tz || "Europe/London",
      dateStyle: "medium",
      timeStyle: "short",
    });
  } catch {
    return dt;
  }
}

function eventToMarkdown(ev: calendar_v3.Schema$Event, tz?: string): string {
  const start = ev.start?.dateTime
    ? formatDateTime(ev.start.dateTime, tz)
    : ev.start?.date || "?";
  const end = ev.end?.dateTime
    ? formatDateTime(ev.end.dateTime, tz)
    : ev.end?.date || "";
  const attendees = (ev.attendees || [])
    .map((a) => `${a.displayName || a.email} (${a.responseStatus})`)
    .join(", ");

  const lines = [
    `### ${ev.summary || "(no title)"}`,
    `- **When**: ${start}${end ? ` → ${end}` : ""}`,
    ev.location ? `- **Where**: ${ev.location}` : "",
    ev.hangoutLink ? `- **Meet**: ${ev.hangoutLink}` : "",
    attendees ? `- **Attendees**: ${attendees}` : "",
    ev.description ? `- **Description**: ${ev.description.slice(0, 300)}${ev.description.length > 300 ? "..." : ""}` : "",
    `- **Status**: ${ev.status || "confirmed"} | ID: ${ev.id}`,
  ];
  return lines.filter(Boolean).join("\n");
}

function eventToJson(ev: calendar_v3.Schema$Event): Record<string, unknown> {
  return {
    id: ev.id,
    summary: ev.summary,
    start: ev.start,
    end: ev.end,
    location: ev.location,
    description: ev.description?.slice(0, 500),
    hangoutLink: ev.hangoutLink,
    status: ev.status,
    organizer: ev.organizer,
    attendees: ev.attendees?.map((a) => ({
      email: a.email,
      displayName: a.displayName,
      responseStatus: a.responseStatus,
      self: a.self,
    })),
    htmlLink: ev.htmlLink,
    recurringEventId: ev.recurringEventId,
  };
}

// ─── Tools ──────────────────────────────────────────────────────────

// 1. List configured accounts
server.registerTool(
  "gcal_list_accounts",
  {
    title: "List Calendar Accounts",
    description: `List all configured Google Calendar accounts.
Returns alias and email for each account. Use the alias in other tools to specify which account to query.`,
    inputSchema: {},
    annotations: { readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: false },
  },
  async () => {
    const accounts = listAccounts();
    if (accounts.length === 0) {
      return { content: [{ type: "text", text: "No accounts configured. Run: npm run setup add <alias> <email>" }] };
    }
    const text = accounts.map((a) => `- **${a.alias}**: ${a.email}`).join("\n");
    return { content: [{ type: "text", text: `# Configured Accounts\n${text}` }] };
  }
);

// 2. List calendars for an account
server.registerTool(
  "gcal_list_calendars",
  {
    title: "List Calendars",
    description: `List all calendars for a given account.
Args:
  - account: Account alias (e.g. "personal", "work", "school")
Returns calendar id, summary, and access role.`,
    inputSchema: {
      account: z.string().describe("Account alias"),
    },
    annotations: { readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: true },
  },
  async ({ account }) => {
    const cal = getCalendar(account);
    const res = await cal.calendarList.list();
    const calendars = res.data.items || [];
    const lines = calendars.map(
      (c) => `- **${c.summary}** (${c.id}) — ${c.accessRole}${c.primary ? " [PRIMARY]" : ""}`
    );
    return {
      content: [{ type: "text", text: `# Calendars for "${account}"\n${lines.join("\n")}` }],
    };
  }
);

// 3. List events
server.registerTool(
  "gcal_list_events",
  {
    title: "List Events",
    description: `List calendar events for a given account within a time range.
Args:
  - account: Account alias
  - calendarId: Calendar ID (default: "primary")
  - timeMin: Start time ISO 8601 (e.g. "2026-04-11T00:00:00+01:00")
  - timeMax: End time ISO 8601
  - maxResults: Max events (default 50, max 250)
  - q: Free text search query
  - timeZone: IANA timezone (default "Europe/London")`,
    inputSchema: {
      account: z.string().describe("Account alias"),
      calendarId: z.string().default("primary").describe("Calendar ID"),
      timeMin: z.string().optional().describe("Start time ISO 8601"),
      timeMax: z.string().optional().describe("End time ISO 8601"),
      maxResults: z.number().int().min(1).max(250).default(50).describe("Max events"),
      q: z.string().optional().describe("Search query"),
      timeZone: z.string().default("Europe/London").describe("IANA timezone"),
    },
    annotations: { readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: true },
  },
  async ({ account, calendarId, timeMin, timeMax, maxResults, q, timeZone }) => {
    const cal = getCalendar(account);
    const params: calendar_v3.Params$Resource$Events$List = {
      calendarId,
      maxResults,
      singleEvents: true,
      orderBy: "startTime",
      timeZone,
    };
    if (timeMin) params.timeMin = timeMin;
    if (timeMax) params.timeMax = timeMax;
    if (q) params.q = q;

    const res = await cal.events.list(params);
    const events = res.data.items || [];

    if (events.length === 0) {
      return { content: [{ type: "text", text: `No events found for "${account}" (${calendarId}).` }] };
    }

    const md = events.map((e) => eventToMarkdown(e, timeZone)).join("\n\n");
    return {
      content: [{ type: "text", text: `# Events (${account} / ${calendarId})\n\n${md}` }],
    };
  }
);

// 4. List events across ALL accounts
server.registerTool(
  "gcal_list_all_events",
  {
    title: "List All Events (All Accounts)",
    description: `List events from ALL configured accounts' primary calendars. Great for morning briefings.
Args:
  - timeMin: Start time ISO 8601
  - timeMax: End time ISO 8601
  - timeZone: IANA timezone (default "Europe/London")
  - maxResults: Max events per account (default 20)`,
    inputSchema: {
      timeMin: z.string().describe("Start time ISO 8601"),
      timeMax: z.string().describe("End time ISO 8601"),
      timeZone: z.string().default("Europe/London").describe("IANA timezone"),
      maxResults: z.number().int().min(1).max(100).default(20).describe("Max events per account"),
    },
    annotations: { readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: true },
  },
  async ({ timeMin, timeMax, timeZone, maxResults }) => {
    const accounts = listAccounts();
    if (accounts.length === 0) {
      return { content: [{ type: "text", text: "No accounts configured." }] };
    }

    const sections: string[] = [];
    for (const { alias, email } of accounts) {
      try {
        const cal = getCalendar(alias);
        const res = await cal.events.list({
          calendarId: "primary",
          timeMin,
          timeMax,
          maxResults,
          singleEvents: true,
          orderBy: "startTime",
          timeZone,
        });
        const events = res.data.items || [];
        if (events.length === 0) {
          sections.push(`## ${alias} (${email})\nNo events.`);
        } else {
          const md = events.map((e) => eventToMarkdown(e, timeZone)).join("\n\n");
          sections.push(`## ${alias} (${email})\n\n${md}`);
        }
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : String(err);
        sections.push(`## ${alias} (${email})\n**Error**: ${msg}`);
      }
    }

    return {
      content: [{ type: "text", text: `# All Calendars\n\n${sections.join("\n\n---\n\n")}` }],
    };
  }
);

// 5. Get single event
server.registerTool(
  "gcal_get_event",
  {
    title: "Get Event Details",
    description: `Get full details of a specific event.
Args:
  - account: Account alias
  - calendarId: Calendar ID (default "primary")
  - eventId: Event ID`,
    inputSchema: {
      account: z.string().describe("Account alias"),
      calendarId: z.string().default("primary").describe("Calendar ID"),
      eventId: z.string().describe("Event ID"),
    },
    annotations: { readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: true },
  },
  async ({ account, calendarId, eventId }) => {
    const cal = getCalendar(account);
    const res = await cal.events.get({ calendarId, eventId });
    const ev = res.data;
    return {
      content: [{ type: "text", text: eventToMarkdown(ev) }],
      structuredContent: eventToJson(ev),
    };
  }
);

// 6. Create event
server.registerTool(
  "gcal_create_event",
  {
    title: "Create Event",
    description: `Create a new calendar event.
Args:
  - account: Account alias
  - calendarId: Calendar ID (default "primary")
  - summary: Event title
  - start: Start time ISO 8601
  - end: End time ISO 8601
  - description: Event description (optional)
  - location: Event location (optional)
  - timeZone: IANA timezone (default "Europe/London")
  - attendees: Array of email addresses (optional)`,
    inputSchema: {
      account: z.string().describe("Account alias"),
      calendarId: z.string().default("primary").describe("Calendar ID"),
      summary: z.string().describe("Event title"),
      start: z.string().describe("Start time ISO 8601"),
      end: z.string().describe("End time ISO 8601"),
      description: z.string().optional().describe("Event description"),
      location: z.string().optional().describe("Event location"),
      timeZone: z.string().default("Europe/London").describe("IANA timezone"),
      attendees: z.array(z.string()).optional().describe("Attendee email addresses"),
    },
    annotations: { readOnlyHint: false, destructiveHint: false, idempotentHint: false, openWorldHint: true },
  },
  async ({ account, calendarId, summary, start, end, description, location, timeZone, attendees }) => {
    const cal = getCalendar(account);
    const event: calendar_v3.Schema$Event = {
      summary,
      start: { dateTime: start, timeZone },
      end: { dateTime: end, timeZone },
    };
    if (description) event.description = description;
    if (location) event.location = location;
    if (attendees) event.attendees = attendees.map((email) => ({ email }));

    const res = await cal.events.insert({
      calendarId,
      requestBody: event,
      sendUpdates: "all",
    });

    return {
      content: [{ type: "text", text: `Event created: **${res.data.summary}** (${res.data.htmlLink})` }],
      structuredContent: eventToJson(res.data),
    };
  }
);

// 7. Update event
server.registerTool(
  "gcal_update_event",
  {
    title: "Update Event",
    description: `Update an existing calendar event.
Args:
  - account: Account alias
  - calendarId: Calendar ID (default "primary")
  - eventId: Event ID to update
  - summary, start, end, description, location, timeZone: Fields to update (all optional)`,
    inputSchema: {
      account: z.string().describe("Account alias"),
      calendarId: z.string().default("primary").describe("Calendar ID"),
      eventId: z.string().describe("Event ID"),
      summary: z.string().optional().describe("New title"),
      start: z.string().optional().describe("New start time ISO 8601"),
      end: z.string().optional().describe("New end time ISO 8601"),
      description: z.string().optional().describe("New description"),
      location: z.string().optional().describe("New location"),
      timeZone: z.string().default("Europe/London").describe("IANA timezone"),
    },
    annotations: { readOnlyHint: false, destructiveHint: false, idempotentHint: true, openWorldHint: true },
  },
  async ({ account, calendarId, eventId, summary, start, end, description, location, timeZone }) => {
    const cal = getCalendar(account);
    const patch: calendar_v3.Schema$Event = {};
    if (summary) patch.summary = summary;
    if (start) patch.start = { dateTime: start, timeZone };
    if (end) patch.end = { dateTime: end, timeZone };
    if (description !== undefined) patch.description = description;
    if (location !== undefined) patch.location = location;

    const res = await cal.events.patch({
      calendarId,
      eventId,
      requestBody: patch,
      sendUpdates: "all",
    });

    return {
      content: [{ type: "text", text: `Event updated: **${res.data.summary}** (${res.data.htmlLink})` }],
    };
  }
);

// 8. Delete event
server.registerTool(
  "gcal_delete_event",
  {
    title: "Delete Event",
    description: `Delete a calendar event.
Args:
  - account: Account alias
  - calendarId: Calendar ID (default "primary")
  - eventId: Event ID to delete`,
    inputSchema: {
      account: z.string().describe("Account alias"),
      calendarId: z.string().default("primary").describe("Calendar ID"),
      eventId: z.string().describe("Event ID"),
    },
    annotations: { readOnlyHint: false, destructiveHint: true, idempotentHint: true, openWorldHint: true },
  },
  async ({ account, calendarId, eventId }) => {
    const cal = getCalendar(account);
    await cal.events.delete({ calendarId, eventId, sendUpdates: "all" });
    return {
      content: [{ type: "text", text: `Event ${eventId} deleted.` }],
    };
  }
);

// 9. Find free time
server.registerTool(
  "gcal_free_busy",
  {
    title: "Check Free/Busy",
    description: `Check free/busy status across accounts.
Args:
  - accounts: Array of account aliases to check
  - timeMin: Start time ISO 8601
  - timeMax: End time ISO 8601
  - timeZone: IANA timezone (default "Europe/London")`,
    inputSchema: {
      accounts: z.array(z.string()).describe("Account aliases to check"),
      timeMin: z.string().describe("Start time ISO 8601"),
      timeMax: z.string().describe("End time ISO 8601"),
      timeZone: z.string().default("Europe/London").describe("IANA timezone"),
    },
    annotations: { readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: true },
  },
  async ({ accounts: accountAliases, timeMin, timeMax, timeZone }) => {
    const sections: string[] = [];
    for (const alias of accountAliases) {
      try {
        const cal = getCalendar(alias);
        const allAccounts = listAccounts();
        const thisAccount = allAccounts.find((a) => a.alias === alias);
        const email = thisAccount?.email || "primary";

        const res = await cal.freebusy.query({
          requestBody: {
            timeMin,
            timeMax,
            timeZone,
            items: [{ id: email }],
          },
        });

        const busy = res.data.calendars?.[email]?.busy || [];
        if (busy.length === 0) {
          sections.push(`**${alias}**: Free for entire period`);
        } else {
          const slots = busy
            .map((b) => `  - ${formatDateTime(b.start, timeZone)} → ${formatDateTime(b.end, timeZone)}`)
            .join("\n");
          sections.push(`**${alias}**: Busy:\n${slots}`);
        }
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : String(err);
        sections.push(`**${alias}**: Error — ${msg}`);
      }
    }

    return {
      content: [{ type: "text", text: `# Free/Busy\n\n${sections.join("\n\n")}` }],
    };
  }
);

// ─── Main ───────────────────────────────────────────────────────────

// Crash guards — keep MCP alive through unexpected errors.
process.on("uncaughtException", (err) => {
  console.error("[multi-gcal-mcp] uncaughtException:", err);
});
process.on("unhandledRejection", (reason) => {
  console.error("[multi-gcal-mcp] unhandledRejection:", reason);
});

async function main(): Promise<void> {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error("multi-gcal-mcp-server running via stdio");
}

main().catch((err) => {
  console.error("[multi-gcal-mcp] Fatal error in main:", err);
  // Don't exit — let Claude Code reconnect.
});
