export const KEYCHAIN_SERVICE = "multi-gmail-mcp";
export const KEYCHAIN_ACCOUNT_LIST_KEY = "account-list";
export const KEYCHAIN_TOKEN_PREFIX = "token:";

export const GMAIL_SCOPES = [
  "https://www.googleapis.com/auth/gmail.readonly",
  "https://www.googleapis.com/auth/userinfo.email"
];

export const OAUTH_REDIRECT_URI = "http://localhost:4242/oauth/callback";
export const OAUTH_PORT = 4242;

export const MAX_RESULTS_DEFAULT = 20;
export const MAX_RESULTS_LIMIT = 500;
export const CHARACTER_LIMIT = 50000;
