# Google Cloud Setup — OAuth credentials for multi-gmail + multi-gcal

Both MCP servers (`multi-gmail`, `multi-gcal`) use the **same Google Cloud OAuth client** to authenticate. You set it up once, then reuse the Client ID + Secret for both.

**Estimated time:** 15 minutes.

---

## Step 1 — Create a Google Cloud project

1. Go to [console.cloud.google.com](https://console.cloud.google.com).
2. Top bar → project selector → **New Project**.
3. Name: anything — e.g. `my-gmail-mcp` or `<yourname>-claude`.
4. Click **Create**.
5. Once created, make sure the new project is selected in the top bar.

---

## Step 2 — Enable the Gmail + Calendar APIs

1. Left nav → **APIs & Services** → **Library**.
2. Search "Gmail API" → click it → **Enable**.
3. Back to Library → search "Google Calendar API" → click → **Enable**.

---

## Step 3 — Configure the OAuth consent screen

1. Left nav → **APIs & Services** → **OAuth consent screen**.
2. **User Type:** choose **External** (unless you have a Google Workspace org — then Internal). Click **Create**.
3. Fill in the required fields:
   - **App name:** e.g. "My Gmail MCP"
   - **User support email:** your email
   - **Developer contact:** your email
4. Click **Save and Continue**.
5. **Scopes:** click **Add or Remove Scopes** and add:
   - `.../auth/gmail.readonly`
   - `.../auth/calendar.readonly`
   - `.../auth/calendar.events` (for creating/updating events)
6. Save and Continue.
7. **Test users:** click **Add Users** and add every Gmail address you plan to connect (personal, work, school, etc.). **This is required** — if you skip it, auth will fail with "access blocked" until the app is verified by Google (which takes weeks).
8. Save. Back on the Dashboard, the app is in "Testing" mode — that's what we want.

---

## Step 4 — Create OAuth 2.0 credentials

1. Left nav → **APIs & Services** → **Credentials**.
2. **Create Credentials** → **OAuth client ID**.
3. **Application type:** **Desktop app**.
4. **Name:** e.g. "multi-gmail-mcp" (label only, doesn't matter).
5. Click **Create**.
6. A dialog shows your **Client ID** and **Client Secret**. Copy both into a safe place (password manager). You'll paste them into `.env` in the next step.

---

## Step 5 — Save credentials locally

The installer script will ask you for these. If you want to pre-populate:

```bash
mkdir -p ~/multi-gmail-mcp-server ~/multi-gcal-mcp-server
cat > ~/multi-gmail-mcp-server/.env <<'EOF'
GMAIL_CLIENT_ID=<paste-client-id-here>
GMAIL_CLIENT_SECRET=<paste-client-secret-here>
EOF
cp ~/multi-gmail-mcp-server/.env ~/multi-gcal-mcp-server/.env
chmod 600 ~/multi-gmail-mcp-server/.env ~/multi-gcal-mcp-server/.env
```

Both servers read the **same** env vars (`GMAIL_CLIENT_ID` / `GMAIL_CLIENT_SECRET`) — the Calendar server reuses the name because it's the same OAuth client.

---

## Step 6 — Add each account (after install)

Once `install_mcps.sh` has built the servers, connect your accounts:

```bash
# Gmail
cd ~/multi-gmail-mcp-server
source .env && export GMAIL_CLIENT_ID GMAIL_CLIENT_SECRET
npm run setup add personal     # opens browser, sign in with your personal@gmail.com
npm run setup add work         # opens browser, sign in with your work email

# Calendar — uses the same client, add each account again for calendar scope
cd ~/multi-gcal-mcp-server
source .env && export GMAIL_CLIENT_ID GMAIL_CLIENT_SECRET
npm run setup add personal
npm run setup add work
```

Labels (`personal`, `work`, etc.) are just nicknames — the MCP tools use these as the `account` argument.

---

## Troubleshooting

**"Access blocked: This app's request is invalid"**
→ You skipped adding the account as a test user. Go back to Step 3.7 and add it.

**"redirect_uri_mismatch"**
→ You selected "Web application" instead of "Desktop app" in Step 4.3. Recreate the credential as Desktop app.

**"No refresh token returned"**
→ The account was previously authorized for the same client without offline access. Go to [myaccount.google.com/permissions](https://myaccount.google.com/permissions), revoke your app, and re-run `npm run setup add`.

**"invalid_client"**
→ Client ID / Secret pasted wrong. Double-check the values in `.env`.

---

## Security notes

- The Client ID and Secret are not "keep absolutely secret" — they identify your app, not you. The **refresh tokens** stored after each `setup add` are the sensitive part; they're encrypted on disk in `~/.multi-gmail-mcp/tokens.enc` (AES-256-GCM).
- Scopes are read-only for Gmail and read-only + events-write for Calendar. No email-send or file-write permissions are requested.
- You can revoke access anytime at [myaccount.google.com/permissions](https://myaccount.google.com/permissions).
