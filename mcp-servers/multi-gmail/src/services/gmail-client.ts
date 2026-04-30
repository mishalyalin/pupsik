import { google } from "googleapis";
import fs from "fs";
import path from "path";
import { getAuthenticatedClient } from "./auth.js";
import type { EmailMessage, EmailThread, ThreadMessage, GmailProfile, AttachmentInfo } from "../types.js";

// ============================================================
// Gmail Client — wraps Gmail API calls per account
// ============================================================

function extractHeader(headers: Array<{ name?: string | null; value?: string | null }>, name: string): string {
  return headers.find(h => h.name?.toLowerCase() === name.toLowerCase())?.value ?? "";
}

function decodeBody(part: {
  body?: { data?: string | null } | null;
  parts?: unknown[] | null;
  mimeType?: string | null;
}): string {
  if (part.body?.data) {
    return Buffer.from(part.body.data, "base64").toString("utf-8");
  }
  if (part.parts && Array.isArray(part.parts)) {
    for (const p of part.parts) {
      const text = decodeBody(p as typeof part);
      if (text) return text;
    }
  }
  return "";
}

interface MessagePart {
  partId?: string | null;
  filename?: string | null;
  mimeType?: string | null;
  body?: { attachmentId?: string | null; size?: number | null; data?: string | null } | null;
  parts?: MessagePart[] | null;
}

function extractAttachments(part: MessagePart | null | undefined): AttachmentInfo[] {
  if (!part) return [];
  const out: AttachmentInfo[] = [];
  if (part.filename && part.filename.length > 0 && part.body?.attachmentId) {
    out.push({
      attachmentId: part.body.attachmentId,
      filename: part.filename,
      mimeType: part.mimeType ?? "application/octet-stream",
      size: part.body.size ?? 0,
      partId: part.partId ?? undefined
    });
  }
  if (part.parts && Array.isArray(part.parts)) {
    for (const p of part.parts) out.push(...extractAttachments(p));
  }
  return out;
}

export async function getProfile(email: string): Promise<GmailProfile> {
  const auth = await getAuthenticatedClient(email);
  const gmail = google.gmail({ version: "v1", auth });
  const { data } = await gmail.users.getProfile({ userId: "me" });
  return {
    email: data.emailAddress ?? email,
    messagesTotal: data.messagesTotal ?? 0,
    threadsTotal: data.threadsTotal ?? 0,
    historyId: data.historyId ?? ""
  };
}

export async function searchMessages(
  email: string,
  query: string,
  maxResults: number = 20
): Promise<EmailMessage[]> {
  const auth = await getAuthenticatedClient(email);
  const gmail = google.gmail({ version: "v1", auth });

  const listRes = await gmail.users.messages.list({
    userId: "me",
    q: query,
    maxResults
  });

  const messageRefs = listRes.data.messages ?? [];
  if (messageRefs.length === 0) return [];

  // Fetch full message details in parallel (batched to avoid rate limits)
  const BATCH = 10;
  const messages: EmailMessage[] = [];

  for (let i = 0; i < messageRefs.length; i += BATCH) {
    const batch = messageRefs.slice(i, i + BATCH);
    const fetched = await Promise.all(
      batch.map(ref =>
        gmail.users.messages.get({
          userId: "me",
          id: ref.id!,
          format: "full"
        })
      )
    );

    for (const res of fetched) {
      const msg = res.data;
      const headers = msg.payload?.headers ?? [];
      const attachments = extractAttachments(msg.payload as MessagePart);
      const hasAttachment = attachments.length > 0;

      messages.push({
        id: msg.id ?? "",
        threadId: msg.threadId ?? "",
        account: email,
        from: extractHeader(headers, "from"),
        to: extractHeader(headers, "to"),
        subject: extractHeader(headers, "subject"),
        date: extractHeader(headers, "date"),
        snippet: msg.snippet ?? "",
        body: decodeBody(msg.payload as Parameters<typeof decodeBody>[0]),
        labelIds: msg.labelIds ?? [],
        isUnread: (msg.labelIds ?? []).includes("UNREAD"),
        hasAttachment,
        attachments: hasAttachment ? attachments : undefined
      });
    }
  }

  return messages;
}

export async function readMessage(email: string, messageId: string): Promise<EmailMessage> {
  const auth = await getAuthenticatedClient(email);
  const gmail = google.gmail({ version: "v1", auth });

  const { data: msg } = await gmail.users.messages.get({
    userId: "me",
    id: messageId,
    format: "full"
  });

  const headers = msg.payload?.headers ?? [];
  const attachments = extractAttachments(msg.payload as MessagePart);
  const hasAttachment = attachments.length > 0;

  return {
    id: msg.id ?? "",
    threadId: msg.threadId ?? "",
    account: email,
    from: extractHeader(headers, "from"),
    to: extractHeader(headers, "to"),
    subject: extractHeader(headers, "subject"),
    date: extractHeader(headers, "date"),
    snippet: msg.snippet ?? "",
    body: decodeBody(msg.payload as Parameters<typeof decodeBody>[0]),
    labelIds: msg.labelIds ?? [],
    isUnread: (msg.labelIds ?? []).includes("UNREAD"),
    hasAttachment,
    attachments: hasAttachment ? attachments : undefined
  };
}

