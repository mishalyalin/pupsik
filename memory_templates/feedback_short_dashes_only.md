---
name: Short dashes only, never em-dashes
description: When drafting text the user will send as themselves, use only short hyphens "-". Never em-dashes "—" or en-dashes "–". Applies to emails, messaging, signatures.
type: feedback
---
Never use em-dashes (—) or en-dashes (–) when writing in the user's voice or drafting text they will send. Only short hyphens "-".

**Why:** Most users do not type em-dashes naturally. When Claude scatters them through drafted text, the result reads as machine-generated, not as the user. Matching the user's typical punctuation is part of voice fidelity.

**How to apply:** When drafting emails, chat messages, or any text the user will send as themselves, use "-" everywhere. Sign-offs follow the same rule: "-handle" not "—handle". Applies across languages (Russian, English, others). If a CLAUDE.md or older style note specifies em-dashes for a sign-off, treat it as stale and prefer the short hyphen.

**Detection:** When reviewing your own draft before showing it to the user, grep for em-dashes (—) and en-dashes (–). If any appear in user-voice content, replace with "-" before presenting.
