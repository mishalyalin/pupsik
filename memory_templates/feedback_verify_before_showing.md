---
name: Always verify before showing results
description: User demands all links and outputs are verified working before being presented
type: feedback
---

Always verify links, URLs, and outputs actually work before showing them to the user.

**Why:** User got broken Spektrix links, search page links instead of show pages, garbage show names, and past/streaming shows mixed in with real results. Multiple rounds of "this doesn't work" feedback.

**How to apply:**
- Before presenting any URL to the user, verify it resolves to the right page
- Test scraper output locally before deploying
- Don't generate URLs from templates — verify the actual target exists
- Check that show names are real shows, not button text or navigation
- Filter out past events, streaming, non-show items proactively
- When building a scraper, research each website's structure individually — don't assume patterns
