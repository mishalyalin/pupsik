---
name: Default workspace and permissions mode
description: All sessions start in ~/Desktop/claude/ with auto permission mode. Settings updated in ~/.claude/settings.json.
type: feedback
originSessionId: 17176b18-3561-4eeb-bd8e-779b13b69319
---
All Claude Code sessions: ~/Desktop/claude/, auto mode, Opus 4.6 (claude-opus-4-6).

**Why:** Working from a single unified workspace. Auto mode = smart middle ground (auto-accepts safe ops, prompts only on risky ones) — safer than bypassPermissions but still low-friction. Opus = most powerful model, always preferred.

**How to apply:** settings.json: `"model": "claude-opus-4-6"`, `"defaultMode": "auto"`. Always cd to ~/Desktop/claude/.

**History:** Was `bypassPermissions` until 2026-04-27 — switched to `auto` because bypass is too permissive for daily work; auto gives same flow with sane guardrails.