export async function readThread(email: string, threadId: string): Promise<EmailThread> {
  const auth = await getAuthenticatedClient(email);
  const gmail = google.gmail({ version: "v1", auth });

  const { data: thread } = await gmail.users.threads.get({
    userId: "me",
    id: threadId,
    format: "full"
  });

  const msgs: ThreadMessage[] = (thread.messages ?? []).map(msg => {
    const headers = msg.payload?.headers ?? [];
    const attachments = extractAttachments(msg.payload as MessagePart);
    return {
      id: msg.id ?? "",
      from: extractHeader(headers, "from"),
      to: extractHeader(headers, "to"),
      date: extractHeader(headers, "date"),
      snippet: msg.snippet ?? "",
      body: decodeBody(msg.payload as Parameters<typeof decodeBody>[0]),
      attachments: attachments.length > 0 ? attachments : undefined
    };
  });

  const firstHeaders = thread.messages?.[0]?.payload?.headers ?? [];
  const subject = extractHeader(firstHeaders, "subject");

  return {
    id: thread.id ?? "",
    account: email,
    subject,
    messages: msgs
  };
}

export async function listAttachments(email: string, messageId: string): Promise<AttachmentInfo[]> {
  const auth = await getAuthenticatedClient(email);
  const gmail = google.gmail({ version: "v1", auth });
  const { data: msg } = await gmail.users.messages.get({
    userId: "me",
    id: messageId,
    format: "full"
  });
  return extractAttachments(msg.payload as MessagePart);
}

export interface DownloadResult {
  account: string;
  messageId: string;
  attachmentId: string;
  filename: string;
  mimeType: string;
  size: number;
  outputPath: string;
}

function sanitizeFilename(name: string): string {
  return name.replace(/[\/\\:*?"<>|\x00-\x1f]/g, "_").slice(0, 200);
}

export async function downloadAttachment(
  email: string,
  messageId: string,
  opts: { attachmentId?: string; filename?: string; outputPath?: string; outputDir?: string }
): Promise<DownloadResult> {
  const auth = await getAuthenticatedClient(email);
  const gmail = google.gmail({ version: "v1", auth });

  // Resolve attachment metadata: need attachmentId + filename + mimeType + size
  let attachmentId = opts.attachmentId;
  let filename = opts.filename ?? "";
  let mimeType = "application/octet-stream";
  let size = 0;

  if (!attachmentId || !filename) {
    const attachments = await listAttachments(email, messageId);
    if (attachments.length === 0) {
      throw new Error(`Message ${messageId} has no attachments`);
    }
    let match: AttachmentInfo | undefined;
    if (attachmentId) {
      match = attachments.find(a => a.attachmentId === attachmentId);
    } else if (filename) {
      match = attachments.find(a => a.filename === filename)
        ?? attachments.find(a => a.filename.toLowerCase() === filename.toLowerCase());
    } else if (attachments.length === 1) {
      match = attachments[0];
    }
    if (!match) {
      const list = attachments.map(a => `  - "${a.filename}" (id=${a.attachmentId.slice(0, 20)}…, ${a.size} bytes, ${a.mimeType})`).join("\n");
      throw new Error(
        `Ambiguous attachment selection for message ${messageId}. Found ${attachments.length} attachments; pass attachmentId or filename explicitly.\n${list}`
      );
    }
    attachmentId = match.attachmentId;
    filename = match.filename;
    mimeType = match.mimeType;
    size = match.size;
  }

  const { data } = await gmail.users.messages.attachments.get({
    userId: "me",
    messageId,
    id: attachmentId!
  });

  if (!data.data) throw new Error(`Empty attachment payload for ${filename}`);

  // Gmail returns base64url (RFC 4648 URL-safe). Convert to standard base64.
  const b64 = data.data.replace(/-/g, "+").replace(/_/g, "/");
  const buf = Buffer.from(b64, "base64");

  // Resolve output path
  let outPath: string;
  if (opts.outputPath) {
    outPath = opts.outputPath.startsWith("~")
      ? path.join(process.env.HOME ?? "", opts.outputPath.slice(1))
      : opts.outputPath;
  } else {
    const dir = opts.outputDir
      ? (opts.outputDir.startsWith("~") ? path.join(process.env.HOME ?? "", opts.outputDir.slice(1)) : opts.outputDir)
      : path.join(process.env.HOME ?? "", "Desktop/claude/outputs/gmail-attachments");
    outPath = path.join(dir, sanitizeFilename(filename));
  }

  const outDir = path.dirname(outPath);
  if (!fs.existsSync(outDir)) fs.mkdirSync(outDir, { recursive: true });
  fs.writeFileSync(outPath, buf);

  return {
    account: email,
    messageId,
    attachmentId: attachmentId!,
    filename,
    mimeType,
    size: size || buf.length,
    outputPath: outPath
  };
}
