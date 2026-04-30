// ============================================================
// Core data types for multi-Gmail MCP server
// ============================================================

export interface AccountConfig {
  email: string;
  label: string;       // e.g. "personal", "work", "kids"
  addedAt: string;     // ISO timestamp
}

export interface TokenData {
  access_token: string;
  refresh_token: string;
  expiry_date: number;
  token_type: string;
  scope: string;
}

export interface StoredAccount {
  config: AccountConfig;
  tokens: TokenData;
}

export interface AttachmentInfo {
  attachmentId: string;   // Gmail API attachment ID (pass to gmail_download_attachment)
  filename: string;
  mimeType: string;
  size: number;           // bytes
  partId?: string;        // message part ID (for debugging)
}

export interface EmailMessage {
  id: string;
  threadId: string;
  account: string;       // which Gmail account this came from
  from: string;
  to: string;
  subject: string;
  date: string;
  snippet: string;
  body?: string;
  labelIds: string[];
  isUnread: boolean;
  hasAttachment: boolean;
  attachments?: AttachmentInfo[];   // metadata only — content via gmail_download_attachment
}

export interface SearchResult {
  account: string;
  messages: EmailMessage[];
  total: number;
}

export interface AggregatedSearchResult {
  accounts_searched: string[];
  accounts_failed: FailedAccount[];
  total_messages: number;
  messages: EmailMessage[];
}

export interface FailedAccount {
  email: string;
  error: string;
}

export interface ThreadMessage {
  id: string;
  from: string;
  to: string;
  date: string;
  body: string;
  snippet: string;
  attachments?: AttachmentInfo[];
}

export interface EmailThread {
  id: string;
  account: string;
  subject: string;
  messages: ThreadMessage[];
}

export interface GmailProfile {
  email: string;
  messagesTotal: number;
  threadsTotal: number;
  historyId: string;
}
