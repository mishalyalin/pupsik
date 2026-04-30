import path from "path";
import os from "os";

// WhatsApp stores chats in a Core Data SQLite DB.
export const WA_DB_PATH = path.join(
  os.homedir(),
  "Library/Group Containers/group.net.whatsapp.WhatsApp.shared/ChatStorage.sqlite"
);

// User's contact database — sync target.
export const CONTACTS_DB_PATH = path.join(
  os.homedir(),
  "Desktop/claude/data/contacts.db"
);

// Core Data / NSDate uses seconds since 2001-01-01 UTC.
// Unix epoch is seconds since 1970-01-01 UTC.
export const APPLE_EPOCH_OFFSET = 978307200;

// JID suffixes we care about.
// `@s.whatsapp.net` = 1-on-1 chat (ZSESSIONTYPE = 0)
// `@g.us` = group (ZSESSIONTYPE = 1)
// `@lid` = Linked ID (privacy-preserving alias for a person)
// `@status` = status broadcasts (skip)
export const JID_DM = "@s.whatsapp.net";
export const JID_GROUP = "@g.us";
export const JID_LID = "@lid";
export const JID_STATUS = "@status";
