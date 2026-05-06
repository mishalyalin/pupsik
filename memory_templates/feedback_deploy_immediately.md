---
name: Always deploy immediately after changes
description: Commit and deploy ticket-hunter changes to VPS right away, never leave changes local-only
type: feedback
---

Always commit and deploy ticket-hunter changes to the VPS immediately after making them. Never ask "should I deploy?" — just do it.

**Why:** The user tests changes via the live Telegram bot on their phone (e.g. while walking the dog). If changes are only local, they test the old version and waste time. They don't need local verification — deploy straight to production.

**How to apply:** After editing ticket-hunter code, immediately: git add → git commit → git push → ssh to VPS → git pull → systemctl restart tickethunter. No confirmation needed.
