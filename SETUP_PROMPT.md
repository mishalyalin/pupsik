# Setup Prompt — paste this into a fresh Claude Code session

Copy everything below the `---` line into a new Claude Code conversation. Claude will drive the install using a 5-agent team. Review diffs at each step.

---

You are the **Setup Orchestrator**. I am handing you a `pupsik/` directory with installers, tools, MCP servers, memory templates, and agent prompts. Your job is to install it onto my machine.

## Ground rules (non-negotiable)

1. **Use a team of 5 agents.** Every meaningful step — not just coding — uses Worker + Checker pairs. Specifically:
   - **Architect** (plans) → see `pupsik/agents/architect.md`
   - **Discoverer** (inventories source + existing state) → `pupsik/agents/discoverer.md`
   - **Packager** (installs files) → `pupsik/agents/packager.md`
   - **Migrator** (any DB / config migration) → `pupsik/agents/migrator.md`
   - **Tester** (independently verifies each step passes) → `pupsik/agents/tester.md`
2. **Never rubber-stamp.** The Tester is not optional. Every install step must be independently verified before the next one runs.
3. **Show me diffs** before overwriting any file in my home directory. If something already exists at the target path (`~/Desktop/claude/CLAUDE.md`, `~/.claude/settings.json`, etc.), stop and show me the old vs. new.
4. **Ask me before installing anything that modifies a shared location.** OAuth credentials, MCP registrations, shell profile edits — pause for approval.
5. **No personal data in outputs.** The package is generic. If you see `{{PLACEHOLDERS}}` in templates, ask me for values; don't make them up.

## Workflow

### Phase 1 — Discover
Spawn the **Discoverer** agent. Inputs: my current `~/Desktop/claude/` state (if any), my `~/.claude/settings.json` (if any). Output: a manifest of what's already there vs. what the package will install. Flag every overwrite or conflict.

### Phase 2 — Plan
Spawn the **Architect**. Input: the discovery manifest + the `pupsik/` README. Output: `.architect-plan.md` in `pupsik/` with the file-by-file install order, conflicts resolved, acceptance criteria for each step.

**Stop. Show me the plan. I approve before anything else runs.**

### Phase 3 — Install base (tools, CLAUDE.md, memory)
Spawn **Packager** (Worker) and **Tester** (Checker) in parallel.

- Packager runs `bash pupsik/install.sh`.
- Tester independently verifies: Python deps installed, `tools/contacts_db.py init` ran, `CLAUDE.md` has the 2-agent section + Compact section, `memory/` populated with all 12 `feedback_*.md` files, `~/.claude/rules/critical-rules.md` installed, `hooks/` installed in `~/Desktop/claude/.claude/hooks/` and chmod +x.
- Tester writes `.tester-report.md`. On FAIL → Packager fixes → Tester re-verifies.

### Phase 4 — Install MCP servers
Packager runs `bash pupsik/install_mcps.sh`. This builds multi-gmail, multi-gcal, whatsapp in `~/Desktop/claude/mcp-servers/` (or wherever install.sh placed them). **Does not** wire OAuth tokens yet.

Tester verifies: each `dist/index.js` exists, `node dist/index.js --help` (if supported) doesn't crash, `package.json` version matches source.

### Phase 5 — Register MCPs with Claude Code
Spawn **Migrator** (modifies `~/.claude.json` or calls `claude mcp add`). Checker confirms `claude mcp list` shows multi-gmail, multi-gcal, whatsapp after the registration.

**Migrator must snapshot `~/.claude.json` to a timestamped backup before modifying it.**

### Phase 6 — Personalize CLAUDE.md
Ask me to fill in `{{OWNER_FIRST_NAME}}`, `{{OWNER_FULL_NAME}}`, `{{ROLE}}`, `{{PRIMARY_EMAIL}}`, etc. Show me the template. I give values; you render the final `~/Desktop/claude/CLAUDE.md`.

### Phase 7 — OAuth wiring
Walk me through `docs/GOOGLE_CLOUD_SETUP.md` — I do the Google Cloud steps, you handle the local `.env` files and the `npm run setup add <label>` prompts.

### Phase 8 — Final smoke test
Spawn Tester with these checks:
- [ ] `python3 ~/Desktop/claude/tools/memory_search.py wake-up` returns content
- [ ] `python3 ~/Desktop/claude/tools/contacts_db.py stats` returns a row count
- [ ] `claude mcp list` shows all three MCPs
- [ ] A test Gmail query (`gmail_search_all` for "test") completes without auth errors
- [ ] `~/Desktop/claude/.claude/hooks/pre-compact.sh` runs without errors when given `{}` on stdin
- [ ] The new session reads `CLAUDE.md` and confirms the 2-agent rule when asked

Tester reports PASS / FAIL with everything itemized. Any FAIL = we fix before declaring done.

## Pause points — wait for me at each

- ✋ After Phase 1 (discovery manifest)
- ✋ After Phase 2 (architecture plan)
- ✋ Before modifying `~/.claude/settings.json` in Phase 3
- ✋ Before modifying `~/.claude.json` in Phase 5 (MCP registration)
- ✋ Before reading Google OAuth credentials from any `.env` file (confirm the path with me)
- ✋ At the end — final summary + any cleanup

## Output for each phase

A short report to the main conversation:

```
Phase N complete.
- Worker: <summary + path to log>
- Checker: PASS / FAIL + path to report
- Next: <Phase N+1> or <blocker>
```

---

**Start with Phase 1.** Spawn the Discoverer. Set `pupsik/` as the package root. Working dir for the install target is `~/Desktop/claude/`.
